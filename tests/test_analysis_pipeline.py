"""Scientific invariants shared by surface and box histogram booking."""
import ctypes
import math

import numpy as np
import pytest
import ROOT

from src.config import AnalysisConfig, BoxSurfaceConfig, HistogramConfig, NewVariableConfig, ParticleConfig, SurfaceConfig
from src.core import Analysis
from src.utils import DummyStyleManager

ROOT.gROOT.SetBatch(True)


@pytest.mark.parametrize('log_bins', [False, True])
@pytest.mark.parametrize('spatial', [False, True])
def test_surface_and_box_yields_errors_and_optional_histograms(tmp_path, log_bins, spatial):
    events = ROOT.RDF.FromNumpy({
        'ParticleID': np.array([8] * 8 + [7], dtype=np.int32),
        'SurfaceID': np.array([7, 7] + [99] * 6 + [7], dtype=np.int32),
        'Energy': np.array([0.25, 0.75] + [0.5] * 7),
        'Weight1': np.array([2., 3.] + [2.] * 6 + [100.]),
        'Vx': np.array([0.5, 1.5, 1., 1., 2., 0., 1., 1., 1.]),
        'Vy': np.array([0.5, 1.5, 1., 1., 1., 1., 2., 0., 1.]),
        'Vz': np.array([1., 1., 0., 2., 1., 1., 1., 1., 1.]),
    })
    analyzer = Analysis.__new__(Analysis)
    analyzer.config = AnalysisConfig(
        particle=ParticleConfig(particle_id=8, name='neutrons', variable='EKin'),
        new_variable=NewVariableConfig('EKin', 'Energy'),
        new_variables=[NewVariableConfig('TwiceEnergy', '2 * EKin')],
        surfaces=[SurfaceConfig(7, xl=0, xh=2, yl=0, yh=2, bin_width=0.5, spatial_analysis=spatial)],
        box_surfaces=[BoxSurfaceConfig('box', 99, 0, 2, 0, 2, 0, 2, bin_width=0.5, spatial_analysis=spatial)],
    )
    analyzer.EOT = 10
    analyzer.set_style = DummyStyleManager
    analyzer.stileh1 = analyzer.stileh2 = None
    histogram_config = HistogramConfig(4, 0.1, 1., also_log_bins=log_bins)
    histograms = analyzer.create_histograms(events, histogram_config)
    assert len(histograms) == 7
    with ROOT.TFile(str(tmp_path / 'analysis.root'), 'RECREATE') as output:
        analyzer.write_histograms(output, histograms)
        for index, group in enumerate(histograms):
            expected = 0.5 if index == 0 else 0.2
            expected_error = math.sqrt(13) / 10 if index == 0 else 0.2
            assert (group.h_log is not None) == log_bins
            assert (group.h_vertex is not None) == spatial
            for histogram in [group.h_lin] + ([group.h_log] if log_bins else []):
                error = ctypes.c_double()
                assert histogram.IntegralAndError(1, 4, error, 'width') == pytest.approx(expected)
                assert error.value == pytest.approx(expected_error)
            if spatial:
                error = ctypes.c_double()
                assert group.h_vertex.IntegralAndError(1, 4, 1, 4, error, '') == pytest.approx(expected)
                assert error.value == pytest.approx(expected_error)
