# Full first-flood validation: corrected rebuild 002

The corrected 250 m, 500 m, 250 m half-CFL, and 0.05 Pa deposition-threshold
sensitivity cases have completed one full flood.
All 31 production cases also completed their first flood and remained active
in flood 2 at the captured observation on 2026-10-09 at 21:39:16 UTC. These
results extend the earlier coarse-grid audit preserved below. They establish
first-flood consistency and substantial resolution sensitivity; they do not
establish grid convergence or reproduce any requested manuscript panel.

## Completed 250 m and 500 m comparison

Both sensitivity cases use run 11, the full 72 km by 48 km domain, and the
same corrected executable. Their recorded numerical parameters differ only
in floodplain spacing. Channel width remains 500 m and initial channel-node
spacing remains 250 m. The 250 m case completed at 20:53:50 UTC; the 500 m
case completed at 19:41:34 UTC, both with exit code 0. Every artifact hash in
both completed process records was verified. The retained
[comparison](../validation/first-flood-audit-002/two-resolution.json) has SHA-256
`6932613746a746f28abae0963e7cf01587cfb3d491f90a2fe5b5c3059951260d`.
Its [analysis script](../validation/first-flood-audit-002/two-resolution.py)
reads the saved data and prints JSON without running the model. The
[retained resolution inputs](../validation/first-flood-audit-002/resolution-inputs.tar.xz)
contain the 24 files under `validation/runs/baseline250/`
and `validation/runs/coarse500/`. The [archive verification instructions](../validation/first-flood-audit-002/README.md)
check those bytes without the original temporary workspace. The original
analysis invocation, which requires that historical source-case layout, was:

```sh
python3 -B validation/first-flood-audit-002/two-resolution.py .
```

The separate [validation figure](../figures/first_flood_validation.pdf) maps
day-20 water depth, event-deposit thickness, and coarse-minus-fine differences.
It can be regenerated directly from the retained archive, without the live
workspace or a model run:

```sh
python3 -B scripts/plot_first_flood.py
python3 -B scripts/diagnostic_sensitivity.py
bash report/build.sh
```

The plotter verifies all 24 archived members and the completed case records,
then recomputes the common-cell differences against the retained comparison.
Its [manifest](../figures/first_flood_validation_manifest.json) records input,
processor and output hashes, package versions, and display conventions.
Water scales are linear; deposit scales are logarithmic from 1e-6 to 0.5 m,
with smaller values white. Signed deposit differences use a base-10 symmetric
logarithmic scale with a linear core of ±1e-4 m. Gray marks channel cells or
excluded comparison blocks. Display thresholds do not modify the metrics.
The report verifies the figure manifest before including it as **Validation
figure V1**; it leaves all 13 manuscript-panel assessments unchanged.

The percentage column uses `100*(coarse500/baseline250 - 1)`. Alpha is sampled
on day 12; the remaining quantities below precede the first remap at day 20.
Deposited mass is the accumulated source ledger retained in the checkpoint.

| Quantity | 250 m | 500 m | Coarse change (%) |
|---|---:|---:|---:|
| Alpha (m) | 0.884485917 | 0.770580353 | -12.8782 |
| Ridge height (m) | 0.0131874394 | 0.0335724137 | +154.5787 |
| Beta | 0.00164371587 | 0.00417847871 | +154.2093 |
| Mean channel bankfull depth (m) | 8.02294344 | 8.03460208 | +0.1453 |
| Total water storage (m³) | 5.55864786e8 | 2.07257542e8 | -62.7144 |
| Deposited mineral mass (kg) | 2.24278687e9 | 4.45430159e9 | +98.6057 |

At day 12, wet floodplain area above 1 mm is 3397.75 km² at 250 m and
3392.75 km² at 500 m. Both have an inundated bank fraction of one, so their
alpha difference is their mean floodplain-depth difference. Similar wet areas
therefore do not imply similar water storage or sediment deposition.

