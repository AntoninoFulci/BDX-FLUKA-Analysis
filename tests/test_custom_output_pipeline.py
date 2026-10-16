"""Custom OutputConfig names reach both PDF and statistics exports through the CLI."""
import argparse
from array import array
import json

import openpyxl
import pytest
import ROOT

from src.analysis import process_single_config

ROOT.gROOT.SetBatch(True)


def write_input(directory):
    directory.mkdir()
    with ROOT.TFile(str(directory / 'simulation.root'), 'RECREATE'):
        for name, values in [
            ('Events', {'ParticleID': 8., 'SurfaceID': 7., 'P': 0.5, 'Weight1': 2.,
                        'Vx': 1., 'Vy': 1., 'Vz': 1.}),
            ('RunSummary', {'TotEvents': 10., 'AvgTime': 0.1, 'StartTime': 1000., 'TotTime': 2.}),
        ]:
            tree = ROOT.TTree(name, name)
            buffers = {key: array('d', [value]) for key, value in values.items()}
            for key, buffer in buffers.items():
                tree.Branch(key, buffer, f'{key}/D')
            tree.Fill()
            tree.Write()


@pytest.mark.parametrize('output_options', [
    {},
    {'base_name': 'custom'},
    {'base_name': 'custom[v1]', 'include_timestamp': True,
     'format_template': 'spectra/{base_name}-{particle_name}-{n_bins:04d}bins-{min_energy}-{max_energy}.root'},
])
def test_custom_output_reaches_pdf_excel_and_macro(tmp_path, output_options):
    write_input(tmp_path / 'input')
    output = tmp_path / 'output'
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps({
        'input_directory': str(tmp_path / 'input'),
        'particle': {'particle_id': 8, 'name': 'neutrons'},
        'histograms': [{'n_bins': 4, 'min_energy': 0.1, 'max_energy': 1., 'also_log_bins': True}],
        'surfaces': [{'id': 7, 'xl': 0, 'xh': 2, 'yl': 0, 'yh': 2, 'bin_width': 1}],
        'output': {'directory': str(output), **output_options},
    }))
    args = argparse.Namespace(input_dir=None, output_dir=None, save_pdf=True, save_hstat=True, save_macro=True)
    assert process_single_config(str(config_path), args)
    assert len(list(output.rglob('*.root'))) == 2
    assert len(list((output / 'plots').glob('*.pdf'))) == 3
    assert len(list((output / 'plots').glob('*.C'))) == 3
    workbook = openpyxl.load_workbook(output / 'histogram_statistics.xlsx', data_only=True)
    rows = list(workbook['00'].values)
    result = dict(zip(rows[0], rows[1]))
    assert result['integral'] == pytest.approx(0.2)
    assert result['error'] == pytest.approx(0.2)
    assert result['energy_range'] == '100.0MeV - 1.0GeV'
    workbook.close()
