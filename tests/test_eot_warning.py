"""Cached EOT reuse warns, but the user retains control of regeneration."""
from src.config import AnalysisConfig, OutputConfig
from src.core import Analysis
from src.simulation_summary import SimulationSummary


def test_cached_eot_warns_without_recomputing(tmp_path, monkeypatch, capsys):
    (tmp_path / 'simulation_summary.root').touch()
    monkeypatch.setattr(SimulationSummary, 'read_eot_from_file', lambda path: 123.)
    config = AnalysisConfig(input_directory=str(tmp_path / 'different_input'), output=OutputConfig(directory=str(tmp_path)))
    analyzer = Analysis(config)
    assert analyzer.EOT == 123.
    message = capsys.readouterr().out
    assert '[WARN]' in message
    assert 'input' in message.lower() and 'not verified' in message
    assert '--remove-runsummary' in message
