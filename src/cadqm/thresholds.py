"""Schwellwerte nachtraeglich auf Rohbefunde anwenden (ohne neu zu pruefen)."""
from __future__ import annotations
from dataclasses import replace
from .findings import Finding, OVERLAP


def apply_thresholds(findings: list[Finding], o: dict) -> list[Finding]:
    """Ueberlappungsbefunde nach den Schwellen o neu einstufen (zu niedrige entfallen); alle anderen unveraendert."""
    out: list[Finding] = []
    for f in findings:
        if f.type != OVERLAP:
            out.append(f)
            continue
        warn, err = ((o["text_text_warn_pct"], o["text_text_error_pct"]) if f.kind == "text_text"
                     else (o["warn_pct"], o["error_pct"]))
        if f.value >= err:
            out.append(replace(f, severity="error"))
        elif f.value >= warn:
            out.append(replace(f, severity="warn"))
    return out


def below_threshold(findings: list[Finding], o: dict) -> list[Finding]:
    """Ueberlappungs-Rohbefunde, die unter den Schwellen liegen (werden nicht angezeigt) - fuer das Feedback."""
    out = []
    for f in findings:
        if f.type == OVERLAP:
            warn = o["text_text_warn_pct"] if f.kind == "text_text" else o["warn_pct"]
            if f.value < warn:
                out.append(f)
    return out
