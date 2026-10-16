import numpy as np
import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Union, Set
from pathlib import Path
from glob import escape
from string import Formatter
from .utils import format_energy

@dataclass
class ComparisonConfig:
    output: str
    files: List[str] = field(default_factory=list)
    hists: List[str] = field(default_factory=list)  # Histogram names after row parsing.
    labels: Optional[List[str]] = None  # One label per input histogram.
    title: str = "Comparison"
    x_label: str = ""
    y_label: str = ""
    logx: bool = False
    logy: bool = True
    use_scientific_notation_x: bool = True  # Enable/disable scientific notation for x-axis tick labels
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    output_directory: Optional[str] = None  # Custom output directory for this comparison
    plot_range: Optional[dict] = None       # Dictionary with x_range and y_range keys
    colors: Optional[List[Union[int, str]]] = None  # ROOT color name or code for each histogram.
    line_width: int = 2                     # Line thickness (same for all histograms)
    legend_position: str = "top_right"      # Legend position: top_right, top_left, bottom_right, bottom_left, center_right
    draw_option: str = "hist"               # Draw option for histograms (e.g., "hist", "histe", etc.)
    draw_option_extra: Optional[str] = None  # Extra string appended to draw_option, e.g. "e" becomes "hist e" and "hist same e".
    legend_order: Optional[List[Union[int, str]]] = None  # Custom legend order: list of indices (int) or label names (str), or mix both. Defaults to drawing order.
    smoothing: str = "off"                  # Smoothing mode: "off" | "overlay" (raw faint + smooth bold) | "replace" (smooth only)
    smoothing_sigma: float = 10             # Gaussian width in BINS (not GeV); large = flatter, small = noisier
    smooth_x_max: Optional[float] = None    # Force smoothed curve to stop at this x value; None = auto-clip to last filled bin
    raw_alpha: float = 0.25                 # Alpha of the faint raw line (overlay mode only)
    smooth_line_width: Optional[int] = None # Bold smoothed line thickness; None falls back to line_width
    smooth_hists: Optional[List[Union[int, str]]] = None  # Which histograms to smooth: list of indices or labels; None = all. Only applies when smoothing != "off"; unselected histograms draw normally.
    rebin: Union[int, List[int]] = 1       # A list produces one comparison per factor.
    rebin_hists: Optional[List[Union[int, str]]] = None  # Original input indices or labels; None = all.

    def __post_init__(self):
        factors = self.rebin if isinstance(self.rebin, list) else [self.rebin]
        if not factors or any(isinstance(value, bool) or not isinstance(value, int) or value < 1
                              for value in factors):
            raise ValueError("rebin must be a positive integer or a nonempty list of positive integers (1 disables rebinning).")
        if len(set(factors)) != len(factors):
            raise ValueError("rebin factors must be unique to avoid duplicate output names.")
        self.get_rebin_indices()

    def get_rebin_indices(self) -> Set[int]:
        """Resolve selections against original inputs, before missing histograms are skipped."""
        if self.rebin_hists is None:
            return set(range(len(self.hists)))
        if not isinstance(self.rebin_hists, list):
            raise ValueError("rebin_hists must be a list of input indices or labels.")
        indices = set()
        labels = self.labels or []
        for selection in self.rebin_hists:
            if isinstance(selection, int) and not isinstance(selection, bool):
                if not 0 <= selection < len(self.hists):
                    raise ValueError(f"rebin_hists index {selection} is out of range.")
                indices.add(selection)
            elif isinstance(selection, str):
                if labels.count(selection) == 0:
                    raise ValueError(f"rebin_hists label '{selection}' was not found.")
                if labels.count(selection) > 1:
                    raise ValueError(f"rebin_hists label '{selection}' is ambiguous; use an input index.")
                indices.add(labels.index(selection))
            else:
                raise ValueError("rebin_hists entries must be integer input indices or label strings.")
        return indices

    @classmethod
    def from_dict(cls, data: dict) -> "ComparisonConfig":
        """Read hists rows: [file, histogram, label, color, legend order]."""
        if not isinstance(data, dict):
            raise ValueError("Each comparison entry must be a mapping/object.")
        legacy = set(data) & {
            "files", "files_name", "files_names_label", "files_names_labels_order",
            "labels", "labels_and_colors", "colors", "legend_order",
        }
        if legacy:
            raise ValueError(
                f"Legacy comparison fields {', '.join(sorted(legacy))} are no longer supported; "
                "use hists: [[file, histogram, label, color, order], ...]."
            )
        rows = data.get('hists')
        if not isinstance(rows, list) or not rows:
            raise ValueError("hists must be a nonempty list of [file, histogram, label, color, order] rows.")
        for index, row in enumerate(rows):
            if (not isinstance(row, (list, tuple)) or len(row) != 5
                    or not all(isinstance(value, str) for value in row[:3])
                    or not isinstance(row[3], (str, int)) or isinstance(row[3], bool)
                    or not isinstance(row[4], int) or isinstance(row[4], bool)):
                raise ValueError(
                    f"Invalid hists entry at index {index}: expected [str, str, str, (str|int), int]."
                )
        return cls(
            **{key: value for key, value in data.items() if key != 'hists'},
            files=[row[0] for row in rows],
            hists=[row[1] for row in rows],
            labels=[row[2] for row in rows],
            colors=[row[3] for row in rows],
            legend_order=sorted(range(len(rows)), key=lambda index: rows[index][4]),
        )


