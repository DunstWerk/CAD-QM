from __future__ import annotations
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from ..findings import Finding
from .markup import TYPE_NAME


def write_xlsx(rows: list[tuple[str, Finding]], path: str) -> None:
    """rows = (Planname, Befund)."""
    wb = Workbook(); ws = wb.active; ws.title = "Befunde"
    head = ["Plan", "Index", "Typ", "Seite", "Schwere", "Wert %", "Art", "Text", "Beschreibung", "x (pt)", "y (pt)", "Status", "Bemerkung"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="333333")
    for plan, f in rows:
        ws.append([plan, f.id, TYPE_NAME[f.type], f.page + 1, "Fehler" if f.severity == "error" else "Hinweis", f.value,
                   f.kind, f.text, f.detail, round(f.bbox[0]), round(f.bbox[1]), "offen", ""])
    for col, w in zip("ABCDEFGHIJKLM", [28, 8, 16, 6, 9, 8, 16, 50, 45, 8, 8, 10, 30]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    wb.save(path)
