import pymupdf
import pytest
from cadqm.config import load_config
from cadqm.runner import check_pdf


def _make(tmp_path, draw, rotate=0):
    d = pymupdf.open(); p = d.new_page(width=400, height=300)
    draw(p)
    if rotate:
        p.set_rotation(rotate)
    f = tmp_path / "t.pdf"; d.save(f)
    return str(f)


def _text(p):
    p.insert_text((50, 100), "Kabelweg", fontsize=12, color=(0, 0, 0))


def kinds(fs):
    return {(f.kind, f.severity) for f in fs}


def test_clean_text_has_no_findings(tmp_path):
    assert check_pdf(_make(tmp_path, _text)) == []


@pytest.mark.parametrize("rot", [0, 90, 270])
def test_black_line_through_black_text(tmp_path, rot):
    def draw(p):
        _text(p)
        for y in (96, 98):                                     # dicke schwarze Linien quer durch den Text
            p.draw_line((40, y), (130, y), color=(0, 0, 0), width=2)
    fs = check_pdf(_make(tmp_path, draw, rot))
    assert any(f.kind == "text_ink" and f.value >= 10 for f in fs)


def test_filled_symbol_covers_text(tmp_path):
    def draw(p):
        _text(p)
        p.draw_rect(pymupdf.Rect(60, 88, 100, 104), color=(0, 0, 1), fill=(0.6, 0.6, 1))
    fs = check_pdf(_make(tmp_path, draw))
    assert any(f.kind == "text_ink" and f.severity == "error" for f in fs)


def test_text_text_overlap(tmp_path):
    def draw(p):
        _text(p)
        p.insert_text((55, 102), "Steckdose", fontsize=12, color=(0, 0, 1))
    assert any(f.kind == "text_text" and f.severity == "error" for f in check_pdf(_make(tmp_path, draw)))


def test_original_unchanged(tmp_path):
    import hashlib
    path = _make(tmp_path, _text)
    h = hashlib.md5(open(path, "rb").read()).hexdigest()
    check_pdf(path)
    assert hashlib.md5(open(path, "rb").read()).hexdigest() == h