@dataclass
class SurfaceConfig:
    id: int
    xl: Optional[float] = None
    xh: Optional[float] = None
    yl: Optional[float] = None
    yh: Optional[float] = None
    zl: Optional[float] = None
    zh: Optional[float] = None
    bin_width: float = 0.5
    name: Optional[str] = None
    spatial_analysis: bool = True
    
    def __post_init__(self):
        if self.name is None:
            self.name = f"surface_{self.id}"
        
        # Determine axis configuration based on which coordinates are provided
        self._determine_axis_config()
    
    def _determine_axis_config(self):
        """Determine the axis configuration based on provided coordinates"""
        coords = []
        
        # Check which coordinates are provided and preserve the order
        # We need to check the order as they would appear in the YAML
        # The order in the dataclass field definition determines the order
        if self.xl is not None and self.xh is not None:
            coords.append(('x', self.xl, self.xh))
        if self.yl is not None and self.yh is not None:
            coords.append(('y', self.yl, self.yh))
        if self.zl is not None and self.zh is not None:
            coords.append(('z', self.zl, self.zh))
        
        if len(coords) < 2:
            # Fallback to default x vs y if not enough coordinates provided
            if self.xl is None:
                self.xl = -250
            if self.xh is None:
                self.xh = 250
            if self.yl is None:
                self.yl = -250
            if self.yh is None:
                self.yh = 250
            coords = [('x', self.xl, self.xh), ('y', self.yl, self.yh)]
        
        # Set the first two coordinates as x and y axes (order matters!)
        self.x_axis = coords[0][0]
        self.y_axis = coords[1][0]
        self.x_min = coords[0][1]
        self.x_max = coords[0][2]
        self.y_min = coords[1][1]
        self.y_max = coords[1][2]
    
    def get_axis_variables(self):
        """Get the ROOT variable names for the configured axes"""
        axis_map = {'x': 'Vx', 'y': 'Vy', 'z': 'Vz'}
        return axis_map[self.x_axis], axis_map[self.y_axis]
    
    def get_axis_labels(self):
        """Get the axis labels for the configured axes"""
        return f"{self.x_axis} [cm]", f"{self.y_axis} [cm]"

