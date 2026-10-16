"""Rebin comparison densities before drawing/smoothing without changing yields."""
from array import array
import ctypes
import hashlib
import json

import numpy as np
import pytest
import ROOT

from src import comparison
from src.config import AnalysisConfig, ComparisonConfig

ROOT.gROOT.SetBatch(True)


def integral_and_error(histogram):
    error = ctypes.c_double(0.)
    integral = histogram.IntegralAndError(1, histogram.GetNbinsX(), error, 'width')
    return integral, error.value


def make_density(edges):
    h = ROOT.TH1D('density', 'Density', len(edges) - 1, array('d', edges))
    h.SetDirectory(0)
    h.Sumw2()
    for index in range(h.GetNcells()):
        h.SetBinContent(index, (index + 1.) / h.GetBinWidth(index))
        h.SetBinError(index, (index + 0.5) / h.GetBinWidth(index))
    h.SetEntries(123.)
    return h


def test_rebin_default_is_disabled():
    assert ComparisonConfig(output='plot').rebin == 1


@pytest.mark.parametrize('factor', [0, -1, 2.5, True, False, '2', None])
def test_invalid_rebin_factor_rejected(factor):
    with pytest.raises(ValueError, match='rebin.*positive integer'):
        ComparisonConfig(output='plot', rebin=factor)


def test_rebin_loads_from_canonical_config(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'comparisons': [{'output': 'plot', 'rebin': 4,
        'hists': [['a.root', 'a', 'A', 2, 0], ['b.root', 'b', 'B', 4, 1]]}]}))
    assert AnalysisConfig.from_file(path).comparisons[0].rebin == 4


@pytest.mark.parametrize('edges', [list(range(9)), [0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8, 25.6]])
@pytest.mark.parametrize('factor', [2, 4, 8])
def test_rebin_preserves_density_integral_errors_and_input(edges, factor):
    h = make_density(edges)
    original = [(h.GetBinContent(i), h.GetBinError(i)) for i in range(h.GetNcells())]
    before = integral_and_error(h)
    rebinned = comparison._rebin_density(h, factor)
    assert rebinned.GetNbinsX() == h.GetNbinsX() // factor
    assert not rebinned.GetDirectory()
    assert rebinned.__python_owns__
    assert rebinned.GetEntries() == h.GetEntries()
    assert integral_and_error(rebinned) == pytest.approx(before, rel=1e-13)
    for index in range(1, rebinned.GetNbinsX() + 1):
        group = range(1 + (index - 1) * factor, 1 + index * factor)
        width = rebinned.GetBinWidth(index)
        content = sum(h.GetBinContent(i) * h.GetBinWidth(i) for i in group) / width
        error = sum((h.GetBinError(i) * h.GetBinWidth(i)) ** 2 for i in group) ** 0.5 / width
        assert rebinned.GetBinContent(index) == pytest.approx(content)
        assert rebinned.GetBinError(index) == pytest.approx(error)
    for source, target in [(0, 0), (h.GetNbinsX() + 1, rebinned.GetNbinsX() + 1)]:
        assert rebinned.GetBinContent(target) * rebinned.GetBinWidth(target) == pytest.approx(h.GetBinContent(source) * h.GetBinWidth(source))
        assert rebinned.GetBinError(target) * rebinned.GetBinWidth(target) == pytest.approx(h.GetBinError(source) * h.GetBinWidth(source))
    assert [(h.GetBinContent(i), h.GetBinError(i)) for i in range(h.GetNcells())] == original


def test_disabled_rebin_keeps_original_object():
    h = make_density(list(range(9)))
    assert comparison._rebin_density(h, 1) is h


def test_rebin_initializes_errors_when_sumw2_is_absent():
    h = ROOT.TH1F('without_sumw2', '', 4, 0., 8.)
    h.SetDirectory(0)
    for index in range(1, 5):
        h.SetBinContent(index, index * 4.)
    h.Sumw2(False)
    before = integral_and_error(h)
    rebinned = comparison._rebin_density(h, 2)
    assert rebinned.GetSumw2N() > 0
    assert h.GetSumw2N() == 0
    assert integral_and_error(rebinned) == pytest.approx(before, rel=1e-6)


