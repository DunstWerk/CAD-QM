"""Text-Extraktion: TrueType-Text (echter Text-Layer) + AutoCAD-SHX-Annotationen.

Alle Koordinaten liegen im *sichtbaren* (rotierten) Seitenraum von PyMuPDF
(page.rect, Ursprung links oben) - dort, wo auch Markierungen gesetzt werden.
"""
from __future__ import annotations
from dataclasses import dataclass
import pymupdf


@dataclass(frozen=True)
class TextItem:
    text: str
    bbox: tuple[float, float, float, float]   # x0,y0,x1,y1 im sichtbaren Raum
    color: tuple[float, float, float] | None  # None = unbekannt (SHX)
    size: float
    direction: tuple[float, float]            # Schreibrichtung (dx,dy)
    source: str                               # "truetype" | "shx"


def _rgb(v: int) -> tuple[float, float, float]:
    return ((v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255)


def extract_truetype(page: pymupdf.Page) -> list[TextItem]:
    items: list[TextItem] = []
    seen: set[tuple] = set()
    for blk in page.get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].replace("\xa0", " ").strip()]
            if not spans:
                continue
            # Doppelt gesetzte Spans (gleicher Text, gleiche Lage) verwerfen
            for s in spans:
                x0, y0, x1, y1 = s["bbox"]
                key = (s["text"], round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
                if key in seen:
                    continue
                seen.add(key)
                items.append(TextItem(
                    text=s["text"].replace("\xa0", " ").strip(),
                    bbox=(x0, y0, x1, y1),
                    color=_rgb(s["color"]),
                    size=s["size"],
                    direction=tuple(line["dir"]),
                    source="truetype",
                ))
    return items


def extract_shx(page: pymupdf.Page) -> list[TextItem]:
    """AutoCAD 'SHX Text': Inhalt steckt unsichtbar in Square-Annotationen."""
    items: list[TextItem] = []
    rot = page.rotation_matrix  # unrotierter Raum -> sichtbarer Raum
    for a in page.annots() or []:
        if a.info.get("title") != "AutoCAD SHX Text":
            continue
        txt = (a.info.get("content") or "").strip()
        if not txt:
            continue
        r = a.rect * rot
        r.normalize()
        w, h = r.width, r.height
        items.append(TextItem(
            text=txt, bbox=(r.x0, r.y0, r.x1, r.y1), color=None,
            size=min(w, h), direction=(1.0, 0.0) if w >= h else (0.0, -1.0),
            source="shx",
        ))
    return items


def extract_text(page: pymupdf.Page) -> list[TextItem]:
    """Beide Quellen; Items ausserhalb der sichtbaren Seite (abgeschnitten) entfallen."""
    r = page.rect
    return [i for i in extract_truetype(page) + extract_shx(page)
            if i.bbox[2] > r.x0 and i.bbox[0] < r.x1 and i.bbox[3] > r.y0 and i.bbox[1] < r.y1]
