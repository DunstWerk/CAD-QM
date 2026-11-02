"""Text-Extraktion: TrueType-Text (echter Text-Layer) + AutoCAD-SHX-Annotationen.

Alle Koordinaten liegen im *sichtbaren* (rotierten) Seitenraum von PyMuPDF
(page.rect, Ursprung links oben) - dort, wo auch Markierungen gesetzt werden.
"""
from __future__ import annotations
from dataclasses import dataclass
import pymupdf


CORE_INSET = 0.22                              # Anteil je Seite, um den Buchstabenboxen verkleinert werden (Ober-/Unterlaengen ignorieren)


@dataclass(frozen=True)
class TextItem:
    text: str
    bbox: tuple[float, float, float, float]   # x0,y0,x1,y1 im sichtbaren Raum
    color: tuple[float, float, float] | None  # None = unbekannt (SHX)
    size: float
    direction: tuple[float, float]            # Schreibrichtung (dx,dy)
    source: str                               # "truetype" | "shx"
    layer: str = ""                           # OCG-/Ebenenname (leer = unbekannt)
    chars: tuple = ()                         # Kernboxen der Buchstaben (sichtbarer Raum), nur TrueType


def _rgb(v: int) -> tuple[float, float, float]:
    return ((v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255)


def _layer_map(page: pymupdf.Page) -> dict[tuple[float, float], str]:
    """Ebene je Text-Span, Schluessel = gerundeter Ursprung des ersten Zeichens (unrotierter Raum)."""
    m: dict[tuple[float, float], str] = {}
    for t in page.get_texttrace():
        ch = t.get("chars")
        if ch and t.get("layer"):
            o = ch[0][2]
            m[(round(o[0], 1), round(o[1], 1))] = t["layer"]
    return m


def extract_truetype(page: pymupdf.Page) -> list[TextItem]:
    """get_text() liefert Koordinaten im UNROTIERTEN Raum -> hier in den sichtbaren Raum umrechnen."""
    items: list[TextItem] = []
    seen: set[tuple] = set()
    rm = page.rotation_matrix
    layers = _layer_map(page)
    for blk in page.get_text("rawdict")["blocks"]:
        for line in blk.get("lines", []):
            d = pymupdf.Point(line["dir"]) * pymupdf.Matrix(rm.a, rm.b, rm.c, rm.d, 0, 0)
            for s in line["spans"]:
                txt = "".join(c["c"] for c in s["chars"]).replace("\xa0", " ").strip()
                if not txt:
                    continue
                r = pymupdf.Rect(s["bbox"]) * rm
                r.normalize()
                key = (txt, round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1))
                if key in seen:                      # doppelt gesetzter Text
                    continue
                seen.add(key)
                cores = []
                for c in s["chars"]:                  # Buchstabenkerne (innen verkleinert): vergleichen Glyphen statt Zeilenkaesten
                    if not c["c"].strip():
                        continue
                    cb = pymupdf.Rect(c["bbox"]) * rm
                    cb.normalize()
                    ix, iy = cb.width * CORE_INSET, cb.height * CORE_INSET
                    cores.append((cb.x0 + ix, cb.y0 + iy, cb.x1 - ix, cb.y1 - iy))
                o = s["origin"]
                items.append(TextItem(
                    text=txt, bbox=(r.x0, r.y0, r.x1, r.y1), color=_rgb(s["color"]),
                    size=s["size"], direction=(round(d.x, 3), round(d.y, 3)), source="truetype",
                    layer=layers.get((round(o[0], 1), round(o[1], 1)), ""), chars=tuple(cores),
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
    """Beide Quellen; Items, deren Mittelpunkt ausserhalb der sichtbaren Seite liegt (abgeschnitten), entfallen."""
    r = page.rect
    return [i for i in extract_truetype(page) + extract_shx(page)
            if r.x0 <= (i.bbox[0] + i.bbox[2]) / 2 <= r.x1 and r.y0 <= (i.bbox[1] + i.bbox[3]) / 2 <= r.y1]