@pytest.mark.parametrize('factor', [3, 9])
def test_rebin_rejects_groups_that_would_lose_range(factor):
    with pytest.raises(ValueError, match='rebin.*divide.*8'):
        comparison._rebin_density(make_density(list(range(9))), factor)


@pytest.mark.parametrize('kind', ['TH2D', 'TProfile', 'TH1I'])
def test_rebin_rejects_non_floating_spectra(kind):
    if kind == 'TH2D':
        h = ROOT.TH2D('unsupported', '', 8, 0., 8., 2, 0., 2.)
    else:
        h = getattr(ROOT, kind)('unsupported', '', 8, 0., 8.)
    h.SetDirectory(0)
    with pytest.raises(ValueError, match='TH1F.*TH1D'):
        comparison._rebin_density(h, 2)


@pytest.mark.parametrize('mode', ['off', 'overlay', 'replace'])
def test_rebin_precedes_smoothing_and_preserves_statistics(tmp_path, monkeypatch, mode):
    paths = []
    for index in range(2):
        path = tmp_path / f'{index}.root'
        with ROOT.TFile(str(path), 'RECREATE'):
            h = make_density([0.1 * 2 ** i for i in range(9)])
            h.SetName(f'h{index}')
            h.Write()
        paths.append(path)
    hashes = [hashlib.sha256(path.read_bytes()).digest() for path in paths]
    cmp = ComparisonConfig(output='rebin', files=list(map(str, paths)), hists=['h0', 'h1'],
                           labels=['A', 'B'], rebin=2, smoothing=mode, smoothing_sigma=1.,
                           smooth_hists=['B'], logx=True, output_directory=str(tmp_path))
    cmp.save_macro = True
    calls = []
    smooth = comparison._smooth_hist_logspace
    def checked_smoothing(h, sigma, x_max):
        assert h.GetNbinsX() == 4
        assert integral_and_error(h) == pytest.approx(integral_and_error(make_density([0.1 * 2 ** i for i in range(9)])))
        calls.append(h.GetName())
        return smooth(h, sigma, x_max)
    monkeypatch.setattr(comparison, '_smooth_hist_logspace', checked_smoothing)
    statistics = []
    def capture_statistics(cmp, integrals, errors, percentages, output_dir):
        statistics.extend(zip(integrals, errors))
    monkeypatch.setattr(comparison, '_write_comparison_table_to_excel_and_print', capture_statistics)
    resources = ROOT.gROOT.GetListOfFiles().GetSize(), ROOT.gROOT.GetListOfCanvases().GetSize()
    comparison.compare_histograms_overlay(cmp)
    assert len(calls) == (0 if mode == 'off' else 1)
    assert all(name.startswith('h1') for name in calls)
    assert (ROOT.gROOT.GetListOfFiles().GetSize(), ROOT.gROOT.GetListOfCanvases().GetSize()) == resources
    np.testing.assert_allclose(statistics, [integral_and_error(h)] * 2, rtol=1e-13)
    for ext in ['pdf', 'C']:
        assert (tmp_path / f'rebin.{ext}').stat().st_size > 0
    assert [hashlib.sha256(path.read_bytes()).digest() for path in paths] == hashes


def test_invalid_rebin_fails_before_export_and_closes_inputs(tmp_path):
    path = tmp_path / 'input.root'
    with ROOT.TFile(str(path), 'RECREATE'):
        h = make_density(list(range(9)))
        h.Write()
    cmp = ComparisonConfig(output='invalid', files=[str(path)] * 2, hists=['density'] * 2,
                           labels=['A', 'B'], rebin=3, output_directory=str(tmp_path))
    resources = ROOT.gROOT.GetListOfFiles().GetSize(), ROOT.gROOT.GetListOfCanvases().GetSize()
    with pytest.raises(ValueError, match='rebin.*divide'):
        comparison.compare_histograms_overlay(cmp)
    assert (ROOT.gROOT.GetListOfFiles().GetSize(), ROOT.gROOT.GetListOfCanvases().GetSize()) == resources
    assert not (tmp_path / 'invalid.xlsx').exists()
    assert not (tmp_path / 'invalid.pdf').exists()


