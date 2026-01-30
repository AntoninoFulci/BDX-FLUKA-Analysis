import ROOT
from ROOT import RDataFrame
from pathlib import Path
from config import AnalysisConfig
from simulation_summary import SimulationSummary
from utils import setup_root, format_energy
from histogram import HistogramSet
from comparison import compare_histograms_overlay

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
            and (not config.variable_2d)
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
            if summary_file_path.exists():
                print(f"Reading EOT from existing summary file: {summary_file_path}")
                self.EOT = SimulationSummary.read_eot_from_file(str(summary_file_path))
            else:
                print(f"Creating new simulation summary file: {summary_file_path}")
                summary_file = ROOT.TFile(str(summary_file_path), "RECREATE")
                RSummary = RDataFrame("RunSummary", self.root_dir)
                summary = SimulationSummary(RSummary)
                self.EOT = summary.process_summary(summary_file)
                summary_file.Close()

    def setup_root(self):
        self.set_style, self.stileh1, self.stileh2, self.quiet = setup_root()

    def process_comparisons(self):
        if not self.config.comparisons:
            return
        print(f"\nProcessing {len(self.config.comparisons)} histogram comparisons...")
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
        print(f"\nProcessing {self.config.particle.name} analysis...")
        print(f"Input directory: {self.config.input_directory}")
        print(f"Number of histogram configurations: {len(self.config.histograms)}")
        for hist_config in self.config.histograms:
            print(f"\nProcessing histogram configuration:")
            print(f"  Number of bins: {hist_config.n_bins}")
            print(f"  Energy range: {format_energy(hist_config.min_energy)} - {format_energy(hist_config.max_energy)}")
            print(f"  Log bins: {hist_config.also_log_bins}")
            output_filename = self.config.output.get_filename(self.config.particle, hist_config)
            print(f"  Output file: {output_filename}")
            REvents = RDataFrame("Events", self.root_dir)
            output_file = ROOT.TFile(output_filename, "RECREATE")
            histograms = self.create_histograms(REvents, hist_config)
            print(f"  Writing histograms to {output_filename}...")
            self.write_histograms(output_file, histograms)
            output_file.Close()
            print(f"  Completed: {output_filename}")
        self.process_comparisons()

    def create_histograms(self, REvents, hist_config):
        """Create histograms for a given configuration"""
        print("  Creating filters...")
        filters = self._create_filters(REvents)
        print("  Creating histograms...")
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

    def _create_histograms(self, filters, hist_config):
        """Create histograms using the filters"""
        from histogram import HistogramSet
        histograms = []
        # Regular surfaces
        for surface in filters['surfaces']:
            if surface.id in filters['surface_filters']:
                print(f"  Processing surface {surface.name} (ID: {surface.id})")
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
                with self.set_style(self.stileh1):
                    if hist_config.also_log_bins:
                        h_log = spatial_filtered_for_1d.Histo1D(
                            (f"{self.config.particle.name}_h1_{surface.name}_log",
                             f"; {self.config.particle.variable} [GeV]; n/(GeV * EOT)",
                             hist_config.n_bins, hist_config.log_bins),
                            self.config.particle.variable, self.config.particle.weight)
                    else:
                        h_log = None  # Don't create log histogram when also_log_bins is False
                    h_lin = spatial_filtered_for_1d.Histo1D(
                        (f"{self.config.particle.name}_h1_{surface.name}_lin",
                         f"; {self.config.particle.variable} [GeV]; n/(GeV * EOT)",
                         hist_config.n_bins, hist_config.min_energy, hist_config.max_energy),
                        self.config.particle.variable, self.config.particle.weight)
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
                    with self.set_style(self.stileh1):
                        if hist_config.also_log_bins:
                            h_log = energy_filtered_face.Histo1D(
                                (f"{self.config.particle.name}_h1_{box_name}_{face_name}_log",
                                 f"; {self.config.particle.variable} [GeV]; n/(GeV * EOT)",
                                 hist_config.n_bins, hist_config.log_bins),
                                self.config.particle.variable, self.config.particle.weight)
                        else:
                            h_log = None  # Don't create log histogram when also_log_bins is False
                        h_lin = energy_filtered_face.Histo1D(
                            (f"{self.config.particle.name}_h1_{box_name}_{face_name}_lin",
                             f"; {self.config.particle.variable} [GeV]; n/(GeV * EOT)",
                             hist_config.n_bins, hist_config.min_energy, hist_config.max_energy),
                            self.config.particle.variable, self.config.particle.weight)
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
