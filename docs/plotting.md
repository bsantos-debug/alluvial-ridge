# Independent plotting procedure

From the project root:

```bash
source scripts/environment.sh
python3 scripts/plot.py --data-root data --output figures
```

The script uses Python 3, NumPy and Matplotlib; it reads only independent model
outputs and `config/runs.csv`. It never opens `sources/` or a published result
table. Matplotlib, Python cache, and temporary directories are set under
project `tmp/` before numerical/plotting imports, so direct execution also
avoids home-directory caches. Output must be inside the project.

The default command produces every requested panel attempt even if required
data are missing. Missing panels are explicit placeholders; they are not
filled using another time, another run, an extrapolation, or published data.
For a completeness gate, append `--strict`: it writes the same figures and
records, then exits with code 2 if any panel lacks its requested complete data.
Exit code 0 without `--strict` means the plotting operation completed, not that
the scientific reconstruction succeeded. Even strict success only verifies
data availability and the recorded documented configuration; the implementation
and scientific agreement require their own verification.

## Archived first-flood validation figure

`python3 -B scripts/plot_first_flood.py` generates
`figures/first_flood_validation.pdf`, its PNG, and a separate provenance
manifest. It reads the retained `validation/first-flood-audit-002` archive,
verifies all 24 input members and completed case records, and reproduces the
recorded common-cell difference measures. These six diagnostic maps are
separate from the 13 manuscript panels and do not establish convergence.
See [first-flood-validation.md](first-flood-validation.md) for their numerical
scope, masks, scales, and archive-based regeneration command.

`report/build.sh` only verifies and includes the saved validation figure;
it does not regenerate it. A missing or stale figure produces a pending
notice while the independently verified numerical tables remain available.
The saved-data finalizer runs the plotter as a separate recorded stage before
compiling the report. Its render-only mode preserves the existing figure bytes.

## Saved products

- `figures/figure1.pdf` and `.png`: manuscript panels 1A–F.
- `figures/figure2.pdf` and `.png`: manuscript panels 2A–D.
- `figures/figure3.pdf` and `.png`: manuscript panels 3A–C.
- `figures/panel_status.csv`: per-panel availability, source files and missing
  or partial-data reasons. This is not a reproduction claim and does not
  overwrite the scientific assessment in `docs/panels.csv`.
- `figures/metrics.csv`: all 31 input configurations, observed flood counts,
  completeness flags, independently calculated beta and alpha95 where their
  full required windows exist, finite-value counts and metadata discrepancies.
- `figures/deposit_metrics.csv`: individual-flood deposit area above 1e-6 m,
  total deposit volume, maximum and 95th percentile over all floodplain cells
  including zeros, the number of cells above the displayed 0.5 m scale,
  deposit-mass-weighted transverse spread, and saved sinuosity when available.
- `figures/sections.csv`: the exact saved model elevations plotted, with run,
  flood, sampling x, transverse y, channel mask, completion flag and source.
- `figures/plot_manifest.json`: command, numerical-package versions,
  statistical conventions and SHA-256 of every consumed input.

## Formats and completion checks

Each run lives in `data/runXX`, where XX is a two-digit configuration ID.
`parameters.txt` must record run, A, C, E, fine, dx, length, width, and duration.
Recorded values are compared with the configuration table and the published
250 m spacing, 72 km by 48 km domain, and 20-day flood duration. Altered or
unrecorded values are reported as partial settings. Other constitutive choices
remain the responsibility of the scientific assumption/implementation record.

`summary.csv` has one row for each completed flood. Duplicate/invalid flood
numbers and malformed rows are flagged. Incomplete floods do not become
completed merely because a raster exists. `fields_NNNN.bin` is read in the
native layout written by `src/model.hpp`: four int32 values (nx, ny, nchan,
flood); three float64 values (dx, cumulative clock, initial slope); then ny by
nx rows of four float32 values (z, h, event_deposit, channel_mask). The script
checks dimensions, byte count, finite values, nonnegative depth/deposition,
binary mask and the cumulative clock for a claimed complete flood.
`channel_NNNN.csv` must exist with the recorded nchan rows.
The script flags a snapshot as partial if its flood is absent from summary.
It can show that same explicitly partial snapshot, but never relabels a
different flood to satisfy a requested time.

