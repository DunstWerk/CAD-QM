"""Getrennte Renderings: nur Grafik (Text entfernt) und nur Text (Grafik entfernt) im sichtbaren Raum."""
from __future__ import annotations
import numpy as np
import pymupdf


def _render(path: str, pno: int, scale: float, text_only: bool) -> np.ndarray:
    doc = pymupdf.open(path)                         # frische Kopie im Speicher, Datei bleibt unveraendert
    p = doc[pno]
    p.add_redact_annot(p.rect * p.derotation_matrix)  # Redaction arbeitet im unrotierten Raum
    if text_only:
        p.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_REMOVE,
                           graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                           text=pymupdf.PDF_REDACT_TEXT_NONE)
    else:
        p.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                           graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                           text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    pm = p.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False, annots=False)
    return np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width, 3).copy()


def render_full(path: str, pno: int, scale: float) -> np.ndarray:
    p = pymupdf.open(path)[pno]
    pm = p.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False, annots=False)
    return np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width, 3).copy()


def render_layers(path: str, pno: int, scale: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(voll, grafik_ohne_text, nur_text), jeweils RGB uint8. 'voll' zeigt die echte Z-Reihenfolge."""
    return render_full(path, pno, scale), _render(path, pno, scale, False), _render(path, pno, scale, True)


def pick_scale(page: pymupdf.Page, max_side_px: int = 7500, max_scale: float = 3.0) -> float:
    return min(max_scale, max_side_px / max(page.rect.width, page.rect.height))
