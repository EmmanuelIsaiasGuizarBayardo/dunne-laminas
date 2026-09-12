"""Prueba de punta a punta del servidor de la sala.

Emplea la biblioteca `websockets` como cliente para que la implementación
del protocolo se valide contra una independiente y no contra sí misma.
"""
import asyncio, json, threading, time, sys
from pathlib import Path
import websockets

# El directorio del archivo, no el de trabajo: la suite debe poder ejecutarse
# desde la raíz del repositorio (`python sala/test_sala.py`) además de desde
# esta carpeta.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from server import serve

PORT = 8399
srv = serve("127.0.0.1", PORT, ROOT, {"topology": "cadena", "dilation": 1})
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(0.4)
URL = f"ws://127.0.0.1:{PORT}/ws"

fails = []
def check(label, ok, detail=""):
    print(f"  {'OK  ' if ok else 'FALLA'} {label}{'  ' + str(detail) if detail else ''}")
    if not ok: fails.append(label)

async def recv_until(ws, kind, pred, timeout=4.0):
    """Espera un mensaje del tipo dado que además cumpla una condición.

    Una neurona recibe un mensaje `targets` por cada cambio del censo, por lo
    que hay que filtrar hasta el que refleja el estado buscado.
    """
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        msg = await recv(ws, kind, end - time.monotonic())
        last = msg
        if pred(msg):
            return msg
    raise TimeoutError(f"{kind} con la condición pedida; último: {last}")


