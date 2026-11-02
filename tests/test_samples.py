"""Smoke-Test ueber die echten Beispielplaene (liegen nicht im Git; ohne Dateien wird uebersprungen)."""
import glob
import pymupdf
import pytest
from cadqm.classify import Classifier
from cadqm.config import load_config
from cadqm.pdfio.text import extract_text

FILES = sorted(glob.glob("tests/data/*.pdf"))


@pytest.mark.skipif(not FILES, reason="keine Beispielplaene")
@pytest.mark.parametrize("f", FILES)
def test_sample_plan(f):
    page = pymupdf.open(f)[0]
    items = extract_text(page)
    r = page.rect
    assert len(items) > 100
    # Mittelpunkt im Blatt (am Rand abgeschnittene Texte ragen teils minimal hinaus)
    assert all(r.x0 <= (i.bbox[0] + i.bbox[2]) / 2 <= r.x1 and r.y0 <= (i.bbox[1] + i.bbox[3]) / 2 <= r.y1 for i in items)
    zone = Classifier(load_config()).title_block_rect(page, items)
    assert 0.7 * r.width < zone[0] < 0.95 * r.width
