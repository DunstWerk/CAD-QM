import pymupdf
import pytest
from cadqm.cluster import cluster
from cadqm.config import load_config
from cadqm.findings import Finding, OVERLAP
from cadqm.report.listing import write_xlsx
from cadqm.report.markup import add_markup, add_summary


def _doc(rot):
    d = pymupdf.open(); p = d.new_page(width=600, height=400)
    p.insert_text((100, 200), "Kabelweg", fontsize=12)
    p.set_rotation(rot)
    return d


def test_cluster_merges_neighbours_and_numbers():
    fs = [Finding(OVERLAP, 0, (0, 0, 10, 10), "warn", 12, "a"), Finding(OVERLAP, 0, (12, 0, 20, 10), "error", 40, "b"),
          Finding(OVERLAP, 0, (300, 300, 310, 310), "warn", 11, "c")]
    out = cluster(fs)
    assert [f.id for f in out] == ["Ü-001", "Ü-002"] and out[0].severity == "error" and out[0].bbox == (0, 0, 20, 10)


@pytest.mark.parametrize("rot", [0, 90, 180, 270])
def test_markup_lands_on_finding_location(rot):
    d = _doc(rot); p = d[0]
    text = pymupdf.Rect(p.search_for("Kabelweg")[0]) * p.rotation_matrix; text.normalize()
    f = cluster([Finding(OVERLAP, 0, tuple(text), "error", 50, "Kabelweg", "test")])
    add_markup(d, f, load_config())
    pm = p.get_pixmap(dpi=72)
    orange = []
    for y in range(pm.height):
        for x in range(pm.width):
            r, g, b = pm.pixel(x, y)
            if r > 230 and 100 < g < 190 and b < 60:
                orange.append((x, y))
    assert orange, "keine Markierung sichtbar"
    near = pymupdf.Rect(text) + (-40, -40, 40, 40)
    assert sum(near.contains(pymupdf.Point(x, y)) for x, y in orange) / len(orange) > 0.95


def test_summary_and_xlsx(tmp_path):
    d = _doc(0)
    f = cluster([Finding(OVERLAP, 0, (100, 190, 150, 205), "warn", 12, "x", "test")])
    add_markup(d, f, load_config()); add_summary(d, f, load_config(), "t")
    assert d.page_count == 2
    write_xlsx([("plan", f[0])], str(tmp_path / "a.xlsx"))
    assert (tmp_path / "a.xlsx").stat().st_size > 0