@pytest.mark.parametrize('factors', [[], [2, 0], [True, 2], [2, '4'], [2, 2], [2.5], [[2]]])
def test_invalid_rebin_sets_are_rejected(factors):
    with pytest.raises(ValueError, match='rebin'):
        ComparisonConfig(output='plot', rebin=factors)


@pytest.mark.parametrize('selection', [True, 'A', [True], [-1], [2], ['missing'], [0.5]])
def test_invalid_rebin_selection_is_rejected(selection):
    with pytest.raises(ValueError, match='rebin_hists'):
        ComparisonConfig(output='plot', files=['a', 'b'], hists=['a', 'b'],
                         labels=['A', 'B'], rebin_hists=selection)


def test_ambiguous_rebin_label_requires_index():
    with pytest.raises(ValueError, match='rebin_hists.*ambiguous'):
        ComparisonConfig(output='plot', hists=['a', 'b'], labels=['A', 'A'], rebin_hists=['A'])


def test_rebin_sets_and_selection_load_from_yaml(tmp_path):
    path = tmp_path / 'comparison.yaml'
    path.write_text('''comparisons:
  - output: selected
    hists:
      - [a.root, ha, A, 2, 0]
      - [b.root, hb, B, 4, 1]
    rebin: [2, 4]
    rebin_hists: [B]
''')
    cmp = AnalysisConfig.from_file(path).comparisons[0]
    assert cmp.rebin == [2, 4]
    assert cmp.rebin_hists == ['B']


def write_comparison_inputs(tmp_path, bins=(8, 8)):
    paths = []
    for index, count in enumerate(bins):
        path = tmp_path / f'input{index}.root'
        with ROOT.TFile(str(path), 'RECREATE'):
            histogram = make_density([0.1 * 2 ** i for i in range(count + 1)])
            histogram.SetName(f'h{index}')
            histogram.Write()
        paths.append(str(path))
    return paths


@pytest.mark.parametrize('selection,expected', [(None, [4, 4]), ([1], [8, 4]), (['B'], [8, 4]),
                                                ([0, 'B'], [4, 4]), ([], [8, 8])])
def test_rebin_affects_only_selected_histograms(tmp_path, monkeypatch, selection, expected):
    paths = write_comparison_inputs(tmp_path)
    cmp = ComparisonConfig(output='selected', files=paths, hists=['h0', 'h1'], labels=['A', 'B'],
                           rebin=2, rebin_hists=selection, output_directory=str(tmp_path))
    observed = []
    def capture(cmp, indexed_hists, output_dir):
        observed.extend(h.GetNbinsX() for _, h in indexed_hists)
    monkeypatch.setattr(comparison, '_draw_comparison', capture)
    comparison.compare_histograms_overlay(cmp)
    assert observed == expected


def test_unselected_histogram_need_not_support_rebin_factor(tmp_path, monkeypatch):
    paths = write_comparison_inputs(tmp_path, bins=(7, 8))
    cmp = ComparisonConfig(output='selected', files=paths, hists=['h0', 'h1'], labels=['A', 'B'],
                           rebin=4, rebin_hists=['B'], output_directory=str(tmp_path))
    observed = []
    monkeypatch.setattr(comparison, '_draw_comparison',
                        lambda cmp, indexed_hists, output_dir: observed.extend(h.GetNbinsX() for _, h in indexed_hists))
    comparison.compare_histograms_overlay(cmp)
    assert observed == [7, 2]


