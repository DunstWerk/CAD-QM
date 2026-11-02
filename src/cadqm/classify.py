"""Tinten-Gewicht, Architekten-Text und Plankopf-Zone.

Urheberschaft (Architekt/wir) ist farblich nicht trennbar (Architekt zeichnet auch Schwarz/Blaugrau).
Fuer die Lesbarkeitspruefung zaehlt daher das *Gewicht der Tinte*: dunkel/gesaettigt = voll, hellgrau = reduziert.
"""
from __future__ import annotations
import re

DARK, LIGHT, NONE = "dark", "light", "none"


class Classifier:
    def __init__(self, cfg: dict):
        k = cfg["ink"]
        self.dark_lum, self.light_lum = k["dark_lum"], k["light_lum"]
        self.sat, self.full, self.minw = k["saturated"], k["full_weight"], k["min_weight"]
        a = cfg["architect_text"]
        self.layer_patterns = a["layer_patterns"]
        self.arch_max_weight = a["max_weight"]
        tb = cfg["title_block"]
        self.anchor = re.compile(tb["anchor_regex"], re.I)
        self.tb_margin = tb["margin"]
        self.tb_fallback = tb["fallback_rect"]

    # --- Tinte -------------------------------------------------------------
    def ink_weight(self, rgb) -> float:
        if rgb is None:
            return 0.0
        r, g, b = rgb[:3]
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        if lum <= self.dark_lum:
            return 1.0
        if max(r, g, b) - min(r, g, b) >= self.sat and lum < self.light_lum:
            return 1.0                                   # Gewerkefarbe (Blau, Gruen, Rot, Cyan, Magenta ...)
        if lum >= self.light_lum:
            return 0.0
        return (self.light_lum - lum) / (self.light_lum - self.dark_lum)

    def ink_class(self, rgb) -> str:
        w = self.ink_weight(rgb)
        return DARK if w >= self.full else (NONE if w < self.minw else LIGHT)

    # --- Text --------------------------------------------------------------
    def is_architect_text(self, item) -> bool:
        if any(p in (item.layer or "") for p in self.layer_patterns):
            return True
        return item.color is not None and self.ink_weight(item.color) < self.arch_max_weight

    # --- Plankopf ----------------------------------------------------------
    def title_block_rect(self, page, items) -> tuple[float, float, float, float]:
        """Sichtbarer Raum (pt). Anker: 'Legende*'-Texte in der rechten Haelfte."""
        W, H = page.rect.width, page.rect.height
        xs = [i.bbox[0] for i in items if i.source == "truetype" and i.bbox[0] > 0.5 * W and self.anchor.match(i.text)]
        if xs:
            return (max(0.0, min(xs) - self.tb_margin * W), 0.0, W, H)
        f = self.tb_fallback
        return (f[0] * W, f[1] * H, f[2] * W, f[3] * H)

    @staticmethod
    def in_rect(bbox, rect) -> bool:
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        return rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]