@dataclass
class BoxSurfaceConfig:
    name: str
    surface_id: int
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    bin_width: float = 0.5
    spatial_analysis: bool = True
    def get_face_configs(self) -> Dict[str, Dict[str, Any]]:
        faces = {
            "front_face": {"condition": f"Vz == {self.zmin}", "x_var": "Vx", "y_var": "Vy", "x_range": (self.xmin, self.xmax), "y_range": (self.ymin, self.ymax)},
            "back_face": {"condition": f"Vz == {self.zmax}", "x_var": "Vx", "y_var": "Vy", "x_range": (self.xmin, self.xmax), "y_range": (self.ymin, self.ymax)},
            "right_face": {"condition": f"Vx == {self.xmax}", "x_var": "Vz", "y_var": "Vy", "x_range": (self.zmin, self.zmax), "y_range": (self.ymin, self.ymax)},
            "left_face": {"condition": f"Vx == {self.xmin}", "x_var": "Vz", "y_var": "Vy", "x_range": (self.zmin, self.zmax), "y_range": (self.ymin, self.ymax)},
            "top_face": {"condition": f"Vy == {self.ymax}", "x_var": "Vz", "y_var": "Vx", "x_range": (self.zmin, self.zmax), "y_range": (self.xmin, self.xmax)},
            "bottom_face": {"condition": f"Vy == {self.ymin}", "x_var": "Vz", "y_var": "Vx", "x_range": (self.zmin, self.zmax), "y_range": (self.xmin, self.xmax)}
        }
        return faces
    def get_histogram_params(self, face_name: str) -> Tuple[int, int, float, float, float, float, str, str]:
        face_config = self.get_face_configs()[face_name]
        x_range = face_config["x_range"]
        y_range = face_config["y_range"]
        x_bins = int((x_range[1] - x_range[0]) / self.bin_width)
        y_bins = int((y_range[1] - y_range[0]) / self.bin_width)
        return (x_bins, y_bins, x_range[0], x_range[1], y_range[0], y_range[1], face_config["x_var"], face_config["y_var"])

@dataclass
class ConfigRequirement:
    path: str
    enabled: bool = True


@dataclass
class HistogramConfig:
    n_bins: int
    min_energy: float
    max_energy: float
    also_log_bins: bool = False
    @property
    def log_bins(self):
        if self.also_log_bins:
            return np.logspace(np.log10(self.min_energy), np.log10(self.max_energy), self.n_bins + 1)
        else:
            return np.linspace(self.min_energy, self.max_energy, self.n_bins)

@dataclass
class NewVariableConfig:
    name: str
    expression: str

@dataclass
class ParticleConfig:
    particle_id: Union[int, List[int]] = 11
    name: str = "mu_plus"
    variable: str = "P"
    weight: str = "Weight1"
    def get_particle_ids(self) -> List[int]:
        if isinstance(self.particle_id, list):
            return self.particle_id
        else:
            return [self.particle_id]
    def get_filter_expression(self) -> str:
        ids = self.get_particle_ids()
        if len(ids) == 1:
            return f"ParticleID == {ids[0]}"
        else:
            conditions = [f"ParticleID == {pid}" for pid in ids]
            return " || ".join(conditions)

@dataclass
class OutputConfig:
    base_name: str = "analysis"
    directory: str = "."
    include_timestamp: bool = False
    format_template: str = "{base_name}_{particle_name}_{n_bins}bins_{min_energy}_{max_energy}.root"

    def get_file_pattern(self, particle_name: Optional[str] = None,
                         energy_range: Optional[Tuple[float, float]] = None) -> str:
        """Match files produced by this template, including optional timestamps."""
        values = {"base_name": self.base_name, "particle_name": particle_name,
                  "n_bins": None, "min_energy": None, "max_energy": None}
        if energy_range is not None:
            values['min_energy'], values['max_energy'] = map(format_energy, energy_range)
        formatter = Formatter()
        parts = []
        for literal, field_name, format_spec, conversion in formatter.parse(self.format_template):
            parts.append(escape(literal))
            if field_name is None:
                continue
            root_field = field_name.split('.', 1)[0].split('[', 1)[0]
            if values[root_field] is None:
                parts.append('*')
            else:
                value, _ = formatter.get_field(field_name, (), values)
                value = formatter.convert_field(value, conversion) if conversion else value
                parts.append(escape(formatter.format_field(value, format_spec)))
        pattern = ''.join(parts)
        if self.include_timestamp:
            stem, extension = pattern.rsplit('.', 1)
            pattern = f"{stem}_????????_??????.{extension}"
        return pattern

    def matches_energy_range(self, file_path: Path, min_energy: float, max_energy: float) -> bool:
        """Identify a configured range using the same template as the writer."""
        fields = {name for _, name, _, _ in Formatter().parse(self.format_template)}
        if not {'min_energy', 'max_energy'} <= fields:
            return False
        return file_path.match(self.get_file_pattern(energy_range=(min_energy, max_energy)))

    def get_filename(self, particle_config: ParticleConfig, hist_config: HistogramConfig) -> str:
        filename = self.format_template.format(
            base_name=self.base_name,
            particle_name=particle_config.name,
            n_bins=hist_config.n_bins,
            min_energy=format_energy(hist_config.min_energy),
            max_energy=format_energy(hist_config.max_energy)
        )
        if self.include_timestamp:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            name_parts = filename.rsplit('.', 1)
            filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
        return str(Path(self.directory) / filename)

