"""Benachbarte Befunde gleichen Typs zu einem Befund zusammenfassen und durchnummerieren."""
from __future__ import annotations
from .findings import Finding, OVERLAP, SPELLING, CONSISTENCY

PREFIX = {OVERLAP: "Ü", SPELLING: "R", CONSISTENCY: "K"}


def _near(a, b, m):
    return not (a[2] + m < b[0] or b[2] + m < a[0] or a[3] + m < b[1] or b[3] + m < a[1])


def cluster(findings: list[Finding], margin: float = 4.0) -> list[Finding]:
    n = len(findings)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            a, b = findings[i], findings[j]
            if a.type == b.type and a.page == b.page and _near(a.bbox, b.bbox, margin):
                parent[find(j)] = find(i)
    groups: dict[int, list[Finding]] = {}
    for i, f in enumerate(findings):
        groups.setdefault(find(i), []).append(f)
    out: list[Finding] = []
    for g in groups.values():
        bb = (min(f.bbox[0] for f in g), min(f.bbox[1] for f in g), max(f.bbox[2] for f in g), max(f.bbox[3] for f in g))
        texts = list(dict.fromkeys(f.text for f in g if f.text))
        top = max(g, key=lambda f: f.value)
        out.append(Finding(top.type, top.page, bb, "error" if any(f.severity == "error" for f in g) else "warn",
                           top.value, " | ".join(texts[:4]) + (" …" if len(texts) > 4 else ""), top.detail,
                           "+".join(sorted({f.kind for f in g if f.kind})),
                           extra={**top.extra, "count": len(g), "members": [{"kind": f.kind, "severity": f.severity, "value": f.value, "text": f.text,
                                                                "bbox": [round(v, 1) for v in f.bbox], "extra": f.extra} for f in g]}))
    out.sort(key=lambda f: (f.page, f.type, f.bbox[1], f.bbox[0]))
    counter: dict[str, int] = {}
    for f in out:
        counter[f.type] = counter.get(f.type, 0) + 1
        f.id = f"{PREFIX[f.type]}-{counter[f.type]:03d}"
    return out
