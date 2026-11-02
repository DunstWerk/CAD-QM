import json
import pymupdf
from cadqm.findings import Finding, OVERLAP, SPELLING
from cadqm.report.feedback import write_feedback


def test_feedback_files(tmp_path):
    d = pymupdf.open(); p = d.new_page(width=400, height=300); p.insert_text((50, 100), "Kabelweg", fontsize=12)
    pdf = tmp_path / "plan1.pdf"; d.save(pdf)
    f1 = Finding(OVERLAP, 0, (50, 90, 100, 104), "error", 42.0, "Kabelweg", "Text verdeckt", "text_ink", id="Ü-001", extra={"covered_pct": 40.0, "members": [{"kind": "text_ink", "value": 42.0, "text": "Kabelweg"}]})
    f2 = Finding(SPELLING, 0, (50, 90, 100, 104), "warn", 0.0, "Kabelweg", "Unbekannt", "unknown", id="R-001")
    f3 = Finding(OVERLAP, 0, (10, 10, 20, 20), "warn", 5.0, "x", "d", "text_ink", id="Ü-002")
    out = write_feedback(tmp_path / "out", [(str(pdf), f1, "accepted"), (str(pdf), f2, "false"), (str(pdf), f3, None)],
                         {"settings": {"Hinweis ab": "10 %"}, "plans": [{"name": "plan1", "size": "400x300", "rotation": 0, "producer": "t", "texts": 1}]},
                         [(str(pdf), f3)], {OVERLAP: (1, .5, 0), SPELLING: (0, .7, .8)})
    assert out.parent.name == "ml_feedback"
    md = (out / "feedback.md").read_text(encoding="utf-8")
    assert "angenommen" in md and "Fehlalarm" in md and "Ü-001" in md and "covered_pct" in md and "Hinweis ab" in md
    js = json.loads((out / "feedback.json").read_text(encoding="utf-8"))
    assert [x["verdict"] for x in js["findings"]] == ["angenommen", "Fehlalarm", "offen"]
    assert (out / "crops" / "plan1_U-001.png").exists() and not any("U-002" in c.name for c in (out / "crops").iterdir())   # offene: kein Bild
    assert js["findings"][0]["features"]["covered_pct"] == 40.0 and len(js["hidden_below_threshold"]) == 1
