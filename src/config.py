import numpy as np
import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Union
from pathlib import Path
from utils import format_energy

@dataclass
class ComparisonConfig:
    output: str
    files: List[str] = field(default_factory=list)
    hists: List[str] = field(default_factory=list)  # Legacy names list; also accepted as combined rows via parser.
    files_name: Optional[Union[List[List[str]], Dict[str, str]]] = None  # Preferred pairing config: [["file.root", "hist_name"], ...] or {"file.root": "hist_name"}
    files_names_label: Optional[Union[List[List[str]], Dict[str, List[str]]]] = None  # Pairing with labels: [["file.root", "hist_name", "label"], ...] or {"file.root": ["hist_name", "label"]}
    files_names_labels_order: Optional[Union[List[List[Union[str, int]]], Dict[str, List[Union[str, int]]]]] = None  # Pairing with labels and explicit legend order: [["file.root", "hist_name", "label", 0], ...]
    labels: Optional[List[str]] = None  # Labels for each histogram. Can be auto-extracted from labels_and_colors if not provided.
    title: str = "Comparison"
    x_label: str = ""
    y_label: str = ""
    logx: bool = False
    logy: bool = True
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    output_directory: Optional[str] = None  # Custom output directory for this comparison
    plot_range: Optional[dict] = None       # Dictionary with x_range and y_range keys
    colors: Optional[Union[List[Union[int, str]], str]] = None  # Custom colors: list of int/str codes, or scheme name ('kP6', 'kP8', 'kP10'). Supports int codes or named colors ('red','blue','kP6Red',...)
    labels_and_colors: Optional[Union[List[List[Union[str, int, str]]], Dict[str, Union[int, str]]]] = None  # Labels and colors: list of [label, color_code_or_name] pairs or {label: color} dict. Colors can be int codes or string names.
    line_width: int = 2                     # Line thickness (same for all histograms)
    legend_position: str = "top_right"      # Legend position: top_right, top_left, bottom_right, bottom_left, center_right
    draw_option: str = "hist"               # Draw option for histograms (e.g., "hist", "histe", etc.)
    draw_option_extra: Optional[str] = None  # Extra string appended to draw_option, e.g. "e" becomes "hist e" and "hist same e".
    legend_order: Optional[List[Union[int, str]]] = None  # Custom legend order: list of indices (int) or label names (str), or mix both. Defaults to drawing order.

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
class Variable2DConfig:
    x_variable: str
    y_variable: str
    x_bins: int
    y_bins: int
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    x_label: str = ""
    y_label: str = ""
    title: str = ""
    enabled: bool = True
    def __post_init__(self):
        if not self.x_label:
            self.x_label = self.x_variable
        if not self.y_label:
            self.y_label = self.y_variable
        if not self.title:
            self.title = f"{self.y_variable} vs {self.x_variable}"

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
    variable_2d: Optional[Variable2DConfig] = None
    requirements: List[ConfigRequirement] = field(default_factory=list)
    comparisons: List[ComparisonConfig] = field(default_factory=list)
    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> 'AnalysisConfig':
        import yaml, json
        config_path = Path(config_path)
        with open(config_path, 'r') as f:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                config_data = yaml.safe_load(f)
            else:
                config_data = json.load(f)
        if not isinstance(config_data, dict):
            raise ValueError("Configuration file must contain a JSON object or YAML mapping")
        particle_data = config_data.get('particle', {})
        if particle_data:
            config_data['particle'] = ParticleConfig(**particle_data)
        else:
            config_data['particle'] = ParticleConfig()
        surfaces_data = config_data.get('surfaces', [])
        if surfaces_data:
            config_data['surfaces'] = [SurfaceConfig(**surf) for surf in surfaces_data]
        else:
            config_data['surfaces'] = []
        histograms_data = config_data.get('histograms', [])
        if histograms_data:
            config_data['histograms'] = [HistogramConfig(**hist) for hist in histograms_data]
        else:
            config_data['histograms'] = []
        output_data = config_data.get('output', {})
        if output_data:
            config_data['output'] = OutputConfig(**output_data)
        else:
            config_data['output'] = OutputConfig()
        box_surfaces_data = config_data.get('box_surfaces', [])
        if box_surfaces_data:
            config_data['box_surfaces'] = [BoxSurfaceConfig(**box_surf) for box_surf in box_surfaces_data]
        else:
            config_data['box_surfaces'] = []
        new_variable_data = config_data.get('new_variable', None)
        if new_variable_data:
            config_data['new_variable'] = NewVariableConfig(**new_variable_data)
        else:
            config_data['new_variable'] = None
        new_variables_data = config_data.get('new_variables', [])
        if new_variables_data:
            config_data['new_variables'] = [NewVariableConfig(**var) for var in new_variables_data]
        else:
            config_data['new_variables'] = []
        variable_2d_data = config_data.get('variable_2d', None)
        if variable_2d_data:
            config_data['variable_2d'] = Variable2DConfig(**variable_2d_data)
        else:
            config_data['variable_2d'] = None

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

        comparisons_data = config_data.get('comparisons', [])
        if comparisons_data:
            normalized_comparisons = []
            for cmp in comparisons_data:
                if not isinstance(cmp, dict):
                    raise ValueError("Each comparison entry must be a mapping/object.")

                cmp_copy = dict(cmp)
                files_names_labels_order_data = cmp_copy.get('files_names_labels_order', None)
                files_names_label_data = cmp_copy.get('files_names_label', None)
                files_name_data = cmp_copy.get('files_name', None)
                hists_data = cmp_copy.get('hists', None)

                if isinstance(hists_data, list) and hists_data and all(isinstance(row, (list, tuple)) for row in hists_data):
                    rows: List[Tuple[str, str, str, Union[str, int], int]] = []
                    for idx, row in enumerate(hists_data):
                        if not isinstance(row, (list, tuple)) or len(row) != 5:
                            raise ValueError(
                                f"Invalid hists entry at index {idx}: expected [file_path, hist_name, label, color, order]."
                            )
                        file_path, hist_name, label, color, order = row
                        if (
                            not isinstance(file_path, str)
                            or not isinstance(hist_name, str)
                            or not isinstance(label, str)
                            or not isinstance(color, (str, int))
                            or not isinstance(order, int)
                        ):
                            raise ValueError(
                                f"Invalid hists entry at index {idx}: expected [str, str, str, (str|int), int]."
                            )
                        rows.append((file_path, hist_name, label, color, order))

                    cmp_copy['files'] = [file_path for file_path, _, _, _, _ in rows]
                    cmp_copy['hists'] = [hist_name for _, hist_name, _, _, _ in rows]
                    cmp_copy['labels'] = [label for _, _, label, _, _ in rows]
                    cmp_copy['colors'] = [color for _, _, _, color, _ in rows]
                    cmp_copy['legend_order'] = sorted(range(len(rows)), key=lambda i: rows[i][4])
                elif files_names_labels_order_data is not None:
                    rows: List[Tuple[str, str, str, int]] = []
                    if isinstance(files_names_labels_order_data, dict):
                        for file_path, values in files_names_labels_order_data.items():
                            if (
                                not isinstance(file_path, str)
                                or not isinstance(values, (list, tuple))
                                or len(values) != 3
                            ):
                                raise ValueError(
                                    "Invalid files_names_labels_order dictionary entry: expected "
                                    '{"file.root": ["hist_name", "label", order]}.'
                                )
                            hist_name, label, order = values
                            if not isinstance(hist_name, str) or not isinstance(label, str) or not isinstance(order, int):
                                raise ValueError(
                                    "Invalid files_names_labels_order dictionary entry: hist_name/label must be strings and order must be int."
                                )
                            rows.append((file_path, hist_name, label, order))
                    elif isinstance(files_names_labels_order_data, list):
                        for idx, row in enumerate(files_names_labels_order_data):
                            if not isinstance(row, (list, tuple)) or len(row) != 4:
                                raise ValueError(
                                    f"Invalid files_names_labels_order entry at index {idx}: "
                                    "expected [file_path, hist_name, label, order]."
                                )
                            file_path, hist_name, label, order = row
                            if not isinstance(file_path, str) or not isinstance(hist_name, str) or not isinstance(label, str) or not isinstance(order, int):
                                raise ValueError(
                                    f"Invalid files_names_labels_order entry at index {idx}: "
                                    "file_path/hist_name/label must be strings and order must be int."
                                )
                            rows.append((file_path, hist_name, label, order))
                    else:
                        raise ValueError("Invalid files_names_labels_order type: expected list or dictionary.")

                    cmp_copy['files_names_labels_order'] = [
                        [file_path, hist_name, label, order]
                        for file_path, hist_name, label, order in rows
                    ]
                    cmp_copy['files'] = [file_path for file_path, _, _, _ in rows]
                    cmp_copy['hists'] = [hist_name for _, hist_name, _, _ in rows]
                    cmp_copy['labels'] = [label for _, _, label, _ in rows]

                    order_indices = sorted(
                        range(len(rows)),
                        key=lambda i: rows[i][3],
                    )
                    cmp_copy['legend_order'] = order_indices
                elif files_names_label_data is not None:
                    rows: List[Tuple[str, str, str]] = []
                    if isinstance(files_names_label_data, dict):
                        for file_path, values in files_names_label_data.items():
                            if (
                                not isinstance(file_path, str)
                                or not isinstance(values, (list, tuple))
                                or len(values) != 2
                            ):
                                raise ValueError(
                                    "Invalid files_names_label dictionary entry: expected "
                                    '{"file.root": ["hist_name", "label"]}.'
                                )
                            hist_name, label = values
                            if not isinstance(hist_name, str) or not isinstance(label, str):
                                raise ValueError(
                                    "Invalid files_names_label dictionary entry: hist_name and label must be strings."
                                )
                            rows.append((file_path, hist_name, label))
                    elif isinstance(files_names_label_data, list):
                        for idx, row in enumerate(files_names_label_data):
                            if not isinstance(row, (list, tuple)) or len(row) != 3:
                                raise ValueError(
                                    f"Invalid files_names_label entry at index {idx}: "
                                    "expected [file_path, hist_name, label]."
                                )
                            file_path, hist_name, label = row
                            if not isinstance(file_path, str) or not isinstance(hist_name, str) or not isinstance(label, str):
                                raise ValueError(
                                    f"Invalid files_names_label entry at index {idx}: "
                                    "file_path, hist_name, and label must be strings."
                                )
                            rows.append((file_path, hist_name, label))
                    else:
                        raise ValueError("Invalid files_names_label type: expected list or dictionary.")

                    cmp_copy['files_names_label'] = [
                        [file_path, hist_name, label]
                        for file_path, hist_name, label in rows
                    ]
                    cmp_copy['files'] = [file_path for file_path, _, _ in rows]
                    cmp_copy['hists'] = [hist_name for _, hist_name, _ in rows]
                    cmp_copy['labels'] = [label for _, _, label in rows]
                elif files_name_data is not None:
                    pairs: List[Tuple[str, str]] = []
                    if isinstance(files_name_data, dict):
                        for file_path, hist_name in files_name_data.items():
                            if not isinstance(file_path, str) or not isinstance(hist_name, str):
                                raise ValueError("Invalid files_name entry: dictionary keys/values must be strings.")
                            pairs.append((file_path, hist_name))
                    elif isinstance(files_name_data, list):
                        for idx, pair in enumerate(files_name_data):
                            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                                raise ValueError(
                                    f"Invalid files_name entry at index {idx}: expected [file_path, hist_name]."
                                )
                            file_path, hist_name = pair
                            if not isinstance(file_path, str) or not isinstance(hist_name, str):
                                raise ValueError(
                                    f"Invalid files_name entry at index {idx}: file_path and hist_name must be strings."
                                )
                            pairs.append((file_path, hist_name))
                    else:
                        raise ValueError("Invalid files_name type: expected list of pairs or dictionary.")

                    cmp_copy['files_name'] = [[file_path, hist_name] for file_path, hist_name in pairs]
                    cmp_copy['files'] = [file_path for file_path, _ in pairs]
                    cmp_copy['hists'] = [hist_name for _, hist_name in pairs]
                else:
                    files = cmp_copy.get('files', [])
                    hists = cmp_copy.get('hists', [])
                    if not files or not hists:
                        raise ValueError("Comparison must provide either files_name or both files and hists.")

                if len(cmp_copy.get('files', [])) != len(cmp_copy.get('hists', [])):
                    raise ValueError("Comparison configuration error: files and hists must have the same length.")
                if cmp_copy.get('labels') is not None and len(cmp_copy.get('labels', [])) != len(cmp_copy.get('files', [])):
                    raise ValueError("Comparison configuration error: labels must have the same length as files/hists.")

                normalized_comparisons.append(ComparisonConfig(**cmp_copy))
            config_data['comparisons'] = normalized_comparisons
        else:
            config_data['comparisons'] = []
        return cls(**config_data)
