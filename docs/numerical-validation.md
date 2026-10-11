# Numerical sensitivity validation

## Remapping defect and corrected transfer

The original remap could overdraw a sediment class when a cutoff abandoned
interpolated raster ghosts whose weighted area exceeded the donor's exact
one-dimensional control area. At 250 m spacing, one neck-cutoff test requested
145,371.759 kg from a 107,303.006 kg pulse. A smooth Gaussian plume also failed
after 120 s of coupled transport. These are numerical counterexamples, not
published data. The source and results are retained under `validation/stress/`.
Clean rebuild `tmp/full-rebuild-001` was interrupted at 2026-10-09 19:14:19 UTC
because of this demonstrated defect; no production flood had completed.

The replacement projects donor inventories with nonnegative weights normalized
over their full old raster support. It uses identical weights for water and
every sediment class and records a separate transfer budget after every flood.
The derivation and momentum/depth limitations are in `docs/implementation.md`.
Dedicated cutoff, repeated-motion, and concentration tests pass in
`validation/remap-full-check.txt`, alongside all component/coupled/restart
checks. In 24 remaps and recycling events, the maximum water residual is
1.16e-8 m3, class residual 3.91e-5 kg, and total solid residual 4.39e-5 kg
while 1.272006e10 kg passes through the bank reservoir. Smooth cutoffs followed
by 120 s of coupled transport pass at all three grid spacings. The tests also
retain an expected physical limit: repeated excavation with aggradation
reaches nonpositive mean bank height at event 9, after eight conservative
remaps. No artificial depth floor is introduced to suppress that failure.

The actual executable's two-flood restart test now compares day-12 rasters,
day-12 channel sections, end-flood outputs, and the final checkpoint byte for
byte. It also verifies exact day-12 metadata, repairs uncheckpointed rows in
both diagnostic CSV files, and checks per-remap water/class/solid budgets.
The updated test passed in `validation/remap-restart.txt`. The checkpoint
signature is version 2, preventing a new executable from silently accepting
state produced by the rejected transfer method.
The initial log `validation/remap-build.txt` retains a false restart-test
failure: searching for the substring `999` also matched a legitimate numerical
value. The test now checks the injected sentinel's actual CSV field and row
structure. No model change was required for that test correction.

## Full-flood sensitivity scope

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

All eight corrected first-flood cases completed with exit code 0:
`baseline250`, `coarse500`, `fine125`, `time250_cfl02`, `tau005`, `tau020`,
`concentration_half`, and `concentration_double`. Their
[retained comparisons](first-flood-validation.md) distinguish grid and
time-step sensitivity from changes to the assumed deposition threshold and
concentration multiplier. No convergence result is claimed from these
comparisons. The half-concentration case completed at
2026-10-10 06:31:55.020253 UTC with exit 0. The driver automatically started
`concentration_double` at 06:31:55.245746 UTC; that case completed at
08:28:03.970245 UTC with exit 0. The final case, `fine125`, completed at
10:50:14.972269 UTC; the sensitivity driver completed with exit 0 at
10:50:24.195323 UTC. All 31 production calculations still request 580 floods
each and remain in progress. The concentration cases vary the
explicit concentration assumption without changing the hydrograph. Their
sediment budget denominators use each case's actual concentration multiplier.
The dimensional deposition threshold remains an unresolved physical parameter.

