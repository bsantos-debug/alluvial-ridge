# Report requirements and comparison record

The report is built with `bash report/build.sh`. Its source is
`report/main.tex`; its compiled artifact is `report/report.pdf`. This command
only compiles the current record and available independently generated plots.
It does not imply that missing simulations have been run. TeX formats, font
caches, temporary files, and logs are redirected to `report/build/` under the
project's `/data/data0` location.

`report/make_inputs.py` renders the current `docs/panels.csv` and
`config/runs.csv`, requiring exactly 13 panels and 31 configurations. The
ledger is the authority for panel status and exact data/plot commands. The
report generator does not promote a panel because a PDF exists. The generator
reads no published simulation values. It includes only the existing kernel
validation log and labels the scope of those checks.

## Report integration contract

The report conditionally includes these independently generated artifacts:

- `figures/figure1.pdf`: all six deposit panels, 1A–F.
- `figures/figure2.pdf`: all four cross sections, 2A–D.
- `figures/figure3.pdf`: all three diagnostics, 3A–C.
- `report/generated/implementation.tex`: actual numerical implementation,
  constitutive laws, boundary and initial conditions, numerical controls,
  migration parameters, and explicit undocumented assumptions.
- `report/generated/validation.tex`: coupled verification and resolution
  sensitivity with commands and numerical errors/budgets.
- `report/generated/results.tex`: numerical comparisons and discrepancies.
- `report/generated/rebuild.tex`: complete clean-rebuild command, execution
  outcome, artifact/runtime inventory, commit/provenance, publication links.

Only status, panels, configuration matrix, and kernel-log inputs are generated
by `make_inputs.py`; it leaves the other named inputs untouched. Missing
inputs are visibly marked pending. Final results text should replace pending
assumption wording if written methods resolve an ambiguity. A compiled PDF
containing placeholders is an interim artifact, not the requested final result.

## Source inspection

The complete local text of Nicholas et al. (2018), GSA DR1 and DR2 was read.
The embedded figure page (journal p. 641, PDF page 4 including the repository
cover page) was rendered and inspected visually. The preview is an ignored
local build artifact; it is neither included in the report nor consumed by a
plotting command. No curves, pixels, coordinates, or published result columns
were digitized into a numerical plotting input. No supplementary figures occur
in the supplied nine-page supplement.

Manuscript captions provide exact panel assignment and graphical scales;
main-text Results provide qualitative comparison targets; DR1 defines domain,
hydrograph bounds, coupling order, diagnostic sampling, and input parameters;
DR2 configuration columns give the run matrix. The DR2 result columns are not
read by the report generator or used as plotted reconstructed results.

## Panel requirements

All listed cases use E=1 and the default grain fractions unless stated. A is
in m/flood. A saved snapshot must record whether it precedes or follows the
end-of-flood migration/aggradation, which the figure captions do not resolve.
Exact data and plot commands belong in `docs/panels.csv`, and remain pending
until the running implementation and plotting workflow supply them.

| Panel | Required saved numerical content | Scientific comparison target | Source |
|---|---|---|---|
| 1A | Individual flood 61 deposit thickness and active channel mask; A=0, C=0.003 | Early bend-apex splays, still narrow channel belt; extent, thickness and volume | Fig. 1 caption; Results first three paragraphs |
| 1B | Individual flood 251 deposits and active mask; A=0, C=0.003 | Increased meander amplitude, cutoff remnants and widening belt | Same |
| 1C | Individual flood 501 deposits and active mask; A=0, C=0.003 | More localized deposition and abandoned-channel infilling; measure spread and deposit area | Same |
| 1D | Individual flood 562 deposits and active mask; A=0, C=0.003 | Event variability permits renewed conveyance at late time; direct comparison to 1C | Same |
| 1E | Flood 562 deposits, active mask and exact connectivity interface; A=0.036, C=0.003 | Greater inundation under high bed aggradation; show the interface used by alpha, not a decorative outline | Fig. 1E and its caption; DR1 alpha definition |
| 1F | Flood 562 deposits and active mask; A=0, C=0.0003 | Lower load retains broader inundation and shallower channels relative to 1D | Fig. 1F; Results third paragraph |
| 2A | Elevation and active channel at y=36 km after 50,225,400,580 floods; A=0.036,C=0.01 | Growing ridge, high near-channel deposition; late ridge plotted around 40–45 m (coarse visual range) | Fig. 2 caption and visual inspection; Results ridge paragraph |
| 2B | Same section and floods; A=0.036,C=0.0003 | Lower ridge than 2A; late ridge around 25–30 m (coarse visual range) | Same |
| 2C | Same section and floods; A=0,C=0.0003 | Limited relief growth at fixed bed; late ridge around 15–17 m (coarse visual range) | Same |
| 2D | Same section and floods; A=0.018,C=0.003 | Intermediate bed rise with strong ridge; late ridge around 30–33 m (coarse visual range) | Same |
| 3A | Per-flood ridge/distal/depth diagnostics for floods 561–580 of all 31 runs | Beta increases with A, generally decreases as C rises at shared A; fine load lowers beta; erodibility effects small | Fig. 3A caption; DR1 final paragraph; Results beta paragraphs |
| 3B | Alpha and both its numerator and denominator sampled on day 12, floods 1–580; runs 7,15,20 | Higher load raises late-time variability and peaks; publication shows order 0.1–10 m over all events | Fig. 3B caption and visual inspection; DR1 alpha definition |
| 3C | Alpha at day 12 for floods 381–580 of all 31 runs | Highest alpha95 at high C and low A; report ordering and ranges | Fig. 3C caption; Results final paragraph; DR1 |

