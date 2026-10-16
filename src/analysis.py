#!/usr/bin/env python3
"""
Unified analysis CLI: processes configs, runs analysis, and handles exports.
"""

import sys
import os
import glob
import argparse
from typing import List, Optional, Set, Tuple

from .config import AnalysisConfig
from .core import Analysis
from .term_logging import section, info, success, warn, error, step, table_box

try:
    from .export_histograms import (
        export_all_analysis_histograms_to_pdf,
        export_histogram_statistics_to_excel,
    )
except Exception:
    export_all_analysis_histograms_to_pdf = None
    export_histogram_statistics_to_excel = None


def find_config_files(config_dir: str) -> List[str]:
    config_extensions = ['*.yaml', '*.yml', '*.json']
    config_files = set()
    for ext in config_extensions:
        pattern = os.path.join(config_dir, '**', ext)
        config_files.update(glob.glob(pattern, recursive=True))
    return sorted(list(config_files))


def _resolve_surface_dims(config: AnalysisConfig) -> Optional[Tuple[float, float, float, float]]:
    try:
        if getattr(config, 'surfaces', None) and len(config.surfaces) > 0:
            surf = config.surfaces[0]
            xl = getattr(surf, 'x_min', getattr(surf, 'xl', None))
            xh = getattr(surf, 'x_max', getattr(surf, 'xh', None))
            yl = getattr(surf, 'y_min', getattr(surf, 'yl', None))
            yh = getattr(surf, 'y_max', getattr(surf, 'yh', None))
            if xl is not None and xh is not None and yl is not None and yh is not None:
                return (xl, xh, yl, yh)
    except Exception:
        return None
    return None


def process_single_config(config_path: str, args: argparse.Namespace, processed_configs: Optional[Set[str]] = None) -> bool:
    if processed_configs is None:
        processed_configs = set()
    config_path = os.path.abspath(config_path)
    if config_path in processed_configs:
        error(f"Circular requirement dependency detected for config: {config_path}")
        return False
    processed_configs.add(config_path)

    try:
        section(f"Processing config: {config_path}")

        # Load configuration
        config = AnalysisConfig.from_file(config_path)
        if args.input_dir:
            config.input_directory = args.input_dir
        if args.output_dir:
            config.output.directory = args.output_dir
        if getattr(args, 'remove_runsummary', False):
            config.remove_runsummary = True

        if config.requirements:
            table_box(
                "Config Requirements",
                ["Path", "Enabled"],
                [[req.path, str(req.enabled)] for req in config.requirements],
            )
            for req in config.requirements:
                req_path = req.path
                if not os.path.isabs(req_path):
                    req_path = os.path.join(os.path.dirname(config_path), req_path)
                if not req.enabled:
                    info(f"Skipping disabled prerequisite: {req_path}")
                    continue
                if not os.path.exists(req_path):
                    error(f"Required config file not found: {req_path}")
                    return False
                section(f"Running prerequisite config: {req_path}")
                if not process_single_config(req_path, args, processed_configs):
                    error(f"Prerequisite config failed: {req_path}")
                    return False

        # Run analysis
        analyzer = Analysis(config, save_macro=bool(getattr(args, 'save_macro', False)))
        analyzer.process_all_configs()
        success(f"Analysis completed successfully for {config_path}")

        # Save histograms to PDF (default True; --no-save-pdf to skip)
        if args.save_pdf and export_all_analysis_histograms_to_pdf:
            section("PDF export")
            step(f"Saving all histograms to PDF in {config.output.directory}/plots ...")
            energy_ranges = [(hist.min_energy, hist.max_energy) for hist in config.histograms]
            export_all_analysis_histograms_to_pdf(
                config.output.directory,
                particle_name=config.particle.name,
                energy_ranges=energy_ranges,
                save_macro=args.save_macro,
                output_config=config.output,
            )
            success("Histograms saved as PDF successfully.")
        elif not args.save_pdf:
            info("Skipping PDF export (disabled by flag).")
        else:
            warn("PDF export helper unavailable; histograms saved only as ROOT files.")

        # Save histogram statistics to Excel (default True; --no-save-hstat to skip)
        if args.save_hstat and export_histogram_statistics_to_excel:
            section("Statistics export")
            step(f"Saving histogram statistics to Excel in {config.output.directory} ...")
            energy_ranges = [(hist.min_energy, hist.max_energy) for hist in config.histograms]
            surface_dims = _resolve_surface_dims(config)
            export_histogram_statistics_to_excel(
                config.output.directory,
                particle_name=config.particle.name,
                energy_ranges=energy_ranges,
                excel_filename="histogram_statistics.xlsx",
                surface_dims=surface_dims,
                output_config=config.output,
            )
            success("Histogram statistics saved as Excel file.")
        elif not args.save_hstat:
            info("Skipping histogram statistics export (disabled by flag).")
        else:
            warn("Statistics export helper unavailable; no Excel written.")

        return True
    except Exception as e:
        error(f"Error processing {config_path}: {str(e)}")
        return False
    finally:
        # Only ancestors on the active recursion path constitute a cycle.
        processed_configs.remove(config_path)


