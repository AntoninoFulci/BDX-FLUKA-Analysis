# BDX Analysis System

## Overview

This is an analsysis Python-based framework for analyzing particle physics simulation data from ROOT files produced by FLUKA simulation using [FlukaROOTOutput](https://github.com/AntoninoFulci/FlukaROOTOutput).

For example, we have the following typical analysis outputs:

<div align="center">
  <img src="imgs/01_plot1d.png" width="300">
  <img src="imgs/02_plot2d.png" width="300">
</div>

<div align="center">
  <img src="imgs/03_plot1d_comparison.png" width="605">
</div>



### Key Features
- **Configuration-driven analysis** via YAML/JSON files
- **Multi-particle support** with flexible filtering
- **Energy histogram generation** with linear and logarithmic binning
- **Spatial analysis** for surface and volume intersections
- **New variable creation** for derived quantities
- **Histogram comparison** and overlay plotting
- **PDF export utilities** for results visualization
- **Parallel processing** via ROOT's RDataFrame

### Project Structure
```
BDX-FLUKA-Analysis/
├── run_analysis.py               # Main entry point
├── src/                          # Core library modules
│   ├── __init__.py               # Package initialization
│   ├── core.py                   # Main analysis engine
│   ├── config.py                 # Configuration data classes
│   ├── utils.py                  # Utility functions
│   ├── histogram.py              # Histogram data structures
│   ├── simulation_summary.py     # Summary data processing
│   ├── export_histograms.py      # PDF export functionality
│   └── comparison.py             # Histogram comparison tools
├── configs/                      # Configuration files
│   └── examples/                 # Example configurations
└── README.md                     # This file
```

---

## Getting Started

### Prerequisites
- Python 3.7+
- ROOT 6.22+ with PyROOT
- Required Python packages: `pint`, `numpy`, `pyyaml`, `pandas` (optional), `tabulate` (optional)

### Quick Start

1. **Basic Analysis Run:**
```bash
./run_analysis.py configs/particles/neutrons.yaml
```

2. **With Custom Input Directory:**
```bash
./run_analysis.py -i ../SimulationData --output-dir Results configs/particles/neutrons.yaml
```

The PDF export creates an organized `plots/` directory with descriptive filenames, for example by using [01_particle_analysis](configs/examples/01_particle_analysis.yaml):
- `01_1000bins_0.1eV_6.0GeV_neutrons_h1_enclose_lin.pdf` - Linear energy histogram (1st energy range)
- `01_1000bins_0.1eV_6.0GeV_neutrons_h1_enclose_log.pdf` - Logarithmic energy histogram (1st energy range)  
- `01_1000bins_0.1eV_6.0GeV_neutrons_h2_enclose.pdf` - 2D spatial histogram (1st energy range)
- `02_100bins_0.1eV_100.0eV_neutrons_h1_enclose_lin.pdf` - Linear energy histogram (2nd energy range)
- ... and so on for all energy ranges

The filename format is: `{order}_{binning}_{min_energy}_{max_energy}_{histogram_name}.pdf`

### Command Line Options
- `-i, --input-dir`: Override input directory for ROOT files
- `--output-dir`: Override output directory for results
- `--no-save-pdf`: Skip PDF export (enabled by default)
- `--no-save-hstat`: Skip histogram statistics export (enabled by default)
- `--save-macro`: Also save plots as ROOT macros (`.C`)
- `--remove-runsummary`: Recompute the cached simulation summary and EOT

Run the same CLI with `python3 -m src.analysis` from the project root.
Python callers can use `import src`; adding `src/` to `sys.path` is unnecessary.

Reusing `simulation_summary.root` emits a warning: the cached EOT is not
checked against the current input dataset. If inputs changed, choose a new
output directory or pass `--remove-runsummary` to rebuild the summary.

---

## System Architecture

### Data Flow
```
ROOT Files → RDataFrame → Filters → Histograms → Output Files
     ↓           ↓          ↓          ↓           ↓
Configuration → Variables → Particles → Analysis → Results
```

### Core Processing Pipeline
1. **Configuration Loading**: Parse YAML/JSON configuration files
2. **Data Initialization**: Create RDataFrame from ROOT file pattern
3. **Variable Creation**: Define new computed variables if specified
4. **Particle Filtering**: Apply particle type and energy filters
5. **Surface/Volume Analysis**: Process spatial intersection data
6. **Histogram Generation**: Create 1D energy and 2D spatial histograms
7. **Output Writing**: Save histograms to ROOT files
8. **Comparison Processing**: Generate overlay plots if configured

---

## Configuration Guide

### Configuration File Structure

All analysis parameters are defined in YAML or JSON configuration files. Here's the complete structure:

```yaml
input_directory: /path/to/simulation/data
particle:
  particle_id: 8
  name: neutrons
  variable: EKin
  weight: Weight1
new_variable:
  name: EKin
  expression: ETot - 0.939565378
new_variables:
- name: Beta
  expression: P / ETot
- name: Gamma
  expression: ETot / 0.939565378
output:
  base_name: analysis
  directory: ./output
  include_timestamp: false
  format_template: '{base_name}_{particle_name}_{n_bins}bins_{min_energy}_{max_energy}.root'
histograms:
- n_bins: 1000
  min_energy: 1.0e-10
  max_energy: 6.0
  also_log_bins: true
- n_bins: 100
  min_energy: 0.001
  max_energy: 0.1
  also_log_bins: false
surfaces:
- id: 1000
  name: enclose
  xl: -250
  xh: 250
  yl: -250
  yh: 250
  bin_width: 0.5
  spatial_analysis: true
box_surfaces:
- name: detector
  surface_id: 101
  xmin: -51.0
  xmax: 51.0
  ymin: -51.0
  ymax: 51.0
  zmin: 7468.0
  zmax: 7761.2
  bin_width: 0.5
comparisons:
- hists:
  - [output1.root, neutrons_h1_enclose_lin, Configuration A, kP6Blue, 0]
  - [output2.root, neutrons_h1_enclose_lin, Configuration B, kP6Yellow, 1]
  output: comparison_plot
  title: Energy Comparison
  x_label: Energy [GeV]
  y_label: Rate [Hz]
  logx: true
  logy: true
```

### Particle Configuration
NB: use the particle ID as specified in the FLUKA manual [Particle Codes].(https://flukafiles.web.cern.ch/manual/chapters/particle_and_material_codes/particles_codes.html)
#### Single Particle Type
```yaml
particle:
  particle_id: 8        # Neutron
  name: "neutrons"
  variable: "EKin"
  weight: "Weight1"
```

#### Multiple Particle Types
```yaml
particle:
  particle_id: [11, -11]  # Electrons and positrons
  name: "electrons"
  variable: "P"
  weight: "Weight1"
```

#### Common Particle IDs
- `8`: Neutron
- `3`: Electron
- `4`: Positron
- `10`: Mu+
- `11`: Mu-
- `7`: Photon

### Energy Range Configuration
All energies are in GeV.
#### Linear Binning
```yaml
histograms:
  - n_bins: 100
    min_energy: 0.001      # 1 MeV
    max_energy: 1.0        # 1 GeV
    also_log_bins: false
```

#### Logarithmic Binning
```yaml
histograms:
  - n_bins: 1000
    min_energy: 1.0e-10    # 0.1 eV
    max_energy: 6.0        # 6 GeV
    also_log_bins: true
```

### Surface Analysis Configuration

#### Standard Surfaces
```yaml
surfaces:
  - id: 1000              # Surface ID from simulation
    name: "exit_window"
    xl: -100              # X range for spatial histogram
    xh: 100
    yl: -100              # Y range for spatial histogram
    yh: 100
    bin_width: 1.0        # Spatial bin size in cm
    spatial_analysis: true # Enable 2D spatial histograms
```

#### Box Volume Analysis
```yaml
box_surfaces:
  - name: "detector_volume"
    surface_id: 101
    xmin: -50.0
    xmax: 50.0
    ymin: -50.0
    ymax: 50.0
    zmin: 7400.0
    zmax: 7800.0
    bin_width: 2.0
```

---

## Usage Examples

### Basic Neutron Analysis

```yaml
# configs/particles/neutrons_basic.yaml
input_directory: "/path/to/simulation"
particle:
  particle_id: 8
  name: "neutrons"
  variable: "EKin"
  weight: "Weight1"

new_variable:
  name: "EKin"
  expression: "ETot - 0.939565378"

histograms:
  - n_bins: 1000
    min_energy: 1.0e-10
    max_energy: 6.0
    also_log_bins: true

surfaces:
  - id: 1000
    name: "detector"
    spatial_analysis: true

output:
  directory: "./results"
```

**Run the analysis:**
```bash
./run_analysis.py configs/particles/neutrons_basic.yaml
```

### Multi-Energy Range Analysis

```yaml
# Detailed energy spectrum analysis
histograms:
  # Thermal neutron range
  - n_bins: 100
    min_energy: 1.0e-10  # 0.1 eV
    max_energy: 1.0e-7   # 100 eV
    also_log_bins: false
  
  # Epithermal range
  - n_bins: 100
    min_energy: 1.0e-7   # 100 eV
    max_energy: 0.0001   # 100 keV
    also_log_bins: false
  
  # Fast neutron range
  - n_bins: 100
    min_energy: 0.001    # 1 MeV
    max_energy: 6.0      # 6 GeV
    also_log_bins: false
```

### Spatial Analysis Configuration

```yaml
# Multiple detector surfaces
surfaces:
  - id: 1
    name: "entrance_window"
    xl: -200
    xh: 200
    yl: -200
    yh: 200
    bin_width: 2.0
  
  - id: 2
    name: "detector_face"
    xl: -100
    xh: 100
    yl: -100
    yh: 100
    bin_width: 1.0

# 3D detector volume
box_surfaces:
  - name: "main_detector"
    surface_id: 101
    xmin: -51.0
    xmax: 51.0
    ymin: -51.0
    ymax: 51.0
    zmin: 7468.0
    zmax: 7761.2
    bin_width: 1.0
```

### Comparison Analysis

```yaml
comparisons:
- hists:
  - [results/config_a.root, neutrons_h1_detector_lin, Configuration A, kP6Blue, 0]
  - [results/config_b.root, neutrons_h1_detector_lin, Configuration B, kP6Yellow,
    1]
  output: config_comparison
  title: Configuration Comparison
  x_label: Kinetic Energy [GeV]
  y_label: "Rate [1/(GeV\xB7EOT)]"
  logx: true
  logy: true
  x_min: 1.0e-08
  x_max: 6.0
```
---

## Advanced Features

### 1. Custom Energy Variables

The system supports creating derived energy variables using ROOT's expression syntax:

```yaml
new_variable:
  name: "EKin"
  expression: "ETot - 0.939565378"  # Kinetic energy for neutrons
```

### 2. Multi-Particle Analysis

Analyze multiple particle types simultaneously:

```yaml
particle:
  particle_id: [10, 11, 3, 4]  # Electrons, positrons, muons, anti-muons
  name: "leptons"
  variable: "P"
  weight: "Weight1"
```

### 3. Statistical Weighting

All histograms support statistical weights for proper normalization:

```yaml
particle:
  weight: "Weight1"  # Use simulation weights
```

Common weight variables:
- `Weight1`: Primary weight
- `Weight2`: Secondary weight
- `1.0`: Uniform weighting (no weights)

### 4. Flexible Output Naming

Customize output file naming with template strings:

```yaml
output:
  format_template: '{base_name}_{particle_name}_{n_bins}bins_{min_energy}_{max_energy}.root'
  include_timestamp: true  # Add timestamp to filename
```

PDF and statistics exports use the same `OutputConfig` template to find files,
including custom prefixes, separators, subdirectories and timestamps. The default
filename is unchanged. Keep both `{min_energy}` and `{max_energy}` in custom
templates for energy-range sorting and statistics labels. Energies are formatted
strings with units; `{n_bins}` is an integer and accepts numeric format specs.

### 5. Histogram Comparison

Generate overlay plots comparing multiple analyses:

```yaml
comparisons:
- hists:
  - [file1.root, hist_name, Label 1, kP6Blue, 0]
  - [file2.root, hist_name, Label 2, kP6Yellow, 1]
  output: comparison_plot
  x_min: 1.0e-06
  x_max: 1.0
  y_min: 1.0e-10
  y_max: 0.01
```

Each comparison uses one format: `hists` rows contain
`[file_path, histogram_name, label, color, legend_order]`. Lower numeric order
appears first in the legend. Colors accept ROOT color names or integer codes.
Separate `files`, `labels`, `colors`, `legend_order`, `labels_and_colors`, and
`files_name` / `files_names_label` / `files_names_labels_order` fields are no
longer supported in YAML/JSON. Move their values into the five-field rows.

A comparison requires at least two available histograms. Fewer inputs cause an
error and a nonzero CLI exit status. Missing histograms still produce warnings
when at least two remain; labels, colors and legend order retain their input
identities. ROOT files and canvases are closed on success and on exceptions.

The unused `variable_2d` configuration and `Variable2DConfig` class were removed.
That option never produced analysis output; configurations containing it now
raise an explicit error. Spatial histograms configured through surfaces and boxes
remain supported.

#### Rebinning before smoothing

Set `rebin` on a comparison to group adjacent energy bins before plotting:

```yaml
comparisons:
  - output: rebinned_spectra
    hists:
      - [file1.root, spectrum_log, Sample A, kP6Blue, 0]
      - [file2.root, spectrum_log, Sample B, kP6Yellow, 1]
    rebin: [5, 10]
    rebin_hists: [1]  # Only Sample B; ["Sample B"] is equivalent.
    smoothing: overlay
    smoothing_sigma: 2
    smooth_hists: [1]
```

`rebin: 5` merges each group of five bins in the selected input spectra.
Default `1` leaves binning unchanged. `rebin_hists` accepts zero-based indices
from the original `hists` rows, exact labels, or a mixture. Omit it (or use `null`)
to select all spectra; `[]` selects none. Unselected spectra keep their original
binning. Invalid indices, unknown labels and ambiguous duplicate labels are errors;
use an index to distinguish identical labels. Missing histograms do not shift indices.

A list such as `rebin: [5, 10]` produces one independent comparison per factor,
in the specified order: `rebinned_spectra_rebin5.pdf` and
`rebinned_spectra_rebin10.pdf` in this example. Each starts from the original
inputs. Excel and optional ROOT macros use the same suffixes. A scalar retains
the original output filename; a one-element list still adds the suffix.
Use `[1, 5, 10]` to include a figure with the original binning. Empty lists,
duplicate factors and non-positive/non-integer factors are rejected.

Each factor must divide every selected, available histogram's bin count exactly.
Unselected histograms do not have this restriction. This prevents ROOT from moving
leftover high-energy bins into overflow and shortening the plotted range.
Rebinning supports floating-point 1D spectra (`TH1F`/`TH1D`), including variable
bin widths; profiles and spatial histograms are not supported by this option.

The project stores spectra as densities, such as n/(GeV·EOT). Each input is cloned
and detached from its file. Contents and errors are multiplied by the original
bin widths, grouped with ROOT `Rebin(N)`, then divided by the new widths. The
width-weighted integral and its uncertainty are preserved up to floating-point
roundoff. Input ROOT files stay unchanged; Excel statistics use the original
unsmoothed histograms.

Order: **rebin → axis setup → optional Gaussian smoothing → draw**. In `overlay`
mode both the faint curve and its smoothed clone use the new binning.
`smooth_hists` and `rebin_hists` select curves independently.
`smoothing_sigma` counts bins **after any selected rebinning** and stays unchanged
across variants, so a fixed value spans a wider energy range after rebinning.
Smoothing remains a visualization and does not guarantee
integral conservation; the conservation guarantee applies to rebinning.

Reference: [ROOT TH1::Rebin documentation](https://root.cern.ch/doc/master/classTH1.html).
ROOT sums grouped contents and propagates stored `Sumw2` errors; width conversions
above preserve this project's density normalization.

---

*Last updated: October 2026*