The [completed 125 m comparison](first-flood-validation.md#completed-250-m-and-125-m-comparison)
changes only floodplain `dx` relative to 250 m; initial channel nodes remain
250 m apart. Day-12 alpha increases by 7.52707%, end-flood water storage by
44.6647%, and ridge height by 109.740%, while deposited mineral source mass
decreases by 20.4507%. Local fields are compared through aligned 2 by 2 fine
cell means over common 250 m floodplain footprints, including dry cells.
The portable `fine-grid.py` replay checks native checkpoint inventories and
first-remap event masks; initial water and full-solid references remain
inferred from the recorded residuals. Small normalized budget residuals and
zero native-grid capture/abandonment counts do not establish convergence or
predict later-flood behavior.

## Production bank recycling

The [retained flood-6/7 comparison](../validation/production-recycling-002/README.md)
tests nonzero bank recycling in production case 30 (`A=0.012`, `C=0.0003`,
`E=1.5`, 250 m). During flood 7, the recorded reservoir releases
`7.95318210766e8 kg`; about 70.38 kg remains before remapping. Independently
decoded masks identify five captured and five abandoned raster cells.
The ledger records a new bank addition of `3.98318032085e9 kg`. The unsaved
pre-remap bed prevents an independent per-cell excavation calculation.

Offline integration of both complete checkpoint payloads checks temporal
water, suspension-plus-deposition and full-solid balances. Their differences
from the recorded residual changes are `-1.49012e-6 m3`, `-8.41566e-7 kg`,
and `+0.00213587 kg`. The full-solid difference is approximately accounted
for by accumulation order; the retained record also reports a stable
cellwise bed difference and a source-order Python diagnostic, without a
fitted acceptance threshold or compiled bit-identity claim. Initial
inventory references cancel in these temporal differences. This is a
single production interval, not evidence of long-term convergence or
manuscript-panel agreement.

The [case-29 initial-reference replay](../validation/production-recycling-002/run29-initial-reference/README.md)
reconstructs fresh-start water and signed bed inventories from the frozen
configuration, constructor and seeded geometry. All 574 raw random words and
287 distribution doubles match a retained GNU 8 standard-library witness;
all 1,156 geometry tokens match the first-peak file at its printed precision.
Source-order initial water is `156892526.49865156 m3`, and initial signed bed
mass is `-457921872591.4135 kg`. Initial hydraulic depth is about 4.3564 m;
the specified 8 m describes bed incision.

At flood 19, the source-order full-solid residual is `-8.367441058158875 kg`,
numerically equal to the recorded post-remap residual. Compensated inventory
and budget sums give `-8.370736122131348 kg`, a discrepancy of
`-0.0032950639724731445 kg`, or `-3.16846e-14` of the prescribed sediment input
over 19 floods. The calculation uses recorded external flux, signed forcing,
recycling and correction ledgers; it does not independently reintegrate
boundary exchanges. Full-solid acceptance remains unassessed, with no new
threshold. Rounded geometry agreement and the random-generator witness do
not establish historical compiled-model bit identity or convergence. The
original flood-19 capsule and its strict water-storage/suspension guards
remain unchanged.

The [case-26 flood-14 replay](../validation/production-recycling-002/run26-flood14/README.md)
adds a later native-inventory check for `A=0.036`, `C=0.003`, `E=1` and
sand/silt/clay fractions `[0.05, 0.20, 0.75]`. Its retained bank inventory is
`8.88909697492e8 kg`, and recorded cumulative recycling is `8.91017993859e9 kg`.
The checkpoint, complete history prefixes, original process/configuration and
reused frozen sources are bound by hashes. The fresh-start initializer has
the same dependency tokens as case 29, and its reconstructed initial
inventories agree exactly. All 1,156 case-26 first-peak geometry tokens match
at printed precision. No initial reference is inferred from the evolved
flood-14 checkpoint.

Reaggregated water differs from the recorded post-remap inventory by
`-1.5497207641601562e-6 m3`; the suspension-plus-deposition residual differs
from its ledger by `-1.3122334507897904e-6 kg`. Both satisfy the inherited
strict `0.001 m3` and `0.001 kg` reconciliation guards, which do not constrain
the absolute budget residual. The source-order full-solid residual is
`-6.115790367126465 kg`, equal to its recorded value. Compensated sums give
`-6.110848426818848 kg`, a difference of `0.0049419403076171875 kg`, or
`6.44923e-15` of prescribed sediment input over 14 floods. Full-solid
acceptance remains unassessed. This calculation uses recorded exchanges and
does not independently reintegrate boundary fluxes, recover event history,
or establish convergence or manuscript-panel agreement. The replay reuses
ten explicitly pinned sibling files; its README lists the complete retained
dependency set and an offline command.