async def recv(ws, kind, timeout=4.0):
    """Espera el primer mensaje de un tipo dado."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        raw = await asyncio.wait_for(ws.recv(), timeout=end - time.monotonic())
        msg = json.loads(raw)
        if msg.get("type") == kind:
            return msg
    raise TimeoutError(kind)

async def main():
    # --- tres neuronas y un mural ---
    async with websockets.connect(URL) as a, websockets.connect(URL) as b, \
               websockets.connect(URL) as c, \
               websockets.connect(URL + "?role=mural") as mural:

        wa = await recv(a, "welcome"); wb = await recv(b, "welcome"); wc = await recv(c, "welcome")
        wm = await recv(mural, "welcome")

        check("asientos consecutivos", [wa["seat"], wb["seat"], wc["seat"]] == [1,2,3],
              [wa["seat"], wb["seat"], wc["seat"]])
        check("el mural no ocupa asiento", wm["seat"] is None)
        # El welcome de la primera se emite cuando aún está sola; los
        # destinos definitivos llegan en el mensaje "targets".
        upd = await recv_until(a, "targets", lambda m: m["targets"] == [2])
        check("cadena: 1 aprende que apunta a 2", upd["targets"] == [2], upd["targets"])
        check("cadena: el último no apunta a nadie", wc["targets"] == [], wc["targets"])

        roster = await recv(mural, "roster")
        check("censo con 3 neuronas", len(roster["neurons"]) == 3, len(roster["neurons"]))
        check("aristas de la cadena", roster["edges"] == [[1,2],[2,3]], roster["edges"])

        # --- un spike de 1 llega a 2 y no a 3 ---
        await a.send(json.dumps({"type": "spike"}))
        got = await recv(b, "input")
        check("el spike llega a la postsináptica", got["from_seat"] == 1, got)
        check("trae peso sináptico", got["weight"] == 0.6, got["weight"])
        check("el mural registra el evento", (await recv(mural, "event"))["seat"] == 1)
        try:
            await asyncio.wait_for(recv(c, "input", 0.8), timeout=1.0)
            check("no llega a quien no es postsináptica", False)
        except (TimeoutError, asyncio.TimeoutError):
            check("no llega a quien no es postsináptica", True)

        # --- desmielinización: el retardo se dispara ---
        d_mielin = got["delay_ms"]
        await a.send(json.dumps({"type": "myelin", "on": False}))
        await recv(mural, "roster")
        await a.send(json.dumps({"type": "spike"}))
        got2 = await recv(b, "input", 8.0)
        check("sin mielina el retardo crece ×10",
              abs(got2["delay_ms"] / d_mielin - 10) < 0.05,
              f"{d_mielin:.1f} ms → {got2['delay_ms']:.1f} ms")

        # --- cambio de topología desde el mural ---
        await mural.send(json.dumps({"type": "config", "topology": "convergencia"}))
        wa2 = await recv(a, "welcome")
        wc2 = await recv(c, "welcome")
        check("convergencia: 1 apunta a la última", wa2["targets"] == [3], wa2["targets"])
        check("convergencia: la última no tiene salida", wc2["targets"] == [], wc2["targets"])

        # --- suma espacial: 1 y 2 llegan ambas a 3 ---
        await a.send(json.dumps({"type": "spike"}))
        await b.send(json.dumps({"type": "spike"}))
        i1 = await recv(c, "input", 8.0); i2 = await recv(c, "input", 8.0)
        check("dos entradas convergen en la misma neurona",
              {i1["from_seat"], i2["from_seat"]} == {1, 2}, (i1["from_seat"], i2["from_seat"]))

    # --- mural: censo, voltaje en vivo y consola del operador ---
    async with websockets.connect(URL) as a, websockets.connect(URL) as b, \
               websockets.connect(URL + "?role=mural") as mural:
        await recv(a, "welcome"); await recv(b, "welcome"); await recv(mural, "welcome")
        r = await recv(mural, "roster")
        check("el censo trae polaridad, mielina y voltaje",
              all(k in r["neurons"][0] for k in ("polarity", "myelinated", "vm")))

        await a.send(json.dumps({"type": "vm", "v": -61.5}))
        v = await recv(mural, "vm")
        check("el voltaje llega al mural", v["seat"] == 1 and v["v"] == -61.5, v)
        try:
            await asyncio.wait_for(recv(b, "vm", 0.7), timeout=0.9)
            check("el voltaje NO se difunde a las neuronas", False)
        except (TimeoutError, asyncio.TimeoutError):
            check("el voltaje NO se difunde a las neuronas", True)

        await mural.send(json.dumps({"type": "config", "topology": "anillo", "dilation": 30}))
        r2 = await recv(mural, "roster")
        check("la consola cambia topología y dilatación",
              r2["config"]["topology"] == "anillo" and r2["config"]["dilation"] == 30)
        check("el anillo cierra el circuito", sorted(r2["edges"]) == [[1, 2], [2, 1]], r2["edges"])

        await mural.send(json.dumps({"type": "polarity", "seat": 2, "kind": "inhibitory"}))
        check("la consola invierte la polaridad de un asiento",
              (await recv(b, "polarity"))["kind"] == "inhibitory")

        await mural.send(json.dumps({"type": "reset"}))
        check("el reset llega a las neuronas", (await recv(a, "reset"))["type"] == "reset")

        await a.send(json.dumps({"type": "spike"}))
        e = await recv(mural, "event")
        check("el evento trae lo que el grafo necesita",
              all(k in e for k in ("seat", "targets", "delay_ms", "polarity")))

    # --- al salir todos, el censo queda vacío ---
    await asyncio.sleep(0.3)
    check("los clientes se dieron de baja", len(srv.hub.clients) == 0, len(srv.hub.clients))

    # --- el mismo puerto sirve archivos estáticos ---
    # Se solicita un archivo existente en lugar de crear uno temporal: en
    # Windows no se puede eliminar un archivo que el hilo del servidor
    # mantiene abierto.
    import urllib.request
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/sala.css") as r:
        body = r.read().decode("utf-8")
        check("HTTP y WebSocket en el mismo puerto",
              r.status == 200 and "--flame" in body, f"{r.status}, {len(body)} bytes")
        check("respuestas sin caché", r.headers.get("Cache-Control") == "no-store")

    # --- las rutas cortas del QR resuelven al cliente ---
    for short, marker in (("/n", "Tu neurona"), ("/", "Tu neurona")):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{short}") as r:
            check(f"ruta corta {short}", r.status == 200 and marker in r.read().decode("utf-8"))

asyncio.run(main())
print()
print("PRUEBA FALLIDA:" if fails else "TODAS LAS VERIFICACIONES PASAN")
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
