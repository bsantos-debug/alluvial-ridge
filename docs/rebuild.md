# Clean rebuild and provenance

Keep the checkout and generated files inside this project on a `/data/data0`
through `/data/data7` volume. The scripts reject output paths outside their
project root and redirect compiler temporaries and application caches into the
project. This checkout is at
`/data/data0/brooke/alluvial-ridge`. Dependencies are a
GNU C++17 compiler, GNU make, Python 3 with NumPy and Matplotlib, and pdfLaTeX.
The numerical rebuild does not require the authors' code, data, or source PDFs.

From the checkout root, start a fresh complete calculation with:

```bash
RIDGE_JOBS=8 RIDGE_VALIDATION_JOBS=2 bash scripts/rebuild.sh
```

The optional argument names a **new** project-local artifact directory:

```bash
bash scripts/rebuild.sh tmp/rebuild-independent
```

The default is `tmp/rebuild-<UTC time>/`. The wrapper copies maintained source,
configuration, tests, documentation, and report source into its `workspace/`.
It preserves existing builds, outputs, and independent live processes. It does
not copy old validation results, scientific output, generated figures, or PDFs.
It retains `report/generated/implementation.tex` because that file contains
maintained methods text; validation and execution claims are generated afresh.

The wrapper runs these stages in order:

1. Freeze source and numerical inputs, then compile a private executable.
2. Run implementation and restart checks using that exact executable; compile
   the unit tests from the same staged source.
3. Start the sensitivity calculations and all 31 configurations for 580 floods
   concurrently, with separate logs and stage outcomes. The eight full first-flood
   sensitivity cases are `baseline250`, `coarse500`, `fine125`, `time250_cfl02`,
   `tau005`, `tau020`, `concentration_half`, and `concentration_double`.
   `RIDGE_JOBS` controls suite concurrency; `RIDGE_VALIDATION_JOBS` is 1 or 2,
   in addition to the suite workers. Failed implementation checks prevent both
   stages. Each stage can finish or fail independently; the wrapper waits for
   both before generating figures.
4. Generate all figure panels and comparisons in strict mode. Missing or failed
   calculations remain visibly incomplete and cause nonzero exit codes.
5. Attempt a PDF documenting the current results and stage outcomes.

The final PDF is `workspace/report/report.pdf`. The outer
`rebuild_manifest.json` records the copied source hashes, stage commands, logs,
exit codes, timings, and PDF hash. A compiled PDF does not make failed numerical
or figure stages successful: the wrapper exits nonzero unless every stage
succeeds. Signal interruption terminates the wrapper's active stage process
groups and records their outcomes before marking the rebuild interrupted.
The wrapper requires a fresh directory
on each invocation; it never deletes an earlier attempt.

# Running and resuming a numerical suite

The numerical runner can be used separately, for example:

```bash
source scripts/environment.sh
python3 scripts/run_suite.py --jobs 8 --data-root regenerated/data --floods 580
```

Fresh output directories must be empty. `--runs 11` selects one case;
`--runs all` is the default. `--config` and `--runs-table` may select other
project-local input files. `--prepare-only` freezes and compiles inputs without
starting a calculation. The private executable is compiled from copied source,
not adopted from `build/ridge`. `CXX`, `CPPFLAGS`, `CXXFLAGS`, `LDFLAGS`, and
`LDLIBS` select the compiler and flags; defaults match the project build.

Each suite contains read-only files in `_inputs/`: `src/`, `physics.txt`,
`runs.csv`, the preparing runner, the executable `ridge`, and `provenance.json`.
The provenance records SHA256 hashes of the exact compiled project source and
binary, compiler command/version, and input hashes. The compiler log is retained.
Read-only permissions guard accidental changes; digest verification rejects
changed files on resume. These records identify project inputs, not a complete
archive of operating-system headers or runtime libraries.

Resume uses these frozen inputs and executable even if working-tree files
change:

```bash
python3 scripts/run_suite.py --data-root regenerated/data --resume --jobs 8
```

A larger `--floods` may extend the history. It cannot shorten the target or add
cases outside the original selection. An explicitly supplied configuration or
run table must match the frozen copy. Older manifests without compiled-source
provenance are rejected. To change model code or physical inputs, use a fresh
output directory.

A directory lock prevents concurrent suite writers. The runner also checks for
live model processes writing each requested case, including a child surviving
its runner. It verifies hashes from terminal attempts before using their files.
An interrupted writer can have advanced its checkpoint beyond the last recorded
attempt; that case resumes through the model's checkpoint parameter checks.
The checkpoint is saved after each complete flood and its migration/aggradation
step. An interrupted flood is recomputed from that state. Uncheckpointed trailing
summary rows are regenerated by the model. A terminal failure before the first
complete flood has no restart checkpoint: its files are preserved under
`_failed_attempts/` before a fresh first-flood attempt. Completed diagnostic rows
without a checkpoint cause refusal, not silent deletion.

