# Finalization and publication checklist

Read-only audit at 2026-10-09 19:26 UTC. All files remain under
`/data/data0/dominik-scratch/Shared/brnisant/alluvial-ridge`. Rebuild 002 is
running: its exact-binary checks passed, all 31 per-case process records are
running, and no production summary contains a completed flood yet. Its frozen
source hashes match the outer manifest. No generated manuscript figures or
002 report PDF exist yet. Root `report/report.pdf` is the 20-page provisional
report, not the eventual 002 report. All 13 scientific assessments remain open.

## Evidence required for each panel

Every row needs a documented assessment against the permitted paper prose and
embedded figure, with the final plot/input hashes and a candid discrepancy
statement. Figure existence and complete sampling establish independent data
coverage, not scientific agreement. The supplement has no figure panels.

| Panel | Required independent data | Assessment still needed |
|---|---|---|
| 1A | Run 11, flood 61 end/peak snapshots | Early splay deposition near bend apices; event thickness, footprint, spread and actual day-12 inundation. |
| 1B | Run 11, flood 251 end/peak snapshots | Channel-belt widening and abandoned-channel elements relative to 1A; localization of deposition. |
| 1C | Run 11, flood 501 end/peak snapshots | Late preferential deposition along abandoned channels and localized floodplain connections; compare with 1A/B. |
| 1D | Run 11, flood 562 end/peak snapshots | Late variability relative to 501 under the identical hydrograph; distinguish deposit area from inundated area. |
| 1E | Run 17, flood 562 end/peak snapshots | High-aggradation contrast with 1D; channel depth, wider inundation and immediate active-bank interface. Magenta denotes full interface, not only wet faces. |
| 1F | Run 03, flood 562 end/peak snapshots | Low-load contrast with 1D; lower channel depth and broader inundation, assessed from water fields rather than deposit threshold alone. |
| 2A | Run 22; floods 50, 225, 400, 580 | Ridge relief growth, width/concavity and channel troughs. Coarse published final relief reference: about 31–36 m. |
| 2B | Run 10; same four floods | High-aggradation/low-load profile versus 2A; approximate final relief reference 16–21 m. |
| 2C | Run 03; same four floods | Zero-aggradation relief and channel deepening; approximate final relief reference 6–8 m. |
| 2D | Run 15; same four floods | Intermediate forcing, relief growth and channel structure; approximate final relief reference 21–24 m. |
| 3A | All 31 runs; 20 finite beta ratios at floods 561–580 | A/C trend signs and reversals; six fine/default contrasts; E=0.5/1.5 contrasts against approximately +15%/−6.5%; ranges and interpretation of beta=1. |
| 3B | Runs 07, 15, 20; alpha over floods 1–580 | Absolute and relative variability, peaks and evolution. Relate alpha numerator/denominator and cutoff history without inventing exact published event timing. |
| 3C | All 31 runs; 200 finite alpha values at floods 381–580 | Percentile ranges and ordering, especially high C/low A. Highest C has no A=0 case; run 18 is its lowest available A. |

For Figure 2, use the saved x=36.125 km column. Its initial model plane is
3.5875 m; the publication's initial section is approximately 9 m. The above
relief intervals are coarse visual comparisons, not digitized measurements or
acceptance bounds. Saved flood n precedes its nth migration/aggradation and
contains `(n−1)A` imposed bed rise. Day-12 files have the `peak_` prefix and
clock `(n−0.4)T`; their float32 fields need not reproduce double-summary
diagnostics exactly. Cutoffs occurring after flood n first enter summary n+1.

## Concrete postprocessing findings

- **The frozen comparison suppresses usable early-panel comparisons after a
  later failure.** `scripts/compare.py:143–148,159–178` requires every source
  run to contain all 580 rows, including for a valid flood-61 deposit map.
  If a run fails later, retain that failure but assess its verified requested
  snapshots separately in later postprocessing; never substitute a late
  snapshot or relax the exact Figure 3 windows. This is a conservative gate,
  not evidence that an early completed map is invalid.
  The later root comparison now removes that blanket gate for Figures 1/2,
  while retaining each exact requested snapshot and canonical-physics checks.
  Figure 2 relief still needs all four profiles, including flood 580. Figure 3
  retains full histories and its finite final windows; 3B also requires three
  complete finite series. The new comparison checks all numeric
  `config/physics.txt` assumptions except the stopping flood count.
