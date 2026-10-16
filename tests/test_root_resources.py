"""ROOT files and canvases are released on successful and exceptional paths."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import ROOT

from src.comparison import compare_histograms_overlay
from src.config import ComparisonConfig
from src.export_histograms import Exporter
from src.simulation_summary import SimulationSummary

ROOT.gROOT.SetBatch(True)


def write_histogram(path, name):
    with ROOT.TFile(str(path), 'RECREATE'):
        histogram = ROOT.TH1D(name, name, 4, 0., 4.)
        histogram.Fill(1., 2.)
        histogram.Write()


def resources():
    return ROOT.gROOT.GetListOfFiles().GetSize(), ROOT.gROOT.GetListOfCanvases().GetSize()


def comparison(tmp_path):
    files = [tmp_path / 'a.root', tmp_path / 'b.root']
    for path, name in zip(files, ['a', 'b']):
        write_histogram(path, name)
    return ComparisonConfig(output='resources', files=list(map(str, files)), hists=['a', 'b'], labels=['A', 'B'])


@pytest.mark.parametrize('fail_save', [False, True])
@pytest.mark.parametrize('rebin', [1, 2])
def test_comparison_closes_files_and_canvas(tmp_path, monkeypatch, fail_save, rebin):
    cmp = comparison(tmp_path)
    cmp.rebin = rebin
    before = resources()
    if fail_save:
        def fail(*args):
            raise RuntimeError('save failed')
        monkeypatch.setattr(ROOT.TCanvas, 'SaveAs', fail)
        with pytest.raises(RuntimeError, match='save failed'):
            compare_histograms_overlay(cmp, str(tmp_path))
    else:
        for _ in range(2):
            compare_histograms_overlay(cmp, str(tmp_path))
        assert (tmp_path / 'resources.pdf').exists()
    assert resources() == before


@pytest.mark.parametrize('fail_save', [False, True])
def test_export_closes_files_and_canvas(tmp_path, monkeypatch, fail_save):
    path = tmp_path / 'input.root'
    write_histogram(path, 'neutrons_h1_detector_lin')
    before = resources()
    if fail_save:
        def fail(*args):
            raise RuntimeError('save failed')
        monkeypatch.setattr(ROOT.TCanvas, 'SaveAs', fail)
        with pytest.raises(RuntimeError, match='save failed'):
            Exporter(verbose=False).export_single_file(str(path), str(tmp_path / 'plots'))
    else:
        Exporter(verbose=False).export_single_file(str(path), str(tmp_path / 'plots'))
    assert resources() == before


def test_summary_read_failure_closes_file(tmp_path):
    path = tmp_path / 'summary.root'
    with ROOT.TFile(str(path), 'RECREATE'):
        pass
    before = resources()
    with pytest.raises(RuntimeError, match='SimSummary tree not found'):
        SimulationSummary.read_eot_from_file(str(path))
    assert resources() == before


@pytest.mark.parametrize('available', [0, 1])
def test_insufficient_histograms_fail_without_success_artifacts(tmp_path, available):
    cmp = comparison(tmp_path)
    cmp.hists = ['a' if available else 'missing_a', 'missing_b']
    before = resources()
    with pytest.raises(ValueError, match='at least two'):
        compare_histograms_overlay(cmp, str(tmp_path))
    assert not (tmp_path / 'resources.pdf').exists()
    assert not (tmp_path / 'resources.xlsx').exists()
    assert resources() == before


def test_missing_comparison_exits_cli_with_failure(tmp_path):
    cmp = comparison(tmp_path)
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps({'comparisons': [{'output': 'missing',
        'output_directory': str(tmp_path),
        'hists': [[cmp.files[0], 'missing', 'A', 2, 0], [cmp.files[1], 'b', 'B', 4, 1]],
    }]}))
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'run_analysis.py'),
                             str(config_path), '--no-save-pdf', '--no-save-hstat'], capture_output=True, text=True)
    assert result.returncode == 1
    assert 'at least two' in result.stdout
