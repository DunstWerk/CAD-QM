"""Bewertungs-Feedback (fuer Kalibrierung/ML): MD + JSON + Bildausschnitte je Export in <ausgabe>/ml_feedback/<zeitstempel>/."""
from __future__ import annotations
import collections
import datetime as dt
import json
import os
from pathlib import Path
import cv2
import numpy as np
import pymupdf
from .. import __version__
from ..findings import Finding
from .markup import TYPE_NAME

VERDICT_NAME = {"accepted": "angenommen", "false": "Fehlalarm", None: "offen"}


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o


def crop_png(path: str, page_no: int, bbox, color, out: Path, width_px: int = 520) -> None:
    page = pymupdf.open(path)[page_no]
    b = pymupdf.Rect(bbox)
    pad = max(50.0, 3.0 * max(b.width, b.height))
    clip = (b + (-pad * 1.6, -pad, pad * 1.6, pad)) & page.rect
    zoom = min(8.0, width_px / max(clip.width, 1.0))
    pm = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, colorspace=pymupdf.csRGB, alpha=False, annots=False)
    img = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width, 3)[..., ::-1].copy()
    x0, y0 = int((b.x0 - clip.x0) * zoom), int((b.y0 - clip.y0) * zoom)
    cv2.rectangle(img, (x0 - 3, y0 - 3), (int((b.x1 - clip.x0) * zoom) + 3, int((b.y1 - clip.y0) * zoom) + 3),
                  tuple(int(c * 255) for c in color[::-1]), 2)
    cv2.imwrite(str(out), img)


def _finding_dict(plan: str, path: str, f: Finding, verdict: str | None) -> dict:
    return _jsonable({"id": f"{plan}:{f.id}", "plan": plan, "file": os.path.basename(path), "page": f.page + 1, "type": f.type, "kind": f.kind,
                      "severity": f.severity, "value": f.value, "text": f.text, "detail": f.detail, "bbox_pt": [round(v, 1) for v in f.bbox],
                      "verdict": VERDICT_NAME[verdict], "features": f.extra})