The field comparison averages each 2 by 2 group of fine cells onto a coarse
cell and excludes every block containing a channel cell in either grid. Over
the resulting 3384 km² common floodplain, end-flood depth has mean absolute
difference 0.100738 m and maximum difference 0.386764 m. Event-deposit thickness
has mean absolute difference 0.000297931 m and maximum difference 0.128899 m.
These spatial means include dry and weakly depositional areas and omit the
excluded channel-containing blocks; they must be interpreted alongside the
integrated mass and near-channel differences.

The sampled bank interface is 144 km long at 250 m and 215 km at 500 m.
After the first migration, the 250 m case captures and abandons no raster
cells and has zero bank reservoir. The 500 m case captures 49 cells and
abandons 50, giving the 1.5680e11 kg reservoir documented below. The minimum
post-remap channel depth is 4.35976 m at 250 m and 6.70414e-8 m at 500 m.
Thus resolution affects the channel footprint and subsequent recycling as
well as the hydraulic and sediment discretization. Both remaps remain
conservative: post-remap water residuals are -1.91927e-5 and -9.29907e-5 m³,
and full-solid residuals are -0.360248 and -0.259179 kg, respectively.
Both water and mass correction ledgers are zero.

Two resolutions do not determine a convergence order. The CFL-controlled
time steps change with floodplain spacing, while channel spacing is held
fixed; the 125 m case remains active. The time-step comparison follows below. Neither
first-flood case tests recycling through a subsequent complete hydrograph.
Run 11 at flood 1 also supplies none of the Figure 2 configurations and
sampling times. Its ridge height is a longitudinal-mean estimator used for
beta, whereas Figure 2 shows individual central cross-sections at floods
50, 225, 400, and 580. The profile area, spread, width, and flank definitions
in [comparison.md](comparison.md) cannot turn these early diagnostics into a
late-time profile comparison.

## Completed first-flood time-step comparison

The corrected `time250_cfl02` process completed at 2026-10-10 00:43:01 UTC
with exit code 0. Its parameters differ from `baseline250` only in the CFL
limit, reduced from 0.4 to 0.2. Both use the same corrected executable, 250 m
floodplain grid, 250 m initial channel spacing, and full 20-day hydrograph.
Macrosteps increase from 125,765 to 250,265; channel substeps increase from
452,282 to 899,949. The adaptive steps are not uniformly halved at every time.

The [retained comparison](../validation/first-flood-audit-002/time-step.json)
and [input archive](../validation/first-flood-audit-002/time-step-inputs.tar.xz)
preserve both completed process records and every recorded artifact. Replay
the numerical comparison directly from the archive:

```sh
python3 -B validation/first-flood-audit-002/time-step.py
```

Percentage changes use `100*(CFL0.2/CFL0.4 - 1)`. Alpha is the day-12 value;
ridge height, beta, channel depth, and water storage are measured at day 20
before migration/remapping. Deposited mass is the accumulated mineral source
ledger retained in the post-remap checkpoint.

| Quantity | CFL 0.4 | CFL 0.2 | Change (%) |
|---|---:|---:|---:|
| Alpha (m) | 0.884485917 | 0.877252155 | -0.81785 |
| Ridge height (m) | 0.0131874394 | 0.0132256502 | +0.28975 |
| Beta | 0.00164371587 | 0.00164846526 | +0.28894 |
| Mean channel bankfull depth (m) | 8.02294344 | 8.02300818 | +0.00080690 |
| Total water storage (m³) | 5.55864786e8 | 5.22785461e8 | -5.95097 |
| Deposited mineral mass (kg) | 2.24278687e9 | 2.07035092e9 | -7.68847 |

Both day-12 inundated interface fractions equal one, so the alpha change is
the change in mean floodplain depth. The saved end-flood fields have identical
channel masks. Over all 3420 km² of floodplain, including dry cells, water
depth has mean absolute difference 0.00941692 m and maximum difference
0.0633942 m. Event-deposit thickness has mean absolute difference
0.0000367180 m and maximum difference 0.00362724 m. The retained analysis
also includes the day-12 fields and floating-point storage bounds.

