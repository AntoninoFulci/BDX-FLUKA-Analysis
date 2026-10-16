import ROOT
from ROOT import RDataFrame
from pathlib import Path
from .config import AnalysisConfig
from .simulation_summary import SimulationSummary
from .utils import setup_root, format_energy
from .histogram import HistogramSet
from .comparison import compare_histograms_overlay
from .term_logging import section, info, success, warn, step, table_box

class Analysis:
    def write_histograms(self, output_file, histograms):
        """Write histograms to ROOT file"""
        for hist_set in histograms:
            # Write log histogram only if it exists
            if hist_set.h_log is not None:
                hist_set.h_log.Scale(1/self.EOT, "width")
                hist_set.h_log.Write()
            
            # Always write linear histogram (required)
            hist_set.h_lin.Scale(1/self.EOT, "width")
            hist_set.h_lin.Write()
            
            # Write spatial histogram only if it exists
            if hist_set.h_vertex is not None:
                hist_set.h_vertex.Scale(1/self.EOT)
                hist_set.h_vertex.Write()
    def __init__(self, config: AnalysisConfig, save_macro: bool = False):
        self.config = config
        self.save_macro = save_macro
        self.comparison_only = (
            (not config.histograms)
            and (not config.surfaces)
            and (not config.box_surfaces)
            and (not config.new_variable)
            and (not config.new_variables)
            and config.comparisons
        )
        self.setup_root()
        if not self.comparison_only:
            self.root_dir = str(Path(config.input_directory) / "*.root")
            output_dir = Path(config.output.directory)
            output_dir.mkdir(parents=True, exist_ok=True)
            summary_file_path = output_dir / "simulation_summary.root"
            if getattr(config, 'remove_runsummary', False) and summary_file_path.exists():
                warn(f"Removing existing simulation summary file: {summary_file_path}")
                summary_file_path.unlink()
            if summary_file_path.exists():
                warn(
                    f"Reusing cached EOT from {summary_file_path}; input identity is not verified. "
                    "If the input dataset changed, use --remove-runsummary to regenerate it "
                    "or choose a different output directory."
                )
                self.EOT = SimulationSummary.read_eot_from_file(str(summary_file_path))
            else:
                info(f"Creating new simulation summary file: {summary_file_path}")
                with ROOT.TFile(str(summary_file_path), "RECREATE") as summary_file:
                    RSummary = RDataFrame("RunSummary", self.root_dir)
                    summary = SimulationSummary(RSummary)
                    self.EOT = summary.process_summary(summary_file)

    def setup_root(self):
        self.set_style, self.stileh1, self.stileh2, self.quiet = setup_root()

    def process_comparisons(self):
        if not self.config.comparisons:
            return
        info(f"Processing {len(self.config.comparisons)} histogram comparisons...")
        for cmp in self.config.comparisons:
            # Propagate save_macro flag from analysis CLI into comparison config dynamically
            try:
                setattr(cmp, 'save_macro', bool(self.save_macro))
            except Exception:
                pass
            # Use default output directory only if comparison doesn't specify its own
            default_output_dir = getattr(self.config, 'output', None)
            default_output_dir = getattr(default_output_dir, 'directory', None) if default_output_dir else None
            compare_histograms_overlay(cmp, output_dir=default_output_dir)

    def process_all_configs(self):
        if self.comparison_only:
            self.process_comparisons()
            return
        info(f"Processing {self.config.particle.name} analysis...")
        info(f"Input directory: {self.config.input_directory}")
        info(f"Number of histogram configurations: {len(self.config.histograms)}")
        output_filenames = [
            self.config.output.get_filename(self.config.particle, hist_config)
            for hist_config in self.config.histograms
        ]
        if len(set(output_filenames)) != len(output_filenames):
            raise ValueError(
                "Histogram configurations produce the same output filename; "
                "adjust the energy ranges, bin counts, or output format_template."
            )
        for hist_config, output_filename in zip(self.config.histograms, output_filenames):
            section("Processing histogram configuration")
            info(f"Number of bins: {hist_config.n_bins}")
            info(f"Energy range: {format_energy(hist_config.min_energy)} - {format_energy(hist_config.max_energy)}")
            info(f"Log bins: {hist_config.also_log_bins}")
            info(f"Output file: {output_filename}")
            REvents = RDataFrame("Events", self.root_dir)
            Path(output_filename).parent.mkdir(parents=True, exist_ok=True)
            with ROOT.TFile(output_filename, "RECREATE") as output_file:
                histograms = self.create_histograms(REvents, hist_config)
                step(f"Writing histograms to {output_filename}...")
                self.write_histograms(output_file, histograms)
            success(f"Completed: {output_filename}")
        self.process_comparisons()

    def create_histograms(self, REvents, hist_config):
        """Create histograms for a given configuration"""
        step("Creating filters...")
        filters = self._create_filters(REvents)
        step("Creating histograms...")
        histograms = self._create_histograms(filters, hist_config)
        return histograms

    def _add_new_variables(self, REvents):
        """Add new variables to the RDataFrame as defined in configuration"""
        df = REvents
        
        # Add single new_variable if defined
        if self.config.new_variable:
            print(f"  Creating new variable: {self.config.new_variable.name} = {self.config.new_variable.expression}")
            df = df.Define(self.config.new_variable.name, self.config.new_variable.expression)
        
        # Add multiple new_variables if defined
        if self.config.new_variables:
            for new_var in self.config.new_variables:
                print(f"  Creating new variable: {new_var.name} = {new_var.expression}")
                df = df.Define(new_var.name, new_var.expression)
        
        return df

    def _create_filters(self, REvents):
        """Create all filters based on configuration"""
        # First, create any new variables that are defined in the configuration
        df = self._add_new_variables(REvents)
        
        particle_filter = df.Filter(self.config.particle.get_filter_expression())
        surface_filters = {}
        for surface in getattr(self.config, 'surfaces', []):
            surf_filter = particle_filter.Filter(f"SurfaceID == {surface.id}")
            surface_filters[surface.id] = surf_filter
        box_filters = {}
        for box_surface in getattr(self.config, 'box_surfaces', []):
            box_filter = particle_filter.Filter(f"SurfaceID == {box_surface.surface_id}")
            face_configs = box_surface.get_face_configs()
            box_filters[box_surface.name] = {
                face_name: box_filter.Filter(face_config["condition"])
                for face_name, face_config in face_configs.items()
            }
        return {
            'surfaces': getattr(self.config, 'surfaces', []),
            'surface_filters': surface_filters,
            'box_filters': box_filters
        }

    def _create_energy_histograms(self, dataframe, hist_config, surface_name):
        """Book spectra after the caller applies its energy and spatial selection."""
        particle = self.config.particle
        name = f"{particle.name}_h1_{surface_name}"
        title = f"; {particle.variable} [GeV]; n/(GeV * EOT)"
        with self.set_style(self.stileh1):
            h_log = None
            if hist_config.also_log_bins:
                h_log = dataframe.Histo1D(
                    (f"{name}_log", title, hist_config.n_bins, hist_config.log_bins),
                    particle.variable, particle.weight,
                )
            h_lin = dataframe.Histo1D(
                (f"{name}_lin", title, hist_config.n_bins,
                 hist_config.min_energy, hist_config.max_energy),
                particle.variable, particle.weight,
            )
        return h_log, h_lin

    def _create_histograms(self, filters, hist_config):
        """Create histograms using the filters"""
        histograms = []

        regular_surfaces = filters.get('surfaces', [])
        if regular_surfaces:
            table_box(
                "Surfaces",
                ["Surface", "ID"],
                [[surface.name, str(surface.id)] for surface in regular_surfaces],
            )

        # Regular surfaces
        for surface in regular_surfaces:
            if surface.id in filters['surface_filters']:
                surf_filter = filters['surface_filters'][surface.id]
                energy_filtered = surf_filter.Filter(
                    f"{self.config.particle.variable} >= {hist_config.min_energy} && {self.config.particle.variable} <= {hist_config.max_energy}"
                )
                # Get flexible axis configuration
                x_var, y_var = surface.get_axis_variables()
                # Apply spatial bounds for 1D histograms using configured surface size
                spatial_filtered_for_1d = energy_filtered.Filter(
                    f"{x_var} >= {surface.x_min} && {x_var} <= {surface.x_max} && {y_var} >= {surface.y_min} && {y_var} <= {surface.y_max}"
                )
                x_label, y_label = surface.get_axis_labels()
                nbins_x = int((surface.x_max - surface.x_min) / surface.bin_width)
                nbins_y = int((surface.y_max - surface.y_min) / surface.bin_width)
                h_log, h_lin = self._create_energy_histograms(
                    spatial_filtered_for_1d, hist_config, surface.name
                )
                with self.set_style(self.stileh2):
                    surface_name = surface.name or f"surf_{surface.id}"
                    if surface.spatial_analysis:
                        h_vertex = energy_filtered.Histo2D(
                            (f"{self.config.particle.name}_h2_{surface_name}",
                             f"; {x_label}; {y_label}; n/(EOT)",
                             nbins_x, surface.x_min, surface.x_max, nbins_y, surface.y_min, surface.y_max),
                            x_var, y_var, self.config.particle.weight)
                    else:
                        h_vertex = None  # Don't create spatial histogram when spatial_analysis is False
                histograms.append(HistogramSet(surface_name, h_log, h_lin, h_vertex))
        # Box surfaces
        if "box_filters" in filters:
            for box_name, face_filters in filters["box_filters"].items():
                print(f"  Processing box surface: {box_name}")
                box_surface = next((bs for bs in getattr(self.config, 'box_surfaces', []) if bs.name == box_name), None)
                if not box_surface:
                    continue
                for face_name, face_filter in face_filters.items():
                    energy_filtered_face = face_filter.Filter(
                        f"{self.config.particle.variable} >= {hist_config.min_energy} && {self.config.particle.variable} <= {hist_config.max_energy}"
                    )
                    h_log, h_lin = self._create_energy_histograms(
                        energy_filtered_face, hist_config, f"{box_name}_{face_name}"
                    )
                    with self.set_style(self.stileh2):
                        if box_surface.spatial_analysis:
                            x_bins, y_bins, xlow, xhigh, ylow, yhigh, x_dim, y_dim = \
                                box_surface.get_histogram_params(face_name)
                            h_vertex = energy_filtered_face.Histo2D(
                                (f"{self.config.particle.name}_h2_{box_name}_{face_name}",
                                 f"; {x_dim} [cm]; {y_dim} [cm]; n/(EOT)",
                                 x_bins, xlow, xhigh, y_bins, ylow, yhigh),
                                x_dim, y_dim, self.config.particle.weight)
                        else:
                            h_vertex = None  # Don't create spatial histogram when spatial_analysis is False
                    histograms.append(HistogramSet(f"{box_name}_{face_name}", h_log, h_lin, h_vertex))
        return histograms