Per-case `process_status.json` retains attempts, commands, process identity,
exit codes, errors, timings, and output hashes. The suite manifest collects
these records. Exit code zero alone is insufficient: completion requires the
reported flood count, consecutive summary rows, finite conservation diagnostics,
and final raster/channel snapshots with matching time, grid, and dimensions.
Completion records numerical execution; conservation tolerances, convergence,
and agreement with the paper require the separate scientific assessment.

For an interrupted clean rebuild, inspect its outer manifest and live processes
first. The numerical suite can be resumed by entering its `workspace/` and using
the command above with `--data-root data`. Downstream plotting, comparison, and
report commands may be rerun there after completion. This manual recovery does
not rewrite the outer rebuild manifest or establish that the original complete
wrapper execution passed; preserve that distinction in the execution record.

# Relocating a project with running calculations

The project moved to `/data/data0/brooke/alluvial-ridge` on 2026-10-10 at
00:25:50 UTC using an atomic same-filesystem directory exchange. The old path
is now a symlink to that directory. All 37 known process identities and 175
writable file handles survived unchanged; all 43 frozen source hashes matched
before and after the move. The [relocation record](../validation/relocation-20261010/README.md)
preserves the observations. No numerical process was signaled or restarted.

A same-filesystem move must preserve the directory inodes and provide the old
project path as an alias throughout the lifetime of existing writers. Their recorded commands,
working directories and cache paths still reference that location. Do not
launch a second suite to perform the move or to replace a merely unobserved
process. The maintained runner resolves output aliases and relative process
arguments when checking for live cases, and resolves its project root again
when enforcing containment. `tests/runner_relocation.py` exercises these checks
with harmless child processes and temporary directories inside the project.

Frozen rebuild 002 retains its original loaded runner. After a live move, its
last containment check can mark a suite case `incomplete` even though that
case's saved process record and numerical attempt are `complete`. Preserve
these original records. Once the entire rebuild is terminal, the later
finalizer can audit this specific discrepancy separately:

```bash
python3 scripts/finalize_report.py --rebuild tmp/full-rebuild-002 --check-only --reconcile-relocation
python3 scripts/finalize_report.py --rebuild tmp/full-rebuild-002 --output deliverables/final --reconcile-relocation
```

This option accepts only the exact cached-root containment error. The suite
and process records must otherwise agree, the latest attempt must have exited
zero at the requested flood count, and its recorded output must match the
original wrapper workspace and still resolve through the old alias to the
current case. All terminal artifacts must retain their recorded hashes.
An independent check then reads the complete summary and remap histories,
finite conservation diagnostics, final and day-12 snapshot headers, sizes,
clocks and channel counts. It requires a nonempty checkpoint but does not
decode that state or scan all raster values. Other record disagreements and
failed checks remain refusals; live-writer and suite-lock checks still apply.

The separate `postprocess_manifest.json` records both original states,
historical and current paths, the original error, and the later check result.
The report retains the original rebuild outcome and states the audit's limited
scope. Keep the old alias until this first audit and packaging finish; the
option refuses an absent or unrelated alias. A completed package's render-only
operation uses its retained evidence and does not require the old alias. This
administrative reconciliation does not establish scientific agreement.

# Later reports from terminal saved data

`scripts/finalize_report.py` generates a later report from the numerical files
already produced by rebuild 002. It never invokes a model executable. It
requires a new destination and refuses running drivers/cases, a held suite
writer lock, surviving writers, missing terminal artifact records or changed
hashes. The current active rebuild is therefore not eligible yet.

First verify eligibility without copying or generating files:

```bash
python3 scripts/finalize_report.py --rebuild tmp/full-rebuild-002 --check-only
```

After the complete wrapper has ended and all case records are terminal:

```bash
python3 scripts/finalize_report.py --rebuild tmp/full-rebuild-002 --output deliverables/final
```

The procedure checks original staged sources and logs, suite/compiler/input
identities, the exact checked executable, all 31 latest terminal production
attempts, and all eight terminal sensitivity records. Sensitivities must use
the production source and binary. Recorded artifact hashes must match; a
successful process state alone is insufficient. It allows terminal failed
cases with verified evidence, preserving that failure in the later report.
It refuses interrupted cases lacking terminal records rather than inventing
proof. Production `checkpoint.tmp` and `progress.tmp` are excluded exactly as
in the runner and are not copied; `.suite.lock` is also omitted. Other
unrecorded case files cause refusal. Earlier attempt records are preserved as
history; overwritten artifacts from those attempts are not claimed reverified.

