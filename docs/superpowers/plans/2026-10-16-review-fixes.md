# Review fixes implementation plan

**Goal:** Apply the user's accepted review fixes and remove unused legacy configuration support.
**Architecture:** Relative package imports; OutputConfig owns filename discovery; ROOT resources have scoped ownership. Preserve box selections, smoothing arithmetic, and default filenames.
**Spec:** User's approved checklist in this session; review `docs/reviews/2026-10-16-code-review.md`.

- [x] Remove previous review artifacts and caches before modifying code.
- [x] Use package imports throughout production and tests; keep run_analysis.py and python -m src.analysis working.
- [x] Warn when cached EOT is reused; keep user's explicit --remove-runsummary choice.
- [x] Let OutputConfig define export discovery for custom names/templates with existing defaults.
- [x] Remove unused Variable2DConfig; reject obsolete input clearly.
- [x] Retain the agreed current YAML comparison schema, remove old parsers, migrate repository examples/docs/tests.
- [x] Fail comparison processing with fewer than two available histograms; preserve warnings and correct identities for partial comparisons that remain usable.
- [x] Close ROOT files/canvases on success and failure in analysis, comparison and export.
- [x] Run regression tests and representative real data checks; remove generated artifacts afterward.
- [x] Update review status and document removed schema/API behavior.

Validation: package/CLI subprocess tests; default/custom/timestamped filename discovery; cached EOT warning without recomputation; malformed/obsolete config rejection; failure status for missing comparisons; ROOT resource counts on successful and exceptional paths; existing scientific invariant tests. Run native execution in this workspace, preserving prior user edits; no commit requested.
