# Hydrodynamic controls on alluvial ridge construction

Independent reconstruction of Nicholas et al. (2018), *Geology* 46, 639–642,
[doi:10.1130/G40104.1](https://doi.org/10.1130/G40104.1).

**Work in progress.** The coupled C++ model, verification tests, 31 published
configuration combinations, plotting scripts for all 13 manuscript panels,
and a LaTeX report scaffold are implemented. Full-duration verification and
production simulations are ongoing. No manuscript panel is claimed reproduced
yet. The report's placeholders explicitly identify missing evidence.

Only published written scientific descriptions are specifications. Original
model code, output files, plotting scripts, source data, and figure files are
excluded. Published figures are inspected only for comparison and are not
digitized. Downloaded reference papers are ignored by git and never become
simulation inputs. DR2's configuration columns are permitted specifications;
its result columns are not replacement numerical data.

The implementation couples a 1-D channel to a 2-D shallow-water floodplain,
three suspended sediment classes, deposition, channel migration and neck
cutoffs, bank erosion/recycling, and prescribed channel-bed aggradation.
Unspecified physical/numerical choices are explicit assumptions. This is an
independent implementation with documented differences, not an assertion that
the unpublished original model has been recovered exactly.

All project files, outputs, and caches are kept on a `/data/data0` through
`/data/data7` volume. Current checkout:
`/data/data0/brooke/alluvial-ridge`.
The project moved there on 2026-10-10 at 00:25:50 UTC. The former path under
`dominik-scratch` is a temporary symlink for running jobs and their later
provenance audit. See [the relocation record](validation/relocation-20261010/README.md).

```bash
source scripts/environment.sh
RIDGE_JOBS=8 RIDGE_VALIDATION_JOBS=2 bash scripts/rebuild.sh
```

This procedure freezes and compiles source, runs checks and fresh full-duration
simulations, generates figures and quantitative validation, then builds the PDF.
The full 580-flood procedure has not yet completed. Existing results are
protected from accidental overwrite. See
[docs/rebuild.md](docs/rebuild.md) for fresh-run/resume details and remaining
workflow work. GCC 8 uses `-lstdc++fs`; newer compilers may omit that flag.
Python requires NumPy/Matplotlib. The report uses pdfLaTeX.

- [Scientific specifications and requirement gates](docs/specification.md)
- [Implemented equations, assumptions and boundary conditions](docs/implementation.md)
- [Hydraulic/sediment evidence](docs/sediment-methods.md)
- [Completed first-flood validation](docs/first-flood-validation.md) and
  [preserved numerical inputs](validation/first-flood-audit-002/README.md), with
  a separate [validation figure](figures/first_flood_validation.pdf)
- [Migration evidence and equations](docs/migration.md)
- [Complete panel ledger](docs/panels.csv)
- [Plot input/output conventions](docs/plotting.md)
- [Current work state](docs/progress.md)
- [LaTeX source](report/main.tex) and [work-in-progress PDF](report/report.pdf)

No GitHub repository has been published yet. SSH access identifies
`bsantos-debug`, but repository creation still needs GitHub API authentication
or an existing empty repository URL. The user's request authorizes publication
once that capability is available.
