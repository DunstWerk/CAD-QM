from __future__ import annotations
import pymupdf
from pathlib import Path
from .checks.overlap import text_vs_ink, text_vs_text
from .checks.spelling import check_spelling, load_whitelist
from .classify import Classifier
from .config import load_config
from .findings import Finding
from .paths import app_dir
from .pdfio.text import extract_text


def check_pdf(path: str, cfg: dict | None = None, checks=("overlap", "spelling"), whitelist_files=()) -> list[Finding]:
    cfg = cfg or load_config()
    wl = load_whitelist(*[app_dir() / w for w in cfg.get("spelling", {}).get("whitelist", [])], *whitelist_files)
    doc = pymupdf.open(path)
    cl = Classifier(cfg)
    out: list[Finding] = []
    for pno, page in enumerate(doc):
        items = extract_text(page)
        zone = cl.title_block_rect(page, items)
        if "overlap" in checks:
            out += text_vs_ink(str(path), pno, page, items, cl, cfg, zone)
            out += text_vs_text(pno, items, cl, cfg, zone)
        if "spelling" in checks and cfg.get("spelling", {}).get("enabled", True):
            out += check_spelling(pno, items, cl, cfg, zone, wl)
    out.sort(key=lambda f: (-(f.severity == "error"), -f.value))
    return out


def ground_truth(old: str, new: str) -> list[tuple[float, float, float, float]]:
    """Von Hand ergaenzte Square-Annotationen (in 'new', nicht in 'old') = markierte Fehlerstellen, sichtbarer Raum."""
    a, b = pymupdf.open(old)[0], pymupdf.open(new)[0]
    seen = {tuple(round(v) for v in x.rect) for x in (a.annots() or [])}
    gt = []
    for x in b.annots() or []:
        if x.info.get("title") == "AutoCAD SHX Text" or tuple(round(v) for v in x.rect) in seen:
            continue
        r = x.rect * b.rotation_matrix
        r.normalize()
        gt.append(tuple(r))
    return gt


class Cancelled(Exception):
    pass


def check_set_files(paths: list[str], cfg: dict | None = None, checks=("overlap", "spelling", "consistency"),
                    whitelist_files=(), progress=None, cancelled=None) -> dict[str, list[Finding]]:
    """Alle Pruefungen fuer mehrere PDFs; Konsolidität laeuft ueber den ganzen Satz. Rueckgabe: Pfad -> Befunde."""
    import os
    from .checks.consistency import build_info, check_set
    cfg = cfg or load_config()
    steps = len(paths) + ("consistency" in checks)
    res: dict[str, list[Finding]] = {}
    for n, p in enumerate(paths):
        if cancelled and cancelled():
            raise Cancelled()
        if progress:
            progress(n, steps, f"Prüfe {os.path.basename(str(p))} …")
        res[str(p)] = check_pdf(str(p), cfg, tuple(c for c in checks if c != "consistency"), whitelist_files)
    if cancelled and cancelled():
        raise Cancelled()
    if "consistency" in checks and cfg.get("consistency"):
        if progress:
            progress(len(paths), steps, "Konsolidität über den Plansatz …")
        cl = Classifier(cfg); infos = []
        for p in paths:
            doc = pymupdf.open(p)
            stem = os.path.splitext(os.path.basename(str(p)))[0]
            for pno, page in enumerate(doc):
                infos.append(build_info(str(p), pno, page, doc.metadata.get("title") or "", cfg, cl,
                                        stem if len(doc) == 1 else f"{stem}[{pno + 1}]"))
        for (path, _), fs in check_set(infos, cfg).items():
            res[path] += fs
    if progress:
        progress(steps, steps, "Fertig")
    return res
