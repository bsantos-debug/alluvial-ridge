# Numerical comparison without published source-data inputs

From the project root, after the requested model outputs exist:

```bash
source scripts/environment.sh
python3 scripts/plot.py --data-root data --output figures
python3 scripts/compare.py --data-root data --figures figures --output figures
bash report/build.sh
```

The comparison writes `figures/comparison.json`, a corresponding CSV, and
`report/generated/results.tex`. The LaTeX input is already included by the
report. Add `--strict` to the comparison command for exit code 2 whenever a
numerical comparison remains pending. Ordinary success means records were
written; it is not a scientific reproduction claim. Missing inputs produce
explicit pending entries and pending report prose, never fabricated values.

The only reference statements embedded in the script are the main manuscript's
written trends, its approximate erodibility percentages (+15% and −6.5%), the
statement that one fine-load case exceeds beta=1, and coarse visual elevation
ranges documented in `docs/report-audit.md`. The script never reads `sources/`,
DR2 result columns, published output files or digitized curves. It does not
infer agreement from the 0–0.5 m deposit scale or other published axis limits.

## Evidence gates

A reported comparison requires documented run/A/C/E/load, 250 m grid spacing, 72 km by 48 km
domain, 20-day duration, 500 m channel width, 8 m initial depth, 1e-4 slope,
2500/15000 m3/s discharge bounds, 2650 kg/m3 sediment density and enabled migration.
All numeric assumptions in `config/physics.txt` must also match, including
erosion threshold, viscosity, sediment concentration scale and migration scale.
Only the requested stopping flood count is excluded: stopping later does not
change the physics of an already completed early flood. The physics reference
is hashed in the comparison record. The plotter must also have verified its
documented configuration subset. Unrecorded values
remain unverified rather than being filled from defaults. Constitutive
assumptions and scientific implementation fidelity are separately documented
in the implementation report; these input checks cannot establish them.

The script verifies the plot manifest's data directory and all input hashes.
If model output changed after plotting, numerical comparisons remain pending
until plots and their derived tables are regenerated. The generated comparison
record adds hashes for the exact CSV tables and raw run metadata/summaries it
consumes. Every Figure 2 profile is also checked cell by cell against its
hashed raster: exact central column, transverse cell centers, elevation,
active-channel mask, run/flood identity, completed-flood clock and geometry.
Changed derived profiles cannot pass merely because the original raster is
unchanged. Mean beta and alpha95 are independently recomputed from raw summary
rows and checked against `metrics.csv` before they enter a comparison.

Figure 3 comparisons require the full recorded history, floods 1–580.
Beta additionally requires 20 finite ratios from floods 561–580. Alpha95 and variability
require 200 finite alpha values from floods 381–580; Figure 3B also requires
all three plotted series to have 580 finite alpha values. Undefined values are not
silently dropped, zero-filled or replaced by another time window. Map/section
comparisons require the corresponding plotter panel status to show all exact
requested snapshots, validated metadata and completed requested floods, but
not unrelated intervening or later history. Thus a verified flood-61 map can
be compared after a later simulation failure. The Figure 2 relief comparison
still requires all four profiles, including flood 580. This
workflow deliberately leaves short, altered-domain smoke runs pending.

## Comparisons performed

1. At each default-load C with multiple A values, count the positive, negative
   and tied changes in mean beta between adjacent A values. These test the
   reported increasing-aggradation tendency without hiding reversals.
2. At each shared A, count beta changes between adjacent C values. The paper
   describes a general inverse tendency, not an exact monotonic constraint.
3. For E=0.5 and E=1.5, calculate beta changes relative to E=1 at A=0 and
   A=0.012, then average the two percentage changes equally. Compare that
   average to the approximate +15% and −6.5% prose values and report the
   difference in percentage points. The publication does not define the
   aggregation weights or an acceptance tolerance; no pass threshold is invented.
4. Pair all six fine-load cases with default cases at identical A/C/E. Report
   each beta difference, the count reduced by fine load, and the number of
   fine-load beta values above one. This does not identify simulated avulsions.
