# Current authoritative state

2026-10-09: The working project, caches, and temporary files remain under
`/data/data0/dominik-scratch/Shared/brnisant/alluvial-ridge` while relocation to
the requested `/data/data0/brooke` awaits directory creation and suitable
ownership by an administrator. The current checkout is maintained temporarily
for the resumed scientific task; its subsequent changes belong in the eventual
move. No project files are written under home directories. Earlier cleanup
removed the former home project and task-created TeX cache. Available space
was about 1.9 TB when this location was selected. The original request is
copied into `docs/user-request.txt`.

## Active corrected clean rebuild

Started 2026-10-09 19:22:42 UTC from revision `e8656f4` using:

```sh
RIDGE_JOBS=31 RIDGE_VALIDATION_JOBS=2 nice -n 10 bash scripts/rebuild.sh tmp/full-rebuild-002
```

Artifacts: `tmp/full-rebuild-002/`; staged workspace:
`tmp/full-rebuild-002/workspace/`; root exec session **72007**.
Launch log: `tmp/full-rebuild-002.launch.log`. Frozen compilation and all
exact-binary component, coupling, remap and restart checks passed. Sensitivity
driver PID **3805339** and simulation driver PID **3805340** were launched.
All **31** production case processes were verified live at the observation
described below. Each requests the full 580-flood calculation; eight full
first-flood sensitivity cases use two
workers. Do not edit the staged sources or restart live cases. Completion and
scientific agreement remain pending.

At 21:39:16 UTC, all 31 production PIDs were verified live with the corrected
executable. Every case had completed one full flood and was advancing through
flood 2, between days 5.86135 and 11.32774 in its saved progress. Frozen source
hashes, checkpoint signatures, finite fields, and nonnegative water and
suspended-class inventories passed the recorded checks. All first remaps have zero captured
or abandoned cells, cutoffs, bank reservoir, recycled mass, and numerical
water/mass corrections. The largest absolute post-remap residuals are
1.31249e-4 m³ water, 2.51689 kg suspension plus deposition, and 0.396595 kg
full solids. The [captured observation](../validation/first-flood-audit-002/production-observation-20261009T213916.json)
retains all 31 records and 289 input hashes; its process observations are
historical, not a guarantee that the same processes remain live later.

Both corrected first-flood sensitivity cases `coarse500` and `baseline250`
completed with exit 0, at 19:41:34 and 20:53:50 UTC respectively. Their saved
artifact hashes match their completed process records. Relative to 250 m,
the 500 m case has 12.8782% lower alpha, 98.6057% more deposited mass, and
62.7144% less end-flood water storage. Its first remap captures 49 cells and
abandons 50, producing a bank reservoir 2.8647 times the first-flood input;
the 250 m case has none of these cell conversions and zero reservoir. The
bank interface is 215 km at 500 m and 144 km at 250 m. Small conservative
budget residuals therefore coexist with substantial sensitivity to raster
geometry and resolution. The [two-resolution record](../validation/first-flood-audit-002/two-resolution.json)
and [validation account](first-flood-validation.md) retain the method,
denominators, field differences, and limits. This is first-flood sensitivity,
not grid convergence or a manuscript-panel reproduction. The finer-grid and
time-step results and later recycling require further assessment.

This version saves day-12 fields and post-remap budgets. Its automatic report
also includes numeric refinement/assumption differences and production budget
extrema with input hashes. `validation/remap-full-check.txt` is the root check
record; `tmp/full-rebuild-002/checks.log` verifies the exact frozen binary.

## Later spatial analysis and report preparation

The numerical source remains unchanged. Root postprocessing now additionally
contains `scripts/inundation_metrics.py` and `scripts/planform_metrics.py`.
They measure actual day-12 water extent, wet-interface patches, bulk deposition,
sparse previous-channel occupancy, planform geometry and correctly indexed
cutoff events. Float32 water/bed rounding is propagated into diagnostic bounds;
neither deposit area nor wet patches are labeled breach discharge or avulsion.
Actual short diagnostic data and analytical geometry/threshold limits were
checked; all requested manuscript snapshots remain pending. Methods are in
`docs/inundation-comparison.md` and `docs/planform-comparison.md`.

