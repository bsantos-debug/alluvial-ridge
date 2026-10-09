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

## Wet-state flux and velocity evaluation

A second review used the corrected characteristic inlet and normal-rating outlet.
It retained the active rectangle, grid, adaptive timesteps, channel subcycling,
transport equations, sediment closures, and all floods. Two changes were adopted.
First, HLL evaluates the three hydraulic components where the caller subsequently
replaces all three suspended-sediment fluxes with its existing donor-cell advection
and turbulent diffusion. The complete six-component HLL remains the default for
other callers. No retained component depends on the omitted passive components.
Second, the velocity magnitude is evaluated as `sqrt(u*u + v*v)`, with
`u = hu/h` and `v = hv/h`, and an explicit failure on nonfinite squared velocity.
This is the same Euclidean magnitude as `hypot(hu,hv)/h`, with different floating-point
roundoff. The existing small-depth condition is unchanged.

The continuation benchmark restored every original `Model` member from the same
12,219,681-byte state at macrostep 8,000 and time 401,532.86370333412 s. Its input
contained 16,170 physical floodplain cells with positive depth, of which 12,446
exceeded 1 mm. Each comparison advanced exactly 1,000 further macrosteps, through
time approximately 416,423.1419400012 s, with 4,000 additional channel substeps.
Thus these are wet-state performance tests during the first flood, not complete
20-day floods or manuscript-panel simulations. No output from these timing tests
is used as a paper prediction.

The source state SHA-256 is
`4d071f39772fb418a721a783dcecfb2457a6f71d6bf5dbc2366bcbe74b47ec32`.
The portable compiler command used GCC 8.5.0 with
`-O3 -std=c++17 -Wall -Wextra -Wpedantic -lstdc++fs`. No fast-math or native-architecture
flags were used for the adopted combined comparison. Runs were pinned to logical
CPU 46, in baseline/combined/combined/baseline order. CPU time is preferable to
wall time on this shared host; both were recorded, and within-variant variation
remains material. Individual baseline CPU times were 9.7940 and 11.2799 s;
combined times were 8.5135 and 9.1346 s. The mean phase measurements were:

| Phase | Corrected baseline CPU (s) | Combined CPU (s) | Reduction |
|---|---:|---:|---:|
| Floodplain rates | 7.427761 | 6.022816 | 18.91% |
| Channel substeps | 0.192542 | 0.181318 | 5.83% |
| Floodplain advance | 2.883819 | 2.596328 | 9.97% |
| Whole continuation process | 10.536935 | 8.824053 | 16.26% |

Whole-process timing includes writing the final state and small timing overhead.
Mean wall time decreased from 21.199886 to 17.764786 s
(16.20%). These observations do not establish
a hardware-independent speedup or the runtime of the 580-flood ensemble.

Separate trials measured the contribution of each change. HLL alone, with the
same portable flags, reduced mean CPU time from 8.859934 to 8.165229 s
(7.84%). Its two final states were byte-identical to both baseline states,
including physical variables, rates, exchange, gradients, counters, and ledgers.
All had SHA-256
`537ca01ed408c2f7b6ac8d47b4019fb14f2c64ac0dd6ce15be57558e1f35ecfc`.
A comparison of 100,000 randomized hydraulic interfaces also found bitwise identity
between the first three components of full and hydraulic HLL. The HLL prototype
passed the coupled tests. Component, sediment, migration, and coupled tests also
passed with the HLL and zero-settling prototypes together; the latter shortcut was
subsequently rejected on performance grounds.

A separate velocity-magnitude trial on CPU 47 used native flags in both variants
and reduced mean CPU from 8.819014 to 7.665703 s
(13.08%). That experiment is evidence
for the operation, not the portable combined timing. Native flags alone improved
mean CPU by about 1.46% and were not adopted. The separate gains must not be added;
the directly measured combined result above is the relevant comparison.

The adopted combined implementation also passed the full component, sediment,
migration, coupled, and restart checks (`make check`).

The adopted combined state is not byte-identical because the magnitude expression
changes rounding. Both repeats produced the same final state within each variant.
Observed maximum absolute differences, over every stored component, were:

| Quantity | Maximum absolute difference |
|---|---:|
| Channel water depth | 3.55e-15 m |
| Grid water depth, including mapped ghosts | 5.33e-15 m |
| Channel or grid momentum | 3.02e-14 m²/s |
| Suspended class inventory | 4.09e-14 kg/m² |
| Bed elevation | 4.44e-16 m |
| Event deposit thickness | 2.39e-18 m |
| Simulation clock | 5.82e-11 s |

