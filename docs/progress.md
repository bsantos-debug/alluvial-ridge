# Current authoritative state

2026-10-09: All project files, caches, and temporary files belong under
`/data/data0/dominik-scratch/Shared/brnisant/alluvial-ridge`. The former home
project and task-created TeX cache are absent. Available space was about 1.9 TB.
The original request is copied into `docs/user-request.txt`.

## Active corrected clean rebuild

Started 2026-10-09 19:22:42 UTC from revision `e8656f4` using:

```sh
RIDGE_JOBS=31 RIDGE_VALIDATION_JOBS=2 nice -n 10 bash scripts/rebuild.sh tmp/full-rebuild-002
```

Artifacts: `tmp/full-rebuild-002/`; staged workspace:
`tmp/full-rebuild-002/workspace/`; root exec session **72007**.
Launch log: `tmp/full-rebuild-002.launch.log`. Frozen compilation and all
exact-binary component, coupling, remap and restart checks passed. Sensitivity
driver PID **3805339** and simulation driver PID **3805340** are running.
All **31** production case processes were verified live. Each requests the
full 580-flood calculation; eight full first-flood sensitivity cases use two
workers. Do not edit the staged sources or restart live cases. Completion and
scientific agreement remain pending.

At 19:47:19 UTC, all 31 production PIDs were live in `/proc`, at flood 1,
days 7.665--8.686, with 32,000--42,000 macrosteps. Frozen source hashes still
matched the outer manifest. The corrected 500 m sensitivity completed its
20-day flood at 19:41:34 UTC with exit 0; baseline250 and fine125 (PID 3831031)
were running. The coarse output has finite/nonnegative fields and checkpoint,
zero water/mass correction ledgers, and small pre/post-remap residuals.
It also exposes substantial whole-cell footprint sensitivity: mean lateral
line motion of 3.22 m captured 49 raster cells, producing a bank reservoir
2.8647 times the first-flood sediment input. This does not establish a
conservation defect or 250 m behavior. The next-hydrograph recycling effect
and grid/time convergence remain untested. See `docs/first-flood-validation.md`
for the measured scope, residuals, original files and limitations.

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

`docs/runtime-observation.md` records live process and timestep measurements.
All 31 production cases continued advancing through flood 1 during this audit;
there is no evidence supporting a complete-run ETA or a stalled calculation.

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

The older 250 m baseline (root session 40462, PID 3756153), 125 m case
(PID 3757990), and half-CFL case (PID 3770900) remain live as of 19:07 UTC.
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
from plot existence. Root `report/report.pdf` is a 20-page work-in-progress
report; clean outputs will be generated in the next staged workspace.
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
