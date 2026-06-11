# tests/test_smoothing.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ROOT
ROOT.gROOT.SetBatch(True)
from comparison import _smooth_hist_logspace, _build_smoothed_clone


def _make_hist(name="h"):
    # 100 bins over [0, 100], constant value 100 in ROOT bins 11..21 (0-based y idx 10..20)
    h = ROOT.TH1D(name, name, 100, 0.0, 100.0)
    for b in range(11, 22):
        h.SetBinContent(b, 100.0)
    return h


def test_constant_region_geometric_mean():
    h = _make_hist("h_const")
    ysm = _smooth_hist_logspace(h, sigma=2, x_max=None)
    assert len(ysm) == 100
    # center of constant block -> geometric mean of a constant is the constant
    assert abs(ysm[15] - 100.0) < 1.0


def test_clip_to_filled_range():
    h = _make_hist("h_clip")
    ysm = _smooth_hist_logspace(h, sigma=2, x_max=None)
    # before first filled bin (idx 10) and after last filled bin (idx 20) -> zero
    assert ysm[5] == 0.0
    assert ysm[25] == 0.0


def test_x_max_cutoff():
    h = _make_hist("h_xmax")
    # x_max=15.5 -> FindBin=16 -> hi = min(20, 15) = 15 ; bins > 15 zeroed
    ysm = _smooth_hist_logspace(h, sigma=2, x_max=15.5)
    assert ysm[15] != 0.0
    assert ysm[18] == 0.0


def test_empty_hist_returns_zeros():
    h = ROOT.TH1D("h_empty", "h_empty", 100, 0.0, 100.0)
    ysm = _smooth_hist_logspace(h, sigma=2, x_max=None)
    assert len(ysm) == 100
    assert float(ysm.sum()) == 0.0


def test_build_smoothed_clone_copies_contents():
    import numpy as np
    h = _make_hist("h_src")
    ysm = np.zeros(100)
    ysm[15] = 42.0
    hs = _build_smoothed_clone(h, ysm)
    assert hs.GetName() == "h_src_smooth"
    assert hs.GetBinContent(16) == 42.0  # ROOT bin 16 == y index 15
    assert hs.GetBinContent(11) == 0.0
