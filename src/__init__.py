"""BDX Analysis Package public API."""

from .config import AnalysisConfig, ParticleConfig, HistogramConfig, SurfaceConfig, BoxSurfaceConfig
from .core import Analysis
from .export_histograms import Exporter, export_histograms_to_pdf, export_all_analysis_histograms_to_pdf
from .utils import setup_root, format_energy
from .simulation_summary import SimulationSummary
from .histogram import HistogramSet
from .comparison import compare_histograms_overlay

__all__ = [
    "AnalysisConfig",
    "ParticleConfig",
    "HistogramConfig",
    "SurfaceConfig",
    "BoxSurfaceConfig",
    "Analysis",
    "Exporter",
    "export_histograms_to_pdf",
    "export_all_analysis_histograms_to_pdf",
    "setup_root",
    "format_energy",
    "SimulationSummary",
    "HistogramSet",
    "compare_histograms_overlay",
]