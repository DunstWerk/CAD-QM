"""Markiertes PDF: Rahmen + Index-Marke je Befund auf eigener Ebene 'QM-Pruefung', plus Uebersichtsseiten."""
from __future__ import annotations
import pymupdf
from ..findings import Finding, OVERLAP, SPELLING, CONSISTENCY

TYPE_NAME = {OVERLAP: "Überlappung", SPELLING: "Rechtschreibung", CONSISTENCY: "Konsolidität"}
LAYER = "QM-Prüfung"


def _scaled(page: pymupdf.Page) -> tuple[float, float]:
    side = max(page.rect.width, page.rect.height)
    return max(0.8, side / 3000), min(10.0, max(6.0, side / 480))   # (Strichstaerke, Schriftgroesse) skaliert mit Blattgroesse


def add_markup(doc: pymupdf.Document, findings: list[Finding], cfg: dict) -> None:
    colors = cfg["markup"]["colors"]
    ocg = doc.add_ocg(LAYER, on=True)
    for f in findings:
        page = doc[f.page]
        lw, fs = _scaled(page)
        col = tuple(colors[f.type])
        pad = {OVERLAP: 1.5, SPELLING: 3.0, CONSISTENCY: 4.5}[f.type] * lw       # konzentrisch gestaffelt: Mehrfachmarken verdecken sich nicht
        r = pymupdf.Rect(f.bbox) + (-pad, -pad, pad, pad)
        d = page.derotation_matrix                                # Annotationen leben im unrotierten Raum
        title = f"{f.id} {TYPE_NAME[f.type]}"
        info = f"{title}: {f.detail} ({f.value:g} %) – {f.text}"
        a = page.add_rect_annot(r * d)
        a.set_colors(stroke=col)
        a.set_border(width=lw * (1.8 if f.severity == "error" else 1.0), dashes=[] if f.severity == "error" else [4, 3])
        a.set_info(title="CAD-QM", content=info)
        a.set_oc(ocg); a.update()
        w = fs * (len(f.id) * 0.62 + 1.0)
        # Label je Typ an anderer Ecke: Ü oben links, R unten links, K unten rechts
        if f.type == CONSISTENCY:
            lab = pymupdf.Rect(r.x1 - w, r.y1, r.x1, r.y1 + fs * 1.7)
        elif f.type == SPELLING:
            lab = pymupdf.Rect(r.x0, r.y1, r.x0 + w, r.y1 + fs * 1.7)
        else:
            lab = pymupdf.Rect(r.x0, r.y0 - fs * 1.7, r.x0 + w, r.y0)
        if lab.y0 < 0:
            lab.y0, lab.y1 = r.y1, r.y1 + fs * 1.7
        if lab.y1 > page.rect.height:
            lab.y0, lab.y1 = r.y0 - fs * 1.7, r.y0
        t = page.add_freetext_annot(lab * d, f.id, fontsize=fs, fontname="helv", text_color=(0, 0, 0),
                                    fill_color=col, rotate=page.rotation, align=pymupdf.TEXT_ALIGN_CENTER)
        t.set_info(title="CAD-QM")                                # Inhalt = nur Index (sichtbarer Text)
        t.set_opacity(0.85); t.set_oc(ocg); t.update()


def add_summary(doc: pymupdf.Document, findings: list[Finding], cfg: dict, name: str) -> None:
    colors = cfg["markup"]["colors"]
    W, H, M = 842, 595, 40
    page = doc.new_page(width=W, height=H)
    y = M
    page.insert_text((M, y), f"CAD-QM Prüfbericht – {name}", fontsize=16, fontname="helv"); y += 28
    for t, nm in TYPE_NAME.items():
        n = sum(f.type == t for f in findings); e = sum(f.type == t and f.severity == "error" for f in findings)
        page.draw_rect(pymupdf.Rect(M, y - 9, M + 14, y + 3), color=tuple(colors[t]), fill=tuple(colors[t]))
        page.insert_text((M + 22, y), f"{nm}: {n} Befunde ({e} Fehler, {n - e} Hinweise)", fontsize=10); y += 16
    y += 8
    page.insert_text((M, y), "Index   Seite  Schwere  Wert   Beschreibung / Text", fontsize=9, fontname="hebo"); y += 14
    for f in findings:
        if y > H - M:
            page = doc.new_page(width=W, height=H); y = M
        line = f"{f.id:7s} {f.page + 1:>4d}   {f.severity:7s} {f.value:5.1f}%  {f.detail} – {f.text}"
        page.insert_text((M, y), line[:150], fontsize=8); y += 11
