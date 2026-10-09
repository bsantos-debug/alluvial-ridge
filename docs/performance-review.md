# Numerical performance review

The floodplain traversal was optimized without changing grid spacing, timestep
restrictions, fluxes, sediment closures, or the number of simulated floods.
The measured improvement is specific to an initially straight river and early
overbank inundation. It does not establish the runtime of the complete ensemble.

## Implemented change

The original solver scanned the full floodplain repeatedly to synchronize
channel ghosts, reset rates, calculate velocity gradients and the CFL limit,
accumulate face fluxes, restrict positivity, update external budgets, and
advance cells. Before inundation, most of those operations visited exactly
dry cells. The 72 km by 48 km domain contains 55,296 cells at 250 m spacing.

`geometry` now records the indices of mapped channel cells and the starting
face index for each floodplain cell. `synchronize` uses the mapped indices.
At each macrostep, one full scan finds the rectangular extent of every cell
with **strictly positive depth**, including mapped channel cells. The rectangle
is enlarged by one cell on each side. Rate resets, gradient calculations,
the floodplain CFL limit, face evaluation, positivity checks, budget sums,
and floodplain updates traverse this rectangle.

This is an exact support restriction for the existing first-order update.
Every face outside the rectangle has two zero-depth states, whose flux the
original solver already skipped. Every dry cell that can receive nonzero
flux from an existing wet cell lies in the one-cell halo. Velocity gradients
required on wet faces retain their original neighbors. Physical boundaries
retain their original faces. Face and cell summation order is preserved.
There is no new wetting threshold and no clipping of small water depths.

The allocated grid and all saved fields retain full resolution and extent.
As the wet extent grows, this optimization approaches the original traversal
cost. In particular, a single small positive-depth cell far from the river
can enlarge the rectangle. Replacing strict positivity by a convenient
depth threshold would change the numerical problem and was not done.

## Measured comparison

On 2026-10-09, a serial C++ harness advanced the full 55,296-cell grid through
7,000 floodplain macrosteps, using default model parameters and zero recycled
bank input. It used the same function sequence as the model driver:

```cpp
double dt = ridge::floodplain_rates(model);
ridge::channel_advance(model, flood_time, dt, {0,0,0});
ridge::floodplain_advance(model, dt);
flood_time += dt;
```

The comparison used the solver immediately before the later normal-rating
outlet-boundary correction. Both variants reached simulation time
272,309.590 s, used 55,051 channel substeps, and contained 1,375 wet physical
floodplain cells. The elapsed time inside the three stepping functions was:

| Phase | Full traversal (s) | Restricted traversal (s) |
|---|---:|---:|
| Floodplain rates | 26.680327 | 9.748611 |
| Channel substeps | 3.511931 | 3.414155 |
| Floodplain advance | 11.566296 | 1.917728 |
| Total | 41.758554 | 15.080494 |

The total improvement was **2.77 times**. The nearly unchanged channel time
is a useful control because that routine was not edited. Measurements used
the shared host, so they include scheduling variability and should not be
interpreted as hardware-independent throughput.

The harness wrote every six-component floodplain state, every six-component
channel state, and every floodplain bed elevation as native doubles.
`cmp` found the two final files byte-identical. Their SHA-256 was
`c4850a125fe90891a1fd2d9b01040db4cef4bbbcdc8a9dde866179871fc93592`.
Thus the tested state equality is stronger than agreement of summary metrics.
Derived scratch arrays outside the active rectangle are not part of this
comparison; they are never read by its subsequent stepping operations.

The precise archived header hashes identify the tested implementation:

| Header | SHA-256 |
|---|---|
| Before optimization | `3e70fedc3da3c4ff0c102aafb54cb46c67c6535d81f1023cf3656bb527d5cebd` |
| After optimization | `dcd4d24f28213881ec824fc895bc6143ea18b3c95fe757c1f7e790005d3e38d0` |

The working copies and harness were retained in
`tmp/performance_current_base/` and `tmp/performance_current_active/` for
the development audit. They are temporary benchmark artifacts, not required
model inputs. Commands used were:

```sh
g++ -std=c++17 -O3 -Wall -Wextra -pedantic tmp/performance_current_base/benchmark.cpp -o tmp/performance_current_base/benchmark -lstdc++fs
./tmp/performance_current_base/benchmark 7000 tmp/performance_current_base/final7000.bin
g++ -std=c++17 -O3 -Wall -Wextra -pedantic tmp/performance_current_active/benchmark.cpp -o tmp/performance_current_active/benchmark -lstdc++fs
./tmp/performance_current_active/benchmark 7000 tmp/performance_current_active/final7000.bin
cmp tmp/performance_current_base/final7000.bin tmp/performance_current_active/final7000.bin
```

The coupled lake-at-rest, exchange conservation, remapping conservation,
plume positivity, and uniform-channel tests also passed after the change.
A contemporaneous recycling test incorrectly required complete reservoir
exhaustion despite permitting positive carry-over; its remaining inventory
was not caused by this traversal change. The coupling review replaced that
criterion with inventory conservation.

## Further opportunities and limits

A prototype cached velocity magnitudes and diffusivities once per cell to
avoid repeated face calculations. Its final states were also byte-identical,
but it was not adopted. Sequential runs pinned to logical CPU 95 measured
the floodplain-rate phase at 8.752287 s without that cache and 9.522603 s
with it. For sparse inundation, writing properties throughout the bounding
rectangle outweighed the saved evaluations. An earlier unpinned comparison
gave a misleading apparent speedup while the unchanged channel phase also
became much faster; the paired measurement identified that confound.

Separate configurations can execute concurrently because their state and
output directories are independent. This can reduce ensemble wall time
without changing the numerical problem. A per-run flux loop cannot simply
be parallelized: adjacent faces update shared cells and channel sections,
so careless parallel accumulation introduces data races and changes sums.

Further low-risk candidates include reusing `Q^2.5` within each channel
substep and skipping the exponential settling evaluation for exactly zero
settling speed or suspended mass. These have not been credited with a
measured gain. Changes to HLL work, face-property storage, or parallel
accumulation require a separate benchmark and comparison of complete states.
Coarsening space or time, shortening floods, and omitting late floods are
not computational optimizations of the same simulation.
