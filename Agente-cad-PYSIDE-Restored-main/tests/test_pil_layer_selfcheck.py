from scripts.arete.pil_layer_selfcheck import _short_face_pass_corner_convention


def test_long_face_pass_corner_is_supported_by_colinear_short_face_contact():
    contacts = {("V301", "C", "passa"): object()}
    assert _short_face_pass_corner_convention("A", "passa", "V301", "AC", contacts)
    assert _short_face_pass_corner_convention("B", "passa", "V301", "BC", contacts)


def test_short_face_corner_convention_does_not_justify_wrong_role_or_corner():
    contacts = {("V301", "C", "passa"): object()}
    assert not _short_face_pass_corner_convention("A", "chega", "V301", "AC", contacts)
    assert not _short_face_pass_corner_convention("A", "passa", "V301", "AD", contacts)
    assert not _short_face_pass_corner_convention("C", "passa", "V301", "CA", contacts)