Deposit maps must show **individual-flood deposition** (m), not net
topographic change after migration, not cumulative bed elevation, and not a
borrowed image. The published scale is 0–0.5 m; values below 1e-6 m are green
and active cells black. Independent plotting may use another accessible
palette but must give the same physical quantity, units and visibility of
small deposits. If saturation at 0.5 m is used for visual comparability, label
values above the scale and preserve them in saved data and mass diagnostics.

Sections span the 48 km transverse domain, with channel interruptions and
the four required times. The published initial plane at mid-domain appears
near 9 m, but absolute datum is unspecified. Compare relief relative to the
initial plane or explicitly document a datum shift; do not tune the physics
to match that vertical offset. Broad ridge envelopes are concave in section.
Exact pointwise channel locations are not identifiable without the original
undocumented initial migration perturbation, so statistical width, depth,
sinuosity, and spatial distribution are more defensible than pixel error.

The publication states that decreasing E to 0.5 raises beta about 15%,
whereas E=1.5 lowers it about 6.5%. Only one fine-load case has beta above 1.
These prose targets may be tested as outcomes and must not become constraints
or calibration coefficients. Beta=1 is an interpreted topographic threshold;
the model does not predict avulsion occurrence. Alpha and alpha95 have units
of meters and are not probabilities.

## Missing definitions that affect agreement

1. Units of S and C in S=C Q^1.5; a mass-concentration unit convention may
   change all sediment supply by orders of magnitude.
2. Hydrograph shape and peak time, drag, representative grain sizes,
   settling/deposition laws, sediment and momentum diffusion, density and
   porosity. Identify all final choices and written supporting sources.
3. Channel cross-section spacing, interpolation weights, CFL, dry threshold,
   external boundaries, initial discharge and stage, flood restart/drainage.
4. Howard–Knutson dimensional scale, nonlinear curvature law and upstream
   influence, initial perturbation, cutoff criterion, endpoint handling and
   centerline resampling.
5. Eroded-bank sediment timing, fraction allocation and concentration return;
   abandoned-channel/point-bar elevation and water/sediment remapping.
6. Ridge and distal regions; whether the mean of beta ratios or the ratio of
   means is used over the final 20 floods; mean channel depth weighting.
7. Whether mean floodplain depth includes dry cells; exact interface geometry,
   length weighting, wet criterion, and alpha handling when wetted interface
   fraction is zero; percentile algorithm and any missing floods.
8. Deposit/section snapshot timing relative to deposition, migration,
   cutoff, and prescribed bed rise.

## Required completion evidence

- Full coupled source with the documented 1-D/2-D exchange, three sediment
  fractions, migration/cutoffs, erosion return and prescribed bed evolution.
- Conservation and positivity checks, analytical transport/settling, zero
  forcing cases, cutoff/remapping budgets and representative grid/time checks.
- Saved runs for all 31 configurations through 580 floods at the specified
  250 m resolution and 20-day hydrographs, with commands, input values,
  implementation identity and measured runtime. Incomplete calculations must
  not be extrapolated into missing floods.
- All 13 panel plotting attempts, saved plotted data provenance and concrete
  per-panel status; every failed attempt is retained and explained.
- Quantitative comparison from generated output, with scales, timing and
  spatial patterns and limitations caused by unresolved specification.
- A successful clean rebuild that runs the model, figures and report; a report
  compilation alone does not satisfy this gate.
- New authenticated-account GitHub repository containing code, parameters,
  scripts, generated data, LaTeX and PDF; verified remote PDF and repository
  links. The report itself does not perform external publication.

## Current report verification

2026-10-09: Initial report compiles as a 12-page work-in-progress PDF with all
13 panels explicitly listed and all model figures marked pending. The source
contains the physical specification, diagnostic definitions, prose/visual
comparison targets and honest limitations. This is report scaffolding only;
it is not evidence of a reproduced numerical panel or a complete model.

## Report status during a clean rebuild

`report/make_inputs.py` merges the maintained `docs/panels.csv` with the freshly
generated `figures/panel_status.csv` without modifying either source. A panel
with no requested data is not reproduced; partial data give partially reproduced.
Complete requested data also give partially reproduced until a scientific
assessment is documented. Thus a successful new calculation cannot inherit
stale "outputs pending" as its current status, and figure-file existence alone
cannot promote a panel to reproduced.

