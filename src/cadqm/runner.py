from __future__ import annotations
import pymupdf
from pathlib import Path
from .checks.overlap import text_vs_ink, text_vs_text
from .checks.spelling import check_spelling, load_whitelist
from .classify import Classifier
from .config import load_config
from .findings import Finding
from .pdfio.text import extract_text


def check_pdf(path: str, cfg: dict | None = None, checks=("overlap", "spelling"), whitelist_files=()) -> list[Finding]:
    cfg = cfg or load_config()
    root = Path(__file__).resolve().parents[2]
    wl = load_whitelist(*[root / w for w in cfg.get("spelling", {}).get("whitelist", [])], *whitelist_files)
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
