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


def _layered(tmp_path, ocg_name):
    """Text mit schwarzer Linie darueber; der Text liegt auf einer PDF-Ebene mit dem gegebenen Namen."""
    d = pymupdf.open(); p = d.new_page(width=400, height=300)
    oc = d.add_ocg(ocg_name, on=True)
    p.insert_text((50, 100), "Kabelweg", fontsize=12, color=(0, 0, 0), oc=oc)
    for y in (96, 98):
        p.draw_line((40, y), (130, y), color=(0, 0, 0), width=2)
    f = tmp_path / "l.pdf"; d.save(f)
    return str(f)


def test_xref_text_is_not_checked_but_own_layer_is(tmp_path):
    own = check_pdf(_layered(tmp_path, "0MT_P_TEXT"), checks=("overlap",))
    assert any(f.kind == "text_ink" for f in own)
    xref = check_pdf(_layered(tmp_path, "325_AVI_G1|_TEXT"), checks=("overlap",))          # XREF-Ebene des Architekten
    assert not any(f.kind == "text_ink" for f in xref)


def _two_texts(tmp_path, a, b, offset, sizes=(12, 12)):
    d = pymupdf.open(); p = d.new_page(width=400, height=300)
    p.insert_text((100, 100), a, fontsize=sizes[0], color=(0, 0, 0))
    p.insert_text((100 + offset[0], 100 + offset[1]), b, fontsize=sizes[1], color=(0, 0, 1))
    f = tmp_path / "tt.pdf"; d.save(f)
    return str(f)


def tt(fs):
    return [f for f in fs if f.kind == "text_text"]


def test_tightly_stacked_lines_are_not_text_overlap(tmp_path):
    """Enge Zeilen: Zeilenkaesten ueberlappen, die Buchstaben nicht -> kein Befund."""
    assert tt(check_pdf(_two_texts(tmp_path, "Elektrisch", "rueckstellbar", (0, 11)), checks=("overlap",))) == []


def test_glyphs_on_glyphs_is_text_overlap(tmp_path):
    assert tt(check_pdf(_two_texts(tmp_path, "Kabelweg", "Steckdose", (3, 1)), checks=("overlap",)))


def test_lone_punctuation_and_duplicates_ignored(tmp_path):
    assert tt(check_pdf(_two_texts(tmp_path, "EG. 06", "-", (-2, 0)), checks=("overlap",))) == []
    assert tt(check_pdf(_two_texts(tmp_path, "G", "G", (0, 0)), checks=("overlap",))) == []
