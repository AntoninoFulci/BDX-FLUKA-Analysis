import sys
import os
import ROOT
from typing import List, Tuple
import pint

# Initialize the unit registry
ureg = pint.UnitRegistry()

class DummyStyleManager:
    """A dummy context manager to use when pyROOTUtils is not available"""
    def __init__(self, style=None):
        pass
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

def format_energy(energy_gev):
    """Format energy value with appropriate units"""
    energy = energy_gev * ureg.GeV
    if energy.to('eV').magnitude < 1000:
        return f"{energy.to('eV').magnitude:.1f}eV"
    elif energy.to('keV').magnitude < 1000:
        return f"{energy.to('keV').magnitude:.1f}keV"
    elif energy.to('MeV').magnitude < 1000:
        return f"{energy.to('MeV').magnitude:.1f}MeV"
    else:
        return f"{energy.to('GeV').magnitude:.1f}GeV"
    
def parse_energy_ranges(ranges_str: str) -> List[Tuple[float, float]]:
    """Parse energy ranges from string input"""
    ranges = []
    for r in ranges_str.split(','):
        min_e, max_e = map(float, r.split('-'))
        ranges.append((min_e, max_e))
    return ranges

class QuietRoot:
    """A context manager to suppress ROOT warnings"""
    def __init__(self, level=ROOT.kWarning):
        self.level = level
        self.old_level = None

    def __enter__(self):
        self.old_level = ROOT.gErrorIgnoreLevel
        ROOT.gErrorIgnoreLevel = self.level
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ROOT.gErrorIgnoreLevel = self.old_level

def setup_root():
    """Initialize ROOT settings and return style configuration
    
    Returns:
        tuple: (set_style, stileh1, stileh2, quiet) style configuration objects and quiet mode
    """
    ROOT.EnableImplicitMT()
    
    # Default to dummy style manager
    set_style = DummyStyleManager
    stileh1 = None
    stileh2 = None
    quiet = QuietRoot(ROOT.kWarning)
    
    # Try to import pyROOTUtils if available
    pyrootutils_path = os.getenv("PYROOTUTILS")
    if pyrootutils_path:
        sys.path.append(pyrootutils_path)
        try:
            from pyROOTUtils.root_set_style import set_style
            from pyROOTUtils.article_style import th1_style, th2_style
            stileh1 = th1_style()
            stileh2 = th2_style()
        except ImportError:
            print("Warning: Could not import pyROOTUtils styles, using default ROOT styles")
            
    return set_style, stileh1, stileh2, quiet