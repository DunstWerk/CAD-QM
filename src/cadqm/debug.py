"""Debug-Bild: unsere Objekte farbig/schwarz, Architekt hellgrau, Texte eingerahmt, Zonen schraffiert."""
from __future__ import annotations
import cv2, numpy as np, pymupdf
from .classify import Classifier, OURS, ARCH
from .pdfio.text import extract_text


def debug_png(page: pymupdf.Page, cfg: dict, out: str, scale: float = 0.4) -> dict:
    cl = Classifier(cfg)
    W, H = int(page.rect.width * scale), int(page.rect.height * scale)
    img = np.full((H, W, 3), 255, np.uint8)
    stats = {OURS: 0, ARCH: 0}
    drawings = page.get_drawings()
    rm = page.rotation_matrix
    for pass_cls in (ARCH, OURS):                        # Architekt zuerst, unsere darueber
        for d in drawings:
            rgb = d.get("color") or d.get("fill")
            if cl.color_class(rgb) != pass_cls:
                continue
            stats[pass_cls] += 1
            col = (200, 200, 200) if pass_cls == ARCH else tuple(int(v * 255) for v in rgb[::-1])
            for it in d["items"]:
                pts = [(int(v.x * scale), int(v.y * scale)) for v in (q * rm for q in it[1:] if hasattr(q, "x"))]
                if it[0] == "re":
                    r = it[1] * rm; r.normalize(); pts = [(int(r.x0 * scale), int(r.y0 * scale)), (int(r.x1 * scale), int(r.y1 * scale))]
                    cv2.rectangle(img, pts[0], pts[1], col, 1)
                elif len(pts) >= 2:
                    cv2.line(img, pts[0], pts[-1], col, 1)
    items = extract_text(page)
    for t in items:
        b = [int(v * scale) for v in t.bbox]
        cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 140, 255) if t.source == "shx" else (200, 150, 0), 1)
    for z in cl.zones:
        cv2.rectangle(img, (int(z[0] * W), int(z[1] * H)), (int(z[2] * W), int(z[3] * H)), (0, 0, 255), 3)
    cv2.imwrite(out, img)
    stats["text"] = len(items)
    return stats