Snapshots currently occur at the end of a completed hydrograph, before that
flood's migration, cutoff and bed-aggradation step. Therefore the section and
channel mask correspond to the geometry used during that flood. This ordering
is an implementation convention; the manuscript captions do not resolve it.
The corrected executable also saves `peak_fields_NNNN.bin` and
`peak_channel_NNNN.csv` at day 12 (0.6 of the flood duration) for the same
requested floods. The `peak_` prefix denotes the diagnostic sampling time;
the assumed symmetric hydrograph reaches its actual discharge maximum at
day 10. These additional files support inundation assessment and do not
replace the end-flood deposition maps below. Both output phases precede
migration/aggradation, so flood n has `(n-1)A` prescribed bed elevation gain.

## Panels 1A–F

| Panel | Run | Flood |
|---|---:|---:|
| 1A | 11 | 61 |
| 1B | 11 | 251 |
| 1C | 11 | 501 |
| 1D | 11 | 562 |
| 1E | 17 | 562 |
| 1F | 03 | 562 |

The maps plot the model's saved individual-flood deposit thickness in meters,
with flow along increasing x. Active channel cells are black and deposits
below 1e-6 m are green. The displayed scale is 0–0.5 m for comparison to the
published figure. Larger computed values remain in data and deposit-volume
calculations; the colorbar identifies saturation above its range. The magenta
line in 1E is drawn along the actual internal Cartesian faces separating
channel and floodplain cells, the same geometry counted by the interface
metric. It is not a fitted or decorative channel-belt outline. The snapshot
is from flood end; alpha wetness was sampled at 60% duration, so this line
shows the interface geometry, not a reconstructed day-12 inundation pattern.

Visual inspection of the embedded published Fig. 1E at 300 dpi supports the
active-channel interpretation: the magenta dashed lines follow both sides
of the current black channel through its bends, while several abandoned
loops and depositional tongues remain outside. They do not follow the outer
envelope of the entire channel belt. This is a visual inference; the enlarged
dashed offset cannot establish an exact grid-face position or the authors'
wetness threshold. Those remain declared numerical choices.

## Panels 2A–D

| Panel | Run | A (m/flood) | C |
|---|---:|---:|---:|
| 2A | 22 | 0.036 | 0.01 |
| 2B | 10 | 0.036 | 0.0003 |
| 2C | 03 | 0 | 0.0003 |
| 2D | 15 | 0.018 | 0.003 |

Each panel requests floods 50, 225, 400 and 580. The grid is cell-centered;
at dx=250 m the exact mid-domain x=36 km lies between two columns. The script
plots the saved column at x=36.125 km and labels that actual coordinate.
No vertical datum shift, smoothing or spatial interpolation is applied. The
model datum has initial floodplain z=slope*(length-x); thus its initial
section is about 3.6 m, whereas the publication uses an unspecified datum
with an initial section near 9 m. Compare relief or state a datum offset
explicitly when interpreting differences. Cyan marks identify saved active
channel-bed cells at flood 580. No active channel is manufactured when the
flood-580 snapshot is absent.

## Panels 3A–C

3A takes the arithmetic mean of the 20 saved per-flood beta ratios at floods
561–580 for every configuration. This averaging convention is explicit
because DR1 does not distinguish mean of ratios from ratio of averages.
3B plots every available per-flood alpha for runs 07, 15 and 20, preserving
undefined or missing values as gaps. Their values are sampled by the model
at 60% flood duration, which is day 12 only for the documented 20-day flood.
3C uses NumPy's linearly interpolated 95th percentile of exactly 200 alpha
values from floods 381–580. No rolling replacement window is used. All 20
beta or 200 alpha values must be finite before a statistic is emitted;
undefined alpha from zero wetted interface is not changed to zero or dropped
from the percentile. A missing window yields an empty metric field and no
plotted point. No later-than-580 flood enters these summaries.

