# tests/test_config_smoothing.py

from src.config import ComparisonConfig


def test_smoothing_defaults():
    cmp = ComparisonConfig(output="x")
    assert cmp.smoothing == "off"
    assert cmp.smoothing_sigma == 10
    assert cmp.smooth_x_max is None
    assert cmp.raw_alpha == 0.25
    assert cmp.smooth_line_width is None


def test_smoothing_overrides():
    cmp = ComparisonConfig(
        output="x",
        smoothing="overlay",
        smoothing_sigma=5,
        smooth_x_max=2.5,
        raw_alpha=0.4,
        smooth_line_width=3,
    )
    assert cmp.smoothing == "overlay"
    assert cmp.smoothing_sigma == 5
    assert cmp.smooth_x_max == 2.5
    assert cmp.raw_alpha == 0.4
    assert cmp.smooth_line_width == 3
