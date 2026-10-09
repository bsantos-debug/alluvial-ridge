# Scientific audit of the live reconstruction

Reviewed 2026-10-09 against the written 2018 Methods and DR1, and Nicholas et al.
(2013), §2.1–2.2 and §3.1. The audit baseline is the frozen source in
`tmp/full-rebuild-001/workspace/data/_inputs/src/`; `model.hpp` has
SHA256 `69e57a6820c2a2d148b823972898e0137b9d08683d67a495658819e82d4d320a`.
The five root source files matched that baseline at the initial review.
This review used methods text and implementation source, not original simulation
outputs or digitized figures. It did not repeat the passing numerical checks.

Dimensional conversions and the global ledger signs are consistent. A subsequent
geometry stress diagnostic demonstrates an invalid remap withdrawal, discussed
below. One report statement also differed from the code, and several physical
omissions require explicit limits on attribution. A corrected remapper requires
fresh frozen provenance and validation; old outputs cannot be relabeled as
results of the correction.

## Demonstrated remap defect and candidate correction

The original remapper subtracts the full-area inventories of abandoned raster
ghost cells from physical 1-D storage. Interpolation defines their state but does
not make their summed areas equal the 1-D control areas. The independent
[geometry diagnostic](../validation/stress/footprint.cpp) records, for its
250 m neck case, an old donor area of 107303.005689 m² and an abandoned
interpolation-weighted support of 145371.759191 m². A class pulse of 1 kg/m²
at that donor therefore demands 38068.753502 kg more than exists. The real
remapper throws. Total raster area is smaller than total channel area in this
case, so a global area check cannot exclude the local defect. These are
independent implementation stress results, not an observed failure of a
published river or a claim that this exact state occurred in the live suite.

The proposed correction is a conservative numerical projection. Write old
node inventory as $U_j=V_jq_j$, and let $w_{rj}$ be its nonnegative interpolation
weight at old raster cell $r$, with area $A_r$. Define

$$
S_j=\sum_{r\in\mathrm{old\ channel}} A_rw_{rj},\qquad
f_{rj}=A_rw_{rj}/S_j.
$$

For $S_j>0$, these fractions partition the donor inventory. An abandoned cell
receives $E_r=\sum_jf_{rj}U_j$ and its state must be **replaced** by $E_r/A_r$;
leaving its old interpolated ghost state would retain the error. Each donor's
retained fraction passes through the nonnegative normalized-arc-length overlap
map to the new channel. A donor with zero raster support is retained entirely.
Newly swallowed floodplain inventories enter nearby new nodes through their new
map weights, whose sum is one. No global component rescaling is needed.

This is a positive, conservative mapping for water and each suspended class.
Applying identical geometric weights preserves a uniform concentration
$M_{j,k}=c_kW_j$ and bounds mixed concentrations by donor values. It generally
does **not** preserve uniform depth or free-surface elevation: the hybrid 1-D
and raster areas differ. That stage perturbation is a numerical geometry error,
not a recovered physical redistribution law. DR1 specifies membership conversion
and eroded bed elevation, but does not prescribe this inventory projection.

Compute bounded fractions before multiplying inventories. Calculate retention
from retained support rather than subtracting nearly equal component masses;
handle zero support explicitly and make the final normalized overlap edge exactly
one. Nonnegative fractions avoid substantive clipping. Remaining floating-point
sum errors should be measured against the transferred inventory and reported in
the budget; the 35.5% overdraw above is not roundoff.

Momentum needs a basis convention in addition to common weights. Abandoned
streamwise momentum rotates into the old local tangent; swallowed floodplain
momentum projects onto a stated new tangent. Projection onto recipient-node
tangents matches the current lateral-exchange convention. This conserves the
chosen scalar transfers, not global Cartesian momentum across a changed curved
centerline; unresolved normal forces accompany the geometric constraint.
The old ratio of global target to original signed momentum is especially
ill-conditioned when positive and negative streamwise momenta cancel.

The candidate is preferable to global area normalization or class-by-class
clipping, which do not resolve the donor geometry. A common physical geometry
with partial floodplain cells and polygon-overlap transfers would better address
uniform-stage preservation, but requires a substantially different discretization.
Acceptance of the candidate requires new cutoff/localized-plume conservation,
positivity, constant-concentration, and zero-support checks; this analytical
review does not claim the candidate has already passed them.

## Definite documentation error: channel sediment sources