def test_rebin_selection_uses_original_indices_after_missing_histogram(tmp_path, monkeypatch):
    paths = write_comparison_inputs(tmp_path)
    cmp = ComparisonConfig(output='selected', files=[paths[0], *paths], hists=['missing', 'h0', 'h1'],
                           labels=['Missing', 'A', 'B'], rebin=2, rebin_hists=[2], output_directory=str(tmp_path))
    observed = []
    monkeypatch.setattr(comparison, '_draw_comparison', lambda cmp, indexed_hists, output_dir:
                        observed.extend((index, h.GetNbinsX()) for index, h in indexed_hists))
    comparison.compare_histograms_overlay(cmp)
    assert observed == [(1, 8), (2, 4)]


@pytest.mark.parametrize('mode', ['off', 'overlay', 'replace'])
def test_rebin_sets_produce_independent_figures_and_keep_smoothing_selection(tmp_path, monkeypatch, mode):
    from pathlib import Path
    import openpyxl
    paths = write_comparison_inputs(tmp_path)
    before = [hashlib.sha256(Path(path).read_bytes()).digest() for path in paths]
    cmp = ComparisonConfig(output='sets', files=paths, hists=['h0', 'h1'], labels=['A', 'B'],
                           rebin=[1, 2, 4], rebin_hists=['B'], smoothing=mode, smooth_hists=[0, 1],
                           smoothing_sigma=1., output_directory=str(tmp_path))
    cmp.save_macro = True
    drawn = []
    smoothed = []
    draw = comparison._draw_comparison
    smooth = comparison._smooth_hist_logspace
    def capture_draw(config, indexed_hists, output_dir):
        drawn.append((config.output, [(h.GetNbinsX(), integral_and_error(h)) for _, h in indexed_hists]))
        # Each pass starts from fresh inputs: no previous SetRangeUser/style state.
        assert all(not h.GetXaxis().TestBit(ROOT.TAxis.kAxisRange) for _, h in indexed_hists)
        return draw(config, indexed_hists, output_dir)
    def capture_smooth(h, sigma, x_max):
        smoothed.append(h.GetNbinsX())
        return smooth(h, sigma, x_max)
    monkeypatch.setattr(comparison, '_draw_comparison', capture_draw)
    monkeypatch.setattr(comparison, '_smooth_hist_logspace', capture_smooth)
    resources = ROOT.gROOT.GetListOfFiles().GetSize(), ROOT.gROOT.GetListOfCanvases().GetSize()
    comparison.compare_histograms_overlay(cmp)
    assert [name for name, _ in drawn] == ['sets_rebin1', 'sets_rebin2', 'sets_rebin4']
    assert [[count for count, _ in rows] for _, rows in drawn] == [[8, 8], [8, 4], [8, 2]]
    for _, rows in drawn:
        np.testing.assert_allclose([result for _, result in rows],
                                   [result for _, result in drawn[0][1]], rtol=1e-13)
    assert smoothed == ([] if mode == 'off' else [8, 8, 8, 4, 8, 2])
    tables = []
    for factor in [1, 2, 4]:
        for ext in ['pdf', 'C', 'xlsx']:
            assert (tmp_path / f'sets_rebin{factor}.{ext}').stat().st_size > 0
        workbook = openpyxl.load_workbook(tmp_path / f'sets_rebin{factor}.xlsx', data_only=True)
        tables.append(list(workbook.active.values))
        workbook.close()
    assert tables[0] == tables[1] == tables[2]
    assert not (tmp_path / 'sets.pdf').exists()
    assert cmp.output == 'sets' and cmp.rebin == [1, 2, 4] and cmp.save_macro
    assert before == [hashlib.sha256(Path(path).read_bytes()).digest() for path in paths]
    assert (ROOT.gROOT.GetListOfFiles().GetSize(), ROOT.gROOT.GetListOfCanvases().GetSize()) == resources


def test_list_with_one_factor_uses_suffix(tmp_path):
    paths = write_comparison_inputs(tmp_path)
    cmp = ComparisonConfig(output='single', files=paths, hists=['h0', 'h1'], labels=['A', 'B'],
                           rebin=[2], output_directory=str(tmp_path))
    comparison.compare_histograms_overlay(cmp)
    assert (tmp_path / 'single_rebin2.pdf').exists()
    assert not (tmp_path / 'single.pdf').exists()