The largest component difference scaled by `max(1, maximum absolute baseline
component)` was 2.74e-15. Both variants finished at macrostep 9,000 and channel
substep 82,727. All physical arrays were finite. Both water and sediment correction
ledgers remained zero. The water-storage difference was 5.96e-8 m³, the beta
difference was 1.22e-19, and the ridge-height difference was 9.76e-19 m.
The water-budget residual differed by 1.49e-7 m³ and the suspended-sediment residual
by 3.88e-7 kg. These are observed roundoff limits for this finite interval, not a
bound on divergence after hundreds of nonlinear floods. The test ends within a
flood and does not exercise migration or the output clock normalization at a
completed-flood boundary.

The archived hashes below identify the exact compared headers. Source files were
copied before compilation and retained with the harness and binary hashes in
`tmp/performance_alternatives/combined_comparison.json`. Earlier hashes in this
review identify their own historical experiments and have not been replaced.

| Snapshot | Header | SHA-256 |
|---|---|---|
| base | `model.hpp` | `ac1a935c8f908ce12eaa7fad347048bcbd9957fc5fb4ed7dc5a385a9ded79b2c` |
| base | `finite_volume.hpp` | `0c5a6cb7b9d7af69a6125cc8c3b721674796fe07f388e3cf5c670dd952108111` |
| hydro | `model.hpp` | `855180ab6796c43cf5e979e63b2b5f2356f1705ff229ff18c89ea423191edbd6` |
| hydro | `finite_volume.hpp` | `b05451791f0f9028db567006f32f99aaabf6fb3500d5051c47d1eee9ce7836d6` |
| combined | `model.hpp` | `69e57a6820c2a2d148b823972898e0137b9d08683d67a495658819e82d4d320a` |
| combined | `finite_volume.hpp` | `57ac8606cd856046e13563fc0f07417943990fbc4f43340baf6f44aad427775d` |

The separate norm-only model header has SHA-256
`a239cd94cf3a7cc2a3601be07403f6a8a148a8056d71f4d99ba1bfe122539bc2`.

The unchanged sediment and migration headers have SHA-256
`3c698eaf05771c09a26a152697fdcdacacf59b08ad18345efcdcaf1e35ccd4d2` and
`047475c7a53b933ccc83273e0576a820f681382fdf22b244a501006c68bf7196`, respectively. The frozen
continuation harness has SHA-256
`7fa3fa77700541cf38f546fbd942bce1ea9c76777f14b98d6a77c332504273c3`.
All original and combined hashes, binary hashes, exact process commands, repeated
phase measurements, individual component differences, and ledgers are retained in
the JSON records. The main source file is not an input to this stepping harness.

Reproduction commands, from the repository root, are:

```sh
g++ -O3 -std=c++17 -Wall -Wextra -Wpedantic tmp/performance_alternatives/base/continuation.cpp -o tmp/performance_alternatives/base/continuation -lstdc++fs
g++ -O3 -std=c++17 -Wall -Wextra -Wpedantic tmp/performance_alternatives/combined/continuation.cpp -o tmp/performance_alternatives/combined/continuation -lstdc++fs
python3 tmp/performance_alternatives/run_combined.py
python3 tmp/performance_alternatives/analyze_combined.py
```

The analyzer reads the native benchmark serialization; it is separate from the
production checkpoint format. Its metrics helper was compiled with the unchanged
baseline metric functions. The experiment directories are development evidence,
not required production inputs.

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

A later per-cell diffusivity cache, tested in the wetter continuation above,
reduced mean CPU by 13.32% and preserved all original model state bytes.
It was not adopted: its benefit overlaps the new velocity calculation, its sparse
behavior was unfavorable, and its additional scratch storage was unnecessary for
the selected patch. No gains from caching are included in the combined result.

Exact-zero settling shortcuts passed 6,561 bitwise operator comparisons, including
signed zeros, extreme finite inputs, and dry states. The coupled runs remained
byte-identical, but the measured benefit was small and inconsistent; those
shortcuts were not adopted. Reusing `Q^2.5` remains an uncredited opportunity.
Parallel accumulation would require its own race and summation-order analysis.
Coarsening space or time, shortening floods, and omitting late floods are not
computational optimizations of the same simulation.