The half-CFL post-remap residuals are −1.71661e-5 m³ water, −1.46355 kg
suspension plus deposition, and −0.692458 kg total solids. Their magnitudes,
normalized by prescribed upstream inputs of 1.512e10 m³ and 5.47345904e10 kg,
are below 2.7e-11. These small conservation residuals coexist with a 5.95%
change in end-flood water storage and a 7.69% change in deposited mass.
Both first remaps have zero captured or
abandoned cells, bank reservoir, recycled mass, cutoffs, and correction terms.
The checkpoint retains signed bed forcing separately: 176,403.115 and
176,406.197 kg, respectively, despite the zero prescribed aggradation rate.
The pre-remap summaries precede this first forcing update and report zero.

Two CFL limits do not determine a temporal convergence order or establish
time-step independence. This completed first-flood comparison does not test
later bank recycling, 580-flood evolution, or agreement with a manuscript panel.

## Completed first-flood deposition-threshold comparison

The corrected `tau005` process completed at 2026-10-10 02:22:51.647420 UTC
with exit code 0. Its process record matches the sensitivity driver manifest,
and all 11 recorded artifact hashes passed verification. Among the 32 numerical
parameter entries, the sole difference from `baseline250` is the critical
deposition shear stress, `tau_critical`, reduced from 0.1 to 0.05 Pa. Both
cases retain CFL 0.4, the 250 m floodplain grid, the same initial channel
geometry, and the complete 20-day hydrograph. Their corrected executable
SHA-256 is
`b3d984881a2f82757ff9bb6ca7c15f9e3c28e3d34106ae477fe7c06af6f8099c`.
The `tau005` checkpoint SHA-256 is
`2bd71574c427fc7f5a74c3775bae8cf3afc7d7e9ba7f2e81ffea3bee5b610411`.

The [retained comparison](../validation/first-flood-audit-002/threshold.json),
[capture record](../validation/first-flood-audit-002/threshold-capture.json),
and [input archive](../validation/first-flood-audit-002/threshold-inputs.tar.xz)
preserve both completed cases and their original process records. Replay
reads the retained archive without consulting the live workspace:

```sh
python3 -B validation/first-flood-audit-002/threshold.py
```

Percentage changes use `100*(tau005/baseline250 - 1)`. Alpha is sampled on
day 12; ridge height, beta, channel depth, and water storage precede remapping
at day 20. Deposited mineral mass is the cumulative deposition-source ledger
retained in the post-remap checkpoint.

| Quantity | 0.1 Pa | 0.05 Pa | Change (%) |
|---|---:|---:|---:|
| Alpha (m) | 0.884485917 | 0.884489763 | +0.000434874 |
| Ridge height (m) | 0.0131874394 | 0.0141532006 | +7.32334 |
| Beta | 0.00164371587 | 0.00176388889 | +7.31106 |
| Mean channel bankfull depth (m) | 8.02294344 | 8.02386174 | +0.0114460 |
| Total water storage (m³) | 5.55864786e8 | 5.56110624e8 | +0.0442261 |
| Deposited mineral mass (kg) | 2.24278687e9 | 1.80697245e9 | −19.4318 |

Lower integrated deposition accompanies higher ridge relief and beta. The
ridge estimator uses crest-to-distal relief in a longitudinally averaged
profile, whereas the deposition ledger integrates mineral mass over the
domain. These quantities weight the spatial deposit pattern differently.
This comparison records their opposite changes without identifying a
mechanism for the changed pattern.

End-flood porous deposit volume decreases from 1,410,557.78 to
1,136,460.66 m³. Multiplication by the dry bulk density
`rho_s*(1-porosity) = 1590 kg/m³` converts those volumes to mineral mass.
For `tau005`, the raster-derived mass differs from the source ledger by
4.26 kg, within its 79.74 kg float32 storage bound. The source ledger and
remaining porous deposit volume retain distinct definitions. Their agreement
here is checked for this first flood with zero captured or abandoned cells.

The field comparison uses all 54,720 common floodplain cells, including dry
cells, over 3420 km². Differences are `tau005` minus baseline; the table gives
their magnitudes. Both day-12 inundated interface fractions equal one, and
wet floodplain area above 1 mm remains 3397.75 km². End-flood inundated area
increases by 0.125 km², or two cells.

