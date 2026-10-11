# Bank recycling between production floods 6 and 7

This retained comparison covers case 30 of clean rebuild 002: a 250 m
floodplain grid, `A=0.012 m/flood`, `C=0.0003`, and `E=1.5`. Both checkpoints
follow the end-of-flood remap. The 580-flood calculation remains active.
These data assess one recycling interval, not a manuscript panel or
long-term convergence.

The `flood6/` and `flood7/` folders each contain an immutable input archive
and its capture manifest. Each archive retains the checkpoint, parameters,
process record, summary and remap budgets, five frozen numerical sources,
the reviewed array decoder, and the original scalar/inventory observations.
The recorded executable identity was checked by those live observers;
executable bytes are not included in these two archives.

`replay.py` checks the pinned manifests, all 28 archive members, checkpoint
headers and signatures, common parameters and process identity, and the
preserved history prefix. It reads the archives without extracting files
and loads only the reviewed array-decoding function. Water and suspended
sediment are integrated over physical floodplain cells and actual channel
control areas. Interpolated channel raster ghosts are excluded. Bed and bank
inventories are included separately in the signed full-solid inventory.

From the project root, reproduce the saved comparison with a new output:

```sh
python3 -B validation/production-recycling-002/replay.py \
  validation/production-recycling-002/flood6 \
  validation/production-recycling-002/flood7 \
  --output tmp/recycling-replay.json
cmp validation/production-recycling-002/replay.json tmp/recycling-replay.json
```

Existing outputs are not overwritten. Replay uses only these retained files;
it does not rerun a live observer or advance the model.

## Recorded bank transfer and raster changes

| Quantity | Mass (kg) |
|---|---:|
| Bank reservoir after flood 6 | 795,318,281.1482041 |
| Recycled during flood 7 | 795,318,210.7659556 |
| Bank reservoir before remap 7, from the 12-digit summary | 70.3822656367 |
| Bank reservoir after remap 7 | 3,983,180,391.2367015 |
| New bank addition during remap 7, derived from the ledger | 3,983,180,320.854436 |

The difference `bank6 - recycled7 - bank7_pre` is `-1.71158e-5 kg`.
The two reconstructed masks contain 576 channel cells each, with 571 in
common, five newly captured cells and five abandoned cells. The stored cell
IDs are zero-based and use row-major order. These are membership changes
across the single remap, not a count of physical erosion events or an
estimate of the continuous area swept during migration. Both cutoff
counters are zero. The pre-remap flood-7 bed was not saved, so the bank
addition is not independently reconstructed from excavation in each cell.

## Temporal conservation calculation

Let `Delta` denote the difference from the post-flood-6 checkpoint to the
post-flood-7 checkpoint. `W` is water, `S` suspended sediment, `D` cumulative
deposition, and `F` signed bed plus suspended plus bank sediment. `Ew` and
`Es` are cumulative net external water and sediment; `J` is cumulative
signed bed forcing and `R` cumulative recycled bank mass. `Cw` and `Cs`
are the recorded corrections. The independent temporal balances are

```text
Delta W - Delta Ew - Delta Cw
Delta S + Delta D - Delta Es - Delta Cs
Delta F + Delta R - Delta J - Delta Es - Delta Cs
```

They are compared with the corresponding differences of the saved
post-remap residuals. The sediment boundary ledger includes recycled bank
injection. Adding `Delta R` in the full-solid equation removes that duplicate
count of material already in `F`. The initial inventory cancels between
checkpoints; no initial water or solid reference is inferred.

The compensated inventory calculation differs from the recorded residual
change by `-1.49012e-6 m3` for water, `-8.41566e-7 kg` for suspension plus
deposition, and `+0.00213587 kg` for full solids. Normalization uses one
prescribed hydrograph: `1.512e10 m3` and `5.473459038918807e9 kg`, excluding
recycling. These discrepancies differ from the nonzero conservation
residuals themselves, which are retained in `replay.json`.

Directly summing cellwise bed changes gives a full-solid discrepancy of
`+0.00210774 kg`. A separate Python calculation following the source's
ordered inventory additions gives `-3.57628e-7 kg`. The endpoint changes
caused by accumulation order account for nearly all of the approximately
2.1 g difference. This diagnostic does not claim bitwise equivalence with
compiled C++, and no acceptance threshold was adjusted to suppress the
discrepancy. Neither arithmetic agreement nor small budget residuals
establish discretization accuracy or agreement with the publication.

## Additional retained endpoint

The [case-29 flood-19 archive](run29-flood19/README.md) preserves a separate
native-array check after that run first records bank recycling. Its offline
replay reconstructs water and suspended-sediment inventories and reports
signed bed and bank inventories. Only one native endpoint is retained there;
initial water and full-solid references were not independently regenerated,
so it does not provide the paired temporal closure calculated above.
