"""Rechtschreibpruefung (M3): Hunspell de_DE (spylls) + Projekt-Whitelist, Plankopf/Architekten-Text ausgenommen."""
from __future__ import annotations
import functools
import re
from pathlib import Path
from ..classify import Classifier
from ..findings import Finding, SPELLING
from ..pdfio.text import TextItem

DICT_BASE = Path(__file__).resolve().parent.parent / "data" / "de_DE" / "de_DE_frami"
WORD = re.compile(r"[A-Za-zÄÖÜäöüß]+")


@functools.lru_cache(maxsize=1)
def _dictionary():
    from spylls.hunspell import Dictionary
    return Dictionary.from_files(str(DICT_BASE))


def load_whitelist(*paths: str | Path | None) -> set[str]:
    words: set[str] = set()
    for p in paths:
        if p and Path(p).is_file():
            for line in Path(p).read_text(encoding="utf-8").splitlines():
                line = line.split("#")[0].strip()
                if line:
                    words.add(line.lower())
    return words


def _dist(a: str, b: str) -> int:
    """Damerau-Levenshtein (optimal string alignment)."""
    a, b = a.lower(), b.lower()
    d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            c = a[i - 1] != b[j - 1]
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


@functools.lru_cache(maxsize=50000)
def _known(tok: str) -> bool:
    d = _dictionary()
    return d.lookup(tok) or d.lookup(tok.capitalize()) or d.lookup(tok.lower())


@functools.lru_cache(maxsize=5000)
def _suggest(tok: str, max_len: int = 16) -> tuple[str, ...]:
    """Nur die schnelle Edit-Stufe von Hunspell (Tippfehler); die n-Gramm-Suche braucht Sekunden pro Wort."""
    if len(tok) > max_len:
        return ()
    base = tok.capitalize() if tok.isupper() else tok
    res: list[str] = []
    for sug in _dictionary().suggester.edit_suggestions(base, lambda s, check_inclusion=False: iter([s]), compounds=False, limit=3):
        t = getattr(sug, "text", sug)
        if t and t != base and t not in res:
            res.append(t)
    return tuple(res[:3])


def _token_bbox(it: TextItem, start: int, end: int) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = it.bbox
    n = max(len(it.text), 1)
    f0, f1 = start / n, end / n
    if abs(it.direction[0]) >= abs(it.direction[1]):            # waagrecht (ggf. gespiegelt)
        w = x1 - x0
        return (x0 + w * f0, y0, x0 + w * f1, y1) if it.direction[0] >= 0 else (x1 - w * f1, y0, x1 - w * f0, y1)
    h = y1 - y0
    return (x0, y0 + h * f0, x1, y0 + h * f1) if it.direction[1] >= 0 else (x0, y1 - h * f1, x1, y1 - h * f0)


def check_spelling(pno: int, items: list[TextItem], cl: Classifier, cfg: dict, zone: tuple,
                   whitelist: set[str]) -> list[Finding]:
    sc = cfg["spelling"]
    out: list[Finding] = []
    for it in items:
        if cl.in_rect(it.bbox, zone) or cl.is_architect_text(it):
            continue
        text = it.text
        for m in WORD.finditer(text):
            tok = m.group()
            if len(tok) < sc["min_len"] or tok.lower() in whitelist:
                continue
            if tok.isupper() and len(tok) <= sc["abbrev_max_len"]:        # Kuerzel (LZ, MK, BT, ...)
                continue
            if m.end() == len(text) and text.endswith("-"):                # Silbentrennung am Zeilenende
                continue
            if sc["skip_single_letter_neighbours"] and re.match(r"[-_.]?\d|[A-Za-z]\d", text[m.end():m.end() + 2]):
                continue                                                    # Bezeichner wie "Kabel1", "MK2"
            if _known(tok):
                continue
            sug = _suggest(tok)
            # wahrscheinlicher Tippfehler: ab 6 Buchstaben, Einzelwort-Vorschlag mit kleinem Editierabstand
            near = [s for s in sug if len(tok) >= sc["typo_min_len"] and " " not in s and "-" not in s
                    and _dist(tok, s) <= sc["typo_distance"]]
            out.append(Finding(SPELLING, pno, _token_bbox(it, m.start(), m.end()), "error" if near else "warn", 0.0, tok,
                               f"Unbekanntes Wort „{tok}“" + (f" → {', '.join(sug)}" if sug else ""),
                               "typo" if near else "unknown", extra={"suggestions": list(sug), "context": text, "layer": it.layer}))
    return out
