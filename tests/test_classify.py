from cadqm.classify import Classifier, OURS, ARCH, IGNORE
from cadqm.config import load_config


def test_color_classes():
    c = Classifier(load_config())
    assert c.color_class((0, 0, 0)) == OURS
    assert c.color_class((0.0, 0.52, 0.0)) == OURS      # Gewerkefarbe Gruen
    assert c.color_class((0.502, 0.502, 0.502)) == ARCH  # Architekt Grau
    assert c.color_class((0.89, 0.89, 0.89)) == ARCH
    assert c.color_class((1, 1, 1)) == IGNORE