@dataclass
class AnalysisConfig:
    input_directory: str = ""
    particle: ParticleConfig = field(default_factory=ParticleConfig)
    surfaces: List[SurfaceConfig] = field(default_factory=list)
    histograms: List[HistogramConfig] = field(default_factory=list)
    output: OutputConfig = field(default_factory=OutputConfig)
    remove_runsummary: bool = False  # Remove existing simulation_summary.root before analysis starts
    box_surfaces: List[BoxSurfaceConfig] = field(default_factory=list)
    new_variable: Optional[NewVariableConfig] = None
    new_variables: List[NewVariableConfig] = field(default_factory=list)
    requirements: List[ConfigRequirement] = field(default_factory=list)
    comparisons: List[ComparisonConfig] = field(default_factory=list)
    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> 'AnalysisConfig':
        import yaml
        import json
        config_path = Path(config_path)
        with open(config_path, 'r') as f:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                config_data = yaml.safe_load(f)
            else:
                config_data = json.load(f)
        if not isinstance(config_data, dict):
            raise ValueError("Configuration file must contain a JSON object or YAML mapping")
        if 'variable_2d' in config_data:
            raise ValueError("variable_2d is no longer supported; it never produced analysis output.")
        config_data['particle'] = ParticleConfig(**(config_data.get('particle') or {}))
        config_data['surfaces'] = [SurfaceConfig(**surf) for surf in (config_data.get('surfaces') or [])]
        config_data['histograms'] = [HistogramConfig(**hist) for hist in (config_data.get('histograms') or [])]
        config_data['output'] = OutputConfig(**(config_data.get('output') or {}))
        config_data['box_surfaces'] = [BoxSurfaceConfig(**box) for box in (config_data.get('box_surfaces') or [])]
        new_variable_data = config_data.get('new_variable')
        config_data['new_variable'] = NewVariableConfig(**new_variable_data) if new_variable_data else None
        config_data['new_variables'] = [NewVariableConfig(**var) for var in (config_data.get('new_variables') or [])]


        requirements_data = config_data.get('requirements', [])
        normalized_requirements: List[ConfigRequirement] = []
        if requirements_data:
            if not isinstance(requirements_data, list):
                raise ValueError("requirements section must be a list of requirement entries")
            for idx, req in enumerate(requirements_data):
                if isinstance(req, str):
                    normalized_requirements.append(ConfigRequirement(path=req, enabled=True))
                elif isinstance(req, list) and len(req) == 2:
                    path, enabled = req
                    if not isinstance(path, str) or not isinstance(enabled, bool):
                        raise ValueError(
                            f"Invalid requirement entry at index {idx}: expected [str, bool] for list format"
                        )
                    normalized_requirements.append(ConfigRequirement(path=path, enabled=enabled))
                elif isinstance(req, dict):
                    normalized_requirements.append(ConfigRequirement(**req))
                else:
                    raise ValueError(
                        f"Invalid requirement entry at index {idx}: expected a string, [str, bool] list, or mapping with path/enabled"
                    )
        config_data['requirements'] = normalized_requirements

        config_data['comparisons'] = [
            ComparisonConfig.from_dict(cmp)
            for cmp in (config_data.get('comparisons') or [])
        ]
        return cls(**config_data)
