# Native inventories after case 29, flood 19

This archive retains one post-remap checkpoint from clean rebuild 002:
case 29, flood 19, at 32,832,000 s. The floodplain spacing is 250 m,
`A=0.012 m/flood`, `C=0.0003`, `E=0.5`, and the sand/silt/clay mass
fractions are 0.05/0.75/0.20. The prescribed concentration scale is 0.001.
The scalar history first records bank recycling during flood 19;
cumulative recycled mass at this endpoint is 794,808,522.3882226 kg.

`inputs.tar.xz` contains 19 hashed members: checkpoint, parameters, process
record, summary and remap histories, scalar observation, comparison, observer
seed, original native-review source and observation, decoder, ordered-sum
helper, original reconciliation-guard source, five frozen numerical sources,
and executable. The executable is retained for hash verification and is never
run by the replay. The historical native observation was made on 2026-10-11
at 11:14:24–25 UTC. Its parsed scientific values and ISO observation timestamps
were retained and serialized for this archive; byte identity with the
original stdout is not claimed. JavaScript number parsing rounded its large
integer checkpoint modification time by 62 ns relative to the later exact
capture stat. Both metadata values are retained and distinguished in the
manifest; this representation difference is not evidence of a checkpoint
change. The original review source is retained byte-for-byte.

From the project root, reproduce the saved result with a new output:

```sh
python3 -B validation/production-recycling-002/run29-flood19/replay.py \
  validation/production-recycling-002/run29-flood19 \
  --output tmp/run29-flood19-replay.json
cmp validation/production-recycling-002/run29-flood19/replay.json \
  tmp/run29-flood19-replay.json
```

Replay checks the pinned manifest, archive and every member; binds all 31
checkpoint signature parameters and the complete header to the retained
records; and reads only the archived inputs. Only the reviewed decoder and
ordered-inventory functions are loaded from the retained helper sources.
Neither a model nor a live observer is invoked. Existing outputs are not
overwritten.

Water and suspended sediment are summed over 54,720 physical floodplain
cells and 290 actual channel control areas. The 576 interpolated channel
raster cells are excluded from those inventories. Bed mass uses all raster
cells and a signed reference to the initial sloping plane.

| Reconstructed quantity | Value |
|---|---:|
| Water storage | 548,945,843.0233959 m³ |
| Suspended sand | 289,733.5880192701 kg |
| Suspended silt | 114,170,715.60579088 kg |
| Suspended clay | 32,806,638.246536933 kg |
| Water storage minus recorded post-remap storage | +5.960464477539062e-7 m³ |
| Suspension-plus-deposition residual minus recorded residual | -9.797513484954834e-7 kg |

Both discrepancies satisfy the existing strict 0.001 m³ and 0.001 kg
reconciliation guards retained in `guard-source.py`; replay raises an error
if either fails. These discrepancies measure inventory/ledger agreement,
not the conservation residuals themselves or discretization accuracy.

The replay reports compensated and source-ordered signed bed-plus-suspension
plus-bank inventories. It also retains the distinction between the decoder's
left-to-right bed multiplication and the original review's grouped solid
density. No full-solid acceptance threshold is fitted, and Python addition
order is not claimed to reproduce compiled C++ bit-for-bit. Initial water
and full-solid inventories were not independently regenerated, so this
single endpoint does not independently establish full-solid closure.
No prior native checkpoint, capture/abandonment count, avulsion history,
or spatial explanation is reconstructed. The full 580-flood experiment and
its manuscript-panel assessment remain incomplete.