| Snapshot | Field | Mean absolute difference (m) | Maximum absolute difference (m) |
|---|---|---:|---:|
| Day 12 | Water depth | 3.72141e-5 | 0.00788608 |
| Day 12 | Event-deposit thickness | 3.70402e-5 | 0.00843491 |
| Day 20 | Water depth | 9.53963e-5 | 0.00367419 |
| Day 20 | Event-deposit thickness | 1.12036e-4 | 0.00822584 |

The snapshot clocks are exactly 1,036,800 and 1,728,000 s, with 289 matching
channel rows. The post-remap v2 checkpoint records flood 1 at 1,728,000 s,
125,769 steps, 452,283 channel substeps, and 290 nodes. Its full parameter
signature, payload size, finite arrays, and nonnegative water and suspended
inventories passed inspection. Actual pre/post-remap mask comparisons give
zero captured and abandoned cells. Bank reservoir, recycled mass, cutoffs,
and water/mass correction terms are zero in both cases. The `tau005`
checkpoint separately records 176,446.832 kg of signed bed forcing; the
pre-remap summary precedes that update and reports zero.

| Tau005 post-remap inventory | Signed residual | Residual / prescribed input |
|---|---:|---:|
| Water | −5.13196e-5 m³ | −3.39415e-15 |
| Suspension plus deposition | −0.636380 kg | −1.16266e-11 |
| Full solid inventory | −0.344117 kg | −6.28701e-12 |

Normalization uses one complete prescribed upstream hydrograph:
1.512e10 m³ water and 5.47345904e10 kg sediment. These gross inputs exclude
outflow, recycling, and signed bed forcing; the checkpoint's net external
ledgers are separate quantities. Small budget residuals establish numerical
closure for the stated inventories. This two-value threshold comparison
quantifies a first-flood assumption sensitivity; it does not select a physical
threshold, establish spatial or temporal convergence, test later recycling,
or reproduce a manuscript panel. Float32 storage bounds do not estimate
discretization or physical uncertainty.

## Diagnostic-definition sensitivity

The publication leaves the ridge, distal-floodplain and channel-depth averages
underdetermined. The [saved-data analysis](../scripts/diagnostic_sensitivity.py)
varies those definitions using the same two archived first-flood states. Its
[results](../figures/first_flood_diagnostic_sensitivity.json) retain the complete
scenario matrix, effective grid windows, source identities and rounding bounds.
This calculation changes diagnostics only; it does not alter the model state.

For the ridge numerator, subtract the initial plane from each end-flood bed
elevation, exclude active-channel cells, and form a longitudinal mean for each
retained cross-valley row. Ridge relief is the largest row mean minus the
equal-weight mean of the valid distal row means. Changing the central reach
while holding the nominal distal bands at 10% and the full-interface mean
channel depth fixed gives:

| Nominal central reach | Beta change at 250 m (%) | Beta change at 500 m (%) |
|---|---:|---:|
| 60% | −21.73 | −18.02 |
| 80%, default | 0 | 0 |
| 100% | +73.52 | +34.07 |

Changes are relative to each grid's default raster reconstruction. Integer
trimming gives central lengths of 43.5 and 44 km at nominal 60%, 58 km on both
grids at nominal 80%, and 72 km at 100%. The default distal bands are 4.75 km
and 4.5 km wide on each side. Thus the modeled first-flood relief varies
substantially with the reach included in the average. This comparison does
not isolate a cause for the spatial variation or select a preferred estimator.

At the default reach, changing each distal band to nominal 5%, 10%, or 20%
changes beta by at most 0.24%. A separate denominator calculation holds the
default ridge fixed and averages bankfull depth only over interface faces
adjacent to floodplain cells in the selected central reach. The nominal
60%, 80%, and full-reach choices change beta by at most 0.20%. Every internal
channel–floodplain face contributes, including dry faces; repeated bank cells
retain their face multiplicity. These two effects are isolated from the reach
changes in the table. The result file also retains all nine numerator
combinations of reach and distal band.

