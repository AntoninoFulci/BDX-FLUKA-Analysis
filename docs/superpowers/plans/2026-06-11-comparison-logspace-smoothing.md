# Log-space Gaussian Smoothing in Comparison Overlay — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional log-space gaussian smoothing (raw-faint + smoothed-bold, or smoothed-only) to `compare_histograms_overlay`, controlled per-comparison via config.

**Architecture:** Five new optional fields on the `ComparisonConfig` dataclass flow automatically from YAML. A pure helper computes smoothed bin contents (geometric mean in log space) from any pre-binned `TH1D`. The draw loop branches on a `smoothing` mode: `off` (unchanged), `overlay` (raw faint + smoothed bold), `replace` (smoothed only). Off by default so existing plots are byte-identical.

**Tech Stack:** Python, PyROOT (`TH1D`, `TCanvas`), numpy, `scipy.ndimage.gaussian_filter1d`, pytest. scipy 1.17.1 and pytest 9.0.3 already installed.

**Spec:** `docs/superpowers/specs/2026-06-11-comparison-logspace-smoothing-design.md`

**Note on style:** `src/comparison.py` uses **tabs** for indentation inside `compare_histograms_overlay`, and 4-spaces for module-level functions. Match the surrounding style exactly in each edit.

---

### Task 1: Add smoothing config fields

**Files:**
- Modify: `src/config.py:35` (end of `ComparisonConfig` field list, after `legend_order`)
- Test: `tests/test_config_smoothing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_smoothing.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config import ComparisonConfig


def test_smoothing_defaults():
    cmp = ComparisonConfig(output="x")
    assert cmp.smoothing == "off"
    assert cmp.smoothing_sigma == 10
    assert cmp.smooth_x_max is None
    assert cmp.raw_alpha == 0.25
    assert cmp.smooth_line_width is None


def test_smoothing_overrides():
    cmp = ComparisonConfig(
        output="x",
        smoothing="overlay",
        smoothing_sigma=5,
        smooth_x_max=2.5,
        raw_alpha=0.4,
        smooth_line_width=3,
    )
    assert cmp.smoothing == "overlay"
    assert cmp.smoothing_sigma == 5
    assert cmp.smooth_x_max == 2.5
    assert cmp.raw_alpha == 0.4
    assert cmp.smooth_line_width == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config_smoothing.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'smoothing'`

- [ ] **Step 3: Add the fields**

In `src/config.py`, immediately after the `legend_order` field (line 35), add (match the existing 4-space indentation of dataclass fields):

```python
    smoothing: str = "off"                  # Smoothing mode: "off" | "overlay" (raw faint + smooth bold) | "replace" (smooth only)
    smoothing_sigma: float = 10             # Gaussian width in BINS (not GeV); large = flatter, small = noisier
    smooth_x_max: Optional[float] = None    # Force smoothed curve to stop at this x value; None = auto-clip to last filled bin
    raw_alpha: float = 0.25                 # Alpha of the faint raw line (overlay mode only)
    smooth_line_width: Optional[int] = None # Bold smoothed line thickness; None falls back to line_width
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config_smoothing.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add -f src/config.py tests/test_config_smoothing.py
git commit -m "feat(config): add smoothing fields to ComparisonConfig"
```

---

### Task 2: Smoothing helpers

**Files:**
- Modify: `src/comparison.py` (module level, after `_get_default_colors`, ~line 31)
- Test: `tests/test_smoothing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_smoothing.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ROOT
ROOT.gROOT.SetBatch(True)
from comparison import _smooth_hist_logspace, _build_smoothed_clone


def _make_hist(name="h"):
    # 100 bins over [0, 100], constant value 100 in ROOT bins 11..21 (0-based y idx 10..20)
    h = ROOT.TH1D(name, name, 100, 0.0, 100.0)
    for b in range(11, 22):
        h.SetBinContent(b, 100.0)
    return h


def test_constant_region_geometric_mean():
    h = _make_hist("h_const")
    ysm = _smooth_hist_logspace(h, sigma=2, x_max=None)
    assert len(ysm) == 100
    # center of constant block -> geometric mean of a constant is the constant
    assert abs(ysm[15] - 100.0) < 1.0


def test_clip_to_filled_range():
    h = _make_hist("h_clip")
    ysm = _smooth_hist_logspace(h, sigma=2, x_max=None)
    # before first filled bin (idx 10) and after last filled bin (idx 20) -> zero
    assert ysm[5] == 0.0
    assert ysm[25] == 0.0


def test_x_max_cutoff():
    h = _make_hist("h_xmax")
    # x_max=15.5 -> FindBin=16 -> hi = min(20, 15) = 15 ; bins > 15 zeroed
    ysm = _smooth_hist_logspace(h, sigma=2, x_max=15.5)
    assert ysm[15] != 0.0
    assert ysm[18] == 0.0


def test_empty_hist_returns_zeros():
    h = ROOT.TH1D("h_empty", "h_empty", 100, 0.0, 100.0)
    ysm = _smooth_hist_logspace(h, sigma=2, x_max=None)
    assert len(ysm) == 100
    assert float(ysm.sum()) == 0.0


def test_build_smoothed_clone_copies_contents():
    import numpy as np
    h = _make_hist("h_src")
    ysm = np.zeros(100)
    ysm[15] = 42.0
    hs = _build_smoothed_clone(h, ysm)
    assert hs.GetName() == "h_src_smooth"
    assert hs.GetBinContent(16) == 42.0  # ROOT bin 16 == y index 15
    assert hs.GetBinContent(11) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoothing.py -v`