- **New peak files are not yet scientific comparison evidence by themselves.**
  Frozen `plot.py` and `compare.py` consume end-flood fields and scalar alpha.
  Any later peak/morphology helper needs its own input hashes, exact time
  checks, wetness definition and saved derived records. The existing 29
  comparisons do not assess ridge concavity or abandoned-channel morphology.
- **Assessment retention is not tied to plot identity.**
  `report/make_inputs.py:68–93` verifies numerical-source hashes before
  retaining an authored assessment, but does not verify the corresponding
  figure or processor hashes. Bind final assessments to those hashes in the
  new manifest, and review affected panels again after plotting changes.
  The later root report renderer now implements the explicit fingerprint
  record described below; the frozen 002 renderer remains unchanged.
- **Relocated root plots are not a portable final package.** Plot and report
  paths resolve relative to each script's project root. Running root scripts
  directly against `tmp/full-rebuild-002/workspace/data` records those paths;
  moving just their figures to a new checkout breaks that provenance. Copy
  data into the final workspace and run that workspace's scripts there.
- **Do not equate a reporting-stage pass with a scientific pass.** The strict
  stages test required coverage; budget tolerances, convergence interpretation,
  spatial fidelity and physical omissions still need assessment. The remaining
  assumptions include zero net channel suspended-bed exchange, no vertical
  floodplain entrainment, omitted secondary-flow terms and fixed bank grain
  fractions rather than evolving bed composition.

## Keep rejected and corrected provenance distinct

Rebuild 001 is an interrupted, rejected attempt with zero completed production
floods. Preserve `tmp/full-rebuild-001/rebuild_manifest.json`,
`interruption_reason.json`, logs and its frozen sources. Its executable SHA256
starts `b0bb5ea6a0f8`; it used the defective inventory-withdrawal remap. It is
not a source of manuscript values or successful validation for 002.

Rebuild 002 uses executable SHA256
`b3d984881a2f82757ff9bb6ca7c15f9e3c28e3d34106ae477fe7c06af6f8099c`
and frozen `model.hpp` SHA256
`e12bb6c79a9e70ca53d555fc2d5cfcefed9b0cf2f8a3f7567defd650cc039a15`.
Its authoritative numerical records are under
`tmp/full-rebuild-002/workspace/data/`; first-flood sensitivities are under
that workspace's `validation/runs/`. Root `validation/runs/` contains older
calculations and must not be merged into 002 sensitivity evidence. While
jobs run, the suite's case list can still say `prepared`; per-case
`process_status.json` and progress records carry the current running state.

## Final report procedure using verified saved data

The later procedure is implemented by `scripts/finalize_report.py`; commands,
terminal-evidence requirements and render-only operation are documented in
`docs/rebuild.md`. It rejects the active 002 case set until the wrapper,
production suite and eight sensitivity cases have terminal records. Its
separate saved-data manifest does not alter the original execution history.

