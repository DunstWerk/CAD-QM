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
    c = sub.add_parser("check", help="Plan pruefen und Befunde ausgeben")
    c.add_argument("pdf"); c.add_argument("--config"); c.add_argument("--top", type=int, default=30)
    g = sub.add_parser("eval-gt", help="Befunde gegen von Hand markierte Stellen (alt-/neu-PDF) auswerten")
    g.add_argument("old_dir"); g.add_argument("new_dir"); g.add_argument("--config"); g.add_argument("--radius", type=float, default=12.0)
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
    if a.cmd == "check":
        from .runner import check_pdf
        fs = check_pdf(a.pdf, load_config(a.config))
        print(f"{len(fs)} Befunde ({sum(f.severity == 'error' for f in fs)} error)")
        for f in fs[: a.top]:
            print(f"  {f.severity:5s} {f.kind:9s} {f.value:5.1f}%  {[round(v) for v in f.bbox]}  {f.text[:50]!r}")
    if a.cmd == "eval-gt":
        import pathlib, time
        from .runner import check_pdf, ground_truth
        cfg = load_config(a.config); hit = tot = 0
        for new in sorted(pathlib.Path(a.new_dir).glob("*.pdf")):
            old = pathlib.Path(a.old_dir) / new.name
            gt = ground_truth(str(old), str(new)); t0 = time.time(); fs = check_pdf(str(new), cfg)
            print(f"== {new.name}: {len(fs)} Befunde ({sum(f.severity == 'error' for f in fs)} error), {time.time()-t0:.1f}s, {len(gt)} markierte Stellen")
            for r in gt:
                rr = pymupdf.Rect(r) + (-a.radius, -a.radius, a.radius, a.radius)
                m = [f for f in fs if pymupdf.Rect(f.bbox).intersects(rr)]
                tot += 1; hit += bool(m)
                print(f"   {'TREFFER' if m else 'verpasst'} {[round(v) for v in r]}", [(f.kind, f.value, f.text[:30]) for f in m[:3]])
        print(f"Recall: {hit}/{tot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
