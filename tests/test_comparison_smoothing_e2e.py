# tests/test_comparison_smoothing_e2e.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ROOT
ROOT.gROOT.SetBatch(True)

from config import ComparisonConfig
from comparison import compare_histograms_overlay


def _write_root(path, name, peak_bin):
    f = ROOT.TFile(str(path), "RECREATE")
    h = ROOT.TH1D(name, name, 100, 0.0, 100.0)
    for b in range(1, 101):
        # smooth-ish bump so log-space smoothing has positive bins
        val = 100.0 * (2.71828 ** (-((b - peak_bin) ** 2) / 200.0))
        if val > 1e-6:
            h.SetBinContent(b, val)
    h.Write()
    f.Close()


def _run(tmp_path, mode):
    f1 = tmp_path / "a.root"
    f2 = tmp_path / "b.root"
    _write_root(f1, "ha", 30)
    _write_root(f2, "hb", 60)
    cmp = ComparisonConfig(
        output=f"smooth_{mode}",
        files=[str(f1), str(f2)],
        hists=["ha", "hb"],
        labels=["A", "B"],
        smoothing=mode,
        output_directory=str(tmp_path),
    )
    compare_histograms_overlay(cmp, output_dir=str(tmp_path))
    return tmp_path / f"smooth_{mode}.pdf"


def test_overlay_mode_produces_pdf(tmp_path):
    out = _run(tmp_path, "overlay")
    assert out.exists() and out.stat().st_size > 0


def test_replace_mode_produces_pdf(tmp_path):
    out = _run(tmp_path, "replace")
    assert out.exists() and out.stat().st_size > 0


def test_off_mode_produces_pdf(tmp_path):
    out = _run(tmp_path, "off")
    assert out.exists() and out.stat().st_size > 0
