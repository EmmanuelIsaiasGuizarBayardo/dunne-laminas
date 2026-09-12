#!/usr/bin/env python3
"""Servidor de la sala interactiva de DUNNE.

Cada dispositivo conectado es una neurona. El servidor mantiene la topología
del circuito, recibe los potenciales de acción que dispara cada uno y los
entrega a sus neuronas postsinápticas con un retardo de conducción calculado.

Decisiones de diseño y por qué
------------------------------
**Un solo puerto para HTTP y WebSocket.** Un navegador en una página servida
por HTTPS no puede abrir un WebSocket ``ws://``: lo bloquea como contenido
mixto activo. Sirviendo la página y el socket desde el mismo origen en HTTP
el problema no existe, y en la sala no hace falta HTTPS porque no se usa la
cámara. Esto permite que un celular del público entre escaneando un QR sin
instalar ni configurar nada.

**Sin dependencias.** El protocolo WebSocket está implementado sobre la
biblioteca estándar, de modo que el despliegue no depende de que un
``pip install`` funcione en el equipo de la sede.

**Mensajes JSON planos.** Compatibles con ``WebSocketsClient`` de ESP32 y
puenteables a MQTT sin modificar el protocolo.

Protocolo
---------
Cliente al servidor:
    ``{"type": "hello", "role": "neuron"|"mural", "seat": int|null}``
    ``{"type": "spike", "at": <ms del cliente>}``
    ``{"type": "vm", "v": <mV>}``            (opcional, para el mural)
    ``{"type": "config", ...}``              (solo desde el mural)
    ``{"type": "myelin", "on": bool}``

Servidor al cliente:
    ``{"type": "welcome", "id":…, "seat":…, "config":…, "targets":…}``
    ``{"type": "input", "from_seat":…, "weight":…}``
    ``{"type": "roster", "neurons": […], "config":…}``
    ``{"type": "event", "kind": "spike", "seat":…, "t":…}``   (al mural)

Ejemplo
-------
$ python server.py --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Parámetros del circuito
# ---------------------------------------------------------------------------

WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OP_TEXT = 0x1
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

DEFAULT_CONFIG: dict[str, Any] = {
    # Dilatación temporal. A escala real el potencial de acción recorre la
    # sala en menos de un milisegundo. Con factor 20, la constante de membrana
    # de 20 ms equivale a 400 ms de reloj de pared, rango en el que la suma
    # temporal es reproducible con la mano. Los clientes muestran el factor en
    # pantalla para no representar una velocidad falsa.
    "dilation": 20,

    # Conducción. Longitud típica de un axón motor y velocidades del orden de
    # las fibras mielinizadas gruesas frente a las delgadas. La razón de 10
    # entre ambas está comprimida respecto a la real, que puede superar 20,
    # para acotar la duración de la demostración de desmielinización.
    "axon_length_m": 0.8,
    "v_myelinated_ms": 60.0,
    "v_unmyelinated_ms": 6.0,

    # Peso sináptico como fracción de la distancia entre reposo y umbral.
    # Con 0.6 se requieren dos entradas coincidentes para alcanzar el umbral.
    "weight": 0.6,

    "topology": "cadena",
}

TOPOLOGIES = ("cadena", "anillo", "convergencia", "divergencia")


# ---------------------------------------------------------------------------
# WebSocket sobre biblioteca estándar
# ---------------------------------------------------------------------------

def accept_key(client_key: str) -> str:
    """Calcula el valor de ``Sec-WebSocket-Accept`` del handshake.

    Parameters
    ----------
    client_key : str
        Valor de ``Sec-WebSocket-Key`` enviado por el cliente.

    Returns
    -------
    str
        Hash SHA-1 del key concatenado con el GUID del protocolo, en base64.
    """
    digest = hashlib.sha1((client_key + WS_MAGIC).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def encode_frame(payload: bytes, opcode: int = OP_TEXT) -> bytes:
    """Arma un frame de servidor, que por especificación va sin máscara."""
    head = bytes([0x80 | opcode])
    length = len(payload)
    if length < 126:
        head += bytes([length])
    elif length < 65536:
        head += bytes([126]) + struct.pack(">H", length)
    else:
        head += bytes([127]) + struct.pack(">Q", length)
    return head + payload


def read_exactly(reader: Any, count: int) -> bytes:
    """Lee exactamente ``count`` bytes de un flujo o levanta ``ConnectionError``.

    Opera sobre el ``rfile`` del manejador y no sobre el socket crudo: el
    handshake se leyó con ese búfer, y los frames que el cliente haya enviado
    pegados a la petición ya están ahí. Leer del socket los descartaría.
    """
    chunks: list[bytes] = []
    remaining = count
    while remaining:
        chunk = reader.read(remaining)
        if not chunk:
            raise ConnectionError("el par cerró la conexión")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(sock: Any) -> tuple[int, bytes]:
    """Lee un frame y devuelve ``(opcode, payload)``.

    Notes
    -----
    No se maneja fragmentación. Los mensajes son objetos JSON de pocos
    cientos de bytes, por debajo del umbral de fragmentación de cualquier
    navegador. Un frame de continuación se trataría como mensaje propio y se
    descartaría al fallar el parseo de JSON.
    """
    first, second = read_exactly(sock, 2)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F

    if length == 126:
        length = struct.unpack(">H", read_exactly(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", read_exactly(sock, 8))[0]

    mask = read_exactly(sock, 4) if masked else b""
    payload = read_exactly(sock, length) if length else b""

    if masked:
        payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))

    return opcode, payload


# ---------------------------------------------------------------------------
# Clientes y concentrador
# ---------------------------------------------------------------------------

@dataclass
class Client:
    """Una conexión WebSocket viva.

    Attributes
    ----------
    sock : socket.socket
        Socket ya promovido a WebSocket.
    cid : int
        Identificador interno, único por conexión.
    role : str
        ``"neuron"`` para un dispositivo que es una neurona, ``"mural"`` para
        una pantalla de monitoreo.
    seat : int or None
        Posición en el circuito. Solo las neuronas tienen asiento.
    """

    sock: socket.socket
    cid: int
    role: str = "neuron"
    seat: int | None = None
    myelinated: bool = True
    # Polaridad de la neurona, no de la sinapsis. Por el principio de Dale,
    # una neurona libera el mismo neurotransmisor en todos sus terminales, de
    # modo que su efecto es excitatorio o inhibitorio, nunca mixto.
    polarity: str = "excitatory"
    last_vm: float = -70.0
    alive: bool = True
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def send(self, message: dict[str, Any]) -> bool:
        """Envía un mensaje JSON. Devuelve ``False`` si la conexión murió.

        El candado por cliente es necesario porque los envíos llegan desde
        hilos distintos: el hilo de la conexión que originó el spike y los
        temporizadores de entrega.
        """
        if not self.alive:
            return False
        data = encode_frame(json.dumps(message, ensure_ascii=False).encode("utf-8"))
        try:
            with self._lock:
                self.sock.sendall(data)
            return True
        except OSError:
            self.alive = False
            return False


class Hub:
    """Estado compartido de la sala: clientes, topología y configuración."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.clients: dict[int, Client] = {}
        self.config: dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self._next_cid = 1
        self._lock = threading.RLock()
        self.log: Callable[[str], None] = print

    # -- ciclo de vida ----------------------------------------------------

    def join(self, sock: socket.socket, role: str, seat: int | None) -> Client:
        """Registra una conexión y le asigna asiento si es una neurona."""
        with self._lock:
            cid = self._next_cid
            self._next_cid += 1
            client = Client(sock=sock, cid=cid, role=role)

            if role == "neuron":
                taken = {c.seat for c in self.clients.values() if c.seat is not None}
                if seat is not None and seat not in taken:
                    client.seat = seat
                else:
                    # Se reutiliza el primer asiento libre para no dejar
                    # huecos en la cadena tras una desconexión.
                    candidate = 1
                    while candidate in taken:
                        candidate += 1
                    client.seat = candidate

            self.clients[cid] = client

        client.send({
            "type": "welcome",
            "id": cid,
            "seat": client.seat,
            "role": role,
            "polarity": client.polarity,
            "config": self.config,
            "targets": self.targets_of(client.seat) if client.seat else [],
        })
        self.broadcast_roster()
        self.log(f"entra {role} cid={cid} asiento={client.seat}")
        return client

    def leave(self, client: Client) -> None:
        """Retira una conexión y avisa al resto."""
        with self._lock:
            client.alive = False
            self.clients.pop(client.cid, None)
        self.broadcast_roster()
        self.log(f"sale {client.role} cid={client.cid} asiento={client.seat}")

    # -- topología --------------------------------------------------------

    def seats(self) -> list[int]:
        """Asientos ocupados, en orden."""
        with self._lock:
            return sorted(c.seat for c in self.clients.values() if c.seat is not None)

    def targets_of(self, seat: int | None) -> list[int]:
        """Asientos postsinápticos de un asiento dado.

        Returns
        -------
        list of int
            Vacía si el asiento no tiene salida en la topología actual.
        """
        if seat is None:
            return []
        order = self.seats()
        if seat not in order or len(order) < 2:
            return []

        index = order.index(seat)
        kind = self.config["topology"]

        if kind == "cadena":
            return [order[index + 1]] if index + 1 < len(order) else []
        if kind == "anillo":
            return [order[(index + 1) % len(order)]]
        if kind == "convergencia":
            # Todas apuntan a la última: demuestra suma espacial.
            return [] if index == len(order) - 1 else [order[-1]]
        if kind == "divergencia":
            return order[1:] if index == 0 else []
        return []

    def by_seat(self, seat: int) -> Client | None:
        """Devuelve el cliente que ocupa un asiento."""
        with self._lock:
            for client in self.clients.values():
                if client.seat == seat:
                    return client
        return None

    # -- conducción -------------------------------------------------------

    def delay_ms(self, client: Client) -> float:
        """Retardo de conducción en milisegundos de reloj de pared.

        Longitud del axón entre velocidad de conducción, multiplicado por el
        factor de dilatación. Sin mielina la velocidad cae un orden de
        magnitud y el retardo crece en la misma proporción.
        """
        speed = (self.config["v_myelinated_ms"] if client.myelinated
                 else self.config["v_unmyelinated_ms"])
        real_ms = self.config["axon_length_m"] / speed * 1000.0
        return real_ms * self.config["dilation"]

    def relay_spike(self, sender: Client) -> None:
        """Entrega un potencial de acción a las neuronas postsinápticas."""
        targets = self.targets_of(sender.seat)
        delay = self.delay_ms(sender)
        sign = -1.0 if sender.polarity == "inhibitory" else 1.0
        weight = self.config["weight"] * sign

        for seat in targets:
            receiver = self.by_seat(seat)
            if receiver is None:
                continue
            payload = {
                "type": "input",
                "from_seat": sender.seat,
                "weight": round(weight, 4),
                "polarity": sender.polarity,
                "myelinated": sender.myelinated,
                "delay_ms": round(delay, 1),
            }
            # Un temporizador por entrega. A esta escala (decenas de
            # dispositivos, unidades de spikes por segundo) resulta más simple
            # que una cola con prioridad.
            threading.Timer(delay / 1000.0, receiver.send, args=(payload,)).start()

        event = {
            "type": "event",
            "kind": "spike",
            "seat": sender.seat,
            "targets": targets,
            "delay_ms": round(delay, 1),
            "polarity": sender.polarity,
            "myelinated": sender.myelinated,
            "t": time.time(),
        }
        self.broadcast(event, roles=("mural",))

    # -- difusión ---------------------------------------------------------

    def broadcast(self, message: dict[str, Any],
                  roles: tuple[str, ...] | None = None) -> None:
        """Envía un mensaje a todos los clientes, o solo a ciertos roles."""
        with self._lock:
            targets = [c for c in self.clients.values()
                       if roles is None or c.role in roles]
        for client in targets:
            client.send(message)

    def broadcast_roster(self) -> None:
        """Publica el censo de neuronas y la configuración vigente."""
        with self._lock:
            neurons = sorted(
                ({"seat": c.seat, "id": c.cid, "myelinated": c.myelinated,
                  "polarity": c.polarity, "vm": round(c.last_vm, 2)}
                 for c in self.clients.values() if c.role == "neuron"),
                key=lambda n: n["seat"] or 0,
            )
        message = {
            "type": "roster",
            "neurons": neurons,
            "config": self.config,
            "edges": [[seat, target]
                      for seat in self.seats()
                      for target in self.targets_of(seat)],
        }
        self.broadcast(message)

        # Los destinos de cada neurona cambian con el censo. El welcome pudo
        # haberse enviado cuando era la única conectada, con lista vacía, por
        # lo que hay que reenviarlos en cada alta o baja.
        with self._lock:
            neurons = [c for c in self.clients.values() if c.role == "neuron"]
        for client in neurons:
            client.send({"type": "targets", "seat": client.seat,
                         "targets": self.targets_of(client.seat)})

    # -- mensajes entrantes ----------------------------------------------

    def handle(self, client: Client, message: dict[str, Any]) -> None:
        """Despacha un mensaje ya deserializado."""
        kind = message.get("type")

        if kind == "spike" and client.role == "neuron":
            self.relay_spike(client)

        elif kind == "vm":
            try:
                client.last_vm = float(message.get("v", -70.0))
            except (TypeError, ValueError):
                pass
            else:
                # Solo a los murales. El censo completo se difunde únicamente
                # ante cambios estructurales; el voltaje se actualiza tres
                # veces por segundo y difundirlo a todos sería redundante.
                if client.seat is not None:
                    self.broadcast({"type": "vm", "seat": client.seat,
                                    "v": client.last_vm}, roles=("mural",))

        elif kind == "myelin":
            client.myelinated = bool(message.get("on", True))
            self.broadcast_roster()

        elif kind == "polarity":
            wanted = message.get("kind")
            if wanted in ("excitatory", "inhibitory"):
                # Puede venir del propio dispositivo o del mural, que indica
                # el asiento al que se refiere.
                target = client
                if "seat" in message and client.role == "mural":
                    target = self.by_seat(int(message["seat"])) or client
                target.polarity = wanted
                target.send({"type": "polarity", "kind": wanted})
                self.broadcast_roster()

        elif kind == "config":
            changed = False
            for key in ("dilation", "weight", "axon_length_m",
                        "v_myelinated_ms", "v_unmyelinated_ms"):
                if key in message:
                    try:
                        self.config[key] = float(message[key])
                        changed = True
                    except (TypeError, ValueError):
                        pass
            if message.get("topology") in TOPOLOGIES:
                self.config["topology"] = message["topology"]
                changed = True
            if changed:
                self.broadcast_roster()
                for c in list(self.clients.values()):
                    if c.role == "neuron":
                        c.send({"type": "welcome", "id": c.cid, "seat": c.seat,
                                "role": c.role, "polarity": c.polarity,
                                "config": self.config,
                                "targets": self.targets_of(c.seat)})

        elif kind == "reset":
            self.broadcast({"type": "reset"}, roles=("neuron",))


