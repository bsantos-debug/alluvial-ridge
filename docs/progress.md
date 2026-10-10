# Current authoritative state

2026-10-10: The working project, caches, temporary files, and live outputs are
under `/data/data0/brooke/alluvial-ridge`. At 00:25:50 UTC, an atomic directory
exchange moved the original directory there and left the former path under
`dominik-scratch` as a symlink. The account's newly available `fastwriters`
membership allowed creation of the destination parent, owned by
`brnisant:others` with mode 0755. About 1.9 TB remained free on the volume.
All 43 frozen source hashes, all 37 known process identities, 175 writable
file handles, and the held suite-lock inode survived the move unchanged.
All 34 model CPU counters advanced afterward. The
[relocation record](../validation/relocation-20261010/README.md) preserves the
checks and the requirement to retain the old alias through terminal audit and
packaging. No project files are written under home directories. Earlier
cleanup removed the former home project and task-created TeX cache. The
original request is copied into `docs/user-request.txt`.

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

At the later read-only check on 2026-10-09 at 22:12:59 UTC, all 31 production
PIDs still matched their recorded start identities. Each had completed one
flood and was in flood 2, from day 9.9046 to 17.5174. The detailed 22:05 audit
also verified their exact commands, executable hashes, wrapper and driver
identities, and unchanged frozen inputs. At 22:13:18 UTC, the corrected 125 m
and half-CFL sensitivity cases were still in their first flood, at days 8.4025
and 10.2734; both commands and actual executable hashes matched their records.
The frozen model and binary remained unchanged. Destination creation still
requires write access; no files moved and no simulation process was signaled.

At 22:21:59 UTC, run 20 had completed flood 2 and entered flood 3, day 0.3421.
Its actual PID/start identity, command and executable hash still matched.
Stable summary/remap reads contained floods 1 and 2; the matching v2 checkpoint
recorded 3,456,000 s, 241,759 steps and 290 channel nodes. Its parameter
signature and finite/nonnegative water and sediment payload passed inspection.
The second cumulative post-remap residuals were −8.85725e−5 m³ water,
−14.433803 kg suspension plus deposition, and −0.611532 kg total solids.
Relative to two-flood prescribed inputs, these are 2.93e−15, 3.96e−11 and
1.68e−12 in magnitude. Bank mass, recycling, cutoffs and correction terms
remained zero; signed bed forcing is a separate ledger. This read-only
observation establishes one second-flood state, not a manuscript result.

At 22:35:15 UTC, all 31 production processes still matched their recorded
PID/start identities and exact commands. Runs 19, 20, 21, and 23 had completed
two floods; the other 27 had completed one. Run 23's summary, remap history,
and checkpoint header agreed, and its progress had entered flood 3.
The wrapper and two drivers retained their identities. The live fine125
and time250_cfl02 sensitivity jobs were on first-flood days 8.6557 and
11.1833, with matching commands and executable hashes. No terminal failure
or process identity mismatch was observed. No process was signaled or
restarted. The destination remained unavailable: an actual `mkdir` attempt
for `/data/data0/brooke` returned permission denied.

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
not grid convergence or a manuscript-panel reproduction. The finer-grid
results and later recycling require further assessment.

