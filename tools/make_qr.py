#!/usr/bin/env python3
"""Genera el código QR de enlace de un sitio de DUNNE.

El código sirve para compartir la página en un taller, no como marcador de
realidad aumentada: un QR es un mal Image Target porque su patrón es
repetitivo y auto-similar, lo contrario de lo que requiere el reconocimiento
por características.

Se usa corrección de errores alta (nivel H, ~30% de redundancia) porque el
código se va a imprimir y proyectar, y en esas condiciones pierde contraste y
nitidez.

Ejemplo
-------
$ python make_qr.py --url https://usuario.github.io/repo/ --output assets/qr_dunne.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import segno


def build(url: str, output: Path, scale: int = 12, quiet_zone: int = 4) -> dict:
    """Escribe el QR y devuelve sus datos de verificación.

    Parameters
    ----------
    url : str
        Destino que codifica el código.
    output : Path
        Ruta de salida. La extensión define el formato (``.png`` o ``.svg``).
    scale : int, optional
        Píxeles por módulo. 12 da un archivo cómodo para imprimir a 10 cm.
    quiet_zone : int, optional
        Módulos de margen blanco. Menos de 4 reduce la tasa de lectura.

    Returns
    -------
    dict
        Versión, nivel de corrección, número de módulos y ruta escrita.
    """
    qr = segno.make(url, error="h")
    qr.save(str(output), scale=scale, border=quiet_zone,
            dark="#000000", light="#ffffff")
    return {
        "url": url,
        "version": qr.version,
        "error_level": qr.error,
        "modules": qr.symbol_size(scale=1, border=0)[0],
        "output": str(output),
    }


def main() -> int:
    """Punto de entrada de línea de comandos."""
    ap = argparse.ArgumentParser(description="Genera el código QR de enlace del sitio.")
    ap.add_argument("--url", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--scale", type=int, default=12)
    args = ap.parse_args()

    info = build(args.url, args.output, args.scale)
    print(f"{info['output']}: versión {info['version']}, corrección "
          f"{info['error_level']}, {info['modules']}×{info['modules']} módulos")
    print(f"codifica: {info['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
