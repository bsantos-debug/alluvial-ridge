# Coupled remap and recycling stress audit

These are constructed small-domain numerical tests. They are not production
floods, manuscript-panel data, or evidence that the sediment closures apply at the
large concentrations used to stress inventory accounting. Production jobs and
production outputs were left untouched. All files were written on `/data`.

## Original defect

The original remap debited abandoned raster cells using interpolated channel
ghost concentrations and depths, although channel inventory was stored on exact
width-times-arc-length control areas. Local raster support can exceed the
corresponding 1-D control area even when the total raster footprint is smaller.
A global footprint comparison therefore cannot guarantee class positivity.

`footprint.cpp`, compiled against the immutable `source/` headers, constructs
polygonal and smooth centerlines and measures every old donor's abandoned raster
support. It then calls the actual remapper with a unit class pulse at the most
overdrawn node. At the production 250 m floodplain spacing and 500 m channel width,
one neck cutoff produced:

| Quantity | Value |
|---|---:|
| Old node | 22, at (3500, 5916.745429380432) m |
| Exact donor control area | 107303.00568887105 m² |
| Abandoned interpolation-weight support | 145371.75919120162 m² |
| Local support / control area | 1.3547780722257892 |
| Available class inventory at 1 kg/m² | 107303.00568887105 kg |
| Requested class debit | 145371.75919120162 kg |
| Resulting class target | -38068.753502330568 kg |
| Remaining uniform channel water target | 19013143.697004057 m³ |
| Total original raster footprint | 7062500 m² |
| Total original 1-D control area | 7753285.9242510144 m² |

The original core threw `remapping raster footprint exceeds channel inventory`.
This is a negative class inventory with abundant remaining water, not the
physically dry result of moving all water into an abandoned reach. Exact per-node
coefficients and all tested grids are in `footprint/nodes.csv` and `cases.csv`.

`plume.cpp` tests a circular loop of radius 1500 m (three channel widths), joined
to an inlet and outlet, with positive Gaussian class inventories plus a 1e-8
background. It uses the actual migration/cutoff/remap call, with a small declared
migration coefficient of 0.001 m/flood to isolate neck removal. A 1000 m Gaussian
standard deviation on the 250 m grid produced a class target of -16364.3 kg.
After 120 s of actual coupled flow and sediment transport before that cutoff,
the target remained -16099.1 kg. A 500 m standard deviation gave -27052.7 kg after
transport. Several refined 125 m cases also failed. Across both loop shapes,
five plume widths, two grids and two transport durations, 34 of
40 original-core trials threw this inventory error; the complete results
and successful broad-plume controls are retained in `plume/results.csv`.

## Conservative correction and acceptance tests

The parent implemented a donor-normalized projection in the root core. The old
node inventory is partitioned over all of its mapped raster support; the same
nonnegative weights apply to water, momentum and all three classes. Abandoned
states are overwritten with the corresponding exported inventories divided by
cell area. Unsupported nodes retain their inventories. Remaining channel donors
are remapped by nonnegative interval overlap, and newly captured floodplain
inventories enter adjacent new channel nodes locally. No component-dependent
global scaling remains.

Full support normalization is preferable to capping the normalization at one:
when raster support is smaller than exact control area, such a cap would retain
channel inventory even after all of that donor's represented footprint departed.
An exact polygon-overlap method would require a separate definition of control
areas at curved and self-contacting reaches. This correction is an explicit
conservative projection between nonmatching representations. It preserves mass
and constant concentration; it generally changes water depth when the represented
areas differ. Prescribed changes in channel direction also imply momentum
rotation. Global Cartesian momentum conservation across a changing bend is not
claimed. Straight-channel momentum and convex velocity bounds are tested.

The new `tests/remap.cpp`, included in `make check`, passed these checks:

- Exact no-change identity, including nonzero local momenta whose integral is zero.
- The original 250 m localized-pulse counterexample.
- Smooth Gaussian cutoffs at 125, 250 and 500 m floodplain spacing.
- 120 s of coupled post-cutoff transport on all three grids.
- Constant concentrations through cutoff and changing masks.
- Retention of 73 nodes with no old raster support in an intentionally
  under-resolved numerical fixture.
- Capture of wet floodplain cells with different concentrations and momentum;
  conserved water/class totals, convex concentrations/velocities, and conserved
  straight-channel streamwise momentum.
- Four conservative aggradation remaps, plus the explicit model-limit test below.
- Twenty-four complete 300 s numerical transport/remap events in the zero-settling
  limit, using actual inlet bank recycling and 192 raster-mask transitions.

The repeated control uses one-sided channel oscillation and A=0 so that an
undisturbed bank remains and the separate mean-depth restriction is respected.
The 300 s events are a stress fixture, not shortened production floods. Large
recycled masses here test the algebra of passive inventory transport; their
concentrations are not a physical prediction. Water, each suspended class,
aggregate bed/bank material, nonnegative states and correction ledgers are checked
after every valid remap. The final measured maxima were:

| Quantity | Maximum / total |
|---|---:|
| Water budget residual | 1.1641532182693481e-8 m³ |
| Individual suspended-class residual | 3.910064697265625e-5 kg |
| Total solid/bed/bank residual | 4.38690185546875e-5 kg |
| Cumulative recycled mass | 12720059999.99999 kg |
| Water or mass correction ledger | 0 |

The class residual is approximately 3.1e-15 of the recycled mass. This is a finite
numerical test, not a long-time error bound. Per-class suspension and reservoir
accounting are tested, but the core does not store per-class bed composition;
full grain-specific bed conservation cannot be inferred from its bulk bed ledger.

## Disclosed limits

A cutoff followed by the retained normalized-arc-length projection produced 14
exactly dry interior channel sections. The inlet remained wet at 8.4534595075 m,
and 120 s of coupled transport passed without clipping or a budget failure.
These dry gaps are a consequence of the explicit remapping assumption. This test
does not establish that every possible future cutoff will retain a valid wet,
subcritical inlet.

A separate symmetric reoccupation experiment excavates banks on both sides and
applies A=0.01 m per remap without infilling. Eight remaps conserved inventory.
At event nine, the measured mean bank-to-bed depth was -0.030000000000006466 m,
and the existing guard rejected migration/remapping as undefined. That rejection
is retained as an expected model-limit test; no artificial depth floor, bed
repair or clipping was introduced. The first failed repeated-control log is
preserved as `remap-first-control-limit.log` rather than silently discarded.

## Reproduction and provenance

`manifest.json` records before/after header hashes, exact commands and output
hashes. Original headers are retained in `source/`; corrected headers are in
`corrected_source/`. `remap-regression.cpp` is the tested regression-source copy.
`remap-current.log` contains the final passing results. To compile the final
regression against its immutable corrected snapshot:

```sh
g++ -O3 -std=c++17 -Wall -Wextra -Wpedantic -Ivalidation/stress/corrected_source validation/stress/remap-regression.cpp -o validation/stress/remap_snapshot_test -lstdc++fs
nice -n 15 ./validation/stress/remap_snapshot_test
```

The original probes intentionally continue to demonstrate the old failure when
compiled against `source/`. They must not be treated as tests of the corrected
core or used to replace production inputs or results.
