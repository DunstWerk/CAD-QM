from __future__ import annotations
from dataclasses import dataclass, field

OVERLAP, SPELLING, CONSISTENCY = "overlap", "spelling", "consistency"


@dataclass
class Finding:
    type: str                                  # overlap | spelling | consistency
    page: int
    bbox: tuple[float, float, float, float]    # sichtbarer Raum (pt)
    severity: str                              # warn | error
    value: float = 0.0                         # z. B. Ueberdeckung in %
    text: str = ""
    detail: str = ""
    kind: str = ""                             # z. B. text_ink | text_text
    id: str = ""
    extra: dict = field(default_factory=dict)
