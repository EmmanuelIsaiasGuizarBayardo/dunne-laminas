#!/usr/bin/env python3
"""Convierte el GLB limpio de la neurona a USDZ para AR Quick Look en iOS.

Existe porque ``<model-viewer>`` delega el modo AR al sistema operativo:
Android usa Scene Viewer y consume glTF directamente, pero iOS usa AR Quick
Look, que solo acepta USDZ. Sin este archivo el botón de AR simplemente no
aparece en iPhone ni iPad.

El conversor asume la salida de ``clean_glb.py``: jerarquía plana,
transformaciones ya horneadas, un material por superficie y sin texturas.
Sobre un GLB con jerarquía anidada produciría geometría mal ubicada.

Ejemplo
-------
$ python gltf_to_usdz.py --input Neurona_v2.glb --output Neurona_v2.usdz
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdUtils, Vt

from clean_glb import Glb


def linear_to_display(c: float) -> float:
    """Deja el color en espacio lineal, que es lo que espera UsdPreviewSurface.

    Se mantiene como función explícita para documentar la decisión: tanto
    ``baseColorFactor`` de glTF como ``diffuseColor`` de UsdPreviewSurface
    son lineales, así que no debe aplicarse ninguna conversión gamma. Hacerlo
    aclararía el modelo de forma visible en iOS y no en Android.
    """
    return c


def build_stage(glb: Glb, stage: Usd.Stage, meters_per_unit: float) -> None:
    """Puebla un stage USD con las mallas y materiales del GLB.

    Parameters
    ----------
    glb : Glb
        Documento de origen, ya limpio y con jerarquía plana.
    stage : pxr.Usd.Stage
        Stage destino, vacío.
    meters_per_unit : float
        Escala física. Con el modelo normalizado a 1.0 unidad, este valor
        equivale al largo en metros que tendrá la neurona en AR.
    """
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, meters_per_unit)

    root = UsdGeom.Xform.Define(stage, "/Neurona")
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.Scope.Define(stage, "/Neurona/Materials")

    materials: list[UsdShade.Material] = []
    for i, mat in enumerate(glb.gltf.get("materials", [])):
        pbr = mat.get("pbrMetallicRoughness", {})
        rgba = pbr.get("baseColorFactor", [1, 1, 1, 1])
        path = f"/Neurona/Materials/mat_{i}"

        usd_mat = UsdShade.Material.Define(stage, path)
        shader = UsdShade.Shader.Define(stage, f"{path}/Surface")
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(*[linear_to_display(c) for c in rgba[:3]])
        )
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(
            float(pbr.get("roughnessFactor", 0.5))
        )
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(
            float(pbr.get("metallicFactor", 0.0))
        )
        if len(rgba) > 3 and rgba[3] < 1.0:
            shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(float(rgba[3]))

        usd_mat.CreateSurfaceOutput().ConnectToSource(
            shader.ConnectableAPI(), "surface"
        )
        materials.append(usd_mat)

    for node in glb.gltf["nodes"]:
        if "mesh" not in node:
            continue
        prim_def = glb.gltf["meshes"][node["mesh"]]["primitives"][0]
        attrs = prim_def["attributes"]

        points = glb.accessor(attrs["POSITION"]).astype(np.float32)
        indices = glb.accessor(prim_def["indices"]).astype(np.int32).ravel()

        mesh = UsdGeom.Mesh.Define(stage, f"/Neurona/{node['name']}")
        mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points))
        mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(indices))
        mesh.CreateFaceVertexCountsAttr(
            Vt.IntArray.FromNumpy(np.full(len(indices) // 3, 3, dtype=np.int32))
        )
        # Sin esta línea Quick Look aplica subdivisión Catmull-Clark y el
        # modelo aparece redondeado y con muchísimo más costo de render.
        mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
        # Gf.Vec3f rechaza numpy.float32: hay que pasar float nativo de Python.
        mesh.CreateExtentAttr(Vt.Vec3fArray([
            Gf.Vec3f(*(float(v) for v in points.min(0))),
            Gf.Vec3f(*(float(v) for v in points.max(0))),
        ]))

        if "NORMAL" in attrs:
            normals = glb.accessor(attrs["NORMAL"]).astype(np.float32)
            mesh.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(normals))
            mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)

        mat_index = prim_def.get("material")
        if mat_index is not None and mat_index < len(materials):
            UsdShade.MaterialBindingAPI(mesh).Bind(materials[mat_index])


def convert(input_path: Path, output_path: Path, meters_per_unit: float = 1.0) -> int:
    """Convierte un GLB a USDZ y devuelve el tamaño del archivo en bytes."""
    glb = Glb.read(input_path)

    with tempfile.TemporaryDirectory() as tmp:
        usdc = Path(tmp) / "neurona.usdc"
        stage = Usd.Stage.CreateNew(str(usdc))
        build_stage(glb, stage, meters_per_unit)
        stage.Save()

        if output_path.exists():
            output_path.unlink()
        ok = UsdUtils.CreateNewUsdzPackage(
            Sdf.AssetPath(str(usdc)), str(output_path)
        )
        if not ok:
            raise RuntimeError("CreateNewUsdzPackage falló")

    return output_path.stat().st_size


def main() -> int:
    """Punto de entrada de línea de comandos."""
    ap = argparse.ArgumentParser(description="Convierte el GLB de la neurona a USDZ.")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--meters-per-unit", type=float, default=1.0,
                    help="Largo en metros de la neurona en AR (default: 1.0).")
    args = ap.parse_args()

    size = convert(args.input, args.output, args.meters_per_unit)
    print(f"{args.output.name}: {size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
