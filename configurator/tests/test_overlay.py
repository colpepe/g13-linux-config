from g13config import model
from g13config.overlay import IMAGE_SIZE, G13OverlayWidget


def test_every_rect_name_has_a_property_index():
    for name in G13OverlayWidget.KEY_RECTS:
        assert name in model.PHYS_TO_INDEX, f"{name} has no property index"


def test_m_row_rects_exist_and_are_inside_the_photo():
    w, h = IMAGE_SIZE
    for name in ("M1", "M2", "M3", "MR"):
        rect = G13OverlayWidget.KEY_RECTS[name]
        assert rect.left() >= 0 and rect.top() >= 0
        assert rect.right() <= w and rect.bottom() <= h


def test_m_row_rects_do_not_overlap_each_other_or_g1():
    names = ["M1", "M2", "M3", "MR", "G1"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ra, rb = G13OverlayWidget.KEY_RECTS[a], G13OverlayWidget.KEY_RECTS[b]
            assert not ra.intersects(rb), f"{a} overlaps {b}"
