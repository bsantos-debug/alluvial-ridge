# Scientific specification and provenance

## Permitted written sources retrieved 2026-10-09

- Nicholas et al. (2018), Geology 46, 639–642,
  https://doi.org/10.1130/G40104.1. Publisher's version obtained from
  https://pure-oai.bham.ac.uk/ws/portalfiles/portal/53209276/Nicholas_et_al_Hydrodynamic_controls_Geology.pdf.
- GSA Data Repository 2018219, DR1 model description and DR2 configuration
  columns, https://doi.org/10.1130/2018219. PDF obtained through
  https://api.figshare.com/v2/articles/12536768 and
  https://ndownloader.figshare.com/files/23308388.
- Required guidance: https://github.com/bradlipovsky/vdv-damage/blob/main/AGENTS.md
  and https://github.com/bradlipovsky/vdv-damage/blob/main/brad-lipovsky-academic-style-guide.md.

The supplement has model prose and a parameter/results table, but no figures.
The results table is not input to the independent implementation. No original
code or output archive was retrieved. Papers downloaded for reading are local
reference documents, excluded from the repository and all numerical workflows.

## Documented physical and numerical structure

DR1 specifies depth-averaged shallow water equations, an explicit finite volume
approximate Riemann solver, and first order spatial accuracy. Channel sections
are rectangular, constant width, and represented by a 1-D scheme. Floodplain
cells use a 2-D scheme. Channel variables are interpolated onto cells within
half a channel width of the centreline, with velocity rotated into the local
tangent direction. Floodplain/channel interface fluxes update the 1-D water
and sediment masses. Exchange must be conservative in both representations;
channel cells on the 2-D mesh must not duplicate physical storage.

Three suspended fractions obey advection–diffusion and overbank deposition.
After every flood: apply Howard–Knutson migration with neck cutoffs, update
channel membership, erode newly occupied cells to interpolated channel bed,
return the eroded sediment to the river inlet concentration, and raise the
channel bed by prescribed A. Channel bed has constant slope in streamwise
arc length, maintaining the original inlet–outlet elevation drop as sinuosity
changes. Bed elevation is prescribed, not obtained from bedload transport.

## Documented parameters

| Quantity | Value | Source |
|---|---|---|
| Floodplain width, length | 48 km, 72 km | DR1 |
| Floodplain grid spacing | 250 m | DR1 |
| Channel width | 500 m | DR1 |
| Initial depth | 8 m | DR1 |
| Initial downstream slope | 0.1 m/km | DR1 |
| Initial floodplain/channel | planar/straight | DR1 |
| Flood duration | 20 days | manuscript and DR1 |
| Minimum/maximum discharge | 2500/15000 m^3/s | manuscript and DR1 |
| Flood count for comparison | 580 | manuscript and DR1 |
| Inlet concentration | S=C Q^1.5 | manuscript and DR1 |
| Default sand/silt/clay fractions | 0.05/0.75/0.20 | DR1 |
| Fine sand/silt/clay fractions | 0.05/0.20/0.75 | DR1 |
| Relative bank erodibility E | 1; variants 0.5, 1.5 | DR1 |
| A | 0–0.036 m/flood, 31 combinations | DR2 configuration columns |

## Unresolved specification items

These must be resolved from cited written methods where possible and otherwise
reported as assumptions with sensitivity checks. They are not reasons to
substitute a simpler model for the coupled model.

- Hydrograph shape, peak time, concentration units, and C units.
- Flow friction law/parameters, horizontal turbulent viscosity and sediment
  diffusivity, representative grain diameters, settling and deposition laws,
  sediment porosity/density, and any entrainment or deposition thresholds.
- Channel cross-section spacing and channel/floodplain interpolation weights.
- Boundary conditions, initial water/velocity/sediment fields, inter-flood
  drainage or restart rules, CFL value, and wetting/drying tolerance.
- Howard–Knutson nonlinear nominal migration function, upstream memory kernel,
  dimensional migration scale corresponding to E=1, initial perturbation,
  node resampling, cutoff criterion, and abandoned-channel/point-bar elevations.
