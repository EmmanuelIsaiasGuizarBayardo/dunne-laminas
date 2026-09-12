#!/usr/bin/env python3
"""Hornea la paleta didáctica de DUNNE en los materiales del modelo de neurona.

El GLB que produce ``clean_glb.py`` conserva los colores del modelo original,
que son cuatro tonos casi indistinguibles entre sí (lavanda para dendritas,
soma, axón y terminales). Para uso pedagógico eso es contraproducente: si el
axón y las dendritas son del mismo color, la distinción que uno quiere enseñar
no se ve.

Este script asigna un material por clase anatómica, leyendo la clase de
``node.extras.class`` que ``clean_glb.py`` dejó en cada nodo, y descarta los
materiales originales que queden sin usar.

La paleta codifica la dirección del flujo de información: azules del lado de
entrada (dendritas), naranjas en el cuerpo celular, verdes del lado de salida
(axón, terminales, botones), y amarillo con rosa para el aparato de
mielinización.

Ejemplo
-------
$ python bake_palette.py --input Neurona_v2.glb --output Neurona_v3.glb
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NamedTuple

from pygltflib import GLTF2, Material, PbrMetallicRoughness


class Surface(NamedTuple):
    """Definición de superficie para una clase anatómica.

    Attributes
    ----------
    hex_color : str
        Color en sRGB, como se elegiría en un editor gráfico.
    roughness : float
        Rugosidad PBR. Valores bajos dan un brillo ceroso; altos, mate.
    rationale : str
        Por qué ese color, para que la decisión quede documentada en el repo.
    """

    hex_color: str
    roughness: float
    rationale: str


PALETTE: dict[str, Surface] = {
    "soma": Surface("#ff7a00", 0.52, "Naranja de marca DUNNE: el cuerpo celular es el ancla visual."),
    "nucleus": Surface("#c81e2d", 0.58, "Rojo profundo: más frío y oscuro que el naranja del soma, así se lee como núcleo interior y no compite con el rosa de Schwann."),
    "dendrite": Surface("#1e88ff", 0.50, "Azul: lado de entrada de información."),
    "dendrite_primary": Surface("#63b0ff", 0.50, "Azul claro: mismo lado, jerarquía distinta."),
    "axon": Surface("#00d3a7", 0.46, "Verde agua: lado de salida; contrasta con el azul de entrada."),
    "myelin_sheath": Surface("#ffe066", 0.34, "Amarillo con brillo ceroso: evoca la mielina sin pretender realismo."),
    "schwann_nucleus": Surface("#ff6f9c", 0.55, "Rosa: célula distinta de la neurona, por eso sale de la escala neuronal."),
    "axon_terminal": Surface("#5ce27a", 0.50, "Verde: continuidad con el axón."),
    "synaptic_bouton": Surface("#c8ff5c", 0.44, "Verde limón: el punto final del recorrido, el más brillante de la rama de salida."),
}


def srgb_to_linear(channel: float) -> float:
    """Convierte un canal sRGB a espacio lineal.

    ``baseColorFactor`` es lineal por especificación glTF. Omitir esta
    conversión produce un modelo visiblemente más claro y lavado.
    """
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def hex_to_linear_rgba(hex_color: str, alpha: float = 1.0) -> list[float]:
    """Convierte un color hexadecimal sRGB a RGBA lineal para glTF."""
    h = hex_color.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [round(srgb_to_linear(c), 6) for c in srgb] + [alpha]


def bake(input_path: Path, output_path: Path, *, per_instance: bool = False) -> dict:
    """Reasigna materiales por clase anatómica y devuelve un reporte.

    Parameters
    ----------
    input_path : Path
        GLB de entrada, con ``extras.class`` en cada nodo con malla.
    output_path : Path
        Destino. El archivo de entrada no se modifica.
    per_instance : bool, optional
        Si es ``True``, crea un material por malla (``dunne_myelin_sheath_01``)
        en lugar de uno por clase. Necesario para animar estructuras repetidas
        de forma independiente.

    Returns
    -------
    dict
        Resumen con materiales antes y después, y el reparto por clase.

    Raises
    ------
    ValueError
        Si algún nodo con malla carece de clase, lo que indicaría que el GLB
        no proviene de ``clean_glb.py``.
    """
    gltf = GLTF2().load(str(input_path))
    materials_before = len(gltf.materials)

    # Un material por clase presente en el modelo, en orden estable.
    classes: list[str] = []
    for node in gltf.nodes:
        if node.mesh is None:
            continue
        cls = (node.extras or {}).get("class")
        if cls is None:
            raise ValueError(f"El nodo '{node.name}' no tiene extras.class")
        if cls not in classes:
            classes.append(cls)

    unknown = [c for c in classes if c not in PALETTE]
    if unknown:
        raise ValueError(f"Clases sin color definido en PALETTE: {unknown}")

    new_materials: list[Material] = []
    index_of: dict[str, int] = {}

    # Con per_instance hay un material por malla en lugar de uno por clase.
    # Cuesta más materiales, pero es lo que permite encender las cuatro
    # vainas de mielina una por una en vez de todas a la vez.
    if per_instance:
        keys = [n.name for n in gltf.nodes if n.mesh is not None]
        class_of = {n.name: n.extras["class"] for n in gltf.nodes if n.mesh is not None}
    else:
        keys = classes
        class_of = {c: c for c in classes}

    for key in keys:
        surface = PALETTE[class_of[key]]
        index_of[key] = len(new_materials)
        new_materials.append(Material(
            name=f"dunne_{key}",
            doubleSided=False,
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorFactor=hex_to_linear_rgba(surface.hex_color),
                roughnessFactor=surface.roughness,
                metallicFactor=0.0,
            ),
        ))

    counts: dict[str, int] = {}
    for node in gltf.nodes:
        if node.mesh is None:
            continue
        cls = node.extras["class"]
        key = node.name if per_instance else cls
        for primitive in gltf.meshes[node.mesh].primitives:
            primitive.material = index_of[key]
        counts[cls] = counts.get(cls, 0) + 1

    gltf.materials = new_materials
    gltf.save(str(output_path))

    return {
        "input": input_path.name,
        "output": output_path.name,
        "materials_before": materials_before,
        "materials_after": len(new_materials),
        "per_instance": per_instance,
        "palette": {
            cls: {
                "hex": PALETTE[cls].hex_color,
                "baseColorFactor": hex_to_linear_rgba(PALETTE[cls].hex_color),
                "roughness": PALETTE[cls].roughness,
                "meshes": counts[cls],
                "rationale": PALETTE[cls].rationale,
            }
            for cls in classes
        },
    }


def main() -> int:
    """Punto de entrada de línea de comandos."""
    ap = argparse.ArgumentParser(description="Hornea la paleta didáctica en el GLB.")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, default=None)
    ap.add_argument("--per-instance", action="store_true",
                    help="Un material por malla en lugar de uno por clase.")
    args = ap.parse_args()

    report = bake(args.input, args.output, per_instance=args.per_instance)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                               encoding="utf-8")

    print(f"materiales: {report['materials_before']} -> {report['materials_after']}")
    for cls, info in report["palette"].items():
        print(f"  {cls:<18}{info['hex']}  rough={info['roughness']:.2f}  "
              f"{info['meshes']:>2} malla(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