Expected: FAIL — `ImportError: cannot import name '_smooth_hist_logspace'`

- [ ] **Step 3: Add the helpers**

In `src/comparison.py`, after `_get_default_colors` (ends ~line 31) and before the comment `# Excel files are now saved individually...`, add (module-level, 4-space indentation):

```python
def _smooth_hist_logspace(h, sigma, x_max=None):
    """Log-space gaussian smoothing of a TH1 -> numpy array of smoothed bin contents.

    Geometric mean in log space so the smoothed line passes through the middle of the
    bins on a log-y plot. Empty bins are skipped via an occupancy weight; the result is
    clipped to the first/last filled bin (or x_max) so it does not bleed past the data.
    Ports check.ipynb cell 7b41bccb.
    """
    import numpy as np
    from scipy.ndimage import gaussian_filter1d

    nb = h.GetNbinsX()
    y = np.array([h.GetBinContent(b + 1) for b in range(nb)])
    pos = y > 0
    logy = np.where(pos, np.log(y), 0.0)
    m = pos.astype(float)
    num = gaussian_filter1d(logy * m, sigma=sigma)
    den = gaussian_filter1d(m, sigma=sigma)
    ysm = np.where(den > 0, np.exp(num / den), 0.0)

    idx = np.where(pos)[0]
    if len(idx) == 0:
        return ysm
    lo, hi = idx[0], idx[-1]
    if x_max is not None:
        hi = min(hi, h.GetXaxis().FindBin(x_max) - 1)
    ysm[:lo] = 0.0
    ysm[hi + 1:] = 0.0
    return ysm


def _build_smoothed_clone(h, ysm, suffix="_smooth"):
    """Clone h and overwrite its bin contents with the smoothed array ysm."""
    hs = h.Clone(f"{h.GetName()}{suffix}")
    for b in range(h.GetNbinsX()):
        hs.SetBinContent(b + 1, float(ysm[b]))
    return hs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_smoothing.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add -f src/comparison.py tests/test_smoothing.py
git commit -m "feat(comparison): add log-space gaussian smoothing helpers"
```

---

### Task 3: Wire smoothing into the draw loop

**Files:**
- Modify: `src/comparison.py:392-417` (the "Draw all histograms" loop)
- Modify: `src/comparison.py` (read config knobs just before the draw loop, ~line 391)

This task has no new unit test of its own — the helper is covered by Task 2 and the end-to-end behavior is covered by Task 4's integration test. Run Task 4's test after this task as the verification step.

- [ ] **Step 1: Read the smoothing config before the draw loop**

In `src/comparison.py`, locate the line (~390):

```python
	labels_and_colors_raw = getattr(cmp, 'labels_and_colors', None)
	labels_and_colors_dict = _normalize_labels_and_colors(labels_and_colors_raw)
```

Immediately after those two lines, insert (TAB indentation to match the function body):