5. Rank all 31 alpha95 values and identify the maximum's A/C. The documented
   highest-load, lowest-available-A case is run 18 (C=0.01, A=0.004); no C=0.01,
   A=0 point is invented. Also record alpha95 changes across adjacent A at each
   default C. The reference predicts a tendency, not strict monotonicity.
6. For runs 07, 15 and 20 at A=0.018, report final-200-flood mean, population
   standard deviation, coefficient of variation (CV), minimum and maximum
   alpha. Test CV, standard-deviation and maximum ordering as C increases. CV is standard deviation
   with divisor N divided by mean; a nonpositive mean leaves CV undefined.
   The manuscript does not provide a numerical CV target. Relative and absolute
   variability need not change in the same direction, so both are retained.
7. For all six deposit panels, report independently derived footprint above
   1e-6 m, volume, maximum and 95th-percentile event thickness, deposit-weighted
   transverse spread and available sinuosity. For 1A–D report the explicit
   areas at floods 61,251,501,562 and their late changes. The paper provides no
   exact area or volume benchmark. These are spatial-scale diagnostics, not
   evidence that splays or abandoned-channel pathways have the published form.
8. For 2A–D, require all four profiles with 192 distinct transverse cells.
   Subtract the model's initial planar elevation at the saved x coordinate.
   Report crest and profile-90th-percentile relief at floods 50,225,400,580.
   Compare final maximum non-active-channel relief to the coarse visual ranges
   obtained by subtracting the publication's approximate 9 m initial datum
   from visible ridge elevations: 31–36 m (2A), 16–21 m (2B), 6–8 m (2C),
   and 21–24 m (2D). A value may fall below, within or above that approximate
   interval. These are neither digitized measurements nor statistical error
   bars or calibrated acceptance ranges. The same four-profile records now
   include positive-relief area, transverse spread, equivalent width,
   half-crest occupied width and span, and two signed flank departures from
   straight endpoint chords. These describe the independent shape; the paper
   supplies no numerical width or mathematical concavity target. Definitions
   and limitations follow below. Direct visual assessment remains necessary.

## Cross-section morphology definitions

The Results paragraph beginning “All simulations” describes concave ridge
sections; Figure 2 and its caption give the four runs and sampling times.
They do not define a curvature estimator or ridge width. The added measures
therefore quantify independent sections without translating that wording
into a numerical acceptance test. All 16 requested profiles are retained in
the existing four `section_relief_2*` comparison records, with each source
raster's SHA-256 and the processor/configuration/table hashes. The canonical
physics and exact four-snapshot gates apply to every measure, including an
explicit completed summary row for each requested flood.

At the saved column let `r_i = z_i − slope*(length−x)`, with transverse cell
centers `y_i` and width `d=250 m`. Exclude every currently active-channel cell
using its saved mask. Set `w_i=max(r_i,0)` in the remaining cells and zero in
active cells. This clipping defines an analysis weight; it does not alter
model elevations, fill channel gaps, or discard abandoned-channel depressions
from the separately reported shape. Define `H=max(r_i)` over non-active cells.

- **Positive-relief section area:** `B=d*sum(w_i)`, in m². It measures area
  above the initial plane per unit downstream length, not total deposited
  sediment or grain volume. Excavation and prescribed bed forcing also affect
  the profile; it is not a mass budget.
- **Transverse spread:** `mu=sum(w_i*y_i)/sum(w_i)` and
  `sigma²=sum(w_i*((y_i−mu)²+d²/12))/sum(w_i)`. The final term integrates each
  piecewise constant cell over its width, so a uniform raised rectangle has
  `sigma=width/sqrt(12)`. Active-cell gaps carry zero weight.
- **Equivalent width:** `B/H`. **Half-crest occupied width:** `d` times the
  number of non-active cells with `r_i≥H/2`. **Half-crest span:** distance from
  the first selected cell's lower edge to the last selected cell's upper
  edge. Span includes gaps; occupied width does not. The record also counts
  contiguous selected cell groups and flags a selected domain-edge cell.
  These are definitions of spatial scale, not published widths or targets.
  Widths are undefined for `H≤0`; centroid/spread are undefined for `B=0`.