If the project moved while frozen 002 was running, its final containment check
may leave an incomplete suite record beside a complete process record. Do not
rewrite either record or restart completed calculations to hide that mismatch.
Use the narrowly scoped `--reconcile-relocation` procedure in
[rebuild.md](rebuild.md#relocating-a-project-with-running-calculations) after
all writers have ended. It rechecks saved completion evidence, preserves the
original failed/incomplete rebuild outcome, and records the discrepancy in the
separate package manifest and report. Keep the old path alias until that audit
and packaging finish. Unrelated failures remain refusals.

1. Preserve the terminal 002 outer manifest and original PDF, even if a stage
   fails. Verify frozen source/input hashes and each terminal run's artifact
   hashes. Record actual completion, finite diagnostic coverage, failed cases,
   and before/after-remap budgets. Do not copy mutable live files as final data.
2. Create a separate project-local workspace, for example
   `deliverables/final/workspace/`. Export versioned source there, excluding
   `.git` and caches. Copy unchanged 002 `data/`, `validation/runs/`, and exact
   `validation/kernel.txt` into the same relative locations. Keep data as real
   copied files rather than symlinks to private temporary paths. Verify hashes
   after copying. Model source/configuration must match 002; any intentional
   postprocessor/report changes receive separate identities.
3. In that workspace, run the final plotter, comparison, optional scientific
   helpers, and `report/make_validation.py`, then `bash report/build.sh`.
   Capture every command, exit code, log and output hash. Pending-data exit
   code 2 remains a failed completeness gate even if the PDF compiles. Do not
   reuse stale generated LaTeX inputs or the provisional root PDF.
4. Inspect every generated panel and numerical comparison, author the 13
   assessments in that workspace's `docs/panels.csv`, and rebuild the PDF.
   Record which data were produced independently and which scientific features
   agree or disagree. Keep physical and numerical sensitivity limits explicit.
   Reassess any panel affected by a later plot change.
5. Write a separate `postprocess_manifest.json` with the 002 outer-manifest
   hash, original executable/input/artifact hashes, final source revision and
   hashes, commands, package versions, assessments, output hashes and PDF hash.
   Preserve the original 002 stage records unchanged. The report should say:
   “Numerical data were generated by rebuild 002; this assessed report was
   generated later from those verified files using the recorded postprocessors.”
   It must give the actual original rebuild outcome, not retroactively claim
   that new postprocessors ran in that clean execution.
6. Document both routes: a fresh full model-to-report rebuild into a new empty
   workspace, and regeneration of the assessed report from published data.
   Report compilation alone establishes neither a new full simulation nor
   scientific agreement.

## Recording and invalidating a scientific assessment

The later root `report/make_inputs.py` writes
`report/generated/panel_evidence.json` and shows each current fingerprint in
the appendix. Add optional `scientific_assessment` and
`assessment_fingerprint` columns to the maintained `docs/panels.csv`. After
reviewing a panel, write its bounded assessment and copy that panel's current
64-character fingerprint into the same ledger row. This is a manual review
record; the renderer never writes or automatically rebinds the source ledger.

The versioned fingerprint hashes a canonical JSON record of the panel's
coverage metadata and numerical-source hashes, the complete plot manifest,
the actual corresponding `figureN.pdf`, current `plot.py` and `compare.py`,
the physics reference, and `comparison.json` when present. For Figure 1,
`panel-assessment-v2` also binds available inundation and planform helper
output bytes and their verified provenance states. Invalid helper provenance
blocks that panel's fingerprint; absent helpers remain explicitly absent.
Other figures have no helper dependency. The renderer
verifies recorded numerical sources, the plotter/configuration identity, and
all recorded comparison inputs before issuing a usable fingerprint. It
preserves a prior complete assessment only with complete requested data, a
documented assessment and an identical fingerprint. A prior partial
assessment also needs matching evidence. Otherwise it withholds the prior
claim and reports data coverage separately. No data remain not reproduced;
partial data or complete unassessed data remain partially reproduced.

A change in PDF bytes, processor source, comparison record, plot manifest,
physics reference, coverage or numerical inputs invalidates review, even if
the visual appearance seems unchanged. Replotting may change PDF metadata
and therefore require another review. A figure-wide change invalidates each
assessed panel in that figure; a plot-manifest/comparison change can invalidate
all panels. This conservative rule prevents silent reuse of an old assessment.
The later renderer also includes verified helper summaries through
`spatial.tex` and `spatial_evidence.json`; missing or noncanonical rows remain
pending. Preserve their hashes and their use in the authored assessment in
the final postprocess manifest. These later report additions do not change
the frozen 002 report source or its recorded execution.

## Files to publish and final checks

Before staging the final package, retain the complete versioned
`validation/first-flood-audit-002/` directory: the original three coarse-case
audit files, the later two-resolution and 31-case observations and scripts,
both compressed input archives, and their capture manifest. Those archives
preserve the 313 input files checked by the provisional report. The finalizer
selects that tracked directory alongside `validation/stress/`. The audit is
historical observational evidence: preserve its original timestamps, PIDs,
input hashes and invocation paths. Do not rewrite its captured JSON or imply
that the original audit invocation becomes portable unchanged.

Update the local raw-data links in `docs/first-flood-validation.md` before
the final package is staged: change
`../tmp/full-rebuild-002/workspace/data/` to `../data/`, and
`../tmp/full-rebuild-002/workspace/validation/runs/` to `../validation/runs/`.
Its audit links should target `../validation/first-flood-audit-002/`. Check
these links in the copied workspace after staging. Keep the corrected audit,
the independent remap regression under `validation/stress/`, and rejected 001
evidence as three distinct records. The 001 archive belongs in a separately
labeled rejected-attempt directory; never copy its numerical files into
canonical `data/` or `validation/runs/`. Historical path strings inside
unchanged execution records remain provenance, not executable package paths.

| Publication content | Local source |
|---|---|
| Final code/configuration/tests/docs and LaTeX | Versioned final workspace; preserve 002 frozen model inputs alongside later postprocessors. |
| Numerical data and provenance | 002 `data/`, including `_inputs/`, parameters, summaries, remap ledgers, all requested end/peak fields and channel coordinates, logs and process/suite records. |
| Validation evidence | 002 `validation/runs/`, exact check log, generated validation summary, and the remap regression evidence under root `validation/stress/`. |
| Corrected first-flood audit | Versioned `validation/first-flood-audit-002/`, its methods/provenance record, and unchanged 002 coarse500 inputs already included under `validation/runs/`. |
| Figures and derived comparisons | Final workspace `figures/`, manifests, metric/section tables and optional helper records. |
| Final report and execution records | Final workspace `report/main.tex`, required `report/generated/` inputs, `report/report.pdf`, original 002 manifest/PDF, and separate postprocess manifest. |
| Rejected-attempt record | Clearly separated 001 reason, manifest, frozen sources and logs; never mixed into canonical data folders. |

`tmp/` is ignored by git, and production/validation checkpoints are also
ignored. Publication therefore needs deliberate copying/selection; a normal
commit of the checkout cannot include the staged deliverable. Retain the final
checkpoint and frozen executable if claiming a resumable archive. Exclude
temporary compiler/TeX caches, credentials, local PDF reading copies and smoke
figures from manuscript results. Preserve the needed validation evidence with
its scope rather than presenting smoke runs as production data.

Before publication, verify the packaged report builds using only packaged
paths, inspect all figure pages and appendix statuses, and reconcile README,
ledger, comparison records and PDF. Then publish the authorized repository and
data, verify its contents and PDF download, and give both links plus the exact
list of partial/unreproduced panels. No remote exists yet. The authentication
request is already pending; do not repeat it while local work remains.

This audit ran no simulations, changed no staged source, and did not interrupt
or restart a process.

## Checks on the later report and comparison fixes

Checks are isolated under `tmp/postprocess-finalization-check/`. The actual
short-domain diagnostic was replotted and compared: all 29 comparisons remain
pending, with no stale-input provenance errors. Its early-map reasons include
the altered physics and coverage, without an unrelated 580-row requirement.
Figure 3 retains its series/window gates. Actual 002 parameter metadata were
checked without inventing snapshots or model values: canonical metadata pass
the early gate, changing only the stopping count leaves it unchanged, and an
in-memory change in critical shear stress fails it.

A separate metadata-only report fixture checks unchanged review retention and
invalidation after changing PDF bytes, either processor, numerical-source
bytes, the physics reference or the comparison record. Missing fingerprints
withhold prior claims; partial coverage cannot preserve a complete claim; no
data remain not reproduced. The renderer leaves the source ledger unchanged.
Its copied report compiles in two TeX passes to 20 pages without layout or
reference warnings. That PDF is a regression fixture, not the final report.
Python syntax and `git diff --check` also passed. No root PDF or canonical
generated result was replaced by these diagnostic checks.
