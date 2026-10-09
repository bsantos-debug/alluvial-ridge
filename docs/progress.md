# Current authoritative state

2026-10-09: Project relocated from /home/brnisant/alluvial-ridge to
/data/data0/dominik-scratch/Shared/brnisant/alluvial-ridge at the user's request.
All project outputs/caches/tempfiles must stay on /data volumes. The home
project directory no longer exists. The supplied request is now copied to
docs/user-request.txt. Required guidance is in AGENTS.md and the style guide.

Previous goal turn made progress: written specifications/configuration/panel
ledger and finite-volume kernel were created and committed. This continuation
has implemented the coupled driver and has not yet completed production.

Current implementation: independent C++ first-order hydrostatic HLL 1-D/2-D
coupling, three sediment advection/diffusion/deposition classes, Chezy friction,
turbulent stress, Howard–Knutson/Ikeda migration, neck cutoffs, conservative
remapping, bank recycling, prescribed bed aggradation, diagnostics and outputs.
Written source recovery/assumptions: docs/sediment-methods.md and migration.md.
Current numerical choices: docs/implementation.md. Many original parameters
remain unspecified; no exact original-code equivalence is asserted.

Component checks pass. Coupled checks identified/fixed wrong reflecting-wall
orientation, donor weighting that withdrew sediment from empty interpolating
nodes, double-counted aggradation in remap, and incorrect downstream boundary.
Characteristic inlet/outlet fixes and assembled-model validation now pass.
`validation/current-build.txt` records the current build, component and coupled
checks, and byte-identical restart test. A changed-parameter checkpoint is
rejected. Full-domain first-flood baseline, floodplain-grid refinement, and
time-step sensitivity calculations are running with frozen validation inputs.
Performance optimization skips exactly dry regions and preserves all full-grid
state values; early7000step benchmark improved41.76→15.08s byte-identically.
See docs/performance-review.md when finalized. No production580-flood suite
has yet been completed. The invalid full_flood_v3 developmental process was
explicitly terminated and logged as rejected; it is not a live production job.

Report scaffold: report/main.tex and compiled report/report.pdf (work in
progress, conditional figures). Plotter scripts/plot.py handles all13 panels,
strictly checks requested flood times/windows, and records input hashes.
Developmental plots/tests under figures/test* and tmp/ are not manuscript
results. See docs/report-audit.md and plotting.md.

No original author code/output/source-data/plotting script was retrieved.
Written papers locally under sources/ are excluded from git and are not model
inputs. DR2's configuration columns were transcribed; its result columns were
not imported into the numerical or plotting workflow.

GitHub: authorized SSH authenticated as bsantos-debug. gh CLI had no API login.
User was asked to authenticate gh or provide an empty repository URL; no answer
yet. Do not repeat this request while useful local work remains. No repo is
published, so no remote PDF link exists.

Outstanding: finish long-case stability and spatial/time/
closure sensitivities; run every published configuration through580floods,
generate all13 panels from saved outputs, quantify differences, complete report,
run a clean full rebuild, publish/verify repository+PDF. Goal remains active.