- Redistribution in space/time/grain class of bank erosion sediment fed at inlet.
- Exact ridge/distal-floodplain and channel-depth averaging used for beta.
- Whether floodplain mean water depth includes dry cells; the channel interface
  is described visually in Figure 1E and may differ from the immediate banks.

## Required diagnostics

Beta is ridge-to-distal elevation difference divided by mean channel depth,
averaged over the last 20 floods. Alpha is floodplain mean water depth at
0.6 times flood duration divided by inundated fraction of channel–floodplain
interface. Alpha95 is the 95th percentile over the final 200 floods. Interface
geometry and zero-inundation handling must be explicitly documented.

## Required verification and completion gates

1. Verify lake at rest over variable topography, wetting/drying positivity,
   channel/floodplain exchange conservation, analytical transport/settling,
   zero sediment/aggradation/migration limits, and cutoff/remapping budgets.
2. Assess grid/time sensitivity on representative coupled cases; quantify
   water and sediment budgets, including external boundary fluxes and bed changes.
3. Run all 31 configurations for 580 floods at documented resolution, recording
   runtime, commands, parameters and implementation version. Preserve outputs
   needed for every panel and metrics; do not manufacture missing late floods.
4. Generate 1A–F, 2A–D, 3A–C from saved numerical output. Classify agreement
   honestly and report failures. No supplementary figures occur in 2018219.
5. Write and compile report with equations, assumptions, validation, panel
   ledger, numerical scales/timing/pattern comparisons and limitations.
6. Run a documented clean rebuild through report compilation. Publish code,
   configuration, plots, generated data, LaTeX and PDF to a new repository in
   the authenticated user's account. Verify remote files and PDF link.

## Implemented reconstruction

`src/finite_volume.hpp` independently implements a first-order HLL shallow-water
face flux with hydrostatic reconstruction and side-specific bed pressure
corrections, following the numerical construction described by Audusse et al.
(2004), https://doi.org/10.1137/S1064827503431090. This is an explicit numerical
choice, not a claim to use the exact Mingham–Causon implementation named in DR1.
It evolves h, hu, hv and three h*c masses. Internal concentration uses kg/m^3.
The inlet assumes the published concentration is in mg/L, with a factor of
0.001 converting it to kg/m^3; the 2018 text does not establish this choice.
The rationale and alternatives are in `docs/sediment-methods.md`.

For each face use z*=max(zL,zR), h*=max(0,h+z-z*), retaining original velocity
and concentration in reconstructed wet states. HLL wave speeds bound u +/-
sqrt(g*h). Each side's momentum receives g*(h^2-h*^2)/2 in the face-normal
component. This preserves constant free-surface zero-velocity solutions over
bed steps. Water and sediment fluxes are identical on both sides.

The coupled driver now includes Chezy resistance, turbulent stress, sediment
advection and diffusion, shear-dependent cohesive deposition, channel exchange,
centerline migration and neck cutoffs, bank sediment recycling, prescribed
channel aggradation, and conservative remapping. The settling substep integrates
the selected well-mixed loss exactly at fixed depth. The recovered 2013 methods
specify channel/floodplain Chezy values of 55/10, viscosity 0.07 u* h, a silt
fall speed of 0.0002 m/s, and a Krone deposition factor. Representative sand
and clay sizes, critical deposition stress, and several other closures remain
explicit assumptions. See `docs/implementation.md`, `docs/sediment-methods.md`,
and `docs/migration.md` for equations, units, provenance, and limitations.

Component and assembled-model checks pass, including closed-lake balance,
coupled mass conservation, positive transport, remapping and recycling budgets,
normal-flow refinement, and restart equivalence. These checks validate the
implemented discretization in their stated limits. They do not establish
agreement with the manuscript or resolve undocumented physical choices.
Full-domain numerical refinement and production runs have separate logs and
completion records; the panel ledger remains authoritative for figure status.