```python
	# --- smoothing configuration ---
	smoothing_mode = getattr(cmp, 'smoothing', 'off')
	if smoothing_mode not in ('off', 'overlay', 'replace'):
		warn(f"Unknown smoothing mode '{smoothing_mode}', using 'off'")
		smoothing_mode = 'off'
	smoothing_sigma = float(getattr(cmp, 'smoothing_sigma', 10) or 10)
	smooth_x_max_raw = getattr(cmp, 'smooth_x_max', None)
	smooth_x_max = float(smooth_x_max_raw) if smooth_x_max_raw is not None else None
	raw_alpha = float(getattr(cmp, 'raw_alpha', 0.25) or 0.25)
	smooth_lw_raw = getattr(cmp, 'smooth_line_width', None)
	smooth_lw = int(smooth_lw_raw) if smooth_lw_raw is not None else line_width
	smoothed_keep = []  # prevent Python GC of smoothed clones until SaveAs
```

- [ ] **Step 2: Replace the draw loop**

Replace the entire block from `# Draw all histograms (order drives...` through the end of that `for i, h in enumerate(hists):` loop (current lines 392-417, i.e. up to and including the `h.GetXaxis().SetMaxDigits(2)` block) with (TAB indentation):

```python
	# Draw all histograms (order drives the canvas setup, but legend order is independent)
	first = True
	for i, h in enumerate(hists):
		color = _get_histogram_color(i, cmp.labels[i], labels_and_colors_dict, colors, colors)
		h.SetLineColor(color)
		h.SetMarkerColor(color)
		color_int = h.GetLineColor()  # resolve name->int (SetLineColorAlpha needs an int)

		if smoothing_mode == 'off':
			h.SetLineWidth(line_width)
			h.Draw(first_draw_str if first else other_draw_str)
			primary = h
		else:
			ysm = _smooth_hist_logspace(h, smoothing_sigma, smooth_x_max)
			hs = _build_smoothed_clone(h, ysm)
			hs.SetLineColor(color_int)
			hs.SetMarkerColor(color_int)
			hs.SetLineWidth(smooth_lw)
			hs.SetStats(0)
			smoothed_keep.append(hs)
			if smoothing_mode == 'overlay':
				h.SetLineColorAlpha(color_int, raw_alpha)
				h.SetLineWidth(1)
				h.Draw(first_draw_str if first else other_draw_str)
				hs.Draw(other_draw_str)
				primary = h
			else:  # replace
				hs.Draw(first_draw_str if first else other_draw_str)
				primary = hs

		# Set axis labels and title on the primary (first-drawn) object
		if getattr(cmp, 'x_label', None):
			primary.GetXaxis().SetTitle(cmp.x_label)
			primary.GetXaxis().SetTitleOffset(1.6)
		if getattr(cmp, 'y_label', None):
			primary.GetYaxis().SetTitle(cmp.y_label)
			primary.GetYaxis().SetTitleOffset(1.6)
		if getattr(cmp, 'title', None):
			primary.SetTitle(cmp.title)

		# Apply scientific notation formatting to x-axis for the first drawn object only
		if first:
			use_scientific_notation_x = getattr(cmp, 'use_scientific_notation_x', True)
			if use_scientific_notation_x:
				primary.GetXaxis().SetMaxDigits(2)

		first = False
```

- [ ] **Step 3: Verify no syntax/indent error**

Run: `python -c "import sys; sys.path.insert(0,'src'); import comparison; print('import ok')"`
Expected: `import ok`

- [ ] **Step 4: Run the full existing test suite (regression — off mode unchanged)**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests from Tasks 1 and 2 still pass)

- [ ] **Step 5: Commit**

```bash
git add -f src/comparison.py
git commit -m "feat(comparison): branch draw loop on smoothing mode"
```

---

### Task 4: End-to-end integration test + example config

**Files:**
- Test: `tests/test_comparison_smoothing_e2e.py`
- Create: `configs/examples/08_smoothing_demo.yaml`

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_comparison_smoothing_e2e.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ROOT
ROOT.gROOT.SetBatch(True)

from config import ComparisonConfig
from comparison import compare_histograms_overlay


def _write_root(path, name, peak_bin):
    f = ROOT.TFile(str(path), "RECREATE")
    h = ROOT.TH1D(name, name, 100, 0.0, 100.0)
    for b in range(1, 101):
        # smooth-ish bump so log-space smoothing has positive bins
        val = 100.0 * (2.71828 ** (-((b - peak_bin) ** 2) / 200.0))
        if val > 1e-6:
            h.SetBinContent(b, val)
    h.Write()
    f.Close()


def _run(tmp_path, mode):
    f1 = tmp_path / "a.root"
    f2 = tmp_path / "b.root"
    _write_root(f1, "ha", 30)
    _write_root(f2, "hb", 60)
    cmp = ComparisonConfig(
        output=f"smooth_{mode}",
        files=[str(f1), str(f2)],
        hists=["ha", "hb"],
        labels=["A", "B"],
        smoothing=mode,
        output_directory=str(tmp_path),
    )
    compare_histograms_overlay(cmp, output_dir=str(tmp_path))
    return tmp_path / f"smooth_{mode}.pdf"


