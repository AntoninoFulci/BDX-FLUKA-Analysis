# Comparison plotting utilities for overlaying histograms from multiple files
from pathlib import Path
from ROOT import TFile, TCanvas, TLegend

try:
    from tabulate import tabulate
    import pandas as pd
    HAS_TABULATE_PANDAS = True
except ImportError:
    HAS_TABULATE_PANDAS = False


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
	print("  Comparing the following histograms:")
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
			print(f"    Saved comparison table to Excel file: {excel_path}")
	except ImportError:
		print("  Comparing the following histograms:")
		# Fallback: print without integral or error
		for h, f, label in zip(cmp.hists, cmp.files, cmp.labels):
			print(f"    {h:30} | {short_path(f):50} | {label}")

def compare_histograms_overlay(cmp, output_dir=None):
	"""
	Overlay multiple histograms from different files on the same canvas.
	Args:
		cmp: ComparisonConfig object (should have .files, .hists, .labels, .output, .title, .x_label, .y_label, .logx, .logy)
		output_dir: Optional override for output directory
	"""
	import ctypes
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
			print(f"    Warning: Could not find histogram '{cmp.hists[i]}' in file '{cmp.files[i]}'")
	hists = [h for h in hists if h]
	if len(hists) < 2:
		print("    Not enough histograms to compare.")
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
	default_colors = [2, 4, 8, 6, 1, 7, 9, 3]  # ROOT color codes
	colors = getattr(cmp, 'colors', None) or default_colors
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
		print(f"    Warning: Unknown or invalid legend_position '{legend_pos_raw}', using 'top_right'")
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

	# Create cloned histograms for legend with thick lines
	legend_hists = []
	for i, h in enumerate(hists):
		# Clone histogram for legend with thick lines
		legend_hist = h.Clone(f"{h.GetName()}_legend")
		color = colors[i % len(colors)]
		legend_hist.SetLineColor(color)
		legend_hist.SetMarkerColor(color)  # Set marker color to match line color
		legend_hist.SetLineWidth(3)  # Always thick for legend
		legend_hists.append(legend_hist)
	
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
	
	for i, h in enumerate(hists):
		color = colors[i % len(colors)]
		h.SetLineColor(color)
		h.SetMarkerColor(color)  # Set marker color to match line color
		h.SetLineWidth(line_width)
		if i == 0:
			h.Draw(draw_option)
		else:
			h.Draw(f"{draw_option}same")
		
		# Add legend entry using the thick clone
		legend.AddEntry(legend_hists[i], cmp.labels[i] if i < len(cmp.labels) else f"Hist {i+1}", "l")
		if getattr(cmp, 'x_label', None):
			h.GetXaxis().SetTitle(cmp.x_label)
			h.GetXaxis().SetTitleOffset(1.6)  # Increase offset for better spacing
		if getattr(cmp, 'y_label', None):
			h.GetYaxis().SetTitle(cmp.y_label)
			h.GetYaxis().SetTitleOffset(1.6)  # Increase offset for better spacing
		if getattr(cmp, 'title', None):
			h.SetTitle(cmp.title)
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
	print(f"    Saved comparison plot: {out_pdf_path}")
	# Optionally save ROOT macro (.C) alongside PDF when requested in config
	try:
		if getattr(cmp, 'save_macro', False):
			out_macro_path = str(Path(outdir) / f"{cmp.output}.C")
			canvas.SaveAs(out_macro_path)
			print(f"    Saved comparison macro: {out_macro_path}")
	except Exception:
		pass

# Individual Excel files are saved immediately for each comparison