For alpha at day 12, thresholds of 0.1, 1, and 10 mm keep all 576 interface
faces wet at 250 m and all 430 wet at 500 m. The full-domain mean floodplain
depth includes dry cells and is unchanged, so alpha is unchanged. The wet
floodplain area nevertheless ranges from 3389.625 to 3404.875 km² and from
3371.25 to 3406.75 km², respectively. No tested face or cell classification
is ambiguous under float32 rounding. This result does not imply that alpha
will be insensitive when later wet interface fractions are smaller.

Each stored elevation and depth is enclosed by its conservative half-ULP
float32 interval. Row means use summed interval widths; crest bounds allow
the maximizing row to change. Bankfull-depth bounds retain both elevations
at every face. Beta bounds use all four endpoint quotients when the depth
interval is positive. Shared cells are correlated, so these are deterministic
representation bounds, not statistical error bars. Default ridge height,
channel depth, beta and alpha agree with the double-precision summary after
allowing for float64 arithmetic and its 12-significant-digit CSV formatting.
The beta reconstruction differences are 3.04e-10 and 2.91e-9, inside intervals
with half-widths about 3.9e-8 and 3.8e-8. These bounds do not estimate numerical
discretization or physical uncertainty.

The analysis establishes first-flood definition sensitivity only. Later
diagnostic robustness requires later states; sparse saved rasters cannot
reconstruct alternative means over all final 20 floods or percentiles over
all final 200 floods. No manuscript panel is supplied by this analysis.

## First production flood in all 31 cases

The [captured production observation](../validation/first-flood-audit-002/production-observation-20261009T213916.json)
records all 31 first-flood summaries, snapshots, and post-remap checkpoints,
with 289 input hashes. Its [script](../validation/first-flood-audit-002/production-observation.py)
verified live process identities, executable hashes, checkpoint signatures,
finite fields, and nonnegative water and suspended-class inventories. At
21:39:16 UTC, every case had completed exactly one flood and was advancing
through flood 2, with saved progress between days 5.86135 and 11.32774.
These are time-specific observations; the script rejects later checkpoints
or exited processes rather than reproducing this earlier state.

All 31 first remaps have zero captured cells, abandoned cells, cutoffs, bank
reservoir, recycled mass, and numerical water/mass corrections. Post-remap
channel depths across all nodes and cases span 4.35888--4.99890 m. This bounds
the initial remap behavior on the production grid, but does not test later
bank erosion, cutoff transfer, or recycling. Aggradation and migration follow
the saved first-flood diagnostics, so those diagnostics cannot establish the
long-term effects of A or E.

Across the 31 cases, first-flood alpha spans 0.884224--0.884829 m, beta spans
1.52612e-5--0.00563365, and the ridge-height estimator spans
0.000122093--0.0455068 m. Maximum local event deposition spans
0.00363068--0.945409 m, and bulk event-deposit volume spans
1.15954e4--4.63861e6 m³. These are independently computed early-flood ranges,
not comparisons with the manuscript's later maps or profiles.

| Post-remap inventory | Largest absolute residual | Largest absolute residual / prescribed input |
|---|---:|---:|
| Water | 1.31249e-4 m³ | 8.68052e-15 |
| Suspension plus deposition | 2.51689 kg | 1.47412e-11 |
| Full solid inventory | 0.396595 kg | 7.24578e-10 |

Each normalized value uses its own run's first-flood prescribed input;
the absolute and normalized maxima need not occur in the same run.
Maximum absolute local remap defects are 8.34465e-7 m³ for water,
3.81470e-6 kg for an individual suspended class, and 5.56290e-4 kg for the
full solid inventory after prescribed bed forcing. Independent checkpoint
storage sums agree with the post-remap ledgers within 4.29153e-6 m³ for
water and 6.37816e-6 kg for suspension plus deposition. These small residuals
verify the stated budgets; they do not resolve the physical closures or the
resolution sensitivity above. All 580-flood production histories and all
13 requested panel assessments remain incomplete.

