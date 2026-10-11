# Early production preview, 2026-10-11

This snapshot supplies the first partial manuscript Figure 3B from the original
independent production calculations. Runs 7, 15 and 20 contribute 13, 13 and 15
completed-flood alpha values, respectively: **41 of the required 1,740 values**.
The plot preserves the full 1–580 flood range and leaves future values missing.
The other 12 panels have no requested numerical data in this snapshot. These
early values do not establish the publication's long-term behavior or agreement.

The original 31 calculations remain active at their full 580-flood target.
Capturing and plotting this snapshot started no model, changed no numerical
source or input, and invoked no additional checkpoint auditor.

## Retained evidence

`capture-manifest.json` records the capture at 09:33:50.243318 UTC and the
explicit observer poll at 09:31:52.312856 UTC. Its SHA256 is
`55003baebf7ae86cf8b22c3e2cc3609b8bf711566f188d1e4777219316bf737f`.
The snapshot contains 414 completed-flood rows across all 31 cases.

For each case, `data/runNN/` retains parameters and exact summary/remap CSV
prefixes whose hashes match the selected completed-checkpoint audit. The
capture did not infer completion from a summary row alone. The selected full
audit records, observer poll, seed and configuration matrix are under
`evidence/`. The manifest records all 127 retained-file hashes, source paths,
original process identities and frozen model hashes. Source paths describe
capture provenance; plotting uses the local retained copies.

Observer acceptance identifies automated scalar verification. Individual
independent review is a separate status and is not asserted for every record.
No native checkpoint arrays are decoded or used by this preview.

## Plotting and completeness

From the repository root:

```sh
python3 -B scripts/plot.py \
  --data-root validation/production-preview-20261011/data \
  --output validation/production-preview-20261011/figures --strict
```

This command generated [Figure 3](figures/figure3.pdf), the two explicitly
missing Figure 1–2 attempts, and all 13 coverage records. It exited **2**, the
expected failed completeness gate: zero panels have their complete requested
data. All 31 saved configurations and all 64 plot input hashes were verified.

The rendered files were copied byte for byte into the repository's `figures/`
directory for the provisional report. The subsequent command was:

```sh
python3 -B scripts/compare.py \
  --data-root validation/production-preview-20261011/data \
  --figures figures --output figures \
  --tex report/generated/results.tex --strict
bash report/build.sh
```

The comparison command also exited **2**: none of its 29 comparisons had the
required complete records. These failed completeness outcomes are retained;
successful PDF compilation does not turn them into completed model results.
Finalization still requires the full production histories, scientific panel
assessments, terminal rebuild audit and publication.

The 34-page provisional PDF compiled successfully. After correcting appendix
source-list wrapping, both LaTeX passes completed and the second pass reported
no warnings, undefined references or overfull/underfull boxes. Its Figure 3 and
partial-status appendix were visually inspected. An independent review checked
all retained hashes, contiguous histories, configurations and the 41 plotted
values. The finalizer's source selection was also checked: all 140 existing
files in this preview directory are selected for the eventual package.
