"""OutputConfig naming is shared by writers and export discovery."""
from pathlib import Path

import pytest

from src.config import HistogramConfig, OutputConfig, ParticleConfig
from src.export_histograms import Exporter


@pytest.mark.parametrize('output', [
    OutputConfig(),
    OutputConfig(base_name='custom'),
    OutputConfig(format_template='{base_name[0]}-{particle_name}-{n_bins}-{min_energy}-{max_energy}.root'),
    OutputConfig(base_name='sample[v1]', format_template='{particle_name}/{base_name}-{n_bins:04d}-{min_energy}-{max_energy}.root'),
    OutputConfig(base_name='custom', include_timestamp=True,
                 format_template='{base_name}.{particle_name}.{min_energy}.{max_energy}.{n_bins}.root'),
])
def test_export_discovery_matches_output_config(tmp_path, output):
    output.directory = str(tmp_path)
    expected = Path(output.get_filename(ParticleConfig(name='neutrons'), HistogramConfig(10, 0.1, 2.)))
    expected.parent.mkdir(parents=True, exist_ok=True)
    expected.touch()
    (tmp_path / 'simulation_summary.root').touch()
    (tmp_path / 'unrelated.root').touch()
    exporter = Exporter(verbose=False, output_config=output)
    assert exporter._get_sorted_analysis_files(tmp_path, 'neutrons', None) == [expected]
    assert exporter._get_sorted_analysis_files(tmp_path, None, None) == [expected]
    assert exporter._derive_energy_label(expected, [(0.1, 2.)]) == '100.0MeV - 2.0GeV'
    assert not exporter._file_matches_energy_range(expected, 1.1, 2.)


def test_custom_template_sorts_and_labels_multiple_ranges(tmp_path):
    output = OutputConfig(directory=str(tmp_path), include_timestamp=True,
                          format_template='spectra/{base_name}-{particle_name}-{min_energy}-{max_energy}-{n_bins}.root')
    ranges = [(1., 2.), (0.1, 2.), (0.1, 1.)]
    paths = []
    for low, high in ranges:
        path = Path(output.get_filename(ParticleConfig(), HistogramConfig(10, low, high)))
        path.parent.mkdir(exist_ok=True)
        path.touch()
        paths.append(path)
    exporter = Exporter(verbose=False, output_config=output)
    assert exporter._get_sorted_analysis_files(tmp_path, None, ranges) == [paths[1], paths[2], paths[0]]
    assert [exporter._derive_energy_label(path, ranges) for path in paths] == [
        '1.0GeV - 2.0GeV', '100.0MeV - 2.0GeV', '100.0MeV - 1.0GeV']


def test_template_without_energy_fields_has_unknown_range(tmp_path):
    output = OutputConfig(directory=str(tmp_path), format_template='{base_name}_{particle_name}.root')
    path = Path(output.get_filename(ParticleConfig(), HistogramConfig(10, 0.1, 2.)))
    exporter = Exporter(verbose=False, output_config=output)
    assert exporter._derive_energy_label(path, [(0.1, 2.)]) == 'unknown'


def test_default_discovery_remains_analysis_prefix(tmp_path):
    expected = tmp_path / 'analysis_neutrons_10bins_100.0MeV_2.0GeV.root'
    expected.touch()
    (tmp_path / 'custom_neutrons_10bins_100.0MeV_2.0GeV.root').touch()
    assert Exporter(verbose=False)._get_sorted_analysis_files(tmp_path, 'neutrons', None) == [expected]
