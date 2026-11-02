"""Klassifikation von Farben/Objekten: 'ours' (unsere Planung), 'architect' (Grau), 'ignore' (Weiss/Zone)."""
from __future__ import annotations

OURS, ARCH, IGNORE = "ours", "architect", "ignore"


class Classifier:
    def __init__(self, cfg: dict):
        c = cfg["colors"]
        self.ours = [tuple(x) for x in c["ours"]]
        self.tol = c["tolerance"]
        self.black = c["gray_black_cutoff"]
        self.white = c["gray_white_cutoff"]
        self.zones = [z["rect"] for z in cfg.get("exclude_zones", [])]

    def color_class(self, rgb) -> str:
        if rgb is None:
            return IGNORE
        r, g, b = rgb[:3]
        if max(r, g, b) - min(r, g, b) < 0.02:          # neutral = Grau
            if r <= self.black:
                return OURS                              # (fast) Schwarz
            if r >= self.white:
                return IGNORE                            # Weiss
            return ARCH
        for o in self.ours:
            if max(abs(r - o[0]), abs(g - o[1]), abs(b - o[2])) <= self.tol:
                return OURS
        return OURS                                      # andere Buntfarbe: Gewerkefarbe -> unsere Planung

    def in_zone(self, bbox, page_rect) -> bool:
        W, H = page_rect.width, page_rect.height
        cx, cy = (bbox[0] + bbox[2]) / 2 / W, (bbox[1] + bbox[3]) / 2 / H
        return any(z[0] <= cx <= z[2] and z[1] <= cy <= z[3] for z in self.zones)
