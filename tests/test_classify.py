from cadqm.classify import Classifier, DARK, LIGHT, NONE
from cadqm.config import load_config
from cadqm.pdfio.text import TextItem


def _t(color, layer=""):
    return TextItem("x", (0, 0, 1, 1), color, 8, (1, 0), "truetype", layer)


def test_ink_classes():
    c = Classifier(load_config())
    assert c.ink_class((0, 0, 0)) == DARK
    assert c.ink_class((0.0, 0.52, 0.0)) == DARK        # Gewerkefarbe Gruen
    assert c.ink_class((0.0, 0.0, 1.0)) == DARK          # Blau
    assert c.ink_class((0.0, 0.75, 1.0)) == DARK         # Cyan
    assert c.ink_class((0.53, 0.6, 0.65)) == LIGHT       # Architekt Blaugrau (DTG)
    assert c.ink_class((0.76, 0.76, 0.76)) == LIGHT      # Architekt Hellgrau
    assert c.ink_class((0.89, 0.89, 0.89)) == NONE       # Flaeche
    assert c.ink_class((1, 1, 1)) == NONE
    assert c.ink_weight((0.76, 0.76, 0.76)) < c.ink_weight((0.5, 0.5, 0.5)) < 1.0


def test_architect_text():
    c = Classifier(load_config())
    assert c.is_architect_text(_t((0, 0, 0), "325_AVI_G1_02|_TEXT"))     # XREF-Ebene
    assert c.is_architect_text(_t((0.76, 0.76, 0.76)))                   # #c2c2c2
    assert not c.is_architect_text(_t((0, 0, 0), "Text"))                # eigene Ebene
    assert not c.is_architect_text(_t((0, 0, 1)))                        # ohne Ebene (KOB/UE), Gewerkefarbe
