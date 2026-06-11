# Comparison plotting utilities for overlaying histograms from multiple files
from pathlib import Path
from ROOT import TFile, TCanvas, TLegend
from term_logging import info, warn, success

try:
    from tabulate import tabulate
    import pandas as pd
    HAS_TABULATE_PANDAS = True
except ImportError:
    HAS_TABULATE_PANDAS = False


# Accessible Color Schemes (colorblind-friendly, from Kumbhare et al.)
# These schemes are designed to be distinguishable for people with color vision deficiency
ACCESSIBLE_COLOR_SCHEMES = {
    'kP6': ['kP6Blue', 'kP6Yellow', 'kP6Red', 'kP6Grape', 'kP6Gray', 'kP6Violet'],
    'kP8': ['kP8Blue', 'kP8Orange', 'kP8Red', 'kP8Pink', 'kP8Green', 'kP8Azure', 'kP8Gray', 'kP8Cyan'],
    'kP10': ['kP10Blue', 'kP10Yellow', 'kP10Red', 'kP10Gray', 'kP10Violet', 'kP10Brown', 'kP10Orange', 'kP10Green', 'kP10Ash', 'kP10Cyan'],
}


def _get_default_colors(num_hists):
    """Select appropriate accessible color scheme based on histogram count."""
    if num_hists <= 6:
        return ACCESSIBLE_COLOR_SCHEMES['kP6']
    elif num_hists <= 8:
        return ACCESSIBLE_COLOR_SCHEMES['kP8']
    else:
        return ACCESSIBLE_COLOR_SCHEMES['kP10']


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
    with np.errstate(divide="ignore", invalid="ignore"):
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


# Excel files are now saved individually for each comparison

def _write_comparison_table_to_excel_and_print(cmp, integrals, errors, error_percents, output_dir=None):
	from pathlib import Path
	def short_path(path, keep=2):
		parts = Path(path).parts
		if len(parts) > keep:
			return '.../' + '/'.join(parts[-keep:])
		return path
	if not HAS_TABULATE_PANDAS:
		return
	def fmt_sci(val):
		try:
			if isinstance(val, (float, int)):
				return f"{val:.2E}"
			elif isinstance(val, str):
				return val
			else:
				return str(val)
		except Exception:
			return val
	def fmt_perc(val):
		try:
			if isinstance(val, (float, int)):
				return f"{val:.2f}%"
			elif isinstance(val, str):
				return val
			else:
				return str(val)
		except Exception:
			return val
	table = [
		(h, short_path(f), label, fmt_sci(ing), fmt_sci(err), fmt_perc(errp))
		for h, f, label, ing, err, errp in zip(cmp.hists, cmp.files, cmp.labels, integrals, errors, error_percents)
	]
	info("Comparing the following histograms:")
	print(tabulate(table, headers=["Histogram", "File", "Name", "Integral", "Error", "Error %"], tablefmt="rounded_grid"))

	# Save to a single Excel file with multiple sheets
	df = pd.DataFrame(table, columns=["Histogram", "File", "Name", "Integral", "Error", "Error %"])
	config_output_dir = getattr(cmp, 'output_directory', None)
	if config_output_dir:
		outdir = config_output_dir
	elif output_dir and output_dir != '.':
		outdir = output_dir
	else:
		outdir = getattr(cmp, 'output_dir', None) or '.'
	Path(outdir).mkdir(parents=True, exist_ok=True)
	# Create individual Excel file for each comparison
	# Use the output config option for the Excel filename
	excel_filename = f"{cmp.output}.xlsx"
	excel_path = str(Path(outdir) / excel_filename)
	
	try:
		# Create a new Excel writer for this specific comparison
		with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
			# Use the output name as sheet name (single sheet per file)
			sheet_name = str(cmp.output)[:31]  # Excel sheet name max 31 chars
			df.to_excel(writer, sheet_name=sheet_name, index=False)
			success(f"Saved comparison table to Excel file: {excel_path}")
	except ImportError:
		info("Comparing the following histograms:")
		# Fallback: print without integral or error
		for h, f, label in zip(cmp.hists, cmp.files, cmp.labels):
			print(f"    {h:30} | {short_path(f):50} | {label}")