The corrected half-CFL case completed at 2026-10-10 00:43:01 UTC with exit 0.
Its terminal record agrees with the sensitivity driver manifest, and all 11
artifact hashes passed verification. The full checkpoint and peak/end fields
passed the finite-value and physical-inventory checks. Only the CFL parameter
differs from the completed baseline (0.4 to 0.2). Alpha changes by −0.81785%,
ridge height by +0.28975%, and end-flood water storage by −5.95097%. The
[completed time-step comparison](first-flood-validation.md#completed-first-flood-time-step-comparison)
retains the original inputs and a portable replay command. It establishes
first-flood sensitivity, without a temporal convergence order. The driver
started `tau005` automatically; PID 4128664 and start tick 53463257 were
verified live with the corrected executable at 00:44:47 UTC. Fine125 and
all 31 production calculations remain active.

The corrected `tau005` case completed at 2026-10-10 02:22:51.647420 UTC
with exit 0. Its process record agrees with the driver manifest, all 11
artifact hashes match, and the full checkpoint and exact day-12/day-20
snapshots passed finite-value and physical-inventory checks. Only
`tau_critical` changes from the completed baseline, from 0.1 to 0.05 Pa.
Integrated mineral deposition decreases by 19.4318%, while ridge height
increases by 7.32334% and beta by 7.31106%; these quantities summarize the
spatial deposit pattern differently. The
[completed threshold comparison](first-flood-validation.md#completed-first-flood-deposition-threshold-comparison)
retains the original records, field differences, normalized budgets, and
portable replay command. First-remap capture, abandonment, bank reservoir,
recycling, cutoffs, and correction terms remain zero. This is a completed
first-flood assumption comparison, without a claim about later evolution.
The driver automatically started `tau020` at 02:22:51.717996 UTC. PID 16284
and start tick 54062286 were verified live at 02:24:05 UTC with matching
recorded arguments and the corrected executable; `fine125` remained live.
The corrected `tau020` case completed at 2026-10-10 04:06:33.990250 UTC
with exit 0. Its full checkpoint and exact day-12/day-20 fields passed
finite-value, physical-inventory, and conservation checks. Only
`tau_critical` differs from the baseline, from 0.1 to 0.2 Pa. Integrated
mineral deposition increases by 46.1026%, while ridge height decreases by
6.57286% and beta by 6.56210%. Both threshold perturbations therefore change
the integrated mass and ridge-relief metrics in opposite directions; this
does not identify a mechanism for their different spatial weighting.
First-remap capture, abandonment, bank reservoir, recycling, cutoffs, and
correction terms remain zero. The threshold comparison retains all three
completed cases and treats each perturbation relative to the 0.1 Pa baseline.

The driver started `concentration_half` at 04:06:34.128871 UTC. PID 97109
and start tick 54684527 were verified live at 04:07:29 UTC, with matching
recorded arguments and the corrected executable. Its sole numerical change
is the concentration scale, from 0.001 to 0.0005; `fine125` remained live.
The half-concentration case completed at 2026-10-10 06:31:55.020253 UTC
with exit 0. Its retained comparison uses the unchanged baseline and the
actual half-concentration sediment input, `2.736729519459404e10 kg`.
Deposited mineral mass decreases by 49.8869%, ridge height by 50.3195%, and
beta by 50.2482%; day-12 alpha changes by -0.0144729% and end-flood water
storage by -0.198028%. These are full first-flood assumption sensitivities,
without a claim about later evolution or an appropriate physical concentration.
The original process records, complete artifacts, budget normalization, and
same-grid field differences are retained in the portable
[concentration comparison](first-flood-validation.md#completed-first-flood-concentration-comparison).
The driver automatically started `concentration_double` at 06:31:55.245746 UTC,
with PID 190256 and start tick 55556639. Six of the eight full first-flood
sensitivity cases have now completed; `fine125` and `concentration_double`
remain active, with no sensitivity case left queued.
The requested scope remains all 31 production cases at 580 floods each and
all eight sensitivity cases. Original runner outcomes are preserved; complete
rebuild and manuscript-panel assessments remain pending.

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
original states. Relocation occurred on 2026-10-10 at 00:25:50 UTC; the terminal
audit remains pending while calculations run. The procedure and its limits
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

The selected original evidence is also preserved for publication in
[`validation/rejected-rebuild-001/`](../validation/rejected-rebuild-001/README.md):
229 original files, including the 39 frozen sources, exact executable,
manifests, logs and case records. Their recorded hashes passed verification.
The separate capture preserves original interrupted/stale states and records
the later absence of all 38 recorded processes. The saved-data finalizer
includes this archive, and the report explains the separate cutoff test that
prompted interruption. No rejected data enter the canonical numerical inputs.

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
from plot existence. Root `report/report.pdf` is a 26-page work-in-progress
report. Its first-flood section verifies 313 retained input files from the
production observation and completed 250 m and 500 m sensitivity cases,
including checkpoints, before rendering their measurements. Those files are
preserved in two compressed archives under `validation/first-flood-audit-002`;
the section does not read changing live outputs. Validation figure V1 on page 8
maps the archived 250 m and 500 m end-flood water depth and deposit fields,
with common-cell differences. Its independent plotter verifies all 24 source
members and recomputes the recorded difference measures. Repeated plotting
produced identical PDF, PNG and manifest bytes. Report compilation verifies
the figure identities and leaves plotting to a separate finalization stage;
render-only preserves figure bytes. The compiled PDF was visually checked,
has no TeX warnings, and retains manuscript figure numbers 1--3.
Figure verification accepted the retained manifest and rejected 26 stale or
missing variants; a missing figure preserved both verified numerical tables.
The existing finalizer relocation regression also passed all 34 refusal cases.
The new diagnostic-definition analysis on page 9 quantifies a separate source
of interpretation sensitivity: changing the nominal central reach from 80%
to 60% or 100% changes first-flood beta by −21.73% or +73.52% at 250 m and
−18.02% or +34.07% at 500 m. Distal-band and channel-depth averaging contrasts
are smaller than 0.24%. Wetness thresholds of 0.1--10 mm leave first-flood
alpha unchanged while changing the inundated area. Default reconstructions
agree with the archived summaries within float32, float64-arithmetic and CSV
rounding bounds. The standalone saved-data analysis regenerates byte for
byte; its methods and complete scenario matrix are retained in
`figures/first_flood_diagnostic_sensitivity.json`. These are first-flood
definition contrasts, not uncertainty intervals or validation of late-window
manuscript statistics. Report verification and a separate finalization stage
preserve the distinction from both model reruns and scientific panel assessment.
The report accepted the verified analysis and rejected 24 missing, stale or
inconsistent variants. Missing/stale analysis retained the two original tables
and verified V1 figure; all checks preserved the historical-observation scope.
All 13 main-manuscript panels
remain unreproduced. Clean outputs will be generated in the staged workspace.
The root `figures/comparison.json` and `.csv` are retained inputs to this
provisional report: they contain zero computed comparisons, and the report
flags their outdated processor identity and missing numerical panel sources.
The supplement has prose and a table, with no supplementary figures.

## Later migration Fourier verification

`tests/migration_linear.cpp` now checks growing and decaying Fourier modes
against independently derived continuum and discrete responses. Its 72 cases
pass under the default compiler flags. Native one-flood complex-rate errors
decrease about fourfold as node spacing is halved, combining spatial and
temporal refinement. Controlled 0.1-flood evolution matches the discrete
Euler response within 6.08e-9 per flood; amplitude, fitting-window,
finite-inlet, and stable-count interpolation controls are separately checked.
Literal-spacing interpolation adds one node and measurably attenuates the
modes, so its zero-duration results have separate bounds and no growth rate.
Equations, numerical values, and limits are in [migration.md](migration.md).

The [retained record](../validation/migration-linear/README.md) contains
commands, logs, all 72 CSV rows, and source/output hashes. This later test is
included in maintained `make check` and final report packaging; it was not
part of the frozen 002 launch checks. No numerical source or production
configuration changed, and the migration header still matches frozen 002.
The 26-page provisional report includes the bounded result on pages 6--7
and compiles without TeX warnings. All 13 manuscript panels remain
unreproduced; this check supplies no coupled grid-convergence or late-planform
claim and does not explain the entire production sinuosity change.

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
