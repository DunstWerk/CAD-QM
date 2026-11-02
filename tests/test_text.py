import pymupdf
from cadqm.pdfio.text import extract_text


def _pdf(rotate=0):
    d = pymupdf.open(); p = d.new_page(width=600, height=400)
    p.insert_text((50, 100), "Rang", fontsize=12)
    p.insert_text((50, 100), "Rang", fontsize=12)       # Duplikat
    p.insert_text((900, 100), "Aussen", fontsize=12)     # ausserhalb
    if rotate: p.set_rotation(rotate)
    return p


def test_dedup_and_offpage():
    items = extract_text(_pdf())
    assert [i.text for i in items] == ["Rang"]


def test_rotated_page_coords_inside_visible_rect():
    p = _pdf(270)
    items = extract_text(p)
    assert items and all(0 <= i.bbox[0] < p.rect.x1 and 0 <= i.bbox[1] < p.rect.y1 for i in items)
