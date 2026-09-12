#!/usr/bin/env python3
"""Limpieza y normalización del modelo de neurona de DUNNE.

Reescribe un archivo GLB exportado desde Blender para que sea apto para
Unity/Vuforia y para WebAR, sin dependencias externas más allá de NumPy.

El script no modifica el archivo de entrada. Todas las operaciones son
verificables contra el reporte JSON que se emite al final.

Operaciones
-----------
1. Renombrado semántico de nodos y mallas a partir de ``mapping.json``.
2. Horneado de la jerarquía: las matrices de mundo se aplican a las
   posiciones y las normales, y el resultado queda en una jerarquía plana
   con transformaciones identidad.
3. Colapso de materiales: las texturas de color plano se resuelven a
   ``baseColorFactor`` y los materiales idénticos se deduplican.
4. Eliminación de datos muertos: imágenes, texturas, samplers,
   ``TEXCOORD_0`` sin textura que muestrear y ``COLOR_0`` constante.
5. Purga de ``KHR_materials_ior`` y ``KHR_materials_specular``.
6. Normalización opcional de escala y centrado en el origen.

Notas
-----
Las normales se transforman con la inversa transpuesta de la submatriz
lineal, no con la matriz de mundo: bajo escala anisotrópica (que este
modelo tiene en varios nodos) aplicar la matriz directa deja las normales
fuera de la superficie y la iluminación se rompe.

Ejemplo
-------
$ python clean_glb.py --input Neurona.glb --mapping mapping.json \
      --output Neurona_v2.glb --report reporte_limpieza.json
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import numpy as np

# ---------------------------------------------------------------------------
# Constantes glTF
# ---------------------------------------------------------------------------

COMPONENT_DTYPE: dict[int, str] = {
    5120: "i1", 5121: "u1", 5122: "i2",
    5123: "u2", 5125: "u4", 5126: "f4",
}
TYPE_COUNT: dict[str, int] = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

@dataclass
class Glb:
    """Contenedor de un GLB ya separado en sus dos chunks.

    Attributes
    ----------
    gltf : dict
        Documento JSON del glTF.
    bin : bytes
        Chunk binario, sin el encabezado de 8 bytes.
    """

    gltf: dict[str, Any]
    bin: bytes

    @classmethod
    def read(cls, path: Path) -> "Glb":
        """Lee un archivo GLB de disco.

        Parameters
        ----------
        path : Path
            Ruta al archivo ``.glb``.

        Returns
        -------
        Glb
            Instancia con el JSON parseado y el chunk binario.

        Raises
        ------
        ValueError
            Si el encabezado no corresponde a un GLB versión 2.
        """
        raw = path.read_bytes()
        magic, version, length = struct.unpack("<III", raw[:12])
        if magic != GLB_MAGIC or version != 2:
            raise ValueError(f"{path} no es un GLB versión 2")

        gltf: dict[str, Any] | None = None
        binary = b""
        offset = 12
        while offset < length:
            clen, ctype = struct.unpack("<II", raw[offset:offset + 8])
            payload = raw[offset + 8: offset + 8 + clen]
            if ctype == CHUNK_JSON:
                gltf = json.loads(payload.decode("utf-8"))
            elif ctype == CHUNK_BIN:
                binary = payload
            offset += 8 + clen

        if gltf is None:
            raise ValueError(f"{path} no contiene chunk JSON")
        return cls(gltf=gltf, bin=binary)

    def view_bytes(self, index: int) -> bytes:
        """Devuelve los bytes crudos de un bufferView."""
        view = self.gltf["bufferViews"][index]
        start = view.get("byteOffset", 0)
        return self.bin[start: start + view["byteLength"]]

    def accessor(self, index: int) -> np.ndarray:
        """Lee un accessor como arreglo NumPy con forma (count, components).

        Parameters
        ----------
        index : int
            Índice del accessor en el documento glTF.

        Returns
        -------
        numpy.ndarray
            Arreglo de forma ``(count, n)``; para SCALAR, ``(count, 1)``.
        """
        acc = self.gltf["accessors"][index]
        dtype = np.dtype("<" + COMPONENT_DTYPE[acc["componentType"]])
        ncomp = TYPE_COUNT[acc["type"]]
        raw = self.view_bytes(acc["bufferView"])
        flat = np.frombuffer(
            raw, dtype=dtype, count=acc["count"] * ncomp,
            offset=acc.get("byteOffset", 0),
        )
        return flat.reshape(acc["count"], ncomp)


# ---------------------------------------------------------------------------
# PNG mínimo: solo lo necesario para leer texturas de color plano
# ---------------------------------------------------------------------------

def decode_png_first_pixel(raw: bytes) -> tuple[float, float, float, float]:
    """Extrae el primer píxel de un PNG como RGBA normalizado.

    Implementa únicamente el subconjunto necesario para estas texturas:
    8 bits por canal, sin entrelazado. Se aplica el desfiltrado de la
    primera línea, que es suficiente porque el color es constante.

    Parameters
    ----------
    raw : bytes
        Contenido completo del archivo PNG.

    Returns
    -------
    tuple of float
        Componentes ``(r, g, b, a)`` en el rango [0, 1].

    Raises
    ------
    ValueError
        Si el PNG usa un tipo de color o profundidad no soportados.
    """
    pos, width, depth, ctype = 8, None, None, None
    idat = bytearray()
    while pos < len(raw):
        clen = struct.unpack(">I", raw[pos:pos + 4])[0]
        ctag = raw[pos + 4:pos + 8]
        data = raw[pos + 8:pos + 8 + clen]
        if ctag == b"IHDR":
            width, _, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", data[:13])
            if depth != 8 or interlace != 0:
                raise ValueError(f"PNG no soportado: depth={depth} interlace={interlace}")
        elif ctag == b"IDAT":
            idat += data
        elif ctag == b"IEND":
            break
        pos += 12 + clen

    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(ctype)
    if channels is None:
        raise ValueError(f"PNG con tipo de color no soportado: {ctype}")

    decoded = zlib.decompress(bytes(idat))
    stride = width * channels
    filt = decoded[0]
    line = np.frombuffer(decoded[1:1 + stride], dtype=np.uint8).astype(np.int32).copy()

    # En la primera línea la fila previa es cero, así que Up y Average
    # degeneran; solo Sub y Paeth necesitan el vecino izquierdo.
    if filt in (1, 4):
        for i in range(channels, stride):
            line[i] = (line[i] + line[i - channels]) & 0xFF
    elif filt == 3:
        for i in range(channels, stride):
            line[i] = (line[i] + (line[i - channels] >> 1)) & 0xFF

    px = (line[:channels] / 255.0).tolist()
    if channels == 1:
        return (px[0], px[0], px[0], 1.0)
    if channels == 2:
        return (px[0], px[0], px[0], px[1])
    if channels == 3:
        return (px[0], px[1], px[2], 1.0)
    return (px[0], px[1], px[2], px[3])


def srgb_to_linear(c: float) -> float:
    """Convierte un canal de sRGB a espacio lineal.

    ``baseColorTexture`` se interpreta como sRGB, mientras que
    ``baseColorFactor`` es lineal; sin esta conversión el modelo se ve
    notablemente más claro tras el colapso de materiales.
    """
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


# ---------------------------------------------------------------------------
# Transformaciones
# ---------------------------------------------------------------------------

def node_matrix(node: dict[str, Any]) -> np.ndarray:
    """Construye la matriz local 4x4 de un nodo glTF (columna-mayor a fila)."""
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T

    m = np.eye(4)
    if "scale" in node:
        m = np.diag([*node["scale"], 1.0]) @ m
    if "rotation" in node:
        x, y, z, w = node["rotation"]
        rot = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ])
        t = np.eye(4)
        t[:3, :3] = rot
        m = t @ m
    if "translation" in node:
        t = np.eye(4)
        t[:3, 3] = node["translation"]
        m = t @ m
    return m


def walk_nodes(glb: Glb) -> Iterator[tuple[int, np.ndarray, int]]:
    """Recorre la escena y produce nodos con malla y su matriz de mundo.

    Yields
    ------
    tuple
        ``(node_index, world_matrix, depth)`` para cada nodo con malla.
    """
    scene = glb.gltf["scenes"][glb.gltf.get("scene", 0)]
    stack: list[tuple[int, np.ndarray, int]] = [
        (i, np.eye(4), 0) for i in reversed(scene["nodes"])
    ]
    while stack:
        idx, parent, depth = stack.pop()
        node = glb.gltf["nodes"][idx]
        world = parent @ node_matrix(node)
        if "mesh" in node:
            yield idx, world, depth
        for child in reversed(node.get("children", [])):
            stack.append((child, world, depth + 1))


# ---------------------------------------------------------------------------
# Materiales
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Surface:
    """Descripción de superficie resuelta a factores escalares."""

    color: tuple[float, float, float, float]
    roughness: float
    metallic: float

    def key(self) -> tuple:
        """Clave de deduplicación con tolerancia de 1e-4."""
        return (*(round(c, 4) for c in self.color),
                round(self.roughness, 4), round(self.metallic, 4))


def resolve_surface(glb: Glb, material_index: int | None) -> Surface:
    """Resuelve un material glTF a factores planos.

    Lee el color desde ``baseColorFactor`` o, si el material usa una
    textura de color plano, desde el primer píxel de esa textura. La
    rugosidad se toma del canal verde de ``metallicRoughnessTexture``,
    que es el canal que la especificación reserva para ese parámetro.

    Parameters
    ----------
    glb : Glb
        Documento de origen.
    material_index : int or None
        Índice del material, o ``None`` para la superficie por omisión.

    Returns
    -------
    Surface
        Color en espacio lineal más rugosidad y metalicidad.
    """
    if material_index is None:
        return Surface((0.8, 0.8, 0.8, 1.0), 0.5, 0.0)

    mat = glb.gltf["materials"][material_index]
    pbr = mat.get("pbrMetallicRoughness", {})

    def texture_pixel(tex_info: dict[str, Any]) -> tuple[float, float, float, float]:
        tex = glb.gltf["textures"][tex_info["index"]]
        image = glb.gltf["images"][tex["source"]]
        return decode_png_first_pixel(glb.view_bytes(image["bufferView"]))

    if "baseColorTexture" in pbr:
        r, g, b, a = texture_pixel(pbr["baseColorTexture"])
        color = (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)
    else:
        color = tuple(pbr.get("baseColorFactor", [1.0, 1.0, 1.0, 1.0]))

    if "metallicRoughnessTexture" in pbr:
        # Este mapa es lineal por especificación: no se convierte de sRGB.
        _, green, _, _ = texture_pixel(pbr["metallicRoughnessTexture"])
        roughness = float(green)
    else:
        roughness = float(pbr.get("roughnessFactor", 1.0))

    metallic = float(pbr.get("metallicFactor", 1.0))
    return Surface(color, roughness, metallic)


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

@dataclass
class BufferBuilder:
    """Acumula bufferViews alineados a 4 bytes."""

    blob: bytearray = field(default_factory=bytearray)
    views: list[dict[str, Any]] = field(default_factory=list)

    def add(self, array: np.ndarray, target: int | None = None) -> int:
        """Agrega un arreglo y devuelve el índice de su bufferView."""
        while len(self.blob) % 4:
            self.blob.append(0)
        offset = len(self.blob)
        data = np.ascontiguousarray(array).tobytes()
        self.blob += data
        view: dict[str, Any] = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        self.views.append(view)
        return len(self.views) - 1


def write_glb(gltf: dict[str, Any], blob: bytes, path: Path) -> int:
    """Serializa un documento glTF y su binario como GLB.

    Returns
    -------
    int
        Tamaño total del archivo escrito, en bytes.
    """
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
    bin_bytes = bytes(blob) + b"\x00" * ((4 - len(blob) % 4) % 4)

    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    out = bytearray()
    out += struct.pack("<III", GLB_MAGIC, 2, total)
    out += struct.pack("<II", len(json_bytes), CHUNK_JSON) + json_bytes
    out += struct.pack("<II", len(bin_bytes), CHUNK_BIN) + bin_bytes
    path.write_bytes(out)
    return total


# ---------------------------------------------------------------------------
# Proceso principal
# ---------------------------------------------------------------------------

def clean(
    input_path: Path,
    mapping_path: Path,
    output_path: Path,
    *,
    normalize: bool = True,
    double_sided: bool = False,
) -> dict[str, Any]:
    """Ejecuta la limpieza completa y devuelve el reporte.

    Parameters
    ----------
    input_path : Path
        GLB de origen; no se modifica.
    mapping_path : Path
        ``mapping.json`` producido por el etiquetador anatómico.
    output_path : Path
        Destino del GLB limpio.
    normalize : bool, optional
        Si es ``True``, centra el modelo en el origen y escala para que su
        dimensión mayor valga 1.0 unidad.
    double_sided : bool, optional
        Valor de ``doubleSided`` en los materiales de salida.

    Returns
    -------
    dict
        Reporte comparativo antes/después.
    """
    glb = Glb.read(input_path)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

    slug_by_node = {p["node"]: p["slug"] for p in mapping["parts"]}
    class_by_node = {p["node"]: p["class"] for p in mapping["parts"]}

    before = {
        "file_bytes": input_path.stat().st_size,
        "nodes": len(glb.gltf.get("nodes", [])),
        "meshes": len(glb.gltf.get("meshes", [])),
        "materials": len(glb.gltf.get("materials", [])),
        "textures": len(glb.gltf.get("textures", [])),
        "images": len(glb.gltf.get("images", [])),
        "extensions": sorted(glb.gltf.get("extensionsUsed", [])),
        "max_depth": 0,
        "triangles": 0,
    }

    # --- 1. Extraer, transformar y renombrar -------------------------------
    parts: list[dict[str, Any]] = []
    unmapped: list[str] = []

    for node_index, world, depth in walk_nodes(glb):
        node = glb.gltf["nodes"][node_index]
        mesh = glb.gltf["meshes"][node["mesh"]]
        before["max_depth"] = max(before["max_depth"], depth)

        for prim in mesh["primitives"]:
            attrs = prim["attributes"]
            pos = glb.accessor(attrs["POSITION"]).astype(np.float64)
            idx = glb.accessor(prim["indices"]).astype(np.uint32).ravel()
            before["triangles"] += len(idx) // 3

            # Posiciones: coordenadas homogéneas por la matriz de mundo.
            homo = np.column_stack([pos, np.ones(len(pos))])
            pos_w = (world @ homo.T).T[:, :3]

            # Normales: inversa transpuesta de la parte lineal. Con escala
            # anisotrópica la matriz directa las saca de la superficie.
            if "NORMAL" in attrs:
                nrm = glb.accessor(attrs["NORMAL"]).astype(np.float64)
                normal_matrix = np.linalg.inv(world[:3, :3]).T
                nrm_w = nrm @ normal_matrix.T
                norms = np.linalg.norm(nrm_w, axis=1, keepdims=True)
                nrm_w = nrm_w / np.where(norms == 0, 1.0, norms)
            else:
                nrm_w = None

            name = node.get("name", f"node_{node_index}")
            if name not in slug_by_node:
                unmapped.append(name)

            parts.append({
                "slug": slug_by_node.get(name, name),
                "class": class_by_node.get(name, "unassigned"),
                "source_node": name,
                "positions": pos_w,
                "normals": nrm_w,
                "indices": idx.astype(np.uint16),
                "surface": resolve_surface(glb, prim.get("material")),
            })

    if unmapped:
        print(f"aviso: {len(unmapped)} malla(s) sin entrada en el mapping: "
              f"{', '.join(unmapped[:5])}", file=sys.stderr)

    # --- 2. Normalizar escala y centro -------------------------------------
    all_pos = np.vstack([p["positions"] for p in parts])
    extent = all_pos.max(axis=0) - all_pos.min(axis=0)
    center = (all_pos.max(axis=0) + all_pos.min(axis=0)) / 2.0
    scale = 1.0 / float(extent.max()) if normalize else 1.0

    if normalize:
        for p in parts:
            p["positions"] = (p["positions"] - center) * scale

    # --- 3. Deduplicar superficies -----------------------------------------
    materials: list[dict[str, Any]] = []
    material_index: dict[tuple, int] = {}
    class_of_material: dict[int, set[str]] = {}

    for p in parts:
        key = p["surface"].key()
        if key not in material_index:
            material_index[key] = len(materials)
            materials.append({
                "name": "",  # se nombra abajo, cuando se conocen las clases
                "doubleSided": double_sided,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [round(c, 6) for c in p["surface"].color],
                    "roughnessFactor": round(p["surface"].roughness, 6),
                    "metallicFactor": round(p["surface"].metallic, 6),
                },
            })
        mi = material_index[key]
        p["material"] = mi
        class_of_material.setdefault(mi, set()).add(p["class"])

    for mi, classes in class_of_material.items():
        materials[mi]["name"] = (
            f"mat_{sorted(classes)[0]}" if len(classes) == 1
            else "mat_shared_" + "_".join(sorted(classes))[:40]
        )

    # --- 4. Reconstruir el documento ---------------------------------------
    builder = BufferBuilder()
    accessors: list[dict[str, Any]] = []
    meshes: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []

    for p in parts:
        pos = p["positions"].astype(np.float32)
        view_pos = builder.add(pos, target=34962)
        accessors.append({
            "bufferView": view_pos, "componentType": 5126, "count": len(pos),
            "type": "VEC3",
            "min": [float(v) for v in pos.min(axis=0)],
            "max": [float(v) for v in pos.max(axis=0)],
        })
        attributes = {"POSITION": len(accessors) - 1}

        if p["normals"] is not None:
            nrm = p["normals"].astype(np.float32)
            view_nrm = builder.add(nrm, target=34962)
            accessors.append({
                "bufferView": view_nrm, "componentType": 5126,
                "count": len(nrm), "type": "VEC3",
            })
            attributes["NORMAL"] = len(accessors) - 1

        view_idx = builder.add(p["indices"], target=34963)
        accessors.append({
            "bufferView": view_idx, "componentType": 5123,
            "count": len(p["indices"]), "type": "SCALAR",
        })

        meshes.append({
            "name": p["slug"],
            "primitives": [{
                "attributes": attributes,
                "indices": len(accessors) - 1,
                "material": p["material"],
            }],
        })
        nodes.append({
            "name": p["slug"],
            "mesh": len(meshes) - 1,
            "extras": {"class": p["class"], "sourceNode": p["source_node"]},
        })

    root = {
        "name": "neuron",
        "children": list(range(len(nodes))),
        "extras": {
            "dunne": {
                "source": input_path.name,
                "mappingRevision": mapping.get("revision", 1),
                "originalExtent": [round(float(v), 6) for v in extent],
                "normalizeScale": round(scale, 8),
                "note": ("Jerarquía plana con transformaciones horneadas. "
                         "Dimensión mayor = 1.0 unidad; escalar en la app al "
                         "tamaño físico deseado."),
            }
        },
    }
    nodes.append(root)
    root_index = len(nodes) - 1

    gltf_out: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "DUNNE clean_glb.py"},
        "scene": 0,
        "scenes": [{"nodes": [root_index]}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": builder.views,
        "buffers": [{"byteLength": len(builder.blob)}],
    }

    total_bytes = write_glb(gltf_out, builder.blob, output_path)

    after_pos = np.vstack([p["positions"] for p in parts])
    report = {
        "input": str(input_path),
        "output": str(output_path),
        "mapping_revision": mapping.get("revision", 1),
        "before": before,
        "after": {
            "file_bytes": total_bytes,
            "nodes": len(nodes),
            "meshes": len(meshes),
            "materials": len(materials),
            "textures": 0,
            "images": 0,
            "extensions": [],
            "max_depth": 1,
            "triangles": sum(len(p["indices"]) // 3 for p in parts),
        },
        "geometry": {
            "original_extent": [round(float(v), 6) for v in extent],
            "normalize_scale": round(scale, 8),
            "final_extent": [round(float(v), 6) for v in (after_pos.max(0) - after_pos.min(0))],
            "final_center": [round(float(v), 6) for v in (after_pos.max(0) + after_pos.min(0)) / 2],
        },
        "materials": [
            {"index": i, "name": m["name"],
             "baseColorFactor": m["pbrMetallicRoughness"]["baseColorFactor"],
             "roughnessFactor": m["pbrMetallicRoughness"]["roughnessFactor"],
             "parts": sorted(p["slug"] for p in parts if p["material"] == i)}
            for i, m in enumerate(materials)
        ],
        "triangles_by_class": {
            cls: sum(len(p["indices"]) // 3 for p in parts if p["class"] == cls)
            for cls in sorted({p["class"] for p in parts})
        },
        "unmapped_meshes": unmapped,
    }
    return report


def main() -> int:
    """Punto de entrada de línea de comandos."""
    ap = argparse.ArgumentParser(description="Limpia el GLB de la neurona de DUNNE.")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--mapping", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, default=None)
    ap.add_argument("--no-normalize", action="store_true",
                    help="Conserva escala y posición originales.")
    ap.add_argument("--double-sided", action="store_true",
                    help="Mantiene doubleSided=true (duplica el sombreado).")
    args = ap.parse_args()

    report = clean(
        args.input, args.mapping, args.output,
        normalize=not args.no_normalize,
        double_sided=args.double_sided,
    )

    if args.report:
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                               encoding="utf-8")

    b, a = report["before"], report["after"]
    print(f"{'':<14}{'antes':>12}{'después':>12}")
    for k in ("file_bytes", "nodes", "meshes", "materials", "textures",
              "images", "max_depth", "triangles"):
        print(f"{k:<14}{b[k]:>12,}{a[k]:>12,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