def write_feedback(out_root: str | Path, rows: list[tuple[str, Finding, str | None]], context: dict, hidden: list[tuple[str, Finding]],
                   colors: dict, crops: bool = True) -> Path:
    """rows = (pdf-Pfad, Befund, Urteil 'accepted'|'false'|None). context: Einstellungen/Plaene. hidden: Befunde unter der Schwelle."""
    now = dt.datetime.now()
    d = Path(out_root) / "ml_feedback" / now.strftime("%Y%m%d-%H%M%S")
    (d / "crops").mkdir(parents=True, exist_ok=True)
    data = [_finding_dict(Path(p).stem, p, f, v) for p, f, v in rows]
    if crops:
        for (p, f, v), rec in zip(rows, data):
            if v is None:
                continue                                                # Bildausschnitte nur fuer bewertete Befunde
            name = f"{Path(p).stem}_{f.id}.png".replace(" ", "_").translate(str.maketrans({"Ü": "U", "Ä": "A", "Ö": "O", "ü": "ue", "ä": "ae", "ö": "oe", "ß": "ss"}))   # ASCII-sicher
            try:
                crop_png(p, f.page, f.bbox, colors[f.type], d / "crops" / name)
                rec["crop"] = f"crops/{name}"
            except Exception as e:                                     # noqa: BLE001
                rec["crop_error"] = str(e)
    hid = [_jsonable({"plan": Path(p).stem, "page": f.page + 1, "type": f.type, "kind": f.kind, "value": f.value, "text": f.text,
                      "bbox_pt": [round(v, 1) for v in f.bbox]}) for p, f in hidden]
    (d / "feedback.json").write_text(json.dumps({"version": __version__, "created": now.isoformat(timespec="seconds"), "context": _jsonable(context),
                                                 "findings": data, "hidden_below_threshold": hid}, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "feedback.md").write_text(_markdown(now, data, hid, context), encoding="utf-8")
    return d


def _markdown(now, data, hid, ctx) -> str:
    L: list[str] = []
    rated = [r for r in data if r["verdict"] != "offen"]
    L += [f"# CAD-QM Bewertungs-Feedback", "",
          f"Erstellt: {now:%Y-%m-%d %H:%M:%S} · CAD-QM {__version__} · {len(data)} Befunde, davon {len(rated)} bewertet", "",
          "> **Zweck:** Diese Datei dient der Kalibrierung der Prüfung (Schwellwerte, Regeln, Filter). "
          "`feedback.json` enthält dieselben Daten maschinenlesbar inkl. aller Messwerte (`features`), `crops/` die Bildausschnitte der bewerteten Befunde.",
          "> **Wert:** bei `text_ink` der Anteil unlesbarer/verdeckter Textpixel in %, bei `text_text` die Boxüberlappung in %; bei zusammengefassten Befunden "
          "(Art `a+b`) der höchste Einzelwert – die Einzelwerte stehen unter „Zusammengefasst“ bzw. in `features.members`. Konsolidität/Rechtschreibung haben keinen Wert (0).",
          "> **Bewertung:** *angenommen* = echter Fehler, *Fehlalarm* = kein Fehler, *offen* = nicht bewertet (nicht als „richtig“ werten).", "",
          "## Einstellungen beim Export", ""]
    for k, v in ctx.get("settings", {}).items():
        L.append(f"- **{k}:** {v}")
    L += ["", "## Pläne", "", "| Plan | Format (pt) | Rot. | Erzeuger | Texte | Befunde | angenommen | Fehlalarm | offen |", "|---|---|---|---|---|---|---|---|---|"]
    for p in ctx.get("plans", []):
        rs = [r for r in data if r["plan"] == p["name"]]
        c = collections.Counter(r["verdict"] for r in rs)
        L.append(f"| {p['name']} | {p['size']} | {p['rotation']} | {p['producer']} | {p['texts']} | {len(rs)} | {c['angenommen']} | {c['Fehlalarm']} | {c['offen']} |")
    L += ["", "## Trefferquote je Art (nur bewertete Befunde)", "", "| Typ | Art | angenommen | Fehlalarm | Anteil Fehlalarm | Wert angenommen (min–max) | Wert Fehlalarm (min–max) |", "|---|---|---|---|---|---|---|"]
    grp = collections.defaultdict(list)
    for r in rated:
        grp[(r["type"], r["kind"])].append(r)
    def rng(rs):
        v = [r["value"] for r in rs]
        return f"{min(v):g}–{max(v):g}" if v else "–"
    for (t, k), rs in sorted(grp.items()):
        a = [r for r in rs if r["verdict"] == "angenommen"]; fa = [r for r in rs if r["verdict"] == "Fehlalarm"]
        L.append(f"| {TYPE_NAME[t]} | {k} | {len(a)} | {len(fa)} | {100 * len(fa) / len(rs):.0f} % | {rng(a)} | {rng(fa)} |")
    if not grp:
        L.append("| – | – | – | – | – | – | – |")
    L += ["", "## Alle Befunde", "", "| ID | Typ | Art | Schwere | Wert | Bewertung | Text | Beschreibung |", "|---|---|---|---|---|---|---|---|"]
    for r in data:
        t = r["text"].replace("|", "\\|")[:60]; dsc = r["detail"].replace("|", "\\|")[:90]
        L.append(f"| {r['id']} | {TYPE_NAME[r['type']]} | {r['kind']} | {r['severity']} | {r['value']:g} | {r['verdict']} | {t} | {dsc} |")
    L += ["", "## Details der bewerteten Befunde", ""]
    for r in rated:
        L += [f"### {r['id']} – {r['verdict']}", "", f"- Typ/Art: {TYPE_NAME[r['type']]} / {r['kind']} · Schwere: {r['severity']} · Wert: {r['value']:g} %",
              f"- Seite {r['page']}, Position (pt, sichtbarer Raum): {r['bbox_pt']}", f"- Text: `{r['text']}`", f"- Beschreibung: {r['detail']}"]
        feats = {k: v for k, v in r["features"].items() if k != "members"}
        if feats:
            L.append(f"- Messwerte: `{json.dumps(feats, ensure_ascii=False)}`")
        mem = r["features"].get("members", [])
        if len(mem) > 1:
            L.append(f"- Zusammengefasst aus {len(mem)} Einzelbefunden: " + "; ".join(f"{m['kind']} {m['value']:g} `{m['text'][:30]}`" for m in mem[:8]))
        if "crop" in r:
            L.append(f"- Bild: ![{r['id']}]({r['crop']})")
        L.append("")
    wa = ctx.get("whitelist_actions", [])
    L += ["## In die Whitelist übernommene Wörter (als korrekt gewertet)", "",
          "Diese Wörter wurden in der Sitzung per Bewertung/Button in die Whitelist aufgenommen. Die zugehörigen Befunde sind aus der Liste verschwunden, "
          "gelten also als **Fehlalarm der Rechtschreibprüfung** (Fachwort/Eigenname), sofern nicht anders vermerkt.", ""]
    if wa:
        L += ["| Wort | Plan | Ebene | Kontext | ausgelöst durch |", "|---|---|---|---|---|"]
        L += [f"| {w['word']} | {w['plan']} | {str(w.get('layer', ''))[-24:]} | {str(w.get('context', ''))[:50].replace('|', '/')} | {w['clicked']} |" for w in wa]
    else:
        L.append("(keine)")
    L += ["", "## Unterhalb der Schwelle (nicht angezeigt)", "",
          f"{len(hid)} Rohbefunde lagen unter den eingestellten Schwellwerten und wurden nicht angezeigt (Liste in `feedback.json` → `hidden_below_threshold`). "
          "Sie sind **nicht bewertet** – wichtig, wenn Schwellen zu hoch gewählt waren.", ""]
    c = collections.Counter(h["kind"] for h in hid)
    for k, n in c.most_common():
        L.append(f"- {k}: {n}")
    return "\n".join(L) + "\n"
