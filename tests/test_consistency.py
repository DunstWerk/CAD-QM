from pathlib import Path

import pymupdf
import pytest
from cadqm.config import load_config
from cadqm.runner import check_set_files


def make_plan(tmp_path, name, *, plannr=None, index="A", stand="18.12.2025", projekt="Erneuerung Technik",
              rows=("a",), body=(), koten=(), legend=("Legende Medientechnik", "Mischpult", "Lautsprecher")):
    d = pymupdf.open(); p = d.new_page(width=1000, height=700)
    x = 760
    for k, t in enumerate(legend):
        p.insert_text((x, 40 + 14 * k), t, fontsize=7)
    for lab, val, y in [("Plannummer:", plannr or name, 400), ("Index:", index, 440), ("Projekt:", projekt, 480), ("Stand:", stand, 520)]:
        p.insert_text((x, y), lab, fontsize=8); p.insert_text((x, y + 18), val, fontsize=15)
    p.insert_text((x, 560), "Index:", fontsize=8)
    for k, r in enumerate(rows):
        p.insert_text((x, 580 + 12 * k), r, fontsize=8); p.insert_text((x + 14, 580 + 12 * k), f"Abgabe {r}", fontsize=10)
    for k, t in enumerate(body):
        p.insert_text((60, 100 + 25 * k), t, fontsize=10)
    for k, t in enumerate(koten):
        p.insert_text((400, 100 + 25 * k), t, fontsize=10)
    f = tmp_path / f"{name}.pdf"; d.save(f)
    return str(f)


def kinds(res):
    return {(Path(k).stem, f.kind) for k, fs in res.items() for f in fs if f.type == "consistency"}      # plattformunabhaengig (Windows: \\)


def run(files):
    return check_set_files(files, load_config(), checks=("consistency",))


def test_clean_set_has_no_findings(tmp_path):
    fs = [make_plan(tmp_path, n) for n in ("MT_EG", "MT_KG", "MT_DG")]
    assert kinds(run(fs)) == set()


def test_plannummer_vs_filename(tmp_path):
    fs = [make_plan(tmp_path, "MT_EG", plannr="MT_KG"), make_plan(tmp_path, "MT_KG")]
    assert ("MT_EG", "plannummer_filename") in kinds(run(fs))


def test_index_vs_table(tmp_path):
    fs = [make_plan(tmp_path, "MT_EG", index="B", rows=("a",)), make_plan(tmp_path, "MT_KG", index="B", rows=("a", "b"))]
    assert kinds(run(fs)) == {("MT_EG", "index_table")}


def test_set_field_majority(tmp_path):
    fs = [make_plan(tmp_path, "MT_EG", stand="01.01.2025"), make_plan(tmp_path, "MT_KG"), make_plan(tmp_path, "MT_DG")]
    res = run(fs)
    assert kinds(res) == {("MT_EG", "set_field")}
    assert [f for f in next(iter(res.values())) if f.kind == "set_field"][0].severity == "error"


def test_variants_across_set(tmp_path):
    fs = [make_plan(tmp_path, "MT_EG", body=["Inspizientenpult", "Inspizientenpult"]),
          make_plan(tmp_path, "MT_KG", body=["Inspizientenpult"]),
          make_plan(tmp_path, "MT_DG", body=["Inspizienten-Pult"])]
    assert kinds(run(fs)) == {("MT_DG", "variant")}


def test_kote_format_minority(tmp_path):
    good = [f"+ {i}.{i:02d}" for i in range(1, 13)]
    fs = [make_plan(tmp_path, "MT_EG", koten=good), make_plan(tmp_path, "MT_KG", koten=good), make_plan(tmp_path, "MT_DG", koten=["+ 1,50", "+ 2.00"])]
    assert ("MT_DG", "kote_format") in kinds(run(fs))


def test_legend_deviation(tmp_path):
    fs = [make_plan(tmp_path, n) for n in ("MT_EG", "MT_KG")] + [make_plan(tmp_path, "MT_DG", legend=("Legende Medientechnik", "Mischpult"))]
    assert ("MT_DG", "legend") in kinds(run(fs))