The initial report said the channel integrates the same
balances as the floodplain, whose sediment equation contains a deposition sink.
However, [channel_advance](../src/model.hpp#L298) has advection, diffusion, inlet
supply, and lateral exchange, but no settling or entrainment source. Deposition
is applied only to floodplain cells in
[floodplain_advance](../src/model.hpp#L339).
The report agent subsequently corrected the root report and explicitly documented
the omissions below; the initial frozen report source remains its original record.

State explicitly that **channel suspension has zero net exchange with the
prescribed channel bed**. DR1, the paragraph beginning “Bed elevations in the
channel,” excludes bedload-based bed evolution; it does not determine the net
exchange between suspension and that bed. Nicholas (2013), §2.1, equations
22–24, includes both deposition and erosion in the sediment balance. Thus the
zero-net-exchange choice is an unresolved physical closure, not a recovered
consequence of prescribing bed elevation. Its effect is to carry sediment along
the channel until lateral or downstream export without a net channel-bed sink.
Adding settling alone would introduce another unsupported choice; an associated
entrainment or capacity closure would also need justification.

## Physical omissions and underdetermined assumptions

**Secondary-flow stresses are absent.** Nicholas (2013), §2.1, equations 2a–b
and 7–12, includes an additional momentum source
$F_{Si}=\partial_j(hT_{ij})$ determined from transported spiral intensity.
This differs from the Boussinesq turbulent stress in equations 3–4. The code
implements the latter in [floodplain_rates](../src/model.hpp#L270) and its
streamwise counterpart, but has no spiral-intensity state or $F_S$ term.
DR1 specifies a 1-D channel and tangent-aligned velocities, so this omission is
compatible with that channel simplification; its treatment on the 2-D floodplain
is unspecified. Document it separately from turbulent viscosity. A statement
that every 2013 momentum term is inherited would be incorrect. Whether the
omission materially changes bend exits and overbank flow remains unquantified.

**Eroded grain identity is not conserved through the bed.** Nicholas (2013),
§2.1, paragraph 13 and equations 14, 22, 24, and 27, stores and uses evolving
bed composition. DR1 returns bank-eroded sediment at the inlet but does not
specify grain allocation. Here [remap_after_flood](../src/model.hpp#L402) assigns
each eroded mass the fixed inlet fractions, regardless of previous selective
deposition. For example, a hypothetical kilogram of pure silt deposit eroded in
a default-load run is returned as 0.05 kg sand, 0.75 kg silt, and 0.20 kg clay.
Total mineral mass closes, but separate bed-plus-suspension class inventories
do not. This declared approximation can alter later sediment sorting and the
contrast between default and fine-load cases. The global solid budget does not
validate conservation of individual grain classes through deposition and erosion.

**Deposition thresholds and grain closures remain consequential assumptions.**
The 2013 Krone law is equation 23; its baseline silt speed is in §3.1,
paragraph 26. The written methods do not establish the adopted 0.1 Pa threshold,
2 micrometre unflocculated clay, 0.2 mm suspended sand, shear-independent sand
settling, or Schmidt number one. With the chosen floodplain Chezy coefficient
10, cohesive deposition stops above
$|u|=10\sqrt{0.1/(1000g)}=0.03193$ m/s. At zero shear and 1 m depth, the
assumed settling times are approximately 43 s, 1.39 h, and 3.22 days for sand,
silt, and clay. These are calculations from the reconstruction parameters, not
published results. They explain why settling and stress assumptions can affect
all deposit and ridge panels. Zero vertical floodplain erosion is also a
closure: 2013 §2.1, paragraph 19 allows reactivation above an unspecified critical
velocity. The current sensitivity cases assess concentration and critical stress;
they do not bound these other physical uncertainties or the dimensional migration
coefficient and inlet/outlet assumptions documented elsewhere.

## Units, bed forcing, and remapping

The 2018 Methods and DR1 define $S=CQ^{1.5}$ as concentration. Under the explicit
mg/L convention, [the inlet](../src/model.hpp#L320) correctly supplies
$10^{-3}CQ^{2.5}$ kg/s, divided by channel width for a unit-width face flux.
Porous bed conversion uses $\rho_s(1-p)$ once. The 2013 inlet concentration unit
supports the convention, but does not establish the unreported 2018 unit.

The global ledger correctly distinguishes recycled sediment from external
supply. Let $I$ contain suspension, the bank reservoir, and bed mass relative to
the reference raster. If $F$ is recorded net boundary sediment input, $R$ is
reservoir release already included in $F$, and $B$ is prescribed bed forcing,
then $\Delta I=F-R+B$, apart from recorded numerical corrections. The residual
in [main.cpp](../src/main.cpp#L83) has these signs. Erosion transfers bed mass to
the reservoir; deposition transfers suspension to the bed. Changes imposed by
channel slope, mask conversion requiring fill, and aggradation enter $B$.
A small residual establishes this ledger, not physical realism of its prescribed
sources or fixed grain composition.

DR1's migration-before-aggradation ordering is respected. Normalized-arc-length
redistribution and the raster versus rectangular control-area difference remain
explicit remapping assumptions. Snapshots and summary budgets precede each
flood's migration/aggradation; checkpoints follow it. Therefore the last summary
does not independently audit the final post-flood remap. Comparisons between a
snapshot and checkpoint must retain that phase distinction.

## Written sources

- [Nicholas et al. (2018), Methods, p. 639](https://doi.org/10.1130/G40104.1).
- [GSA Data Repository 2018219, DR1](https://doi.org/10.1130/2018219): coupling,
  migration/mask conversion, prescribed channel bed, and grain fractions.
- [Nicholas et al. (2013)](https://doi.org/10.1002/jgrf.20132): §2.1 equations
  2–12 and 22–27; paragraphs 13 and 19; §3.1 paragraph 26.
