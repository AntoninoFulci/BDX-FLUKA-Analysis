# Log-space Gaussian Smoothing in Comparison Overlay

**Date:** 2026-06-11
**Status:** Approved design, pending implementation plan

## Goal

Port the log-space gaussian smoothing visualization from the analysis notebook
(`/Users/tonyf/Work/BDX/2025-11-21_BDX_NeutronArticle/GeometryB_Cprop/check.ipynb`,
cell `7b41bccb`) into the comparison-plotting code so any histogram comparison can
optionally render a smoothed bold curve, with or without the faint raw histogram
underneath.

The notebook produces a neutron-flux-per-surface plot: raw histogram drawn faint
(low alpha) plus a gaussian-smoothed bold line, on a log-x/log-y canvas. The
smoothing is done in **log space** (geometric mean of bin contents) so the smoothed
line passes through the middle of the bins on a log-y plot rather than sitting above
(linear mean) or below (inverse-variance weighting) them.

## Key Insight

The comparison code loads **already-binned** `TH1D` objects from `.root` files,
unlike the notebook which builds histograms from a raw `RDataFrame`. This does not
matter for the smoothing: the algorithm operates on bin contents in **bin-index
space**. The "log space" in the notebook refers to taking the geometric mean of
y-values, not to the x-axis binning. The recipe ports directly to any pre-binned
`TH1D` regardless of log or linear x-binning.

## Scope

Per-comparison feature inside `compare_histograms_overlay` in `src/comparison.py`.
When smoothing is enabled for a comparison, **all** histograms in that comparison are
smoothed uniformly (matches notebook behavior; no per-histogram opt-in). Off by
default, so existing comparison plots are unchanged.

## Configuration

Five new optional fields on `ComparisonConfig` (`src/config.py`), each with a default
so existing configs keep working untouched:

| field | type | default | meaning |
|---|---|---|---|
| `smoothing` | str | `"off"` | mode: `"off"` \| `"overlay"` (raw faint + smooth bold) \| `"replace"` (smooth only) |
| `smoothing_sigma` | float | `10` | gaussian width in **bins** (not GeV); large = flatter, small = noisier |
| `smooth_x_max` | float \| None | `None` | force the smoothed curve to stop at this x value; `None` = auto-clip to last filled bin |
| `raw_alpha` | float | `0.25` | alpha of the faint raw line (overlay mode only) |
| `smooth_line_width` | int \| None | `None` | bold smoothed line thickness; `None` falls back to existing `line_width` |

Unknown `smoothing` values warn and fall back to `"off"`.

## Algorithm

Helper `_smooth_hist_logspace(h, sigma, x_max)` returns a numpy array of smoothed bin
contents. Ports notebook cell `7b41bccb`:

```python
nb   = h.GetNbinsX()
y    = np.array([h.GetBinContent(b + 1) for b in range(nb)])
pos  = y > 0
logy = np.where(pos, np.log(y), 0.0)
m    = pos.astype(float)                       # occupancy weight: skip empty bins
num  = gaussian_filter1d(logy * m, sigma=sigma)
den  = gaussian_filter1d(m,        sigma=sigma)
ysm  = np.where(den > 0, np.exp(num / den), 0.0)

# clip to [first filled bin, last filled bin] so smoothing does not bleed past data
idx = np.where(pos)[0]
if len(idx) == 0:
    return ysm                                 # nothing to smooth
lo, hi = idx[0], idx[-1]
if x_max is not None:
    hi = min(hi, h.GetXaxis().FindBin(x_max) - 1)
ysm[:lo]     = 0.0
ysm[hi + 1:] = 0.0
return ysm
```

`FindBin(x_max) - 1` replaces the notebook's `np.searchsorted(en_log_bins, ...) - 1`
because the `TH1D` already knows its bin edges.

The smoothed clone is built with `h.Clone(name + "_smooth")` then
`SetBinContent(b + 1, ysm[b])` for each bin.

## Rendering

Color and alpha: the existing code sets line color from a name string (e.g.
`"kP6Blue"`), which PyROOT resolves to an int index. `SetLineColorAlpha` however
requires an int and rejects the name string. Sidestep: set the color via the existing
string path, read it back as an int with `GetLineColor()`, then apply alpha with that
int. No new color resolver needed.

- **off** — current code path untouched. Raw histograms drawn as today.
- **overlay** — for each histogram: raw drawn faint first
  (`SetLineColorAlpha(idx, raw_alpha)`, width 1) as the axis primary, then the
  smoothed clone bold (solid `idx`, `smooth_line_width`) on top.
- **replace** — smoothed clone is the axis primary; raw not drawn.

The first drawn object per comparison establishes the axes (title, ranges, scientific
notation) exactly as the current code does for the first histogram. Smoothed clones
are appended to a keep-alive list to prevent Python GC from collecting them before the
canvas is saved.

## Legend

Legend entries point to the **smoothed** clones (solid, thick) in overlay and replace
modes, and to the raw clones when smoothing is off. The existing `legend_hists`
construction and `legend_order` resolution are reused; only the source clone changes
based on mode.

## Touch Points

- `src/config.py` (~line 35) — add 5 dataclass fields to `ComparisonConfig`.
- `src/comparison.py`:
  - module imports — `import numpy as np`, `from scipy.ndimage import gaussian_filter1d`.
  - new helper `_smooth_hist_logspace(h, sigma, x_max)`.
  - draw loop (~line 393) — branch on `smoothing` mode for raw/smooth drawing.
  - legend-clone loop (~line 419) — point clones at smoothed hist when smoothing on.
- scipy 1.17.1 already installed; no new dependency.

## Assumptions

1. Smoothing is uniform across all histograms in a comparison (matches notebook). No
   per-histogram opt-in.
2. The axis auto-range logic (`src/comparison.py` lines 296-336) keys off raw bin
   contents and is left unchanged; the smoothed curve stays within the raw envelope so
   the computed ranges remain valid in all three modes.
3. A histogram with zero filled bins is drawn raw (or skipped per existing logic); its
   smoothed clone is all-zero and contributes nothing.

## Out of Scope

- Per-histogram smoothing selection.
- Smoothing in the standalone `histogram.py` / `export_histograms.py` paths (this spec
  covers only `compare_histograms_overlay`).
- Error-aware smoothing (inverse-variance) — explicitly rejected in the notebook
  exploration because it pulls the line off-center on log-y.
