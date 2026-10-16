"""The current comparison schema is explicit; legacy YAML is rejected."""
import json

import pytest

from src.config import AnalysisConfig


def load_config(tmp_path, data):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(data))
    return AnalysisConfig.from_file(path)


def test_comparison_rows_preserve_pairs_colors_and_order(tmp_path):
    comparison, = load_config(tmp_path, {'comparisons': [{
        'output': 'plot',
        'hists': [['a.root', 'ha', 'A', 'red', 5], ['b.root', 'hb', 'B', 4, 2]],
    }]}).comparisons
    assert comparison.files == ['a.root', 'b.root']
    assert comparison.hists == ['ha', 'hb']
    assert comparison.labels == ['A', 'B']
    assert comparison.colors == ['red', 4]
    assert comparison.legend_order == [1, 0]


@pytest.mark.parametrize('legacy', [
    {'files': ['a.root'], 'hists': ['ha'], 'labels': ['A']},
    {'files_name': [['a.root', 'ha']]},
    {'files_names_label': {'a.root': ['ha', 'A']}},
    {'files_names_labels_order': [['a.root', 'ha', 'A', 0]]},
    {'labels_and_colors': {'A': 'red'}},
    {'colors': 'kP6'},
    {'legend_order': [0]},
])
def test_legacy_comparison_fields_report_migration(tmp_path, legacy):
    with pytest.raises(ValueError, match='Legacy comparison fields'):
        load_config(tmp_path, {'comparisons': [{'output': 'plot', **legacy}]})


@pytest.mark.parametrize('hists', [[], ['ha'], [['a.root', 'ha']],
    [['a.root', 'ha', 'A', 'red', 'first']], [['a.root', 'ha', 'A', True, 0]],
    [['a.root', 'ha', 'A', 'red', True]], [['a.root', 'ha', 3, 'red', 0]]])
def test_invalid_comparison_rows_report_expected_format(tmp_path, hists):
    with pytest.raises(ValueError, match='hists'):
        load_config(tmp_path, {'comparisons': [{'output': 'plot', 'hists': hists}]})


@pytest.mark.parametrize('value', [None, {}, [], False])
def test_empty_optional_sections_keep_defaults(tmp_path, value):
    config = load_config(tmp_path, dict.fromkeys([
        'particle', 'output', 'surfaces', 'histograms', 'box_surfaces',
        'new_variable', 'new_variables', 'requirements', 'comparisons',
    ], value))
    assert config.particle.name == 'mu_plus'
    assert config.output.directory == '.'
    assert config.surfaces == config.histograms == config.box_surfaces == config.new_variables == []
    assert config.new_variable is None
    assert config.requirements == config.comparisons == []


def test_removed_variable_2d_reports_unsupported_option(tmp_path):
    with pytest.raises(ValueError, match='variable_2d.*no longer supported'):
        load_config(tmp_path, {'variable_2d': {}})
