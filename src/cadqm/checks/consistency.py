"""Konsolidität (M4): Plankopf-Felder, Index, Schreibvarianten, Koten-Format, Legende - ueber einen Plansatz."""
from __future__ import annotations
import collections
import re
from dataclasses import dataclass, field
import pymupdf
from ..classify import Classifier
from ..findings import Finding, CONSISTENCY
from ..pdfio.text import TextItem, extract_text

TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß0-9]+(?:[-_/][A-Za-zÄÖÜäöüß0-9]+)*")
KOTE = re.compile(r"^\s*([+\-±])(\s?)(\d+)([.,])(\d{1,3})\s*(m|M)?\s*$")
TRANSLIT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


@dataclass
class Field:
    text: str
    bbox: tuple[float, float, float, float]


@dataclass
class PlanInfo:
    path: str
    pno: int
    name: str                                   # Dateiname ohne Endung (+ [Seite] bei Mehrseitern)
    items: list[TextItem]
    zone: tuple
    fields: dict[str, Field] = field(default_factory=dict)
    index_rows: dict[str, str] = field(default_factory=dict)     # Buchstabe -> Beschreibung (nur befuellte Zeilen)
    body: list[TextItem] = field(default_factory=list)           # Plantext (ohne Plankopf/Architekt)
    legend: list[TextItem] = field(default_factory=list)
    title: str = ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.casefold().translate(TRANSLIT))


def _union(items) -> tuple:
    return (min(i.bbox[0] for i in items), min(i.bbox[1] for i in items), max(i.bbox[2] for i in items), max(i.bbox[3] for i in items))


def _find_field(label: TextItem, tb: list[TextItem], max_lines: int) -> Field | None:
    """Wert = Textzeilen unterhalb des Labels (groessere Schrift, gleiche Spalte), bis zum naechsten Label."""
    cand = [v for v in tb if v is not label and v.size > label.size + 1 and label.bbox[3] - 3 <= v.bbox[1] <= label.bbox[3] + 110
            and label.bbox[0] - 8 <= v.bbox[0] <= label.bbox[0] + 60 and not v.text.endswith(":")]
    cand.sort(key=lambda v: (v.bbox[1], v.bbox[0]))
    if not cand:
        return None
    lines = [cand[0]]
    for v in cand[1:]:
        if len(lines) >= max_lines or v.bbox[1] - lines[-1].bbox[3] > 2.2 * lines[-1].size or abs(v.size - lines[0].size) > 1.5:
            break
        lines.append(v)
    return Field(" ".join(v.text for v in lines), _union(lines))


def build_info(path: str, pno: int, page: pymupdf.Page, doc_title: str, cfg: dict, cl: Classifier, name: str) -> PlanInfo:
    cc = cfg["consistency"]
    items = extract_text(page)
    zone = cl.title_block_rect(page, items)
    info = PlanInfo(path, pno, name, items, zone, title=doc_title)
    tb = [i for i in items if cl.in_rect(i.bbox, zone) and i.source == "truetype"]
    tb.sort(key=lambda i: (i.bbox[1], i.bbox[0]))
    for fname, labels in cc["fields"].items():
        wanted = {_norm(l.rstrip(":")) for l in labels}
        for lab in tb:                                           # nach y sortiert: das erste Vorkommen mit Wert gilt
            if lab.text.endswith(":") and _norm(lab.text.rstrip(":")) in wanted:
                fv = _find_field(lab, tb, cc["max_value_lines"].get(fname, 1))
                if fv and (fname != "Index" or len(fv.text) <= 3):
                    info.fields[fname] = fv
                    break
    # Indextabelle: Zeilen a..h mit Beschreibung
    for r in tb:
        if re.fullmatch(r"[a-h]", r.text) and r.size < 9:
            rest = [v for v in tb if abs(v.bbox[1] - r.bbox[1]) < 8 and v.bbox[0] > r.bbox[2] + 3 and v.size > 9
                    and v.bbox[0] < r.bbox[0] + 250]
            if rest and "Index" in info.fields and r.bbox[1] > info.fields["Index"].bbox[3]:
                info.index_rows[r.text] = " ".join(v.text for v in sorted(rest, key=lambda v: v.bbox[0]))
    # Legende = Plankopf-Zone oberhalb des ersten Feld-Labels
    tops = [f.bbox[1] for f in info.fields.values()]
    ytop = min(tops) - 40 if tops else page.rect.height * 0.45
    info.legend = [i for i in tb if i.bbox[3] < ytop]
    info.body = [i for i in items if not cl.in_rect(i.bbox, zone) and not cl.is_architect_text(i)]
    return info


def _majority(values: dict[str, str]) -> tuple[str | None, bool]:
    """(Mehrheitswert, strikte Mehrheit?)"""
    c = collections.Counter(_norm(v) for v in values.values())
    top, n = c.most_common(1)[0]
    return top, n > len(values) / 2