- **Broad flank shape:** the lower-y flank extends from the first non-active
  cell to the first cell attaining `H`; the upper-y flank extends from the
  last cell attaining `H` to the last non-active cell. Thus tied crests have
  an explicit extent rather than an arbitrarily selected center. On each
  flank construct the straight chord through its endpoint elevations and
  average `r_i−chord(y_i)` over all observed non-active cells, including the
  endpoints. Report this departure in meters and divided by `H`. Positive
  means above the chord and negative below it. At least three non-active
  cells and positive `H` are required. No surface is interpolated across
  excluded channel cells. This statistic can be affected by multiple ridges
  and abandoned depressions; it is not the local second derivative and does
  not automatically classify the publication's concavity claim.

All diagnostics retain the saved 250 m grid. Elevations are float32; the
positive-relief area includes conservative bounds from the largest adjacent
half-ULP of each elevation. `positive_relief_resolved` requires at least one
non-active cell whose positive relief exceeds its rounding bound. Nominal
widths and shape remain in the numeric record when nonzero relief is
unresolved, but are not interpreted in report prose. Half-height selection,
tied crest locations and flank descriptors have no statistical error bars;
small changes near their thresholds can change them. Active-channel width
and minimum active-bed elevation are saved separately, while the existing
crest and percentile relief measures continue to exclude the active bed.

Signs use a numerical tie tolerance of 1e-12 times the larger of one or the
largest absolute value in the compared sequence. This prevents machine-scale
roundoff from becoming a physical trend; it does not serve as an agreement
tolerance. Alpha percentiles use linear interpolation, matching the plotting
script. Every CSV comparison also carries a reference description, scope
limitation and the exact pending reasons when evidence is incomplete.

## Limits that remain explicit

Deposited area is not inundation extent. In particular, changing sediment load
can change the area crossing a deposit threshold even at the same water extent.
Thus the script does not call the broader-inundation interpretation reproduced
from deposits alone. Splay formation, cutoff-channel infilling and localized
breaches require visual/map diagnostics, not just a scalar area or alpha value.
Likewise, axis limits cannot become observational maxima. The implementation
does not calculate an avulsion occurrence or frequency, so no comparison is
phrased as successful prediction of an avulsion event.

For isolated smoke data, direct both record and LaTeX outputs to a test folder:

```bash
python3 scripts/compare.py --data-root tmp/plot-stat-smoke --figures figures/test-stat --output figures/test-stat --tex figures/test-stat/results.tex --strict
```

The altered-domain/time configuration should remain pending even when its
summary has 580 rows. Synthetic reference curves or published result columns
are never needed to test the pending gates or arithmetic functions.

The initial check was executed both against absent production data and an
isolated, independently simulated 580-row short-domain dataset. Both produced
29 explicit pending comparisons and returned code 2 with `--strict`; the
altered benchmark was not promoted to a production comparison. Trend-sign
counting and linear-percentile arithmetic were checked separately, including
the benchmark's actual final-200 alpha values. Full scientific comparisons
remain to be exercised on the completed canonical run ensemble.

The cross-section extension was checked with
`python3 tmp/section-morphology-check/check.py`. Analytic profiles test exact
cell-integrated rectangular spread, split occupied width versus span, zero
departure for straight flanks, opposite chord-departure signs for two quadratic
flanks, datum/amplitude invariance, active-bed exclusion, and zero/unresolved
relief. The same helper reads the actual two-flood outputs in
`tmp/restart-validation/continuous`, retaining their noncanonical status and
source hashes in `tmp/section-morphology-check/actual-short-morphology.json`.
Missing cells, duplicate coordinates, altered elevations/masks, wrong identity
or column, absent source hashes, and missing completed-summary rows are rejected.
The end-to-end existing short-domain comparison still has 29 pending records;
no canonical Figure 2 morphology has yet been assessed.
