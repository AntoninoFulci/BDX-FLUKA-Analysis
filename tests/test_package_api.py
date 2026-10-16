"""The package and supported CLI entry points work without sys.path patches."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

PROJECT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('arguments', [
    ['-c', 'import src; from src.config import AnalysisConfig; assert src.AnalysisConfig is AnalysisConfig'],
    [str(PROJECT / 'run_analysis.py'), '--help'],
    ['-m', 'src.analysis', '--help'],
])
def test_package_and_cli_entry_points(arguments):
    search_paths = [entry for entry in os.environ.get('PYTHONPATH', '').split(os.pathsep)
                    if entry and Path(entry).resolve() != PROJECT / 'src']
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(search_paths), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, *arguments], cwd=PROJECT, env=environment,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if '--help' in arguments:
        assert '--remove-runsummary' in result.stdout
