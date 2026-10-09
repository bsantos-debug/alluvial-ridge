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
`/data/data0/dominik-scratch/Shared/brnisant/alluvial-ridge`.

```bash
source scripts/environment.sh
make -j4 all check
python3 tests/restart.py
python3 scripts/run_suite.py --jobs 8 --data-root data --floods 580
python3 scripts/plot.py --data-root data --output figures --strict
bash report/build.sh
```

These are the rebuild commands; the full 580-flood procedure has not yet
completed. Existing results are protected from accidental overwrite. See
[docs/rebuild.md](docs/rebuild.md) for fresh-run/resume details and remaining
workflow work. GCC 8 uses `-lstdc++fs`; newer compilers may omit that flag.
Python requires NumPy/Matplotlib. The report uses pdfLaTeX.

- [Scientific specifications and requirement gates](docs/specification.md)
- [Implemented equations, assumptions and boundary conditions](docs/implementation.md)
- [Hydraulic/sediment evidence](docs/sediment-methods.md)
- [Migration evidence and equations](docs/migration.md)
- [Complete panel ledger](docs/panels.csv)
- [Plot input/output conventions](docs/plotting.md)
- [Current work state](docs/progress.md)
- [LaTeX source](report/main.tex) and [work-in-progress PDF](report/report.pdf)

No GitHub repository has been published yet. SSH access identifies
`bsantos-debug`, but repository creation still needs GitHub API authentication
or an existing empty repository URL. The user's request authorizes publication
once that capability is available.
