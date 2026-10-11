# Initial references for the case-29 flood-19 budget

This offline calculation reconstructs the initial water and signed solid
inventories for corrected rebuild 002, case 29. It combines those references
with the unchanged [flood-19 native-inventory capsule](../run29-flood19/README.md)
to calculate budget residuals at 32,832,000 s. External flux, bed forcing,
recycling and correction ledgers remain the recorded model quantities.
Boundary exchanges are not independently reintegrated. No model or PDE is
executed by this replay, and no full-solid acceptance threshold is introduced.

From the project root, reproduce the deterministic result with a new output:

```sh
python3 -B validation/production-recycling-002/run29-initial-reference/replay.py \
  validation/production-recycling-002/run29-initial-reference \
  --output tmp/run29-initial-reference.json
cmp validation/production-recycling-002/run29-initial-reference/replay.json \
  tmp/run29-initial-reference.json
```

`analyze(folder)` returns the same result as a plain dictionary. The CLI
requires a new output path and refuses writing into the older flood-19
capsule. Replay verifies the capture manifest, all seven added input files,
and the sibling capsule's source, manifest, archive and retained result. It
loads only the hash-bound offline replay definitions, imports and constants;
the sibling CLI is excluded. Its native-array reconciliation runs unchanged,
and its returned result must equal the retained result exactly. Both sibling
directories are required for portable replay. Historical absolute paths in
provenance are never opened.

The capture retains the original frozen compiler provenance, physics
configuration, runs table, first-peak geometry witness, and a new RNG witness
with its source and provenance. Original parameters, process records, seed
and numerical sources are bound through the sibling archive. The replay
reconstructs the effective command/configuration merge: original command
options take precedence, the selected case supplies its run parameters, and
neither command nor physics configuration contains `resume`. Thus the initial
references belong to a fresh run. Checking command arguments alone would not
establish this because the model also accepts options from its configuration.

## Initial state and independent witnesses

The pinned `src/model.hpp:49-55` defines a centerline with 289 nodes, spaced
250 m in x. Seed 2018 initializes MT19937; 287 interior y-coordinates receive
uniform perturbations on `[-5 sqrt(3), +5 sqrt(3)]` m. Endpoints consume no
random draws. An independent Python integer recurrence and GNU8 conversion
are checked against `rng-witness.csv`: all 574 32-bit words and 287 double
values agree exactly. The retained witness was compiled once with the
originally recorded GCC 8.5.0 and uses only standard-library random/math/output
headers. It contains no model headers or model calls. The compiler command,
version, executable hash and observed GNU header hashes/line references are
retained in `rng-provenance.json`; third-party header contents are not copied.
Offline replay neither compiles nor executes this witness.

The Python initializer follows frozen `model.hpp:125-179`: sequential arc
lengths, channel areas, nearest-segment raster projection and interpolated
channel bed. Its x/y/bed/control-area values match all 1,156 corresponding
12-significant-digit tokens in `peak-channel-initial-geometry.csv`. That file
was saved during flood 1 before the first migration/remap, so those geometry
columns retain initialization. Its evolved water depth and velocity are
excluded. Agreement at printed precision does not establish historical
native-double identity or cross-language identity of `hypot` and `pow`.

The channel length is 72,028.38146356188 m and its summed control area is
36,014,190.73178094 m². Initial water depth is 4.356408496504154 m, obtained
from the minimum-discharge Chezy relation with slope `S0 L / Lc`.
The 8 m `initial_depth` parameter specifies bed incision, not initial water
depth. All physical floodplain cells are initially dry, and initial suspended
sediment and bank reservoirs are zero. There are 576 mapped channel raster
cells and 54,720 physical floodplain cells.

Water storage sums actual one-dimensional channel control areas and excludes
interpolated channel raster cells. Signed solid inventory includes suspension
and bank mass plus every raster bed cell relative to the original sloping
plane, as in `model.hpp:451-454`. It includes no separate one-dimensional
channel bed inventory and no additional cumulative-deposition term. Its
initial value is negative because channel incision precedes the initial
inventory measurement.