The first remap's signed prescribed bed forcing spans -7.75454e5 to
+2.06082e9 kg across the production cases. Its largest ratio to prescribed
upstream sediment input is 37.6511%, in run 10. This ledger includes imposed
channel-bed aggradation and adjustments associated with the prescribed bed
geometry. It is explicitly external forcing in the solid budget. Small
closure residuals therefore do not establish that all modeled solid changes
arise from conservative transport of upstream sediment.

All 289 hashed production inputs are preserved in the
[capture archive](../validation/first-flood-audit-002/production-inputs-20261009T213916.tar.xz), including
the first-flood checkpoints that subsequent floods replace in the live suite.
The [capture manifest](../validation/first-flood-audit-002/capture-provenance.json)
binds the observation, retained audit scripts, and input archive. The
[verification command](../validation/first-flood-audit-002/README.md) reads the
saved archive without changing any simulation output.

## Historical coarse audit: 19:44:59 UTC

The initial read-only audit covered the independent `coarse500` sensitivity
case from `tmp/full-rebuild-002`, observed on 2026-10-09 at 19:44:59 UTC. It uses run 11
(A=0, C=0.003, E=1, default grain fractions), the full 72 km by 48 km domain,
and a complete 20-day flood. Floodplain spacing is 500 m; channel width is
500 m and the initial channel-node spacing remains 250 m. This coarsened
validation case is not a manuscript panel or a substitute for the requested
250 m experiments. The declared migration scale is 400 m/flood, with initial
perturbation parameter 5 m and seed 2018; these are reconstruction assumptions.

The calculation completed with exit code 0 at 19:41:34 UTC, after 1101.11 s
wall time, 59,535 floodplain steps and 404,334 channel steps. The executable
SHA-256 is
`b3d984881a2f82757ff9bb6ca7c15f9e3c28e3d34106ae477fe7c06af6f8099c`.
It matches the production executable. The source hashes, compiler command
and version, and executable identity are retained in the `provenance` object
of member `data/suite_manifest.json` in the
[production input archive](../validation/first-flood-audit-002/production-inputs-20261009T213916.tar.xz).
The original separate record was read at
`tmp/full-rebuild-002/workspace/data/_inputs/provenance.json`; that file is
not a member of the capture archive.

The [resolution input archive](../validation/first-flood-audit-002/resolution-inputs.tar.xz)
retains the case process record as
`validation/runs/coarse500/process_status.json`, including its command,
runtime, return code, and artifact hashes. These case files were captured
from `tmp/full-rebuild-002/workspace/validation/runs/coarse500/`. This wall
time was measured under concurrent host load; it does not establish a
production-run completion estimate.

The numerical evidence is in
[audit.json](../validation/first-flood-audit-002/audit.json), generated by the
[read-only audit script](../validation/first-flood-audit-002/audit.py).
The audit hashes saved numerical/provenance inputs, verifies the frozen files,
decodes the raster and checkpoint, and independently reconstructs channel control areas
and raster membership. It launches no model calculation and changes no
production or sensitivity output. Its initial observation is also retained.
These are captured historical records: process IDs, observation times and local
input paths describe that observation, rather than a portable rerun invocation.

### Timing, states, and inventories

The diagnostic snapshot clock is exactly 1,036,800 s (day 12); the end-flood
snapshot and post-remap checkpoint clocks are exactly 1,728,000 s (day 20).
Day 12 is the specified post-peak diagnostic time; the assumed hydrograph
reaches its discharge maximum at day 10. Every saved raster component is
finite, and depth and event deposition are nonnegative. Maximum event
deposition is 0.362877 m at day 12 and 0.448356 m at flood end.

The independently reconstructed day-12 interface has 430 wetted faces out
of 430. Its mean floodplain depth and alpha are both 0.770580353032 m,
within 7.75e-11 m of the saved double-precision summary. End-flood water
storage reconstructed from the float32 raster and channel CSV differs from
the summary by 0.00213 m³, below the 2.016 m³ bound from output rounding.
The post-remap checkpoint's independently summed water storage differs
from the post-remap ledger by 4.18e-7 m³.

