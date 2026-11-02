import pymupdf
import pytest
from cadqm.pdfio.text import extract_text


def _page(rotate=0):
    d = pymupdf.open(); p = d.new_page(width=600, height=400)
    p.insert_text((50, 100), "Rang", fontsize=12)
    p.insert_text((50, 100), "Rang", fontsize=12)       # Duplikat
    p.insert_text((900, 100), "Aussen", fontsize=12)     # ausserhalb
    if rotate:
        p.set_rotation(rotate)
    return p


def test_dedup_and_offpage():
    assert [i.text for i in extract_text(_page())] == ["Rang"]


@pytest.mark.parametrize("rot", [0, 90, 180, 270])
def test_rotated_page_text_position_exact(rot):
    """Textbox muss im SICHTBAREN Raum an der gedrehten Position liegen (nicht im unrotierten)."""
    p = _page(rot)
    (item,) = extract_text(p)
    q = pymupdf.Point(50, 100) * p.rotation_matrix       # Baseline-Ursprung sichtbar
    x0, y0, x1, y1 = item.bbox
    assert x0 - 2 <= q.x <= x1 + 2 and y0 - 2 <= q.y <= y1 + 2
    ref = p.search_for("Rang")[0] * p.rotation_matrix       # search_for liefert unrotierte Koordinaten
    ref.normalize()
    assert item.bbox == pytest.approx(tuple(ref), abs=4)