| Independently reconstructed reference | Source-order Python | Compensated sums |
|---|---:|---:|
| Initial water, m³ | 156892526.49865156 | 156892526.49865165 |
| Initial suspension, each class, kg | 0 | 0 |
| Initial bank, each class, kg | 0 | 0 |
| Initial signed solid inventory, kg | -457921872591.4135 | -457921872591.4134 |

The compensated-minus-source-order differences are `8.940696716308594e-8 m³`
for initial water and `0.0001220703125 kg` for initial solids. Neither reference
is inferred by rearranging the flood-19 recorded residual.

## Budget diagnostics

Let `W` be water storage, `S` suspended mass, `D` cumulative deposited mass,
and `F` signed bed plus suspension plus bank inventory. Subscript `0` denotes
the independently reconstructed start. The endpoint ledger supplies net
external water `Ew`, net external sediment `Es`, recycled mass `R`, signed
bed forcing `J`, and corrections `Cw,Cs`. The calculated residuals are

```text
W - W0 - Ew - Cw
S - S0 + D - Es - Cs
F - F0 + R - J - Es - Cs
```

The full-solid equation adds `R` because the sediment flux ledger also
includes reinjection of bank material already represented in `F`. Bed forcing
retains its recorded sign. Source-order diagnostics use sequential inventory
and class-ordered residual operations; compensated diagnostics use `math.fsum`
for inventories and the signed residual terms.

| Quantity | Source-order residual | Source-order minus ledger | Compensated residual | Compensated minus ledger |
|---|---:|---:|---:|---:|
| Water, m³ | 0.0002570152282714844 | 0 | 0.0002575218677520752 | 5.066394805908203e-7 |
| Suspension + deposition, kg | -50.26099383831024 | 9.313225746154785e-8 | -50.260994423530065 | -4.920875653624535e-7 |
| Full solids, kg | -8.367441058158875 | 0 | -8.370736122131348 | -0.0032950639724731445 |

Normalization uses the case's 19 prescribed hydrographs, excluding recycled
input: `287280000000 m³` of water and `103995721739.45734 kg` of sediment.
The compensated full-solid discrepancy divided by prescribed sediment input
is `-3.168461084128381e-14`; this discrepancy differs from the nonzero
full-solid residual itself. Source-order numerical equality of selected
residuals does not establish compiled C++ bit identity or a zero conservation
residual. The stored post-remap ledger combines pre-remap residual and remap
transfer operations whose historical intermediates are not reconstructed.

The original strict `0.001 m³` water-storage and `0.001 kg` suspension-ledger
reconciliation guards execute unchanged in the sibling replay and pass.
They are not extended to full solids. `budget_diagnostics` explicitly labels
full-solid acceptance **unassessed**, retaining both arithmetic results and
all discrepancies without a fitted bound. This single endpoint does not
establish discretization accuracy, capture/abandonment counts, avulsion
history, manuscript agreement, or completion of the 580-flood experiment.

## Evidence pins

- Capture manifest: `23b008117d075c453a33c6befa42fb1246d71fd4c507c687ecf6dbe6f4bdb1fc`
- Replay source: `b1136088ca9e6e86f71cb02ca36bbc55d50562002049c4cd15a2198da4418a81`
- Retained result: `d500c6fa7aa77d8e78b845f5413e7a8d3ceae8c85c82b10012366911ca40ce3d`
- RNG source: `2de20f0218c99aa82cd5772bbd9875d259693acda3d6075d790082f23c2e8e1b`
- RNG output: `637535884306525f6cffece468512f23f221c46dbab46f79cd23668d791b0966`
- Rounded geometry witness: `bdcdeb29a104ac5d5ab2af39c5f9455fbbff3b990d9b59a76467558df37c84c6`
