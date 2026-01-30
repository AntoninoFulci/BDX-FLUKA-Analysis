#!/usr/bin/env python3
"""
Unified analysis CLI: processes configs, runs analysis, and handles exports.
"""

import sys
import os
import glob
import argparse
from pathlib import Path
from typing import List, Optional, Tuple

from config import AnalysisConfig
from core import Analysis

try:
    from export_histograms import (
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


def process_single_config(config_path: str, args: argparse.Namespace) -> bool:
    try:
        print(f"\n{'='*60}")
        print(f"Processing config: {config_path}")
        print(f"{'='*60}")

        # Load configuration
        config = AnalysisConfig.from_file(config_path)
        if args.input_dir:
            config.input_directory = args.input_dir
        if args.output_dir:
            config.output.directory = args.output_dir

        # Run analysis
        analyzer = Analysis(config, save_macro=bool(getattr(args, 'save_macro', False)))
        analyzer.process_all_configs()
        print(f"\n{'='*60}")
        print(f"✓ Analysis completed successfully for {config_path}")
        print(f"{'='*60}\n")

        # Save histograms to PDF (default True; --no-save-pdf to skip)
        if args.save_pdf and export_all_analysis_histograms_to_pdf:
            print(f"\n{'='*60}")
            print(f"Saving all histograms to PDF in {config.output.directory}/plots ...")
            energy_ranges = [(hist.min_energy, hist.max_energy) for hist in config.histograms]
            export_all_analysis_histograms_to_pdf(
                config.output.directory,
                particle_name=config.particle.name,
                energy_ranges=energy_ranges,
                save_macro=args.save_macro,
            )
            print("✓ Histograms saved as PDF successfully.")
            print(f"{'='*60}\n")
        elif not args.save_pdf:
            print(f"\n{'='*60}")
            print("↷ Skipping PDF export (disabled by flag).")
            print(f"{'='*60}\n")
        else:
            print(f"\n{'='*60}")
            print("⚠ PDF export helper unavailable; histograms saved only as ROOT files.")
            print(f"{'='*60}\n")

        # Save histogram statistics to Excel (default True; --no-save-hstat to skip)
        if args.save_hstat and export_histogram_statistics_to_excel:
            print(f"\n{'='*60}")
            print(f"Saving histogram statistics to Excel in {config.output.directory} ...")
            energy_ranges = [(hist.min_energy, hist.max_energy) for hist in config.histograms]
            surface_dims = _resolve_surface_dims(config)
            export_histogram_statistics_to_excel(
                config.output.directory,
                particle_name=config.particle.name,
                energy_ranges=energy_ranges,
                excel_filename="histogram_statistics.xlsx",
                surface_dims=surface_dims,
            )
            print("✓ Histogram statistics saved as Excel file!")
            print(f"{'='*60}\n")
        elif not args.save_hstat:
            print(f"\n{'='*60}")
            print("↷ Skipping histogram statistics export (disabled by flag).")
            print(f"{'='*60}\n")
        else:
            print(f"\n{'='*60}")
            print("⚠ Statistics export helper unavailable; no Excel written.")
            print(f"{'='*60}\n")

        return True
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"✗ Error processing {config_path}: {str(e)}")
        print(f"{'='*60}\n")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run BDX Analysis and optionally save histograms and statistics.")
    parser.add_argument("-i", "--input-dir", help="Input directory for simulation ROOT files")
    parser.add_argument("config", nargs='?', help="Path to the configuration file (JSON or YAML)")
    parser.add_argument("--config-dir", help="Directory containing multiple config files to process")
    parser.add_argument("--no-save-pdf", action="store_false", dest="save_pdf", default=True, help="Do not save all histograms to PDF after analysis")
    parser.add_argument("--save-macro", action="store_true", help="Also save each plot as ROOT macro (.C) when exporting PDFs")
    parser.add_argument("--no-save-hstat", action="store_false", dest="save_hstat", default=True, help="Do not save histogram statistics to Excel after analysis")
    parser.add_argument("--output-dir", help="Override output directory from config file")
    args = parser.parse_args()

    # Validate arguments
    if not args.config and not args.config_dir:
        parser.error("Either a config file or --config-dir must be specified")

    if args.config and args.config_dir:
        parser.error("Cannot specify both a config file and --config-dir")

    # Process single config file
    if args.config:
        success = process_single_config(args.config, args)
        if success:
            print("\n✓ All analysis completed successfully!")
        else:
            print("\n✗ Analysis failed!")
            sys.exit(1)
        return

    # Process directory of config files
    if args.config_dir:
        if not os.path.isdir(args.config_dir):
            print(f"Error: Directory '{args.config_dir}' does not exist")
            sys.exit(1)

        config_files = find_config_files(args.config_dir)
        if not config_files:
            print(f"No config files found in directory '{args.config_dir}'")
            sys.exit(1)

        print(f"Found {len(config_files)} config files in '{args.config_dir}':")
        for config_file in config_files:
            print(f"  - {config_file}")

        successful = 0
        failed = 0
        failed_files: List[str] = []

        for i, config_file in enumerate(config_files, 1):
            print(f"\n[{i}/{len(config_files)}] Processing {os.path.basename(config_file)}...")
            if process_single_config(config_file, args):
                successful += 1
            else:
                failed += 1
                failed_files.append(config_file)

        print(f"\n{'='*60}")
        print(f"BATCH PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Total config files: {len(config_files)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")

        if failed > 0:
            print(f"\n⚠ {failed} config file(s) failed to process:")
            for failed_file in failed_files:
                print(f"  - {failed_file}")
            sys.exit(1)
        else:
            print(f"\n✓ All {successful} config files processed successfully!")


if __name__ == "__main__":
    main()