def main():
    parser = argparse.ArgumentParser(description="Run BDX Analysis and optionally save histograms and statistics.")
    parser.add_argument("-i", "--input-dir", help="Input directory for simulation ROOT files")
    parser.add_argument("config", nargs='?', help="Path to the configuration file (JSON or YAML)")
    parser.add_argument("--config-dir", help="Directory containing multiple config files to process")
    parser.add_argument("--no-save-pdf", action="store_false", dest="save_pdf", default=True, help="Do not save all histograms to PDF after analysis")
    parser.add_argument("--save-macro", action="store_true", help="Also save each plot as ROOT macro (.C) when exporting PDFs")
    parser.add_argument("--no-save-hstat", action="store_false", dest="save_hstat", default=True, help="Do not save histogram statistics to Excel after analysis")
    parser.add_argument("--remove-runsummary", action="store_true", dest="remove_runsummary", help="Remove existing simulation_summary.root before running the analysis")
    parser.add_argument("--output-dir", help="Override output directory from config file")
    args = parser.parse_args()

    # Validate arguments
    if not args.config and not args.config_dir:
        parser.error("Either a config file or --config-dir must be specified")

    if args.config and args.config_dir:
        parser.error("Cannot specify both a config file and --config-dir")

    # Process single config file
    if args.config:
        success_flag = process_single_config(args.config, args)
        if success_flag:
            success("All analysis completed successfully.")
        else:
            error("Analysis failed.")
            sys.exit(1)
        return

    # Process directory of config files
    if args.config_dir:
        if not os.path.isdir(args.config_dir):
            error(f"Directory '{args.config_dir}' does not exist")
            sys.exit(1)

        config_files = find_config_files(args.config_dir)
        if not config_files:
            warn(f"No config files found in directory '{args.config_dir}'")
            sys.exit(1)

        info(f"Found {len(config_files)} config files in '{args.config_dir}':")
        for config_file in config_files:
            info(f"- {config_file}")

        successful = 0
        failed = 0
        failed_files: List[str] = []

        for i, config_file in enumerate(config_files, 1):
            section(f"[{i}/{len(config_files)}] Processing {os.path.basename(config_file)}")
            if process_single_config(config_file, args):
                successful += 1
            else:
                failed += 1
                failed_files.append(config_file)

        section("BATCH PROCESSING SUMMARY")
        info(f"Total config files: {len(config_files)}")
        success(f"Successful: {successful}")
        if failed:
            error(f"Failed: {failed}")
        else:
            info("Failed: 0")

        if failed > 0:
            warn(f"{failed} config file(s) failed to process:")
            for failed_file in failed_files:
                error(f"- {failed_file}")
            sys.exit(1)
        else:
            success(f"All {successful} config files processed successfully.")


if __name__ == "__main__":
    main()
