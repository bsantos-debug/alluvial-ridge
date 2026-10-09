# Coupled implementation, in development

All project artifacts, including temporary files, reside under
`/data/data0/dominik-scratch/Shared/brnisant/alluvial-ridge`. The `/data/data0`
volume had approximately 1.9 TB free when selected. Its volume root was not
writable by the current account; the shared scratch location was writable.
`source scripts/environment.sh` directs temporary files and Python plotting
caches here. The report build also redirects TeX caches here.

The numerical state is water depth, two depth-integrated momenta, and three
suspended masses per horizontal area. All internal concentrations are kg/m3.
The geometry uses a Cartesian floodplain (x downstream, y across valley), a
centreline sampled near 250 m spacing, and rectangular 500 m wide channel
control volumes. Sections at the two endpoints have half control volumes.
A nearest-segment projection identifies channel raster cells within 250 m
of the centreline and linearly interpolates the two enclosing section states.
These cells are excluded from the 2-D storage. Their interpolated momenta
are rotated into the local tangent direction before solving bank-face fluxes.

Shallow-water face fluxes use first-order HLL and hydrostatic reconstruction.
Sediment advection uses that same signed water flux and upwind concentration.
Diffusion uses the common reconstructed wet aperture, face-averaged diffusivity,
and concentration gradient. Chezy friction has an exact fixed-depth local
update. The full 2-D symmetric turbulent stress tensor uses centered velocity
gradients. Diffusivity equals 0.07 u_* h (Schmidt number one assumption).
Sand settles at the Ferguson–Church speed for 0.2 mm particles; silt uses
0.2 mm/s inherited from the 2013 paper; clay uses Stokes settling for 2 um
unflocculated spheres. Cohesive deposition is reduced by the Krone factor
with assumed critical stress 0.1 Pa. Sand deposition has no shear reduction.
Vertical floodplain entrainment is zero, an explicit closure choice because
the earlier sand-capacity-based entrainment closure is not specified for the
2018 prescribed-bed, three-fraction model.

Floodplain rates are held fixed over a macro step constrained by local wave
speeds, positive inventories, and a maximum of 120 s. The channel advances with
its own smaller CFL steps and receives the fixed lateral rates in every
substep. This is first-order multirate explicit coupling; time-step sensitivity
must be evaluated. Water and suspended mass transferred over each bank face
are subtracted from one representation and added to the other with identical
integrated flux. Incoming mass uses the linear interpolation weights. Outgoing
water and each sediment class use the contributions of the two channel nodes
to the interpolated donor inventory; an empty donor cannot lose material. Channel momentum exchange
contains advective streamwise momentum. Hydrostatic side pressure is omitted
from the channel's streamwise equation because the physical side bank is
normal to that direction; stair-step raster normals do not define its true
streamwise pressure force. Channel curvature-induced transverse momentum is
unresolved by the prescribed 1-D approximation.

Initial floodplain elevation is S0(L-x), choosing zero downstream datum.
The initial channel bed is S0 L (1-s/Lc)-8 m. Floodplain cells are dry; the
channel starts at the minimum-discharge Chezy normal depth and zero suspended
concentration. There is no hydraulic spinup or reset between floods. The
unspecified hydrograph is assumed to be Qmin+(Qmax-Qmin)sin²(pi t/T), T=20 d.
Channel boundary conditions are explicit reconstruction assumptions because
the written description does not specify them. At the wet subcritical inlet,
water discharge is imposed exactly, and the outgoing shallow-water invariant
$R_-=u_i-2\sqrt{gh_i}$ determines the boundary depth through

$$
\frac{Q}{Bh_b}-2\sqrt{gh_b}=R_-.
$$

The left side strictly decreases with positive depth, so a bracketed scalar
solve determines a unique depth without a prescribed minimum head. Momentum
enters through $Q^2/(B^2h_b)+gh_b^2/2$. At the subcritical downstream endpoint,
the outgoing invariant $R_+=u_i+2\sqrt{gh_i}$ is matched to an assumed Chezy
normal-flow rating $u_b=C_h\sqrt{S_ch_b}$, where $S_c=S_0L/L_c$. Therefore

$$
\sqrt{h_b}=\frac{R_+}{C_h\sqrt{S_c}+2\sqrt g}.
$$

Physical water, momentum, and passive-sediment fluxes are evaluated at this
boundary state. The endpoint sections lie on the domain boundary and retain
half control volumes; no full-spacing ghost-bed continuation is applied.
The outlet condition supplies the incoming subcritical characteristic rather
than extrapolating an unconstrained endpoint state. It permits subcritical
interior backflow while requiring nonnegative discharge in the normal rating.
A dry outlet has zero flux, and supercritical outward flow uses its interior
physical flux because both characteristics leave the domain. Incoming
supercritical flow at the downstream boundary is rejected with an explicit
message: an external hydraulic state would be required. Similarly, a dry inlet
with positive imposed discharge, or a non-subcritical inlet, requires an
additional upstream depth condition and is reported instead of assigning one.
The initialized production channel is wet and subcritical. Zero-discharge
inflow and zero-slope outflow preserve the still-lake limiting case.

Floodplain lateral boundaries and its upstream boundary are reflecting;
downstream is transmissive with continued valley slope. Boundary orientation
is tested at both ends of both coordinate axes.

