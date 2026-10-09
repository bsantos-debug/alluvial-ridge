# Independent planform geometry and cutoff timing

The written Results in [Nicholas et al. (2018)](https://doi.org/10.1130/G40104.1)
describe bend growth interrupted by cutoff, widening of the channel belt,
and accumulation of abandoned channel elements. Figure 1 shows individual-flood
deposits with active channel cells shaded black. The text and caption provide
no numerical sinuosity, bend wavelength, lateral amplitude, or cutoff schedule.
Consequently the measurements below describe the independent calculation;
they cannot establish quantitative agreement with an unreported target. No
author output, source-data table, code, or digitized figure coordinates enters
this calculation.

Run from the project root:

```bash
python3 scripts/planform_metrics.py --data-root data --output figures
```

The standard-library script reads `config/runs.csv`, `config/physics.txt`, `parameters.txt`,
`summary.csv`, end-flood `channel_NNNN.csv`, and the corresponding
`fields_NNNN.bin` for runs 03, 11, and 17. It reads all available end-flood
centerlines in those runs, together with explicit entries for the six requested
Figure 1 snapshots: run 11 at floods 61, 251, 501, and 562; run 17 at 562; and
run 03 at 562. It excludes `peak_` snapshots, which duplicate the same geometry
at an earlier hydraulic sampling time. Output stays inside the project.

## Measured quantities

Coordinates are in meters; the valley axis is x and lateral distance is y.
For saved points p_i, let d_i = |p_(i+1)-p_i| and L = sum(d_i).
The script reports L, endpoint separation, L divided by recorded valley length
(the core's sinuosity convention), and L divided by endpoint separation.
The two sinuosities coincide for the fixed equal-y inlet and outlet. A mismatch
between calculated valley sinuosity and the same flood's summary beyond
relative 1e-8 or absolute 1e-10 flags the snapshot. This tolerance accommodates
the saved 12-significant-digit CSV coordinates; it is not an agreement threshold
against the paper.

The active centerline's physical lateral extent is max(y)-min(y). Its mean y
and lateral RMS about that mean are weighted by arc length. The integral of
y is trapezoidal, and the integral of (y-mean_y)^2 is evaluated exactly along
each linear segment, using d_i*(a^2+a*b+b^2)/3 for endpoint departures a,b.
These measures describe the saved active line. They do not recover the total
historical belt, channel width, point-bar area, or number of abandoned channels.
Sparse saved lines can miss an excursion before cutoff; even their union would
provide only a sampled lower bound on the historical centerline envelope.

At each interior point the signed three-point circumcircle curvature is

    k_i = 2 cross(p_i-p_(i-1), p_(i+1)-p_i)
          / [d_(i-1) d_i |p_(i+1)-p_(i-1)|].

The script reports mean absolute curvature, RMS curvature, maximum absolute
curvature, and inverse RMS curvature in meters. Interior weights are
w_i=(d_(i-1)+d_i)/2; endpoint curvatures are excluded. The reported support
length is sum(w_i), not the full arc length. A straight line has zero curvature
and a null inverse RMS scale; a sampled circular arc of radius R has RMS 1/R.
The inverse RMS quantity is a curvature scale, not a bend wavelength or the
mean of local radii. No smoothing, fitting, resampling, or amplitude threshold
is applied. Node count and minimum/maximum segment lengths accompany each
measurement because raw curvature is sensitive to the initial perturbation,
node spacing, and cutoff corners. Duplicate adjacent points and degenerate
reversals make the geometry invalid rather than silently changing it.

## Flood indexing and event censoring

In this implementation, `summary.csv` and the end-flood snapshots are written
after the hydraulic calculation for flood n and before its migration, cutoff,
and aggradation. Thus the saved line is the geometry used during flood n, and
its imposed elevation gain is (n-1)A. This ordering is an implementation
convention; the manuscript does not specify the same phase.

If C(n) denotes the summary's cumulative `cutoffs`, then

    cutoffs in the remap after flood n = C(n+1) - C(n).

The JSON lists positive count increments. Adjacent summaries give an exact
remap flood, even if that remap contains several cutoffs. If only summary
rows a and b are available, C(b)-C(a) belongs to remaps after floods a through
b-1; the script retains that entire interval. It does not distribute events
across missing floods. A nonzero cumulative count in the first available row
is separately left-censored. The remap after the last summary is always
unobserved by this convention: even a full 580-row history only dates events
through the remap after flood 579. The geometry retained in a checkpoint or
the presence of a remap budget row does not supply an additional cutoff count.
Flood indices are not converted to calendar years or return periods.

The full observed summary series (flood, sinuosity, cumulative cutoff count)
is retained for assessing growth between cutoff intervals. A decrease across
an event interval combines migration and cutoff; it does not isolate the
length removed by cutoff. Duplicate/invalid summary rows, noninteger or
negative counts, decreasing counts, and a nonzero pre-remap count in flood 1
invalidate cutoff timing and prevent a completed-snapshot claim.

## Output and missing-data contract

`planform_metrics.json` contains the exact command, input SHA-256 hashes, all
recorded parameters, configuration discrepancies, summary series, censored
cutoff events, and per-snapshot metrics/status. The hashes cover the exact
bytes read, including the script and configuration table. A run's original
binary/source provenance remains the responsibility of the suite manifest;
these hashes do not certify that an arbitrary input was generated by the
current executable. `planform_metrics.csv` gives one row per requested or
additionally available snapshot, with flat metric columns and status flags.
Absent metrics are null in JSON and blank in CSV, never zero-filled estimates.

A completed snapshot requires a valid same-flood summary and centerline,
matching binary row count, dimensions, flood index and byte count, recorded
grid/domain agreement, and an end-flood clock. Only the binary header and
byte count are checked here; the raster's hydraulic/deposit values are not
analyzed. `scripts/plot.py` performs the raster validation. A partial snapshot
can still have measurable geometry, explicitly labeled as a partial diagnostic.
Noncanonical snapshots remain labeled as diagnostic, even when their shorter
floods have completed. No nearby time or different configuration fills a
missing requested panel.

`panel_data_ready` requires completed snapshots and the documented configuration
checks used by `scripts/compare.py`: run/A/C/E/load, grid/domain, flood duration,
channel width, slope, initial depth, discharge bounds, and migration enabled,
plus the recorded grain density of 2650 kg/m^3.
It additionally checks all recorded assumptions against the hashed
`config/physics.txt`, including migration scale, initial perturbation/seed,
friction/settling parameters, and CFL. The requested flood count is excluded:
a valid early snapshot remains measurable when a later flood fails. Missing
assumptions or deliberate sensitivity variants therefore remain noncanonical.
This flag does not validate the physical adequacy of these assumed closures.
`required_data_complete` requires all six requested canonical snapshots;
`histories_complete_1_to_580` separately records full histories in all three
runs. Neither flag establishes scientific agreement. `--strict` writes all
diagnostics and exits 2 until the six requested snapshots are ready. It does
not require later floods to assess an already available panel. Ordinary exit
0 means only that postprocessing completed.

## Development checks, 2026-10-09

The script was exercised only on existing independent small diagnostic outputs:

```bash
python3 scripts/planform_metrics.py --data-root tmp/plot-smoke --output tmp/planform-smoke
python3 scripts/planform_metrics.py --data-root tmp/suite-runner-smoke/data --output tmp/planform-restart-smoke --strict
```

The first dataset uses a 6 km by 4 km domain, 600-second floods, and disabled
migration. Its three available centerlines give L=6003.199188786 m,
sinuosity=1.000533198131, lateral extent=16.836931500 m, and lateral
RMS=4.584066557 m. Their calculated sinuosity differs from saved summary by
9.24e-13. All three are explicitly noncanonical diagnostics; zero of six
manuscript panels is ready. The second dataset has two 10-second floods on a
4 km domain, disabled migration, and a straight line: sinuosity=1, lateral
extent=0, and curvature=0. Its strict exit code is 2. Its final remap is
explicitly unobserved, despite both floods having completed.

Separate function checks passed for circular curvature (R=2000 m), straight
geometry, the exact lateral variance of a sloping segment, translation
invariance, exact and gapped cutoff intervals, left/right censoring, and
rejection of decreasing or impossible initial counts. Copies of the actual
small diagnostic inputs verified that a missing summary, duplicate summary
row, and truncated binary preserve partial/invalid status. Input hashes were
recomputed and matched. These are postprocessing checks, not numerical
planform predictions or manuscript results. The requested full-domain panel
assessment remains pending.
