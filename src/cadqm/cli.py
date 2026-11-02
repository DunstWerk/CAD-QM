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
    m = sub.add_parser("smoke", help="Alle PDFs eines Ordners durchlaufen (Laufzeit, Textzahlen, Plankopf) + Debug-PNGs")
    m.add_argument("folder"); m.add_argument("outdir"); m.add_argument("--config"); m.add_argument("--scale", type=float, default=0.25)
    a = ap.parse_args(argv)
    if a.cmd == "debug":
        page = pymupdf.open(a.pdf)[0]
        print(debug_png(page, load_config(a.config), a.out, a.scale))
    if a.cmd == "smoke":
        import time, pathlib
        cfg = load_config(a.config); out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
        for f in sorted(pathlib.Path(a.folder).glob("*.pdf")):
            t0 = time.time(); doc = pymupdf.open(f); page = doc[0]
            st = debug_png(page, cfg, str(out / (f.stem + ".png")), a.scale)
            print(f"{f.name:12s} {page.rect.width:.0f}x{page.rect.height:.0f} rot{page.rotation:3d} {time.time()-t0:5.1f}s {st}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
