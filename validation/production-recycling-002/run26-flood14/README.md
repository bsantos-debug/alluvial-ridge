# Case26 flood14 native inventory and independent initial reference

This capsule checks one completed post-remap endpoint of the original case26 process: flood14, 24,192,000 s, `A=0.036`, `C=0.003`, `E=1`, `fine=1`, and sand/silt/clay fractions `[0.05, 0.20, 0.75]`. The process was still running its original 580-flood request when captured. All 31 cases already have first-flood native water/suspension checks. This extension adds a later fine-load endpoint with nonzero bank and recycling ledgers; it does not establish convergence, model accuracy, a causal comparison, or completion of 580 floods.

From the project root, replay with Python3.6.8 or a compatible later Python:

```sh
mkdir -p tmp
python3 -B validation/production-recycling-002/run26-flood14/replay.py --output tmp/run26-flood14-replay.json
```

The output path must be new. Omitting `--output` prints JSON without writing a file. No cache, archive extraction, model, auditor, compilation, RNG executable, or historical/live path is used. The script loads only named pure function definitions from hash-checked retained sources; their module top-level code is not executed. The explicit folder positional argument can select a relocated capsule. Preserve the relative sibling layout and the ten dependency files listed in [capture.json](capture.json); this folder alone is not self-contained. Shared dependencies are the immutable `../run29-flood19/{capture.json,inputs.tar.xz}` and eight explicitly pinned files in `../run29-initial-reference/`. The old case29 checkpoint is hash-checked as an archive member but is not decoded, and neither case29-bound replay wrapper is called.

The [capture observation](capture-observation.json) records two-second pre/post byte, metadata, parameter-signature, full-header and process-identity agreement for all 11 retained inputs. The accepted checkpoint SHA256 is `7e42968dfc38ffb9f968c2ed9eae5abae836a06018147306e3eb7bd106e0c379`. PID 3805586, start ticks 51544923 and parent 3805340 remained fixed; CPU ticks advanced by 204. Capture completed at `2026-10-11T15:15:07.830328+00:00`. Frozen compiler provenance, configuration, run table, five source files and executable were separately observed identical to the retained shared bytes. Historical absolute paths, including the original scratch alias, are provenance strings only. The original automated marker retains its historical `independent_review: pending` value; that marker is evidence of scalar-observer acceptance, not evidence of a completed independent review.

The exact `summary.csv` and `remap_budget.csv` histories cover floods 1–14. Replay binds every final token and the accepted flood13 byte prefixes to the retained comparison and prior scalar endpoint. It binds the full native checkpoint signature, scalar header, payload length, finite arrays, original command, run row and effective parameters to the accepted hashes. Hash/format/binding failures abort before a result is written. The full hash inventory is in [capture.json](capture.json).

Fresh-start proof follows the frozen model argument/configuration merge and parser, including all numerical defaults and overrides. Neither the original model argv nor merged configuration contains `--resume`; suite-level orchestration settings are not model arguments. The 12 actual initializer dependency tokens (`length`, `width`, `dx`, `channel_width`, `slope`, `initial_depth`, `qmin`, `channel_chezy`, `porosity`, `rho_s`, `seed`, `perturbation`) exactly match the independently validated case29 initializer. `A` enters initial geometry as `0*A`, which is equal for both finite positive values; `C`, `E`, `fine` and run number do not enter the zero-sediment initial geometry/inventories. The replay nevertheless reconstructs case26 initialization from its actual parameters, then checks equality with the retained reference result. It does not infer an initial reference from the evolved checkpoint.

The reused MT19937/GNU8 conversion functions reproduce 574 raw words and 287 noise doubles exactly against the retained RNG-only witness. All 1,156 case26 first-peak x/y/bed/control-area tokens agree at their printed 12 significant digits. Peak water depth and velocity are excluded because they have already evolved. Initial water is reconstructed from the equilibrium flow, with depth 4.356408496504154 m; `initial_depth=8 m` denotes bed incision. These checks do not establish native compiled C++ bit identity for geometric and transcendental arithmetic.

