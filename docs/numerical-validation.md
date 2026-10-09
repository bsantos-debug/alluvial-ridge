# Numerical sensitivity validation

These calculations test numerical sensitivity over the first complete flood.
They are separate from the 580-flood manuscript experiments. A completed
first flood cannot establish the accuracy of long-term meander, cutoff,
sediment-recycling, or ridge-growth statistics.

## Prescribed experiments

All runs use configuration 11 (`A=0`, `C=0.003`, `E=1`, default sediment
fractions), the 72 km by 48 km domain, and the full 20-day hydrograph.
The dimensional parameters and reconstruction assumptions are read from
`config/physics.txt`; the run configuration is read from `config/runs.csv`.
The sinusoidal-squared hydrograph varies from 2,500 to 15,000 m³/s.
The first-flood reference has a 250 m floodplain grid and CFL coefficient
0.4. The initial channel uses 250 m nodes in every case.

| Case | Floodplain grid (m) | CFL | Purpose |
|---|---:|---:|---|
| `baseline250` | 250 | 0.4 | Reference first flood |
| `coarse500` | 500 | 0.4 | Coarser floodplain comparison only |
| `fine125` | 125 | 0.4 | Refined floodplain comparison |
| `time250_cfl02` | 250 | 0.2 | Reduced hydraulic timestep |

Changing floodplain resolution also changes the discrete raster footprint
of the fixed-width channel. The comparison therefore tests the combined
floodplain discretization and channel-to-grid coupling. It does not refine
the channel's one-dimensional control volumes. Coarse-grid runs are used
for validation and never substituted for the documented-resolution manuscript
experiments.

The executable, physical configuration, and run table are frozen before
launch. The initial validation campaign uses executable SHA-256
`c723c3cf8656e7b8935a35d718fe469f4a90c5d0de65de62d2b24d546010632b`.
Source hashes observed at preparation are recorded in
`validation/runs/_inputs/provenance.json`. They describe the files observed
when the binary was frozen; a hash record by itself is not proof of a
compiler's inputs.

The reference reuses the already running first-flood calculation at
`tmp/full_flood_v4`. Its actual live executable was independently hashed
through `/proc/3756153/exe`, after a later build had replaced its original
pathname. The hash matched the frozen validation binary. The PID, process
start ticks, argument vector, and verification timestamp are preserved in
`validation/runs/_inputs/baseline-process.json`. The reference is copied
into `validation/runs/baseline250` only after its status, summary row, and
saved elapsed simulation time prove that the entire flood finished.

## Commands and records

The complete fresh validation procedure is:

```sh
make all check
python3 scripts/validate_runs.py --output validation/fresh-runs --jobs 2
```

The first campaign avoids duplicating the reference calculation:

```sh
python3 scripts/validate_runs.py --prepared --baseline-from tmp/full_flood_v4 --jobs 2
```

`scripts/validate_runs.py` is a Python standard-library runner. It launches
at most two model processes and supplies `--floods 1`; it does not shorten
the flood or impose an observation-time stop. Each model process writes its
own log, parameters, summary, field snapshot, and checkpoint. The runner
records the exact command, PID, runtime, return code, and artifact hashes.
Existing case directories are never overwritten or automatically restarted.

To regenerate comparisons from completed outputs without rerunning a model:

```sh
python3 scripts/validate_runs.py --analyze-only --baseline-from tmp/full_flood_v4
```

The current machine-readable campaign records are
`validation/runs/validation_manifest.json`, each case's
`process_status.json`, and `validation/runs/comparison.json`.
An incomplete or failed calculation contributes no final-flood comparison.

## Quantities compared

The scalar comparisons include alpha at 0.6 flood duration, inundated
interface fraction, mean floodplain water depth, final beta, ridge height,
channel depth, and total water storage. Relative changes are reported only
when the reference is finite and nonzero. Undefined diagnostics remain
undefined.

Saved field comparisons average each fine-grid block onto its corresponding
coarse cell. A block is compared only if both the coarse cell and every fine
child are classified as physical floodplain. This avoids comparing the
one-dimensional channel's interpolated ghosts as though they represented
additional floodplain storage. Mean and maximum absolute differences are
reported for bed elevation, water depth, and per-flood deposition, together
with the common physical area. This field comparison uses the model's
float32 snapshots; small errors near that output precision are unresolved.
An isolated analytical fixture checked block averaging and mask exclusion:
a prescribed 0.25 m coarse-grid bed offset was recovered exactly, while
the otherwise matching affine/bilinear fields differed by at most
`1.2e-7 m` after float32 storage. Those unit-test values are not model data
and are excluded from all campaign results and manuscript panels.

The water budget includes external boundary transport and any recorded
roundoff correction. Its residual is normalized by prescribed upstream
water input, `20 days × (2,500+15,000)/2 = 1.512e10 m³`.
Suspended-plus-deposited sediment and full solid-sediment residuals are
normalized by the prescribed first-flood sediment input. The latter scale
is independently integrated from `concentration_scale × C × Q^(5/2)` using
20,000-interval Simpson quadrature. The first flood starts with no recycled
bank inventory. The residuals themselves come from the model's double-
precision ledger, not from the float32 plot snapshots.

## Current outcome

The campaign is running. No convergence result is claimed before the full
first-flood outputs have passed the completion checks. The dimensional
deposition threshold remains an unresolved physical parameter; optional
cases `tau005` and `tau020` are available in the runner but are deferred
until the core grid/time comparisons establish computational cost. Optional
`concentration_half` and `concentration_double` cases vary the explicit
concentration-unit assumption without changing the hydrograph.