All scatter symbols come from computed summary values; color identifies C,
diamonds identify fine load, and plus/cross identify E=0.5/1.5. Red rings
mark values computed from a full required window when their metadata differs
or a complete flood 1–580 history is not established. Such points remain
partial. Alpha axes are logarithmic when all available values are positive;
nonpositive finite alpha requires a labeled linear axis. The beta=1 line is a
published interpretive reference, not an enforced threshold or avulsion event.

For plotting smoke tests, use a separate `--data-root` and an output such as
`figures/test`; test or benchmark data must never replace production run
folders. Missing-data checks can be exercised against an empty directory and
must retain all 13 explicit missing statuses.

## Verification performed

The all-missing-data command emitted all 13 explicit missing statuses and
returned exit code 2 with `--strict`. Separate, independently calculated
6 km by 4 km, 600-second-flood, migration-disabled smoke runs exercised a
flood-61 deposition raster, a flood-50 section, and all 580 summary rows.
These altered-domain/time tests are stored under `tmp/plot-smoke` and
`tmp/plot-stat-smoke`, with plots under `figures/test-*`; none is a manuscript
reproduction. Their actual model outputs verified binary parsing, time checks,
partial-configuration labels and statistics. The beta mean and alpha95 from
the 580-row test agreed with direct arithmetic averaging and the sorted-value
linear-percentile formula. Removing flood 580 from that test's in-memory
records prevented both final-window statistics. Generated raster and section
pages were visually inspected; partial/missing times are visibly identified.

## Saved spatial measurements in the PDF

After generating the inundation and planform JSON files, `bash report/build.sh`
renders their exact requested Figure 1 samples into `report/generated/spatial.tex`.
The three tables report day-12 water extent and wet-bank patches, deposition
fractions, and active-centerline geometry. Definitions and limits are in
`docs/inundation-comparison.md` and `docs/planform-comparison.md`. The tables
do not promote diagnostic or altered-configuration runs into manuscript data.
Missing, inconsistent and noncanonical samples remain dashes.

The renderer verifies each helper's processor/configuration hashes and every
recorded numerical input inside the packaged project before displaying its
values. Each eligible Figure 1 record must also identify the exact requested
run and flood, and its end-flood raster, parameters and summary must match the
paths and hashes recorded for that panel in the current plot manifest and
panel-status table. Planform records additionally bind the channel CSV;
inundation records require the day-12 raster in that same plotted run folder.
Hash-valid diagnostics from another retained run directory are withheld even
when their numerical files have identical bytes. Any eligible-record mismatch
withholds that helper's entire table contribution.
`report/generated/spatial_evidence.json` records these checks and the plot
manifest/panel-status hashes used for binding. Figure 1
assessment fingerprints also bind the optional helper JSON bytes and their
verified/absent state; changed or unverifiable spatial evidence invalidates
the corresponding previous assessment. Numerical availability never assigns
scientific agreement automatically.

An isolated check used actual shortened two-flood restart data: both helpers
remained noncanonical, all requested rows were withheld, and a change to the
consumed parameter file caused both diagnostic records to be rejected. A
separate in-memory renderer fixture exercised numeric formatting with those
diagnostic values without publishing them as canonical results. Checks and
their generated files are under `tmp/spatial-report-check`; root and rebuild
002 generated outputs were not overwritten.
A focused metadata-only check (`python3 tmp/spatial-report-check/binding-check.py`)
accepted matching source paths/hashes for both helpers, rejected an alternate
directory whose input hashes were all valid and whose bytes were identical,
and rejected a wrong requested flood. Its readiness flags test only the binding
branch; the fixture contains no numerical arrays or scientific results.