The root comparator now permits a valid early requested snapshot even if a
later flood is absent, while retaining complete-history requirements for the
Figure 3 statistics. It checks the full declared physics configuration.
Retained scientific assessments require an explicit fingerprint binding their
numerical inputs, processors, figure and comparison record. These later changes
are included in future rebuilds; immutable rebuild 002 still uses its original
postprocessors. Its data and execution manifest must remain unchanged when
preparing the later assessed report. `docs/finalization-checklist.md` gives
the 13-panel assessment, separate provenance and publication requirements.

The later report now renders verified spatial tables and ties their source
paths to the exact plotted run, in addition to checking hashes. Figure 2
comparisons measure profile area, spread, widths and signed flank departures
with explicit definitions; all derived section cells are checked against
the saved raster. Analytical/actual diagnostic checks retain noncanonical
status. An isolated PDF including the actual 002 kernel log compiled without
layout/reference warnings; root and staged 002 PDFs were not overwritten.

`scripts/finalize_report.py` stages and processes verified terminal saved
data, preserving the original rebuild separately. Its check-only mode
currently refuses 002 because the suite is still live. It neither starts
models nor treats compiled PDFs as scientific acceptance. A later render-only
mode permits authored ledger assessments while preserving figure bytes.

The maintained runner now resolves output aliases when detecting existing
writers and resolves its project root again for containment checks. Frozen 002
retains its original runner, whose final path check can disagree with complete
process records after a live project move. The later finalizer's explicit
`--reconcile-relocation` option checks only that specific discrepancy against
the recorded historical output path, unchanged artifact hashes and saved
completion metadata. It records the later check separately and preserves all
original states. Relocation and this terminal audit have not occurred; the
destination still awaits administrator creation. The procedure and its limits
are in [rebuild.md](rebuild.md#relocating-a-project-with-running-calculations).
`python3 -B tests/runner_relocation.py` passed with real harmless children.
`python3 -B tests/finalizer_relocation.py` passed the explicit relocation case
and rejected 34 invalid or unsafe cases using archived one-flood sensitivity
bytes and synthetic terminal metadata. It ran no model and establishes no
580-flood completion. The actual 002 check-only command, even with relocation
reconciliation enabled, still refuses its held suite writer lock. Frozen
runner, model and executable hashes remain unchanged.

`docs/runtime-observation.md` records earlier process and timestep measurements.
The later production observation above confirms all 31 cases in flood 2.
These observations do not establish a complete-run ETA.

## Interrupted clean rebuild and correction

Started 2026-10-09 19:06:36 UTC using:

```sh
RIDGE_JOBS=31 RIDGE_VALIDATION_JOBS=2 nice -n 10 bash scripts/rebuild.sh tmp/full-rebuild-001
```

Artifacts: `tmp/full-rebuild-001/`; numerical workspace:
`tmp/full-rebuild-001/workspace/`. Root exec session: 10864.
Launch output: `tmp/full-rebuild-001.launch.log`.
Prepare and all exact-binary component, coupling, and restart checks passed.
Simulation driver PID 3782519 and sensitivity driver PID 3782518 started at
19:07:02 UTC. All 31 numerical cases were verified live, each requesting 580
full 20-day floods on the documented 250 m grid. Eight first-flood refinement
and assumption-sensitivity cases run concurrently with two workers.

At 2026-10-09 19:14:19 UTC, the verified wrapper was sent SIGTERM because a
new cutoff test demonstrated that the remap could overdraw suspended inventory.
All its numerical child processes stopped, and the manifest records
`interrupted`. The reason is retained in `interruption_reason.json`. No
production flood had completed. Frozen source remains unchanged at revision
dc96644; all partial output and provenance are preserved. This is a rejected
numerical attempt, not a completed clean rebuild.

The correction normalizes each old channel section's inventory over its whole
raster support, transfers the abandoned fraction, and remaps the remainder
with positive overlap weights. Water and all classes share the same weights.
Newly captured floodplain inventories enter neighboring new sections locally.
There is no global component rescaling. Regression tests exercise the actual
250 m cutoff counterexample, smooth plumes at 125/250/500 m, repeated transfers,
constant concentrations, unsupported sections, and subsequent hydraulic flow.
Root source additionally saves day-12 rasters at the requested snapshot floods,
records post-remap budgets, and rejects old checkpoints with a v2 signature.
All component, coupled, remap, and actual-executable restart checks pass in
`validation/remap-full-check.txt`. The corrected fresh rebuild is described above.

Read manifests, per-case `process_status.json`, and `progress.json` before
acting. Never restart live work. Do not edit any staged source. No manuscript
panel is yet established from a completed production history. Goal remains active.

## Earlier independent validation

The 500 m first-flood case completed in 724.49 s. Absolute budget residuals
normalized by prescribed input are approximately 6.18e-15 for water,
6.17e-12 for suspended sediment plus deposition, and 4.76e-12 for the total
solid/bank/suspension ledger. This is validation, not a manuscript panel.

At the earlier 19:07 UTC observation, the older 250 m baseline (root session
40462, PID 3756153), 125 m case (PID 3757990), and half-CFL case
(PID 3770900) were live.
Their runner PID 3757950 writes `validation/runs/`. Its original agent
session 38913 cannot be polled from root; inspect logs and process records.
All use the frozen v4 binary with corrected characteristic boundaries,
preceding the norm optimization and output/checkpoint metadata additions.
Do not mistake these for production or the new clean rebuild.

The invalid earlier full_flood_v3 process was explicitly terminated and
recorded as rejected. Small-domain and wall-time-limited development outputs
under `tmp/` and `figures/test*/` are not manuscript results.

## Implementation and report

Independent C++17: conservative 1-D/2-D shallow-water coupling, Chezy friction,
turbulent stress, three suspended advection/diffusion/deposition classes,
Howard--Knutson/Ikeda migration and neck cutoffs, conservative remapping, bank
recycling, prescribed aggradation, diagnostics, checkpoints, and provenance.
Equations and assumptions are in `docs/implementation.md`,
`docs/sediment-methods.md`, and `docs/migration.md`. Written descriptions leave
substantial parameters and closures unspecified; exact original equivalence
is not asserted. No original author code, output, plotting script, source data,
or separate figure file was used. DR2 result columns were not numerical inputs.

`validation/optimized-build.txt` records passing component/coupled/restart
checks. Restart reproduces uninterrupted output byte-for-byte and rejects
changed parameters. `docs/performance-review.md` records exact dry-support
optimization and paired HLL/norm tests: combined CPU reduction 16.26%, maximum
warm-continuation state difference 4.09e-14 from norm roundoff. No compiler fast
math, grid coarsening, flood shortening, or skipped floods is used in production.

Plotter and comparison scripts handle all 13 requested panels, record hashes,
and leave missing/nonfinite samples absent. The report renderer merges actual
coverage with the maintained scientific assessment and does not infer agreement
from plot existence. Root `report/report.pdf` is a 24-page work-in-progress
report. Its first-flood section verifies 313 retained input files from the
production observation and completed 250 m and 500 m sensitivity cases,
including checkpoints, before rendering their measurements. Those files are
preserved in two compressed archives under `validation/first-flood-audit-002`;
the section does not read changing live outputs. All 13 main-manuscript panels
remain unreproduced. Clean outputs will be generated in the staged workspace.
The root `figures/comparison.json` and `.csv` are retained inputs to this
provisional report: they contain zero computed comparisons, and the report
flags their outdated processor identity and missing numerical panel sources.
The supplement has prose and a table, with no supplementary figures.

## Publication and remaining work

SSH authentication identified the GitHub account as bsantos-debug. The gh CLI
has no API login, so repository creation is not yet available. The user was
already asked to authenticate gh or provide an empty repository SSH URL;
no answer has arrived. Do not repeat the request while local work remains.
No repository or remote PDF link has been published.

Next: monitor actual processes; inspect completed first-flood/refinement
results; investigate any numerical failures without substituting shorter runs;
complete all attempted 580-flood configurations; generate and inspect all
panels; quantify discrepancies; finalize panel assessments and report; record
the clean rebuild outcome; publish and verify repository/PDF.

At publication, retain scientific run/compile logs. Consider including final
checkpoints and the exact frozen binary so published provenance and resume
records are usable; checkpoints are currently ignored to prevent committing
live intermediate state. All final files must stay on the selected /data volume.