The source-order initial water/solid references are 156,892,526.49865156 m³ and −457,921,872,591.4135 kg; compensated references are 156,892,526.49865165 m³ and −457,921,872,591.4134 kg. Initial suspended classes, bank, deposition, exchange, recycling, forcing and correction ledgers are zero. Current water and suspended classes are summed from physical floodplain raster cells plus actual 1D channel control areas, excluding raster channel cells. Signed bed inventory includes every raster cell relative to the initial plane. Bank classes are decoded from the checkpoint header. Current mapped/floodplain counts are 576/54,720; a single endpoint cannot determine capture, abandonment or avulsion events.

The existing absolute reconciliation guards from the retained `guard-source.py:77–80` both pass: native compensated water minus recorded post-remap water is −1.5497207641601562e−6 m³, and the reconstructed suspension-plus-deposition residual minus its recorded value is −1.3122334507897904e−6 kg. Both use strict absolute bounds of 0.001 in their respective units. These guards concern current inventory/ledger agreement. The `budget_diagnostics` section separately reconstructs residuals using the independently generated initial references:

- Water: `W − W0 − external_water − water_correction`.
- Suspension: `sum(S − S0) + deposited − sum(external_sediment) − mass_correction`.
- Full solid: `T − T0 + recycled − signed_bed_forcing − sum(external_sediment) − mass_correction`, where `T` is signed bed plus suspended plus bank inventory.

Source-order and compensated budgets are separate arithmetic diagnostics. The source-order full-solid residual is −6.115790367126465 kg, matching the recorded residual exactly; the compensated result is −6.110848426818848 kg, differing by +0.0049419403076171875 kg. Full-solid acceptance remains **unassessed**: there is no new or fitted bound. The result also preserves the unchanged decoder's left-to-right bed products, grouped-density compensated bed products, and sequential sums as distinct fields. Neither arithmetic order asserts compiled C++ bit identity.

Boundary exchange, deposition, signed bed forcing, recycling, corrections and prescribed hydrograph normalization totals are retained recorded quantities, not independently integrated from a time history. Bank mixture agreement is arithmetic on decoded header values, not a separate reconstruction of per-cell bank excavation. Scalar histories contain no earlier native arrays. Matching ledgers and reconstructed references therefore does not demonstrate independent boundary-flux physics or spatial causation.

The retained [replay result](replay.json) was produced by:

```sh
python3 -B validation/production-recycling-002/run26-flood14/replay.py validation/production-recycling-002/run26-flood14 --output validation/production-recycling-002/run26-flood14/replay.json
```

That command exited 0. Repeating it with the existing output was refused before replay and left all capsule bytes unchanged; the focused check source/result are under ignored `tmp/run26-flood14-capsule-check-002/{exclusive-output.py,exclusive-output.json}`. An isolated copy of the three required capsule folders reproduced all 24,540 saved result bytes exactly. Focused integrity checks rejected a corrupted checkpoint, a missing shared dependency and an inconsistent saved result; the report withheld numerical claims for each invalid archive. The check record is `tmp/case26-native-root-checks-do8n8uqq/checks.json`. No model or auditor was invoked.

Retained SHA256 pins:

- `capture-observation.json`: `be9f4026cf07716638e87a4f87ea62b3fd5a7022a5937bf17e7531bb8cbab819`
- `capture.json`: `285b6d5017c381c42cef2a9f2bffefeae924b9b985278962996ae436e0abb66d`
- `replay.py`: `4c562d6bbb8ebd1f681c4819e6491b6e211d3dd3f4ed32c80a1905ef35a62b87`
- `replay.json`: `d277b3cbfc85ca7a47887cbdec6259032da70b99f734c563cc9983469e31304b`