# ---------------------------------------------------------------------------
# Manejador HTTP con promoción a WebSocket
# ---------------------------------------------------------------------------

class RoomHandler(SimpleHTTPRequestHandler):
    """Sirve los archivos de la sala y promueve ``/ws`` a WebSocket."""

    hub: Hub  # inyectado con functools.partial

    protocol_version = "HTTP/1.1"

    # Rutas cortas: reducen la densidad del QR que se imprime para la sala.
    # Mapear "/" también evita el listado de directorio de la clase base.
    ALIASES = {
        "/": "/neurona.html",
        "/n": "/neurona.html",
        "/m": "/mural.html",
    }

    def log_message(self, fmt: str, *args: Any) -> None:
        """Silencia el registro de cada archivo servido."""
        if "/ws" in (self.path or ""):
            super().log_message(fmt, *args)

    def do_GET(self) -> None:  # noqa: N802  (nombre impuesto por la clase base)
        """Atiende un GET, o toma la conexión si pide upgrade a WebSocket."""
        upgrade = (self.headers.get("Upgrade") or "").lower()
        if self.path.split("?")[0] == "/ws" and upgrade == "websocket":
            self.handle_websocket()
            return

        path, _, query = self.path.partition("?")
        if path in self.ALIASES:
            self.path = self.ALIASES[path] + (f"?{query}" if query else "")

        # Sin caché: en la sala se itera y no se quiere depurar versiones
        # viejas guardadas por el navegador.
        super().do_GET()

    def end_headers(self) -> None:
        """Agrega cabeceras anti-caché a toda respuesta estática."""
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def handle_websocket(self) -> None:
        """Completa el handshake y atiende el flujo de frames."""
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400, "falta Sec-WebSocket-Key")
            return

        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept_key(key))
        # Obligatorio: send_response y send_header solo acumulan en un búfer;
        # end_headers es lo que lo escribe. Sin esta llamada el cliente recibe
        # una respuesta vacía y el handshake falla.
        self.end_headers()

        sock = self.connection
        sock.settimeout(None)
        reader = self.rfile

        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        params = dict(part.split("=", 1) for part in query.split("&") if "=" in part)
        role = "mural" if params.get("role") == "mural" else "neuron"
        seat = int(params["seat"]) if params.get("seat", "").isdigit() else None

        client = self.hub.join(sock, role, seat)

        try:
            while client.alive:
                opcode, payload = read_frame(reader)

                if opcode == OP_CLOSE:
                    break
                if opcode == OP_PING:
                    with client._lock:  # noqa: SLF001  (mismo módulo)
                        sock.sendall(encode_frame(payload, OP_PONG))
                    continue
                if opcode == OP_PONG:
                    continue
                if opcode != OP_TEXT:
                    continue

                try:
                    message = json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(message, dict):
                    self.hub.handle(client, message)

        except (ConnectionError, OSError, struct.error):
            pass
        finally:
            self.hub.leave(client)
            self.close_connection = True


# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------

def local_ips() -> list[str]:
    """Direcciones IPv4 locales plausibles para compartir en la sala."""
    found: list[str] = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))          # no envía nada, solo enruta
        found.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127.") and address not in found:
                found.append(address)
    except OSError:
        pass
    return found


def serve(host: str, port: int, directory: Path,
          config: dict[str, Any] | None = None) -> ThreadingHTTPServer:
    """Levanta el servidor y devuelve la instancia, ya escuchando."""
    hub = Hub(config)

    # El manejador recibe el hub como atributo de clase porque
    # ThreadingHTTPServer instancia la clase por cada conexión y no acepta
    # pasarle argumentos propios.
    class Bound(RoomHandler):
        pass

    Bound.hub = hub

    server = ThreadingHTTPServer((host, port), partial(Bound, directory=str(directory)))
    server.daemon_threads = True
    server.hub = hub                             # para pruebas e inspección
    return server


def main() -> int:
    """Punto de entrada de línea de comandos."""
    ap = argparse.ArgumentParser(description="Servidor de la sala DUNNE.")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--dir", type=Path, default=Path(__file__).parent)
    ap.add_argument("--topology", choices=TOPOLOGIES, default="cadena")
    ap.add_argument("--dilation", type=float, default=DEFAULT_CONFIG["dilation"])
    args = ap.parse_args()

    server = serve(args.host, args.port, args.dir,
                   {"topology": args.topology, "dilation": args.dilation})

    print(f"Sala DUNNE en el puerto {args.port}, sirviendo {args.dir}")
    print(f"topología: {args.topology} · dilatación temporal: ×{args.dilation:g}")
    for ip in local_ips():
        print(f"  neuronas → http://{ip}:{args.port}/n")
        print(f"  mural    → http://{ip}:{args.port}/m")
    print("Ctrl+C para detener.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\ndeteniendo…")
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
