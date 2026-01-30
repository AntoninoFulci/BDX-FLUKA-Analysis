from dataclasses import dataclass
from typing import Any, Optional, List

@dataclass
class HistogramSet:
    """Class to store histogram and canvas sets for a surface"""
    name: str
    h_log: Optional[Any] = None  # ROOT.RDF.RResultPtr - Optional when log bins disabled
    h_lin: Any = None  # ROOT.RDF.RResultPtr  
    h_vertex: Optional[Any] = None  # ROOT.RDF.RResultPtr - Optional for non-spatial analysis
    h_2d_var: Optional[Any] = None  # ROOT.RDF.RResultPtr - Optional 2D variable histogram