def compare_histograms_overlay(cmp, output_dir=None):
	"""
	Overlay multiple histograms from different files on the same canvas.
	Args:
		cmp: ComparisonConfig object (should have .files, .hists, .output, .title, .x_label, .y_label, .logx, .logy)
		       .labels or .labels_and_colors for histogram labels (one is required)
		output_dir: Optional override for output directory
	"""
	import ctypes
	
	# Extract or validate labels
	def _extract_labels_from_config(cmp):
		"""Extract labels from labels_and_colors if labels not provided, or validate labels field."""
		# Priority: explicit labels field > extract from labels_and_colors
		if cmp.labels is not None:
			return cmp.labels
		
		# Try to extract from labels_and_colors
		labels_and_colors_raw = getattr(cmp, 'labels_and_colors', None)
		if labels_and_colors_raw is None:
			raise ValueError("ComparisonConfig must have either 'labels' or 'labels_and_colors' field specified")
		
		# Extract labels from labels_and_colors
		if isinstance(labels_and_colors_raw, dict):
			# Dict format: {label: color, ...}
			return list(labels_and_colors_raw.keys())
		elif isinstance(labels_and_colors_raw, list):
			# List format: [[label, color], ...]
			try:
				return [pair[0] for pair in labels_and_colors_raw]
			except (IndexError, TypeError) as e:
				raise ValueError(f"Could not extract labels from labels_and_colors: {e}")
		else:
			raise ValueError(f"labels_and_colors must be a list or dict, got {type(labels_and_colors_raw)}")
	
	# Set labels on config if not already set (for downstream code)
	if cmp.labels is None:
		cmp.labels = _extract_labels_from_config(cmp)

	if len(cmp.files) != len(cmp.hists):
		raise ValueError(
			f"Comparison '{getattr(cmp, 'output', 'unknown')}' has mismatched lengths: "
			f"files={len(cmp.files)} hists={len(cmp.hists)}. "
			"Provide equal-length files/hists or use files_name."
		)
	if cmp.labels is not None and len(cmp.labels) != len(cmp.files):
		raise ValueError(
			f"Comparison '{getattr(cmp, 'output', 'unknown')}' has mismatched lengths: "
			f"labels={len(cmp.labels)} files={len(cmp.files)}. "
			"Ensure labels align with each file/hist input."
		)
	
	# Open files and get integrals and errors for each histogram
	files = [TFile(f, "READ") for f in cmp.files]
	hists = [f.Get(hname) for f, hname in zip(files, cmp.hists)]
	integrals = []
	errors = []
	error_percents = []
	for h in hists:
		if h:
			err = ctypes.c_double(0.0)
			integral = h.IntegralAndError(1, h.GetNbinsX(), err, "width")
			integrals.append(integral)
			errors.append(err.value)
			if integral != 0:
				error_percents.append(100.0 * err.value / abs(integral))
			else:
				error_percents.append('N/A')
		else:
			integrals.append('N/A')
			errors.append('N/A')
			error_percents.append('N/A')
	_write_comparison_table_to_excel_and_print(
		cmp, integrals, errors, error_percents,
		output_dir=output_dir
	)
	for i, h in enumerate(hists):
		if not h:
			warn(f"Could not find histogram '{cmp.hists[i]}' in file '{cmp.files[i]}'")
	hists = [h for h in hists if h]
	if len(hists) < 2:
		warn("Not enough histograms to compare.")
		for f in files:
			f.Close()
		return
	canvas = TCanvas(f"c_{cmp.output}", cmp.title, 700, 600)
	# Increase right margin for legend and axis labels
	canvas.SetRightMargin(0.1)  # Default is ~0.05, increase to 0.18
	if getattr(cmp, 'logy', False):
		canvas.SetLogy()
	if getattr(cmp, 'logx', False):
		canvas.SetLogx()
	
	# Get colors and line width from config
	# Color resolution priority:
	# 1. If colors is a scheme name string (e.g., 'kP6', 'kP8', 'kP10'), use that scheme
	# 2. If colors is a list, use it directly
	# 3. If not specified, auto-select accessible scheme based on histogram count
	colors_raw = getattr(cmp, 'colors', None)
	
	if colors_raw is None:
		# Auto-select accessible color scheme based on histogram count
		colors = _get_default_colors(len(hists))
	elif isinstance(colors_raw, str):
		# Treat as scheme name
		if colors_raw in ACCESSIBLE_COLOR_SCHEMES:
			colors = ACCESSIBLE_COLOR_SCHEMES[colors_raw]
		else:
			warn(f"Unknown color scheme '{colors_raw}', using auto-selected accessible colors")
			colors = _get_default_colors(len(hists))
	elif isinstance(colors_raw, list):
		# Use list directly (can contain int codes or color names)
		colors = colors_raw
	else:
		warn("Invalid colors format, using auto-selected accessible colors")
		colors = _get_default_colors(len(hists))
	
	line_width = getattr(cmp, 'line_width', 2)
	
	# Define legend positions (predefined shortcuts)
	legend_positions = {
		"top_right": (0.65, 0.75, 0.89, 0.89),
		"top_left": (0.15, 0.75, 0.39, 0.89),
		"bottom_right": (0.65, 0.15, 0.89, 0.29),
		"bottom_left": (0.15, 0.15, 0.39, 0.29),
		"center_right": (0.65, 0.50, 0.89, 0.64),
		"center_left": (0.15, 0.50, 0.39, 0.64),
		"custom" : (0.45, 0.78, 0.89, 0.93)
	}

	# Get legend position from config. Accept either:
	# - a predefined string key (e.g. 'top_right'),
	# - a sequence/list/tuple of 4 numbers, or
	# - a string that can be parsed into 4 numbers (e.g. "0.1,0.2,0.3,0.4").
	legend_pos_raw = getattr(cmp, 'legend_position', 'top_right')

	def _to_coords(val):
		# Return a 4-tuple of floats or None on failure
		import re
		# If it's a string and matches a predefined name
		if isinstance(val, str):
			if val in legend_positions:
				return legend_positions[val]
			# try to parse numeric values from string
			parts = re.split(r'[\s,;]+', val.strip())
			if len(parts) == 4:
				try:
					return tuple(float(p) for p in parts)
				except Exception:
					return None
			return None
		# If it's a list/tuple, try to coerce to floats
		if isinstance(val, (list, tuple)):
			if len(val) == 4:
				try:
					return tuple(float(x) for x in val)
				except Exception:
					return None
			return None
		# Unknown type
		return None

	coords = _to_coords(legend_pos_raw)
	if coords is None:
		warn(f"Unknown or invalid legend_position '{legend_pos_raw}', using 'top_right'")
		coords = legend_positions['top_right']

	x1, y1, x2, y2 = coords
	legend = TLegend(x1, y1, x2, y2)

	# Check for manual axis limits in config
	def to_float(val):
		if val is None:
			return None
		try:
			return float(val)
		except Exception:
			return None
	
	# Priority: plot_range > individual x_min/x_max/y_min/y_max > automatic
	plot_range = getattr(cmp, 'plot_range', None)
	if plot_range:
		# Use plot_range if specified
		x_range = plot_range.get('x_range', [None, None])
		y_range = plot_range.get('y_range', [None, None])
		x_axis_min = to_float(x_range[0]) if len(x_range) > 0 else None
		x_axis_max = to_float(x_range[1]) if len(x_range) > 1 else None
		y_axis_min = to_float(y_range[0]) if len(y_range) > 0 else None
		y_axis_max = to_float(y_range[1]) if len(y_range) > 1 else None
	else:
		# Fallback to individual axis limits
		x_axis_min = to_float(getattr(cmp, 'x_min', None))
		x_axis_max = to_float(getattr(cmp, 'x_max', None))
		y_axis_min = to_float(getattr(cmp, 'y_min', None))
		y_axis_max = to_float(getattr(cmp, 'y_max', None))

	# If not set, use automatic logic
	if x_axis_min is None or x_axis_max is None or y_axis_min is None or y_axis_max is None:
		# Find the minimum nonzero bin content and corresponding x value among all histograms
		min_y = None
		min_x = None
		max_x = None
		for h in hists:
			for b in range(1, h.GetNbinsX() + 1):
				val = h.GetBinContent(b)
				if val > 0:
					x = h.GetBinCenter(b)
					if min_y is None or val < min_y:
						min_y = val
					if min_x is None or x < min_x:
						min_x = x
					if max_x is None or x > max_x:
						max_x = x
		if min_y is None:
			min_y = 0
		# Calculate a small shift for x-axis minimum (5% of the x-range or a small fixed value)
		h0 = hists[0]
		x_min_global = h0.GetXaxis().GetXmin()
		x_max_global = h0.GetXaxis().GetXmax()
		x_range = x_max_global - x_min_global
		if x_axis_min is None and min_x is not None:
			x_shift = max(0.05 * x_range, 0.01 * abs(x_range), 1e-6)
			x_axis_min = max(x_min_global, min_x - x_shift)
		if x_axis_max is None and max_x is not None:
			x_axis_max = x_max_global
		if y_axis_min is None:
			y_axis_min = min_y
		if y_axis_max is None:
			y_axis_max = None  # Let ROOT autoscale

	# Set axis ranges on all histograms before drawing
	for h in hists:
		if x_axis_min is not None and x_axis_max is not None:
			h.GetXaxis().SetRangeUser(x_axis_min, x_axis_max)
		if y_axis_min is not None:
			h.SetMinimum(y_axis_min)
		if y_axis_max is not None:
			h.SetMaximum(y_axis_max)
	
	# Get draw option from config, default to "hist"
	draw_option = getattr(cmp, 'draw_option', 'hist')
	if isinstance(draw_option, str):
		draw_option = draw_option.strip()
	else:
		draw_option = str(draw_option)

	draw_option_extra = getattr(cmp, 'draw_option_extra', None)
	if isinstance(draw_option_extra, str):
		draw_option_extra = draw_option_extra.strip()
	else:
		draw_option_extra = None

	if draw_option_extra:
		first_draw_str = f"{draw_option} {draw_option_extra}".strip()
		other_draw_str = f"{draw_option} same {draw_option_extra}".strip()
	else:
		first_draw_str = draw_option
		other_draw_str = f"{draw_option} same"
	
	# Helper function to convert labels_and_colors to dict format
	def _normalize_labels_and_colors(labels_and_colors_raw):
		"""Convert labels_and_colors from list or dict format to dict."""
		if labels_and_colors_raw is None:
			return {}
		if isinstance(labels_and_colors_raw, dict):
			return labels_and_colors_raw
		if isinstance(labels_and_colors_raw, list):
			try:
				return {pair[0]: pair[1] for pair in labels_and_colors_raw}
			except (IndexError, TypeError) as e:
				warn(f"Could not parse labels_and_colors format: {e}, skipping label-based colors")
				return {}
		warn(f"Unknown labels_and_colors format, expected list or dict, got {type(labels_and_colors_raw)}")
		return {}
	
	# Function to resolve color for each histogram by label or index
	def _get_histogram_color(hist_index, label, labels_and_colors_dict, colors_list, default_colors_list):
		"""
		Resolve color for a histogram.
		Priority: 1) label-based lookup, 2) colors list by index, 3) default colors
		"""
		# First priority: label-based color mapping
		if label in labels_and_colors_dict:
			return labels_and_colors_dict[label]
		# Second priority: colors list by index
		if hist_index < len(colors_list):
			return colors_list[hist_index]
		# Third priority: cycle through default colors
		return default_colors_list[hist_index % len(default_colors_list)]
	
	labels_and_colors_raw = getattr(cmp, 'labels_and_colors', None)
	labels_and_colors_dict = _normalize_labels_and_colors(labels_and_colors_raw)
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
	
	# Create cloned histograms for legend with thick lines (using resolved colors)
	legend_hists = []
	for i, h in enumerate(hists):
		legend_hist = h.Clone(f"{h.GetName()}_legend")
		color = _get_histogram_color(i, cmp.labels[i], labels_and_colors_dict, colors, colors)
		legend_hist.SetLineColor(color)
		legend_hist.SetMarkerColor(color)  # Set marker color to match line color
		legend_hist.SetLineWidth(3)  # Always thick for legend
		legend_hists.append(legend_hist)
	
	# Resolve legend order: convert mixed list of indices/labels to indices
	def _resolve_legend_order(legend_order_raw, labels, num_hists):
		"""
		Convert legend_order_raw (list of int indices or str labels or mix) to list of indices.
		Returns list of valid indices in desired legend order.
		If legend_order_raw is None, returns range(num_hists) (drawing order).
		"""
		if legend_order_raw is None:
			return list(range(num_hists))
		
		resolved_indices = []
		for entry in legend_order_raw:
			if isinstance(entry, int):
				# It's an index
				if 0 <= entry < num_hists:
					resolved_indices.append(entry)
				else:
					warn(f"legend_order index {entry} out of range [0, {num_hists-1}], skipping")
			elif isinstance(entry, str):
				# It's a label name - find matching histogram index
				try:
					idx = labels.index(entry)
					resolved_indices.append(idx)
				except ValueError:
					warn(f"legend_order label '{entry}' not found in labels {labels}, skipping")
			else:
				warn(f"legend_order entry '{entry}' has unsupported type {type(entry)}, skipping")
		
		# Fall back to drawing order if no valid entries resolved
		if not resolved_indices:
			warn("No valid legend_order entries, falling back to drawing order")
			resolved_indices = list(range(num_hists))
		
		return resolved_indices
	
	# Get and resolve legend order
	legend_order_raw = getattr(cmp, 'legend_order', None)
	legend_indices = _resolve_legend_order(legend_order_raw, cmp.labels, len(hists))
	
	# Add legend entries in resolved order
	for idx in legend_indices:
		legend.AddEntry(legend_hists[idx], cmp.labels[idx] if idx < len(cmp.labels) else f"Hist {idx+1}", "l")
	
	legend.SetFillStyle(0)
	legend.SetBorderSize(1)
	legend.Draw()
	# Save in output directory if defined (priority: config.output_directory > function parameter > config.output_dir > current dir)
	config_output_dir = getattr(cmp, 'output_directory', None)
	if config_output_dir:
		outdir = config_output_dir
	elif output_dir and output_dir != '.':
		outdir = output_dir
	else:
		outdir = getattr(cmp, 'output_dir', None) or '.'
	Path(outdir).mkdir(parents=True, exist_ok=True)
	out_pdf_path = str(Path(outdir) / f"{cmp.output}.pdf")
	canvas.SaveAs(out_pdf_path)
	success(f"Saved comparison plot: {out_pdf_path}")
	# Optionally save ROOT macro (.C) alongside PDF when requested in config
	try:
		if getattr(cmp, 'save_macro', False):
			out_macro_path = str(Path(outdir) / f"{cmp.output}.C")
			canvas.SaveAs(out_macro_path)
			success(f"Saved comparison macro: {out_macro_path}")
	except Exception:
		pass

# Individual Excel files are saved immediately for each comparison
