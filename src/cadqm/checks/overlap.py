"""Ueberlagerungspruefung (M1): Text <-> Grafik (Kontrast unter den Glyphen) und Text <-> Text."""
from __future__ import annotations
import cv2
import numpy as np
import pymupdf
from shapely.geometry import box
from shapely.strtree import STRtree
from ..classify import Classifier
from ..findings import Finding, OVERLAP
from ..pdfio.render import render_layers, pick_scale
from ..pdfio.text import TextItem


def _lum(img: np.ndarray) -> np.ndarray:
    return (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114) / 255.0


def _sev(pct: float, ocfg: dict) -> str | None:
    return "error" if pct >= ocfg["error_pct"] else ("warn" if pct >= ocfg["warn_pct"] else None)


def text_vs_ink(path: str, pno: int, page: pymupdf.Page, items: list[TextItem], cl: Classifier, cfg: dict,
                zone: tuple, debug: list | None = None) -> list[Finding]:
    """Je Glyphenpixel: verdeckt (sichtbare Farbe != Textfarbe) oder kontrastarm (Hintergrund ~ Textfarbe)."""
    o = cfg["overlap"]
    s = pick_scale(page)
    full, ink, txt = render_layers(path, pno, s)
    # Haarlinien werden beim Rendern aufgehellt -> dunkle Grafik um 1 px verdicken (Erosion der Leuchtdichte)
    bg = cv2.erode(_lum(ink).astype(np.float32), np.ones((3, 3), np.uint8))
    tmin = txt.min(axis=2)
    covered_all = np.abs(full.astype(np.int16) - txt.astype(np.int16)).max(axis=2) > o["covered_delta"]
    out: list[Finding] = []
    for it in items:
        if it.source != "truetype" or it.color is None or cl.in_rect(it.bbox, zone):
            continue
        if cl.is_architect_text(it):                                 # Lesbarkeit von Architekten-/XREF-Text ist nicht unser Thema
            continue
        x0, y0, x1, y1 = (int(max(0, v * s)) for v in (it.bbox[0], it.bbox[1], it.bbox[2] + 1, it.bbox[3] + 1))
        thr = (min(it.color) * 255 + 255) / 2                        # halbe Abdeckung je Textfarbe (auch hellgrau)
        g = tmin[y0:y1, x0:x1] < thr
        n = int(g.sum())
        if n < o["min_glyph_px"]:
            continue
        sl = (slice(y0, y1), slice(x0, x1))
        covered = g & covered_all[sl]
        lowc = np.zeros_like(g)
        light = cl.ink_weight(it.color) < o["min_text_weight"]
        if light:       # hellgrauer (Architekten-)Text: nur melden, wenn DUNKLE Tinte ihn verdeckt
            dark_bg = (bg[sl] <= cl.dark_lum) | _sat(ink[sl])
            bad = covered & dark_bg
        else:
            lt = 0.299 * it.color[0] + 0.587 * it.color[1] + 0.114 * it.color[2]
            lowc = g & (np.abs(bg[sl] - lt) < o["contrast_min"])
            bad = covered | lowc
        pct = 100.0 * int(bad.sum()) / n
        if debug is not None:
            debug.append((it, pct))
        sev = _sev(pct, o)
        if sev:
            out.append(Finding(OVERLAP, pno, it.bbox, sev, round(pct, 1), it.text,
                               "Text von Grafik verdeckt/kontrastarm" + (" (hellgrauer Text)" if light else ""),
                               "text_ink", extra={"layer": it.layer, "font_size": round(it.size, 1), "text_color": [round(c, 2) for c in it.color],
                                                  "text_class": "light" if light else "dark", "glyph_px": n, "scale": round(s, 2),
                                                  "covered_pct": round(100.0 * int(covered.sum()) / n, 1),
                                                  "lowcontrast_pct": round(100.0 * int(lowc.sum()) / n, 1)}))
    return out


def _sat(img: np.ndarray) -> np.ndarray:
    """Gesaettigte (bunte) Pixel, z. B. Gewerkefarben."""
    return (img.max(axis=2).astype(np.int16) - img.min(axis=2)) > 64


def _core_overlap(a: TextItem, b: TextItem, min_frac: float) -> float:
    """Anteil der Buchstaben des KUERZEREN Textes, deren Kern einen Buchstabenkern des anderen Textes ueberdeckt (0..100)."""
    if not a.chars or not b.chars:                                   # SHX (keine Buchstaben): Boxvergleich
        ia = box(*a.bbox).intersection(box(*b.bbox)).area
        sm = min(box(*a.bbox).area, box(*b.bbox).area)
        return 100.0 * ia / sm if sm > 0 else 0.0
    small, big = (a, b) if len(a.chars) <= len(b.chars) else (b, a)
    hit = 0
    for c in small.chars:
        ca = max((c[2] - c[0]) * (c[3] - c[1]), 1e-6)
        for d in big.chars:
            w = min(c[2], d[2]) - max(c[0], d[0])
            h = min(c[3], d[3]) - max(c[1], d[1])
            if w > 0 and h > 0 and w * h >= min_frac * min(ca, max((d[2] - d[0]) * (d[3] - d[1]), 1e-6)):
                hit += 1
                break
    return 100.0 * hit / max(len(small.chars), 1)


def text_vs_text(pno: int, items: list[TextItem], cl: Classifier, cfg: dict, zone: tuple) -> list[Finding]:
    """Text ueber Text: Buchstabenkerne statt Zeilenkaesten (eng gesetzte/gedrehte Zeilen ueberlappen als Kasten, nicht als Schrift)."""
    o = cfg["overlap"]
    cand = [i for i in items if not cl.in_rect(i.bbox, zone) and (i.color is None or cl.ink_weight(i.color) >= o["min_text_weight"])]
    boxes = [box(*i.bbox) for i in cand]
    tree = STRtree(boxes)
    out: list[Finding] = []
    for a, ia in enumerate(cand):
        for b in tree.query(boxes[a]):
            if b <= a:
                continue
            ib = cand[b]
            if ia.text == ib.text and boxes[a].intersection(boxes[b]).area >= 0.8 * min(boxes[a].area, boxes[b].area):
                continue                                             # doppelt gesetzter, identischer Text: kein Lesbarkeitsproblem
            if cl.is_architect_text(ia) and cl.is_architect_text(ib):  # beide vom Architekten: nicht unser Thema
                continue
            if any(len(t.text) == 1 and not t.text.isalnum() for t in (ia, ib)):    # einzelnes Satzzeichen ('-', '.', '/') beruehrt Nachbarn: normal
                continue
            ratio = _core_overlap(ia, ib, o["char_overlap_min_frac"])
            sev = _sev(ratio, {"warn_pct": o["text_text_warn_pct"], "error_pct": o["text_text_error_pct"]})
            if sev:
                u = boxes[a].union(boxes[b]).bounds
                out.append(Finding(OVERLAP, pno, u, sev, round(ratio, 1), f"{ia.text} / {ib.text}",
                                   "Texte überlagern sich", "text_text",
                                   extra={"texts": [ia.text, ib.text], "font_sizes": [round(ia.size, 1), round(ib.size, 1)],
                                          "layers": [ia.layer, ib.layer], "sources": [ia.source, ib.source], "method": "char_cores"}))
    return out
