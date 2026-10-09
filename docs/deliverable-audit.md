# Deliverable readiness audit

Audited 2026-10-09 against the frozen source in
`tmp/full-rebuild-001/workspace` and the main paper's text and embedded
figures. The staged source and running model were not changed. No published
curves or pixels were digitized, and no published numerical result columns
were imported. This is a readiness audit, not an assessment of numerical
agreement. At audit time, preparation and implementation checks had passed
while production and sensitivity stages were running. The coordinator later
stopped rebuild 001 at 19:14:19 UTC; its reason is retained in
`tmp/full-rebuild-001/interruption_reason.json`. No completed numerical
rebuild or report-stage success is claimed here.

## Panel coverage and fidelity

The following mappings are consistent between the publication, configuration
table, plotter, and panel ledger. All 13 main panels are accounted for; the
supplement contains no figures.

| Panels | Independent output requested | Quantity and convention |
|---|---|---|
| 1A, 1B, 1C, 1D | Run 11; floods 61, 251, 501, 562 | Individual-flood deposit thickness, m; not cumulative elevation. |
| 1E | Run 17; flood 562 | Event deposit and active channel–floodplain interface. |
| 1F | Run 03; flood 562 | Event deposit for the lower sediment load. |
| 2A, 2B, 2C, 2D | Runs 22, 10, 03, 15; each at floods 50, 225, 400, 580 | Raw elevation, m, at the saved column x=36.125 km; cyan marks active bed at flood 580. |
| 3A | All 31 runs; floods 561–580 | Arithmetic mean of 20 per-flood beta ratios; dimensionless. |
| 3B | Runs 07, 15, 20; floods 1–580 | Alpha, m, sampled exactly at day 12 of each 20-day flood. |
| 3C | All 31 runs; floods 381–580 | Linearly interpolated 95th percentile of all 200 finite alpha values, m. |

Figure 1 retains the published 0.5 m display limit, green for deposition
below 1e-6 m, and black active channel cells. Values above the color scale
remain in the data and volume calculations. Its different continuous color
map is labeled and does not alter numerical values. Figure 2 preserves the
model datum rather than shifting elevations toward the published curves.
Figure 3 identifies sediment coefficient, load mixture, and erodibility;
undefined alpha remains missing, never zero or an omitted percentile sample.

The magenta dashed line in published Figure 1E follows the immediate banks
of the active black channel through its bends, with several abandoned loops
outside it. It does not trace the outer channel-belt envelope. This is a
visual inference, not proof of the authors' raster-face geometry or wetness
threshold. The independent plot shows the same internal Cartesian faces
counted by its diagnostic, although its line is solid. Because migration
occurs after the hydrograph, end-flood geometry is also the day-12 geometry.
The line denotes the full interface, not its day-12 inundated subset.

## Findings that remain after successful simulations

1. **Scientific assessment remains necessary for every panel.**
   `scripts/compare.py:304–376` explicitly leaves splay morphology, abandoned
   channel infilling, ridge width/concavity, and localized breaches untested.
   Its area, volume, relief, trend-sign, and variability calculations are
   useful but do not establish those spatial claims. Compare the generated
   maps and profiles directly with the permitted embedded publication
   figures, describe agreement and disagreement for 1A–F and 2A–D, and assess
   the three diagnostic panels. Record an authored assessment for each row
   of `docs/panels.csv`. `report/make_inputs.py:88–105` correctly keeps all
   complete but unassessed panels partial; strict plot/comparison success
   must not be reported as 13 scientifically reproduced panels.

2. **Peak inundation maps cannot be reconstructed from the saved products.**
   `src/main.cpp:65,87–90` saves day-12 mean floodplain depth and inundated
   interface fraction, but raster snapshots occur only at flood end. Thus
   peak inundated area and the location of day-12 breach flow are absent.
   Event deposit area cannot test inundation extent. Existing per-flood
   alpha components, sinuosity, and cumulative cutoff count can still test
   temporal changes and coincident events. A cutoff counted in row n has
   occurred before flood n; migration following flood n first appears in
   row n+1. Exact published event timing is not determined by the written
   initial conditions. State these limits rather than manufacture a peak
   map or claim a precise temporal match.

3. **The PDF omits the available numerical sensitivity differences.**
   `scripts/validate_runs.py:184–190` calculates relative diagnostic changes
   and mean/maximum absolute field differences. The rebuild's report writer
   (`scripts/rebuild.sh:179–195`) prints case states and normalized budgets,
   but merely points to JSON for those differences. Include their numerical
   magnitudes and interpretation in the final PDF. Separate grid/time
   changes from critical-stress and concentration assumptions. These are
   first-flood tests with fixed 250 m channel spacing; they do not establish
   long-term migration or 580-flood grid independence.

4. **Production conservation needs an interpreted record.**
   `scripts/run_suite.py:152–155` requires finite budget diagnostics, not
   small residuals. Neither plotting nor manuscript comparison summarizes
   budget drift across the 31 production histories. Report maximum and
   terminal water, suspended-sediment, and combined solid-sediment residuals
   with stated normalization. The summary is sampled before that flood's
   migration/aggradation, so its last row excludes the final remap stored
   in the checkpoint. Preserve this scope. Kernel conservation checks and
   a finite production history alone do not establish negligible drift.

5. **Report captions and bed indexing need actual metadata.**
   The staged `report/main.tex:68–75` shows nA while leaving snapshot order
   unspecified. Saved flood n precedes its nth migration/aggradation and
   therefore has (n−1)A imposed bed rise. The captions at lines 209–277 also
   leave known colors, symbols, and datum as future requirements. State the
   implemented convention, actual legend, and initial plane
   z0(x)=1e-4(72000−x) m, hence 3.5875 m at the plotted column. The mean of
   ratios and dry-cell-inclusive alpha definitions are already documented
   in the maintained implementation text and should be stated directly
   where these diagnostics are introduced. These corrections were applied
   to root `report/main.tex` after coordination, together with explicit
   sediment-closure omissions from `docs/scientific-audit.md`. They do not
   alter the frozen staged source or its future report.

6. **A final assessment/publication pass is outside the automatic rebuild.**
   The wrapper produces an execution report with frozen pending scientific
   ledger notes; it cannot author the panel assessments in finding 1. Its
   source-hash check deliberately rejects changes to staged sources. Keep
   this run and its outer manifest intact. Any later assessed report must
   retain the original run provenance and separately record its report
   source, plot inputs, commands, and PDF hash. The staged products are
   under ignored `tmp/`; final code, data, manifests, figures, LaTeX, and PDF
   still require deliberate publication packaging. Root report fixes do not
   automatically alter the running staged rebuild.

## Provenance checks

The suite freezes source, configuration, compiler command, executable, and
per-case artifacts. Plotting records hashes of all consumed numerical inputs;
comparison verifies that manifest and independently recomputes the beta and
alpha windows. The report merges current panel coverage with source-ledger
assessments and checks numerical source hashes before retaining a prior
assessment. No stage imports the paper, supplement result columns, or
published figure values as numerical inputs. This chain supports independent
origin, while scientific agreement and the declared physical omissions
(including floodplain entrainment) remain separate questions.

No new numerical tests were run for this audit. All audit output is inside
the project on `/data/data0` (approximately 1.9 TB available when checked).
