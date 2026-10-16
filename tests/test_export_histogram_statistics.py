"""Regression tests for counts/EOT maps and differential energy spectra."""

import math
from array import array

import openpyxl
import pytest
import ROOT

from src.export_histograms import Exporter

ROOT.gROOT.SetBatch(True)


def export_rows(directory):
    Exporter(verbose=False).export_histogram_statistics(str(directory))
    workbook = openpyxl.load_workbook(directory / "histogram_statistics.xlsx", data_only=True)
    rows = []
    for sheet in workbook:
        if sheet.title == "Notes":
            continue
        values = list(sheet.values)
        rows.extend(dict(zip(values[0], row)) for row in values[1:])
    notes = workbook["Notes"].cell(1, 1).value
    workbook.close()
    return rows, notes


@pytest.mark.parametrize("pixel_width", [0.1, 0.25])
@pytest.mark.parametrize("spatial_first", [False, True])
def test_spatial_counts_export_yield_and_error_without_pixel_area(tmp_path, pixel_width, spatial_first):
    """Catch area scaling and loss of TH2 priority in either key order."""
    with ROOT.TFile(str(tmp_path / "analysis_neutrons_2bins_1.0MeV_1.0GeV.root"), "RECREATE"):
        spectrum = ROOT.TH1D("neutrons_h1_detector_lin", ";E;n/(GeV * EOT)", 2, 0, 1)
        spectrum.Fill(0.25, 99)
        spatial = ROOT.TH2D("neutrons_h2_detector", ";X;Y;n/(EOT)", 2, 0, 2 * pixel_width, 2, 0, 2 * pixel_width)
        spatial.Sumw2()
        spatial.Fill(pixel_width / 2, pixel_width / 2, 2)
        spatial.Fill(1.5 * pixel_width, 1.5 * pixel_width, 3)
        # Neither contents nor variances from flow bins may enter the export.
        spatial.Fill(-pixel_width, pixel_width / 2, 70)
        spatial.Fill(pixel_width / 2, 3 * pixel_width, 80)
        for hist in ([spatial, spectrum] if spatial_first else [spectrum, spatial]):
            hist.Write()
    rows, notes = export_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["histogram_name"] == "neutrons_h2_detector"
    assert rows[0]["integral"] == pytest.approx(5)
    assert rows[0]["error"] == pytest.approx(math.sqrt(13))
    assert rows[0]["error_percent"] == pytest.approx(math.sqrt(13) / 5 * 100)
    assert "TH2" in notes and "underflow" in notes.lower() and "overflow" in notes.lower()


def test_differential_spectrum_export_integrates_variable_energy_bins(tmp_path):
    """Catch removal of width weighting or inclusion of flow bins for TH1."""
    with ROOT.TFile(str(tmp_path / "analysis_neutrons_2bins_1.0MeV_1.0GeV.root"), "RECREATE"):
        spectrum = ROOT.TH1D("neutrons_h1_detector_lin", ";E;n/(GeV * EOT)", 2, array("d", [0, 0.1, 1]))
        spectrum.Sumw2()
        spectrum.Fill(0.05, 2)
        spectrum.Fill(0.5, 3)
        spectrum.Fill(-1, 70)
        spectrum.Fill(2, 80)
        spectrum.Scale(0.5, "width")
        spectrum.Write()
    rows, _ = export_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["integral"] == pytest.approx(2.5)
    assert rows[0]["error"] == pytest.approx(math.sqrt(13) / 2)


def test_empty_spatial_map_exports_zero_without_division(tmp_path):
    with ROOT.TFile(str(tmp_path / "analysis_neutrons_2bins_1.0MeV_1.0GeV.root"), "RECREATE"):
        spatial = ROOT.TH2D("neutrons_h2_detector", ";X;Y;n/(EOT)", 2, 0, 0.2, 2, 0, 0.2)
        spatial.Write()
    rows, _ = export_rows(tmp_path)
    assert [rows[0][key] for key in ("integral", "error", "error_percent")] == [0, 0, 0]
