from __future__ import annotations
import argparse
import pymupdf
from .config import load_config
from .debug import debug_png


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cadqm", description="Lokale QM-Pruefung fuer PDF-Plaene")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("debug", help="Debug-PNG: was gilt als 'unser' / Architekt / Text")
    d.add_argument("pdf"); d.add_argument("out"); d.add_argument("--config"); d.add_argument("--scale", type=float, default=0.3)
    a = ap.parse_args(argv)
    if a.cmd == "debug":
        page = pymupdf.open(a.pdf)[0]
        print(debug_png(page, load_config(a.config), a.out, a.scale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