The current checkout's numerical source and configuration must still match
002. Reporting code and prose may differ. Before staging, follow the
[finalization checklist](finalization-checklist.md) to retain the complete
versioned first-flood audit, including both input archives. Its evidence
links target those retained files and need no staging-time path changes.
Check the links and archive hashes in the copied workspace; preserve the
historical paths inside captured records.
The later `first-flood-figure` stage regenerates Validation figure V1 from
that historical archive and records its output hashes separately. Report
compilation verifies the saved figure without rerunning its plotter, so
`--render-only` preserves all figure bytes. This diagnostic is not one of the
13 manuscript panels and supplies no convergence claim.
The separate `diagnostic-sensitivity` stage measures how the same first-flood
states depend on ridge/distal/channel-depth averages and wetness thresholds.
Its JSON records source identities and float32 representation bounds. The
report verifies this saved analysis; render-only does not regenerate it.
The package contains:

- `original/`: the unchanged outer rebuild manifest, stage logs, frozen source,
  available original PDF, and original figures/generated report inputs.
- `workspace/`: copied numerical and sensitivity evidence, frozen executable,
  current postprocessors/report source, later figures and `report/report.pdf`.
- `postprocess_manifest.json` and `logs/`: original/copy hashes, actual source
  revision and working-tree status, package versions, each command/exit/log,
  case states and generated-output hashes.

The tracked `validation/rejected-rebuild-001/` archive is retained under the
copied workspace's same relative path. Its unchanged interrupted records stay
inside that labeled archive, separate from canonical production data.
The tracked `validation/relocation-20261010/` evidence is also retained at its
original relative path, preserving the documentation links and move audit.

Files are copied as real files, rehashed, and checked against unchanged source
evidence. A read-only descriptor holds the existing suite lock during the
copy. Original rebuild files are never rewritten. Postprocessing runs plots,
comparison, inundation, planform diagnostics, validation reporting and PDF
compilation in the copied workspace. Pending stages remain nonzero even if
the PDF compiles: exit 0 means all reporting stages returned zero, exit 2
means one or more stages were incomplete, and exit 1 means refusal or error.
None of these codes establishes scientific acceptance. The report states the
actual original rebuild outcome and identifies the later execution separately.

Review all panels and comparisons, then edit only the package's
`workspace/docs/panels.csv`, including the bounded assessment and matching
fingerprint described in `docs/finalization-checklist.md`. Re-render from the
packaged procedure, preserving figure PDF bytes:

```bash
python3 deliverables/final/workspace/scripts/finalize_report.py --render-only --output ..
```

Paths are resolved against the script's workspace, so this command also works
after moving the package to another project-local `/data/data[n]` directory.
The rendering mode verifies copied numerical evidence, original archives,
source files other than the editable ledger, and existing generated outputs.
It runs only `report/build.sh`; it does not regenerate plots, comparisons or
helpers. Each render preserves the preceding manifest/PDF, the submitted
ledger, procedure and resulting PDF under `renders/assessment-render-NNN/`.
The manifest's `source_sha256` remains the **initial staged source** identity,
including its original ledger. The latest assessment-render command's
`assessment_ledger_sha256` and archived `panels.csv` identify the current
review; they do not silently replace that initial source record.

If data, processors or figures change, create a new package and reassess the
affected panels. For publication retain the manifests, logs, sources, numerical
evidence, figures, generated LaTeX inputs and final PDF; omit `workspace/tmp/`
and `workspace/report/build/` caches. Historical absolute command paths remain
in untouched provenance records, but new processors consume package-relative
files and re-rendering needs no access to the original temporary workspace.

# Verification status

The full clean wrapper has not yet been executed to completion. Shell and Python
syntax have been checked. An interrupted staging check under
`tmp/rebuild-interruption-smoke/` recorded interruption, terminated its own
process group, and started no numerical case. Dummy subprocess checks under
`tmp/rebuild-concurrency-smoke/` verified concurrent starts, independent success
and failure records, and interruption of both stage groups and their children.
Temporary 4 km, 10 s calculations under
`tmp/suite-runner-smoke/` completed one flood and extended it to two using a
checkpoint. Resume checks rejected changed explicit/frozen inputs, checkpoint
corruption, shortened histories, unknown cases, a concurrent runner, a surviving
writer, and a home-directory output path. A forced early stop returned model
exit code 3 and suite failure; retry preserved its partial output. These are
runner checks, not manuscript simulations or evidence of scientific agreement.

Saved-data finalization checks are isolated under
`tmp/finalization-procedure-check/`. Active 002 was refused without copying;
its actual completed `coarse500` terminal artifact hashes were verified
read-only. Synthetic terminal driver/case records with no model values
exercised staging: plots/comparisons/helpers/validation remained incomplete,
the PDF compiled, and the package returned 2. Changed artifacts, a nonterminal
case, a surviving dummy writer, and an existing destination were refused.
Known production atomic-write remnants were omitted. Original manifest/PDF
bytes were preserved. Editing only the fixture ledger re-rendered the report
while preserving every figure and derived-data byte, recording the new ledger
hash and archiving the previous manifest/PDF. A relocated package without
application/TeX caches also re-rendered and remained incomplete. These checks
ran no model, changed no staged 002 source, and replaced no canonical output.