An authored reproduced/partial assessment is retained only when the required
current coverage is appropriate and the recorded numerical source files exist
with hashes matching `figures/plot_manifest.json`. A prior complete assessment
is withheld if current data are partial, missing or changed. Assessment prose
may be supplied in `scientific_assessment` or `assessment`; substantive `notes`
on an assessed source-ledger row are also accepted. Empty or explicitly pending
assessment text does not establish scientific reproduction.

The generated appendix includes current coverage notes, source paths and hash
verification, together with explicitly labeled prior source-ledger status and
notes. Existing data/plot commands, documentation and command formatting are
preserved. The report counts reflect the merged statuses, while source-ledger
notes remain visibly prior documentation rather than overriding current data.

## Metadata and physical-closure corrections

2026-10-09: Root `report/main.tex` now states the saved flood-n convention
explicitly: diagnostics and rasters precede that flood's migration and
aggradation, hence the imposed bed rise is `(n-1)A`; restart checkpoints follow
the nth update. The report states the initial plane and its 3.5875 m elevation
at x=36.125 km, the final-20 mean of per-flood beta ratios, the finite 200-value
alpha percentile, and the actual plot colors, symbols, and interface geometry.

The sediment review identified an inaccurate statement that the channel uses
the same sediment source balance as the floodplain. It now explicitly states
zero net channel suspended-bed exchange, with prescribed bed changes retained
as independent signed forcing. Omitted secondary-flow/dispersive terms and
the absence of evolving bed composition are also stated. Total-solid accounting
does not establish grain-class conservation through deposition and bank erosion.

The report retains pending morphology, production-conservation, and sensitivity
assessment, and explains that day-12 scalar diagnostics have no accompanying
rasters. No new numerical results or reproduction claims were added. These
root report changes do not alter the immutable staged rebuild or live outputs.

Verification: `bash report/build.sh` completed two pdfLaTeX passes, producing
a 19-page, 324261-byte PDF with no LaTeX warnings, undefined references, or
overfull/underfull boxes. `git diff --check` passed. Extracted PDF text confirms
the corrected equation and all three figure captions. The compiled PDF SHA256
is `8ddefd3e990c4616516868b5d222b51e44ddd5ecd877ca96f2146f14a36728d8`.
This is a report build, not completion of the full numerical rebuild.
The coordinator interrupted numerical rebuild 001 at 19:14:19 UTC; its reason
is recorded separately in that attempt's `interruption_reason.json`.

## Numerical validation report generator

`report/make_validation.py` now reads saved histories and the sensitivity
comparison record, then writes `report/generated/validation.tex` and
`validation/report_summary.json`. The clean rebuild calls it in strict mode
before compiling the PDF. Pending histories or unverified sensitivity cases
produce an explicit report and exit code 2. Exit zero without strict mode means
only that the reporting operation completed.

The generated text includes numerical diagnostic changes and mean/maximum field
differences for verified baseline/case pairs, separating grid/time resolution
from physical-assumption changes. Case artifact hashes and recorded values are
checked; evidence from a different production executable is withheld. Missing
baseline evidence leaves contrast calculations pending.

For all 31 production cases, the JSON retains coverage, parameter checks,
normalization, and maximum absolute/terminal signed budget residuals. The PDF
prints available pre-remap and optional post-remap residuals in native units
and normalized by prescribed cumulative upstream input through each flood.
External sediment supply uses the recorded concentration conversion and
20,000-interval Simpson quadrature of the prescribed hydrograph. This scale
excludes recycled banks and imposed bed forcing; it is not net boundary flux.
Residual rows are not summed. Resumed runs are flagged because their residual
baselines reset, so full-history drift cannot be recovered from these rows.
The optional local remap table includes water, three suspended fractions, and
combined solids; missing or nonfinite entries remain pending.

Checks used existing independently generated files, without new simulations:
the interrupted 001 suite remains 0/31 complete; its binary mismatch rejects
the older full-domain coarse500 sensitivity case; the same historical case
retains its actual budget when no production comparison is claimed; and the
real two-flood small-domain restart output exercises pre/post/local remap
tables while remaining noncanonical. Isolated artifacts are under
`tmp/validation-report-check/`; none replaced root validation inputs. Actual
terminal CSV values were checked against the rendered JSON. A verified full
baseline/refinement pair is not yet available, so scientific convergence
interpretation remains pending. Shell and embedded-Python syntax and
`git diff --check` pass; the isolated validation document compiles twice with
no warnings.

The root report also now describes the new `peak_` snapshot and
`remap_budget.csv` outputs. With the coordinator's updated remap methods prose,
it compiles to 20 pages (327635 bytes), without warnings. Its SHA256 is
`81228cc8c66aec0752d93044200a9fb2b039aac99b8b49c642eb68b22327d81b`.