def check_set(infos: list[PlanInfo], cfg: dict) -> dict[tuple[str, int], list[Finding]]:
    cc = cfg["consistency"]
    out: dict[tuple[str, int], list[Finding]] = {(i.path, i.pno): [] for i in infos}

    def add(i: PlanInfo, bbox, sev, text, detail, kind):
        out[(i.path, i.pno)].append(Finding(CONSISTENCY, i.pno, bbox, sev, 0.0, text, detail, kind))

    # A: Plannummer <-> Dateiname
    if cc["rules"]["plannummer_filename"]:
        for i in infos:
            f = i.fields.get("Plannummer")
            if f and _key(f.text) and _key(f.text) not in _key(i.name) and _key(i.name) not in _key(f.text):
                add(i, f.bbox, "error", f.text, f"Plannummer „{f.text}“ passt nicht zum Dateinamen „{i.name}“", "plannummer_filename")
    # C: Index im Kopf = letzte befuellte Zeile der Indextabelle
    if cc["rules"]["index_table"]:
        for i in infos:
            f = i.fields.get("Index")
            if f and i.index_rows:
                last = max(i.index_rows)
                if f.text.strip().casefold() != last:
                    add(i, f.bbox, "error", f.text, f"Index im Kopf „{f.text}“, letzte Zeile der Indextabelle ist „{last}“", "index_table")
    # B: Felder, die im ganzen Satz gleich sein muessen
    if len(infos) >= 2:
        for fname in cc["rules"]["set_equal"]:
            vals = {i.name: i.fields[fname].text for i in infos if fname in i.fields}
            if len(vals) < 2 or len({_norm(v) for v in vals.values()}) == 1:
                continue
            top, strict = _majority(vals)
            for i in infos:
                f = i.fields.get(fname)
                if f and _norm(f.text) != top:
                    add(i, f.bbox, "error" if strict else "warn", f.text,
                        f"{fname} uneinheitlich im Plansatz: „{f.text}“ statt „{top}“" if strict else
                        f"{fname} uneinheitlich im Plansatz: „{f.text}“ ({len(set(_norm(v) for v in vals.values()))} Varianten)", "set_field")
    # D: Schreibvarianten (Bindestrich/Leerzeichen/Umlaut) ueber den ganzen Satz
    if cc["rules"]["variants"]:
        occ: dict[str, dict[str, list[tuple[PlanInfo, TextItem]]]] = collections.defaultdict(lambda: collections.defaultdict(list))
        for i in infos:
            for it in i.body:
                for t in TOKEN.findall(it.text):
                    if len(t) >= cc["variant_min_len"] and not re.fullmatch(r"[\d._/-]+", t) and not t.isupper():
                        occ[_key(t)][t.casefold()].append((i, it))
        for key, forms in occ.items():
            if len(forms) < 2:
                continue
            cnt = {k: len(v) for k, v in forms.items()}
            lead = max(cnt, key=cnt.get)
            tie = sorted(cnt.values())[-1] == sorted(cnt.values())[-2]
            for k, hits in forms.items():
                if k == lead and not tie:
                    continue
                for i, it in hits:
                    sev = "error" if (not tie and cnt[lead] >= 3 * cnt[k]) else "warn"
                    add(i, it.bbox, sev, k, f"Schreibvariante „{k}“ ({cnt[k]}×) – im Satz auch: " +
                        ", ".join(f"„{o}“ ({cnt[o]}×)" for o in cnt if o != k), "variant")
    # F: Koten-Format (Vorzeichen-Leerzeichen, Dezimaltrennzeichen) - Minderheit je Schriftgroessenklasse melden
    if cc["rules"]["kote_format"]:
        groups: dict[int, dict[tuple, list[tuple[PlanInfo, TextItem]]]] = collections.defaultdict(lambda: collections.defaultdict(list))
        for i in infos:
            for it in i.body:
                m = KOTE.match(it.text)
                if m and it.size >= 2:
                    groups[round(it.size)][(m.group(4), bool(m.group(2)))].append((i, it))
        for size, styles in groups.items():                  # unterschiedliche Textarten haben oft unterschiedliche Schriftgroesse
            total = sum(len(v) for v in styles.values())
            if len(styles) < 2 or total < cc["kote_min_total"]:
                continue
            lead = max(styles, key=lambda k: len(styles[k]))
            for st, hits in styles.items():
                if st != lead and len(hits) <= cc["kote_minority_max_share"] * total:
                    for i, it in hits:
                        add(i, it.bbox, "warn", it.text, f"Koten-Format abweichend: „{it.text}“ – bei Schrift ~{size} pt überwiegend "
                            f"Trennzeichen „{lead[0]}“, {'mit' if lead[1] else 'ohne'} Leerzeichen nach dem Vorzeichen", "kote_format")
    # G: Legende in allen Plaenen gleich
    if cc["rules"]["legend"] and len(infos) >= 3:
        bags = {(i.path, i.pno): collections.Counter(_norm(t.text) for t in i.legend if len(t.text) > 2) for i in infos}
        share = collections.Counter(k for b in bags.values() for k in b)
        for i in infos:
            b = bags[(i.path, i.pno)]
            missing = sorted(k for k, n in share.items() if n >= 0.6 * len(infos) and k not in b)
            extra = sorted(k for k in b if share[k] == 1)
            if missing or extra:
                ys = [t.bbox for t in i.legend] or [i.zone]
                bb = (min(x[0] for x in ys), min(x[1] for x in ys), max(x[2] for x in ys), max(x[3] for x in ys))
                parts = ([f"fehlt: {', '.join(repr(m) for m in missing[:4])}"] if missing else []) + \
                        ([f"nur hier: {', '.join(repr(e) for e in extra[:4])}"] if extra else [])
                add(i, bb, "warn", "Legende", "Legende weicht vom Rest des Plansatzes ab – " + "; ".join(parts), "legend")
    return out
