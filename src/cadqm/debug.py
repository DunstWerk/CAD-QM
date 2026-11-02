"""Debug-Bild: dunkle Tinte in Originalfarbe, helle Tinte hellgrau, Texte eingerahmt, Plankopf rot."""
from __future__ import annotations
import cv2, numpy as np, pymupdf
from .classify import Classifier, DARK, LIGHT
from .pdfio.text import extract_text


def debug_png(page: pymupdf.Page, cfg: dict, out: str, scale: float = 0.3) -> dict:
    cl = Classifier(cfg)
    rm = page.rotation_matrix
    W, H = int(page.rect.width * scale), int(page.rect.height * scale)
    img = np.full((H, W, 3), 255, np.uint8)
    stats = {DARK: 0, LIGHT: 0}
    drawings = page.get_drawings()
    for pass_cls in (LIGHT, DARK):                        # helle Tinte zuerst, dunkle darueber
        for d in drawings:
            rgb = d.get("color") or d.get("fill")
            if cl.ink_class(rgb) != pass_cls:
                continue
            stats[pass_cls] += 1
            col = (200, 200, 200) if pass_cls == LIGHT else tuple(int(v * 255) for v in rgb[:3][::-1])
            for it in d["items"]:
                if it[0] == "re":
                    r = it[1] * rm; r.normalize()
                    cv2.rectangle(img, (int(r.x0 * scale), int(r.y0 * scale)), (int(r.x1 * scale), int(r.y1 * scale)), col, 1)
                    continue
                pts = [(int(v.x * scale), int(v.y * scale)) for v in (q * rm for q in it[1:] if hasattr(q, "x"))]
                if len(pts) >= 2:
                    cv2.line(img, pts[0], pts[-1], col, 1)
    items = extract_text(page)
    for t in items:
        b = [int(v * scale) for v in t.bbox]
        col = (0, 140, 255) if t.source == "shx" else ((160, 160, 160) if cl.is_architect_text(t) else (200, 120, 0))
        cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), col, 1)
    z = cl.title_block_rect(page, items)
    cv2.rectangle(img, (int(z[0] * scale), int(z[1] * scale)), (int(z[2] * scale) - 2, int(z[3] * scale) - 2), (0, 0, 255), 3)
    cv2.imwrite(out, img)
    stats.update(text=len(items), architect_text=sum(1 for t in items if cl.is_architect_text(t)),
                 title_block_x=round(z[0] / page.rect.width, 3))
    return stats