The full checkpoint contains finite water, momentum, and suspended-class
states. Water and each suspended class are nonnegative, as are all bank
reservoir classes. Water and mass correction ledgers are both exactly zero.
Before remapping, the minimum channel depth is 4.34091 m. Afterwards it is
6.70e-8 m, with maximum 4.51507 m and inlet depth 4.34257 m. No channel node
is exactly dry, but newly excavated reaches can be almost dry: conservative
transfer preserves inventory, not uniform stage. This one-flood experiment
does not advance that post-remap state through another hydrograph.

The summary is written before migration; the remap ledger and checkpoint
follow it. The members `validation/runs/coarse500/summary.csv` and
`validation/runs/coarse500/remap_budget.csv` in the
[resolution input archive](../validation/first-flood-audit-002/resolution-inputs.tar.xz)
give the following residuals:

| Inventory | Before remap | Remap increment | After remap |
|---|---:|---:|---:|
| Water (m³) | -9.32887e-5 | +2.98023e-7 | -9.29907e-5 |
| Suspension plus deposition (kg) | -0.337443113 | -3.49246e-8 | -0.337443148 |
| Full solid inventory (kg) | -0.260296583 | +0.001117883 | -0.259178700 |

Individual remap suspended-class errors are +4.66e-10 kg sand, -4.47e-8 kg
silt, and +9.31e-9 kg clay. The pre/post ledger identities agree within
summary serialization precision. Prescribed upstream inputs are 1.512e10 m³
water and 5.473459e10 kg sediment; the latter was independently integrated
from the recorded concentration law and hydrograph. Absolute pre-remap
residuals normalized by those inputs are 6.17e-15 for water, 6.17e-12 for
suspension plus deposition, and 4.76e-12 for the full solid inventory.
These results establish ledger closure at this scope, not physical accuracy
of the boundary, deposition, migration, or recycling assumptions.

### Small line motion and whole-cell erosion

The first migration produces no cutoff. The saved pre-remap line has 289
nodes; the post-remap checkpoint has 290 after resampling. Both lines are
strictly monotone in x. Comparing their piecewise-linear y(x) on the union
of all saved x coordinates gives the following valley-length-weighted shape
changes: mean absolute lateral difference 3.22071 m, RMS 4.53536 m, and
maximum 32.5831 m. These are differences at fixed valley x, not reconstructed
material-node trajectories. The lateral centerline span changes from
17.1882 m to 28.6589 m.

Despite that small motion, 50 old raster cells become floodplain and 49
floodplain cells become channel. The newly occupied cells cover 12.25 km².
For scale, the exact area between the two piecewise-linear centerlines is
0.231891 km²; this centerline diagnostic is not an exact swept-bank polygon.
At dx equal to channel width, small changes in the centerline can change
which entire cells satisfy the channel-membership criterion. The comparison
therefore exposes the discretization of the channel footprint and bank
erosion, even though every transfer remains conservative.

The post-remap bank reservoir contains 1.5679963e11 kg, or 2.86473 times the
prescribed upstream sediment input during the first flood. Its pre-remap
value was zero. This material is available for recycling in a subsequent
flood; it does not explain the first flood's deposition, which was saved
before excavation. A grid comparison based only on first-flood end fields
cannot assess the effect of this reservoir on the next hydrograph, nor
establish convergence of long-term recycling, planform, or ridge development.
No corresponding 250 m behavior is inferred from this coarsened case. This
is a measured resolution-dependent limitation, not a conservation defect.

### Version and completion limits at the earlier observation

The corrected end-flood raster and channel CSV are byte-identical to the
legacy `validation/runs/coarse500` pre-remap files at their saved precision.
Their checkpoints differ, and the legacy executable is separately identified
by SHA-256
`c723c3cf8656e7b8935a35d718fe469f4a90c5d0de65de62d2b24d546010632b`.
The legacy files are not relabeled as results of the corrected remapper.

At the recorded observation, 31 corrected production processes and two
corrected sensitivity processes were running with nice value 10. The
corrected 250 m reference and newly launched 125 m sensitivity had no
completed-flood summary. The legacy reference, 125 m, and CFL=0.2 processes
were still running with no completed-flood summaries. These observations
provide no grid/time convergence result or completed manuscript panel.
