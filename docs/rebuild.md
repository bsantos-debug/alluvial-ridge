# Clean rebuild and provenance

Keep the checkout and generated files inside this project on a `/data/data0`
through `/data/data7` volume. The scripts reject output paths outside their
project root and redirect compiler temporaries and application caches into the
project. This checkout is at
`/data/data0/dominik-scratch/Shared/brnisant/alluvial-ridge`. Dependencies are a
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
