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


def _run_three(tmp_path, smoothing, smooth_hists):
    paths = []
    for i, (n, pk) in enumerate((("ha", 20), ("hb", 50), ("hc", 80))):
        p = tmp_path / f"{n}.root"
        _write_root(p, n, pk)
        paths.append(str(p))
    cmp = ComparisonConfig(
        output="smooth_sel",
        files=paths,
        hists=["ha", "hb", "hc"],
        labels=["A", "B", "C"],
        smoothing=smoothing,
        smooth_hists=smooth_hists,
        output_directory=str(tmp_path),
    )
    compare_histograms_overlay(cmp, output_dir=str(tmp_path))
    return tmp_path / "smooth_sel.pdf"


def test_smooth_hists_by_index_produces_pdf(tmp_path):
    # Smooth only the 2nd and 3rd histograms (indices 1, 2); 1st draws normally
    out = _run_three(tmp_path, "overlay", [1, 2])
    assert out.exists() and out.stat().st_size > 0


def test_smooth_hists_by_label_produces_pdf(tmp_path):
    out = _run_three(tmp_path, "overlay", ["B", "C"])
    assert out.exists() and out.stat().st_size > 0


def test_smooth_hists_none_smooths_all(tmp_path):
    out = _run_three(tmp_path, "overlay", None)
    assert out.exists() and out.stat().st_size > 0
