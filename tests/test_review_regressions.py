"""Regressions found by the full repository review."""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import pytest
import ROOT

from src import analysis
from src.comparison import compare_histograms_overlay
from src.config import ComparisonConfig
from src.export_histograms import Exporter
from src.simulation_summary import SimulationSummary

ROOT.gROOT.SetBatch(True)


def test_shared_prerequisite_is_not_a_cycle(tmp_path, monkeypatch):
    for name, requirements in [('a', ['b.json', 'c.json']), ('b', ['d.json']), ('c', ['d.json']), ('d', [])]:
        (tmp_path / f'{name}.json').write_text(json.dumps({'requirements': requirements}))
    class NoOpAnalysis:
        def __init__(self, *args, **kwargs):
            pass
        def process_all_configs(self):
            pass
    monkeypatch.setattr(analysis, 'Analysis', NoOpAnalysis)
    args = argparse.Namespace(input_dir=None, output_dir=None, save_pdf=False, save_hstat=False)
    stack = set()
    assert analysis.process_single_config(str(tmp_path / 'a.json'), args, stack)
    assert stack == set()


def test_real_dependency_cycle_still_fails(tmp_path):
    (tmp_path / 'a.json').write_text(json.dumps({'requirements': ['b.json']}))
    (tmp_path / 'b.json').write_text(json.dumps({'requirements': ['a.json']}))
    args = argparse.Namespace(input_dir=None, output_dir=None, save_pdf=False, save_hstat=False)
    assert not analysis.process_single_config(str(tmp_path / 'a.json'), args)


def write_spectrum(path, name, height):
    with ROOT.TFile(str(path), 'RECREATE'):
        histogram = ROOT.TH1D(name, name, 10, 0., 10.)
        for index in range(1, 11):
            histogram.SetBinContent(index, height)
        histogram.Write()


@pytest.mark.parametrize('selection', [None, [2], ['C']])
def test_missing_histogram_keeps_labels_colors_and_legend_order(tmp_path, selection):
    paths = [tmp_path / f'{name}.root' for name in ('a', 'b', 'c')]
    for path, name in zip(paths, ('a', 'b', 'c')):
        write_spectrum(path, name, 2.)
    cmp = ComparisonConfig(output='identity', files=list(map(str, paths)),
                           hists=['missing', 'b', 'c'], labels=['A', 'B', 'C'],
                           colors=[2, 3, 4], legend_order=['C', 'B'],
                           smoothing='replace' if selection else 'off', smooth_hists=selection)
    cmp.save_macro = True
    compare_histograms_overlay(cmp, output_dir=str(tmp_path))
    macro = (tmp_path / 'identity.C').read_text()
    if selection:
        assert 'c_smooth' in macro
        assert 'b_smooth' not in macro
    entries = re.findall(r'AddEntry\("([^"]+)","([^"]+)"', macro)
    assert entries == [('c_legend', 'C'), ('b_legend', 'B')]
    # Keep original input indices when selecting colors after missing entries.
    assert re.search(r'b__\w*->SetLineColor\(3\)', macro)
    assert re.search(r'c(?:_smooth)?__\w*->SetLineColor\(4\)', macro)


@pytest.mark.parametrize('y_max', [None, 50.])
def test_comparison_autoscale_respects_all_curves_and_manual_limits(tmp_path, y_max):
    a, b = tmp_path / 'low.root', tmp_path / 'high.root'
    write_spectrum(a, 'low', 1.)
    write_spectrum(b, 'high', 100.)
    cmp = ComparisonConfig(output='autoscale', files=[str(a), str(b)], hists=['low', 'high'], labels=['low', 'high'], y_max=y_max)
    cmp.save_macro = True
    compare_histograms_overlay(cmp, output_dir=str(tmp_path))
    macro = (tmp_path / 'autoscale.C').read_text()
    maximum = re.search(r'low\w*->SetMaximum\(([^)]+)\)', macro)
    assert maximum is not None
    if y_max is None:
        assert float(maximum.group(1)) > 100.
    else:
        assert float(maximum.group(1)) == y_max


def test_energy_range_matching_uses_whole_tokens():
    exporter = Exporter(verbose=False)
    assert exporter._file_matches_energy_range(Path('analysis_n_10bins_1.0GeV_20.0GeV.root'), 1., 20.)
    assert not exporter._file_matches_energy_range(Path('analysis_n_10bins_11.0GeV_20.0GeV.root'), 1., 20.)


def test_zero_duration_parallel_jobs_are_zero():
    instant = datetime.datetime(2026, 1, 1)
    assert SimulationSummary(None)._calculate_parallel_jobs([instant], [instant], 0.) == (0., 0.)


def test_colliding_output_names_fail_before_overwriting(tmp_path):
    from src.config import AnalysisConfig, HistogramConfig, OutputConfig
    from src.core import Analysis
    analyzer = Analysis.__new__(Analysis)
    analyzer.comparison_only = False
    analyzer.config = AnalysisConfig(
        histograms=[HistogramConfig(10, 1.01, 2.), HistogramConfig(10, 1.02, 2.)],
        output=OutputConfig(directory=str(tmp_path)),
    )
    with pytest.raises(ValueError, match="same output filename"):
        analyzer.process_all_configs()
    assert not list(tmp_path.iterdir())


def test_comparison_excel_uses_available_engine(tmp_path, monkeypatch):
    from src import comparison
    import openpyxl
    # pandas/openpyxl are available even when the optional xlsxwriter is absent.
    monkeypatch.setitem(sys.modules, 'xlsxwriter', None)
    cmp = ComparisonConfig(output='statistics', files=['a.root'], hists=['ha'], labels=['A'])
    comparison._write_comparison_table_to_excel_and_print(cmp, [2.], [0.5], [25.], str(tmp_path))
    workbook = openpyxl.load_workbook(tmp_path / 'statistics.xlsx', data_only=True)
    assert list(workbook.active.values)[1] == ('ha', 'a.root', 'A', '2.00E+00', '5.00E-01', '25.00%')
    workbook.close()


def test_comparison_autoscale_uses_visible_x_range(tmp_path):
    a, b = tmp_path / 'low.root', tmp_path / 'high.root'
    write_spectrum(a, 'low', 1.)
    write_spectrum(b, 'high', 1.)
    with ROOT.TFile(str(b), 'UPDATE') as root_file:
        histogram = root_file.Get('high')
        histogram.SetBinContent(9, 1e6)
        histogram.Write('', ROOT.TObject.kOverwrite)
    cmp = ComparisonConfig(output='cropped', files=[str(a), str(b)], hists=['low', 'high'],
                           labels=['low', 'high'], x_min=0., x_max=5.)
    cmp.save_macro = True
    compare_histograms_overlay(cmp, output_dir=str(tmp_path))
    macro = (tmp_path / 'cropped.C').read_text()
    maximum = re.search(r'low\w*->SetMaximum\(([^)]+)\)', macro)
    assert maximum is not None
    assert 1. < float(maximum.group(1)) < 10.