After each flood, migrate the centreline, identify cutoffs, update masks, cut
new channel cells to the prescribed pre-aggradation bed, and put eroded dry
mineral mass in an inlet reservoir with the chosen load fractions. Then raise
all channel sections by A. The inlet reservoir is released during subsequent
floods with a Q^1.5 concentration shape. The intended release is normalized by
numerical quadrature; available inventory bounds each substep release and any
remaining mass is carried into the next flood. Released mass is recorded
separately from the prescribed external rating supply.

Water and suspension from abandoned channel raster cells are transferred out
of the 1-D storage. The old method subtracted full interpolated raster-cell
inventories and globally rescaled each remaining component. A 250 m neck-cutoff
test demonstrated a negative class target of -38,068.75 kg, despite positive
water storage. Smooth Gaussian tracers also failed. The raster support can
exceed the exact rectangular area of an individual channel section, so this
method was rejected before completing the first production flood.

The corrected remap partitions each old section's inventory using normalized
geometrical weights. Let $V_j$ be its exact control area, $q_j$ its conserved
state, $a_r$ a raster-cell area, and $w_{rj}$ its linear interpolation weight.
For $S_j=\sum_{r\in\mathrm{old\ mask}}a_rw_{rj}>0$, an abandoned cell receives
$\sum_j (a_rw_{rj}/S_j)V_jq_j$. This replaces its previous ghost state.
The section retains the fraction of $S_j$ lying in cells still mapped to the
new channel; a section with no raster support retains all its inventory.
Each remaining donor is conservatively resampled by overlap in normalized
arc length. Newly captured floodplain-cell inventories enter adjacent new
sections with their new interpolation weights. All water and sediment classes
use the same nonnegative weights. This preserves class masses and constant
concentrations without component-dependent global scaling. It cannot also
preserve local water depth when raster and exact channel areas disagree.

Abandoned-cell momentum rotates from streamwise to the old segment tangent;
captured-cell momentum projects onto the new segment tangent. The retained
streamwise momentum follows the remapped channel. Global Cartesian momentum
is not conserved through an imposed geometry change: unresolved bank forces
and the loss of transverse momentum are explicit assumptions. Normalized
arc-length redistribution may leave shallow or dry channel sections after
a cutoff. The flow solver, rather than a depth floor, must resolve them.
Abandoned cells retain the former excavated bed, allowing cutoff-channel filling.
The prescribed bed geometry may require signed bed mass sources, which are
recorded separately. Bed inventory is evaluated on the topographic raster;
its channel footprint differs slightly from exact W times centreline length.
Water storage always uses the latter for the 1-D channel, never both.

`remap_budget.csv` records water and each suspended class before and after
every remap, the bank-plus-bed-plus-suspension residual after subtracting
prescribed bed forcing, and post-remap cumulative residuals. Cumulative
residuals restart from the beginning of each executable invocation; they
must not be summed across rows or interpreted as a full-history residual
after checkpoint resume. The per-remap residual is independent of that window.
At each requested snapshot flood, `peak_fields_NNNN.bin` and
`peak_channel_NNNN.csv` additionally save the day-12 diagnostic state.
Unprefixed snapshots remain at the end of the flood, before its migration
and aggradation. Both have `(n-1)A` prescribed channel aggradation at flood n.

For the diagnostic alpha, mean floodplain depth includes dry cells. The wet
interface is the fraction of immediate channel/FP grid faces whose floodplain
has >1 mm water and whose channel stage exceeds the bank by >1 mm. This is a
diagnostic threshold only. Zero wet fraction gives undefined alpha, not zero.
Ridge height is the maximum longitudinal-mean floodplain relief across valley,
minus the mean in the outermost 10% lateral bands; only the central 80% of the
reach enters that profile. Channel depth is mean bank-face elevation minus
adjacent interpolated channel bed. These averaging choices are not specified
in the publication and require comparison/sensitivity reporting. Slope is
removed before measuring relief; absolute datum does not enter beta.

No numerical manuscript result has yet been validated. Component tests and
small coupled experiments are developmental evidence only. Full-resolution
production outputs, sensitivity tests and figure assessments remain required.


## Coupled verification

`tests/coupled.cpp` directly exercises the production model API. It checks
characteristic boundary invariants and the stated boundary-regime branches,
a closed coupled lake, hydraulic and sediment exchange, conservative transfer
of an isolated sediment plume over 150 multirate macro steps, and channel
remapping with and without imposed aggradation. It also checks the combined
suspension–bank–bed budget and the time convergence of recycled inlet supply.
These tests use a 4 km square domain so failures can be inspected before long
production runs.

For constant normal flow at 2500 m$^3$ s$^{-1}$, the maximum channel-depth
relative error after 1000 s is 0.001790 at 250 m channel spacing and 0.000843
at 125 m spacing, consistent with first-order spatial convergence. This is a
moving-flow consistency check, not exact preservation: hydrostatic HLL
reconstruction exactly balances a lake rather than normal flow. The isolated
plume test closes water and suspended-sediment budgets to $4\times10^{-9}$
m$^3$ and $5\times10^{-11}$ kg, respectively, in the tested build. The
fractional recycled-inlet integration error at 0.4 flood duration decreases
from 0.004915 to 0.002461 when CFL decreases from 0.4 to 0.2 in a short
1000 s stress test. Injected plus remaining bank inventory agrees with its
initial mass to $7\times10^{-9}$ kg; leftover material remains available for
the next flood. These checks do not replace full-resolution budget and
convergence measurements.
