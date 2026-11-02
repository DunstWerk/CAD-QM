import pymupdf
from cadqm.config import load_config
from cadqm.runner import check_pdf


def _pdf(tmp_path, texts, rot=0, y0=60):
    d = pymupdf.open(); p = d.new_page(width=600, height=400)
    y = y0
    for t, col in texts:
        p.insert_text((50, y), t, fontsize=12, color=col); y += 30
    if rot:
        p.set_rotation(rot)
    f = tmp_path / "s.pdf"; d.save(f)
    return str(f)


def words(fs):
    return {f.text for f in fs if f.type == "spelling"}


def test_typo_found_correct_and_compound_ok(tmp_path):
    f = _pdf(tmp_path, [("Requsite Kabelweg Mischpult Erdgeschoss", (0, 0, 0))])
    fs = check_pdf(f, checks=("spelling",))
    assert words(fs) == {"Requsite"} and fs[0].severity == "error" and "Requisite" in fs[0].extra["suggestions"]


def test_allcaps_and_abbreviations(tmp_path):
    f = _pdf(tmp_path, [("ERDGESCHOSS LZ MK BT 2x54W CAM-A-01", (0, 0, 0))])
    assert words(check_pdf(f, checks=("spelling",))) == set()


def test_whitelist_and_architect_gray(tmp_path):
    f = _pdf(tmp_path, [("Inspizientenpult", (0, 0, 0)), ("Xyzzyqwert", (0.76, 0.76, 0.76))])
    assert words(check_pdf(f, checks=("spelling",))) == {"Inspizientenpult"}      # grauer Architektentext wird nicht geprueft
    wl = tmp_path / "wl.txt"; wl.write_text("inspizientenpult\n")
    assert words(check_pdf(f, checks=("spelling",), whitelist_files=[str(wl)])) == set()


def test_token_bbox_rotated(tmp_path):
    for rot in (0, 90, 270):
        f = _pdf(tmp_path, [("Kabelweg Requsite", (0, 0, 0))], rot, y0=200)
        (hit,) = [x for x in check_pdf(f, checks=("spelling",))]
        ref = pymupdf.Rect(pymupdf.open(f)[0].search_for("Requsite")[0]) * pymupdf.open(f)[0].rotation_matrix; ref.normalize()
        c = pymupdf.Rect(hit.bbox)
        assert abs((c.x0 + c.x1) / 2 - (ref.x0 + ref.x1) / 2) < 12 and abs((c.y0 + c.y1) / 2 - (ref.y0 + ref.y1) / 2) < 12
