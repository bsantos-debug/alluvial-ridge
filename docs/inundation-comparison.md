# Day-12 inundation and deposition diagnostics

`scripts/inundation_metrics.py` measures water extent independently of deposit
extent for Figure 1A–F. It reads only this reconstruction's saved numerical
files. It imports no published numerical fields, curves, or pixels, and it
does not assign a scientific reproduction status.

```sh
source scripts/environment.sh
python3 scripts/inundation_metrics.py --data-root data --output figures/inundation_metrics.json --strict
```

The six default samples are run 11 at floods 61, 251, 501 and 562; run 17 at
562; and run 03 at 562. Optional `--sample 11:1` adds a diagnostic record
without a manuscript panel label. Missing snapshots remain pending. Shortened
domains, altered flood durations, and changed physical/numerical parameters
are explicitly noncanonical. The parameter comparison includes the complete
maintained `config/physics.txt` except the requested flood count, the run table,
and the fixed slope and grain density. Requesting more future floods does not
alter an earlier completed flood's physics.
Strict mode writes all available evidence and exits 2 until all six requested
canonical snapshots pass the geometry/diagnostic checks. This checks data
coverage and internal consistency, not agreement with the publication.

Each sample requires a completed summary row, a day-12 raster with clock
`(n−0.4)T`, and an end-flood raster with clock `nT`. Their geometry and masks
must agree because migration occurs after the flood. Both states precede the
nth migration/aggradation event. The `peak_` filename prefix means the day-12
diagnostic state; maximum discharge in the assumed hydrograph is at day 10.
Hashes identify every consumed file, the configuration references and script.
Run the helper in the final packaged workspace so its relative input paths
remain usable after publication. It is included in future clean rebuilds and
is a later postprocessor for the immutable rebuild 002 execution. That run's
staged sources remain unchanged.

## Quantities

- **Inundation:** floodplain area with water depth greater than 1 mm, its
  fraction of the unmasked floodplain, water volume, and mean depth including
  dry cells. Channel ghosts are excluded from these floodplain quantities.
- **Wet interface:** immediate channel–floodplain grid faces whose floodplain
  depth and channel stage above the adjacent bank both exceed 1 mm. Face
  counts and lengths use the same definition as the model's alpha diagnostic.
  Alpha reconstructed from the raster is mean depth divided by wet fraction.
- **Spatial concentration of wet interface:** number and largest length of
  connected wet-face patches. Two faces connect when they share a grid vertex.
  These are nominal raster features; diagonal contact and threshold rounding
  affect topology. They do not measure flow discharge, breach discharge, or
  avulsion occurrence.
- **Deposition:** bulk deposit volume at flood end, and the portion on cells
  inundated at day 12. These volumes include pore space: the model converts
  sediment mass into bed thickness using grain density times solid fraction.
  Deposited area is never substituted for inundated area.
- **Previously occupied cells:** end-flood deposition in currently unmasked
  cells that were active channel in an earlier completed saved raster. The
  output lists those earlier flood indices. This sparse occupancy history
  misses unsaved channel positions, and later burial is not resolved by the
  mask alone. It therefore cannot establish total cutoff-channel infilling.

## Snapshot precision and interpretation

Rasters store float32 values; summary diagnostics were calculated in double
precision. Half-ULP intervals bound each saved depth and bed elevation's
rounding. The helper reports definite and possible wet areas and bank faces,
and propagates these bounds into mean water depth, alpha, and deposit volume
on the day-12 wet mask. Reported mean depth, wet-interface fraction, and alpha
are checked against those intervals, allowing for the summary CSV's decimal
rounding. A mismatch is retained explicitly. If zero wet faces remain possible,
an alpha bound can be undefined; it is not replaced by zero. Connected-patch
counts use the nominal stored values and have no claimed topology bound.

Use these quantities to compare water extent and localization across the
requested early/late, high-aggradation, and low-load cases. They supplement
direct inspection of the independently generated maps against the permitted
embedded manuscript figure. They cannot establish visual agreement by
themselves or supply unreported quantitative targets from the paper.

## Executed checks

The helper was checked against actual two-flood restart output on a 6 km by
4 km, 3600 s diagnostic domain. Its second day-12 raster records 5760 s and
reconstructs mean floodplain depth and alpha as 0.3124961011 m, consistent with
the double summary within float32 rounding bounds. Both banks comprise 48
wet grid faces, giving wet fraction 1. The output remains a noncanonical
diagnostic; all six requested manuscript samples remain pending.

Small analytical arrays independently check two connected wet banks, a dry
gap that separates one bank into two patches, and a stored 1 mm depth whose
rounding interval crosses the wetness threshold. These are numerical checks,
not manuscript results. Reading the active production folder while its requested
snapshots were absent produced six pending records and no calculated substitute.
