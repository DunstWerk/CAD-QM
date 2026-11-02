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
    c.add_argument("pdf", help="PDF-Datei oder Ordner"); c.add_argument("--config"); c.add_argument("--top", type=int, default=30)
    c.add_argument("--out", help="Ausgabeordner: markierte PDFs + QM_Befunde.xlsx")
    c.add_argument("--whitelist", action="append", default=[], help="Zusaetzliche Wortliste (eine Zeile pro Wort)")
    c.add_argument("--only", choices=["overlap", "spelling", "consistency"], help="Nur diese Pruefung")
    w = sub.add_parser("words", help="Haeufigste unbekannte Woerter (Vorlage fuer die Whitelist)")
    w.add_argument("pdf", help="PDF-Datei oder Ordner"); w.add_argument("--config"); w.add_argument("--top", type=int, default=80)
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
        import pathlib
        from .cluster import cluster
        from .runner import check_set_files
        from .report.markup import add_markup, add_summary
        from .report.listing import write_xlsx
        cfg = load_config(a.config)
        src = pathlib.Path(a.pdf)
        files = sorted(src.glob("*.pdf")) if src.is_dir() else [src]
        rows = []
        raw = check_set_files([str(f) for f in files], cfg, (a.only,) if a.only else ("overlap", "spelling", "consistency"), a.whitelist)
        for f in files:
            fs = cluster(raw[str(f)])
            print(f"{f.name}: {len(fs)} Befunde ({sum(x.severity == 'error' for x in fs)} Fehler)")
            for x in fs[: a.top if not a.out else 0]:
                print(f"  {x.id} {x.severity:5s} {x.kind:9s} {x.value:5.1f}%  {[round(v) for v in x.bbox]}  {x.text[:50]!r}")
            rows += [(f.stem, x) for x in fs]
            if a.out:
                out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
                doc = pymupdf.open(f)
                add_markup(doc, fs, cfg); add_summary(doc, fs, cfg, f.stem)
                doc.save(out / f"{f.stem}_QM.pdf", garbage=3, deflate=True)
        if a.out:
            write_xlsx(rows, str(pathlib.Path(a.out) / "QM_Befunde.xlsx"))
            print(f"-> {a.out}")
    if a.cmd == "words":
        import collections, pathlib
        from .runner import check_pdf
        src = pathlib.Path(a.pdf); files = sorted(src.glob("*.pdf")) if src.is_dir() else [src]
        cnt = collections.Counter()
        for f in files:
            cnt.update(x.text for x in check_pdf(str(f), load_config(a.config), checks=("spelling",)))
        for word, n in cnt.most_common(a.top):
            print(f"{n:4d}  {word}")
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