def test_overlay_mode_produces_pdf(tmp_path):
    out = _run(tmp_path, "overlay")
    assert out.exists() and out.stat().st_size > 0


def test_replace_mode_produces_pdf(tmp_path):
    out = _run(tmp_path, "replace")
    assert out.exists() and out.stat().st_size > 0


def test_off_mode_produces_pdf(tmp_path):
    out = _run(tmp_path, "off")
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 2: Run test to verify it passes (helpers + wiring already exist from Tasks 2-3)**

Run: `python -m pytest tests/test_comparison_smoothing_e2e.py -v`
Expected: PASS (3 passed). If any FAIL, fix the wiring from Task 3 before continuing.

- [ ] **Step 3: Add an example YAML config**

Create `configs/examples/08_smoothing_demo.yaml`. Match the structure of `configs/examples/02_comparison_analysis.yaml` (open it first to copy the exact top-level key layout used by the parser), then add the smoothing keys to one comparison. Minimal shape:

```yaml
comparisons:
  - output: "flux_smoothed_overlay"
    title: "Neutron flux per surface - log-space gaussian smoothing"
    x_label: "Kinetic Energy (GeV)"
    y_label: "Flux (n / EOT / GeV)"
    logx: true
    logy: true
    files_name:
      - ["path/to/fileA.root", "hflux_surf0"]
      - ["path/to/fileB.root", "hflux_surf1"]
    labels: ["Surface 0", "Surface 1"]
    smoothing: "overlay"      # off | overlay | replace
    smoothing_sigma: 10        # gaussian width in BINS
    raw_alpha: 0.25            # faint raw line alpha (overlay only)
    # smooth_x_max: 6.0        # optional: stop smoothed curve at this x (GeV)
    # smooth_line_width: 2     # optional: bold line thickness
```

- [ ] **Step 4: Verify the example YAML parses as valid YAML and contains the new keys**

Run:
```bash
python -c "import yaml; d=yaml.safe_load(open('configs/examples/08_smoothing_demo.yaml')); c=d['comparisons'][0]; assert c['smoothing']=='overlay'; print('yaml ok')"
```
Expected: `yaml ok`

(If the project exposes a config loader entry point, prefer loading the file through it instead; check `src/core.py` for the loader call.)

- [ ] **Step 5: Commit**

```bash
git add -f tests/test_comparison_smoothing_e2e.py configs/examples/08_smoothing_demo.yaml
git commit -m "test(comparison): e2e smoothing modes + example config"
```

---

### Task 5: Manual visual verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite one final time**

Run: `python -m pytest tests/ -v`
Expected: all green (Tasks 1, 2, 4 tests pass).

- [ ] **Step 2: Generate a real plot against actual data**

Point `configs/examples/08_smoothing_demo.yaml` at two real `.root` files containing the flux histograms, then run the project's normal driver (see `src/core.py` for the entry point that calls `compare_histograms_overlay`). Open the produced `flux_smoothed_overlay.pdf` and confirm:
- raw histogram drawn faint, smoothed bold line on top (overlay), centered through the bins on the log-y axis
- switching `smoothing: replace` shows only the bold smoothed line
- switching `smoothing: off` reproduces the previous (pre-feature) plot exactly

- [ ] **Step 3: Final commit if any config tweaks were made**

```bash
git add -f configs/examples/08_smoothing_demo.yaml
git commit -m "chore: finalize smoothing demo config"
```

---

## Self-Review Notes

- **Spec coverage:** all 5 config fields (Task 1), algorithm w/ log-space geometric mean + clip + x_max (Task 2), three render modes off/overlay/replace + color-int alpha sidestep + keep-alive (Task 3), legend unchanged because `_legend` clones are independent and already solid+thick (verified by Task 4 e2e). Out-of-scope items (per-hist opt-in, histogram.py, inverse-variance) correctly absent.
- **Type consistency:** helper names `_smooth_hist_logspace` / `_build_smoothed_clone` identical across Tasks 2-4. Config field names identical across Tasks 1, 3, 4.
- **Tabs vs spaces:** Task 3 edits inside the function body use TABS; Tasks 1-2 module/dataclass level use 4 spaces. Flagged in each task.
