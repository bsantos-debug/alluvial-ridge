# Early Figure 3B assessment

This assessment uses the immutable
[2026-10-11 production preview](../validation/production-preview-20261011/README.md).
Runs 7, 15 and 20 contain 13, 13 and 15 floods, respectively: 41 of the
1,740 required Figure 3B values. All three use A = 0.018 m per flood,
default grain fractions and E = 1. Their C values are 0.0003, 0.003 and 0.01.
The retained values come from the independent model, not published result
tables or digitized curves.

Nicholas et al. (2018, Figure 3B and its accompanying prose) define alpha as
mean floodplain water depth divided by the inundated fraction of the
channel–floodplain interface, sampled at 60% of flood duration. They report
greater inter-flood variability and higher peaks with increasing suspended
load as the ridge develops. This short initial record permits descriptive
comparison, but cannot establish that developed-ridge behavior.

## Common floods 1–13

The same 13 floods are used for each load. Standard deviation is the population
standard deviation; CV is that standard deviation divided by the mean. These
statistics include the early drift and have not been detrended.

| Run | C | Minimum alpha (m) | Maximum alpha (m) | Standard deviation (m) | CV |
|---|---:|---:|---:|---:|---:|
| 7 | 0.0003 | 0.884249 | 0.910552 | 0.00814557 | 0.00906770 |
| 15 | 0.003 | 0.884486 | 0.900550 | 0.00476455 | 0.00532753 |
| 20 | 0.01 | 0.811893 | 0.886492 | 0.0245175 | 0.0285793 |

The highest-load case has the largest spread, while the intermediate-load
case has the smallest. The observed maxima decrease with load. Thus these
early values do not show a monotonic increase in both variability and
peak alpha with C. This early ordering does not determine whether the
reported general pattern will emerge over the requested 580 floods.

Runs 7 and 15 have inundated interface fraction 1 throughout their retained
records. Run 20 has fractions 0.981034 at flood 11 and 0.998276 at floods 14
and 15; its other retained fractions are 1. Alpha therefore mostly tracks
the mean floodplain water depth during this interval. These broadly inundated
interfaces do not establish later localized breach behavior. Every retained
summary has zero cutoffs; the final summary does not describe its following
remap. Spatial breach locations and later morphology remain unassessed.

One rise in alpha illustrates the denominator's role. Between floods 10 and
11 in run 20, alpha rises from 0.832238 to 0.847742 m while mean water depth
falls from 0.832238 to 0.831664 m. The wet-interface fraction falls from 1
to 0.981034. The increase in this ratio therefore does not indicate increasing
mean water depth, and these scalar records do not identify a breach location.

Over all 15 retained floods, run 20 spans 0.802042–0.886492 m, with population
standard deviation 0.0283446 m and CV 0.0332933. These longer-prefix statistics
are kept separate from the common-window comparison above. No missing value
is interpolated, extrapolated or replaced, and no final-200-flood statistic
is inferred. Figure 3B remains **partially reproduced**; all other manuscript
panels remain **not reproduced**.

## Reproduce the descriptive statistics

Run from the repository root. This reads only the retained snapshot and writes
the statistics to standard output:

```sh
python3 -B - <<'PY'
import csv
from pathlib import Path
from statistics import mean, pstdev

root = Path('validation/production-preview-20261011/data')
for run in (7, 15, 20):
    with (root / ('run%02d' % run) / 'summary.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert [int(r['flood']) for r in rows] == list(range(1, len(rows) + 1))
    for label, selected in [('common', rows[:13]), ('all', rows)]:
        values = [float(r['alpha']) for r in selected]
        deviation = pstdev(values)
        print(run, label, len(values), min(values), max(values),
              deviation, deviation / mean(values))
PY
```

The partial assessment in [the panel ledger](panels.csv) is bound to
`panel-assessment-v2` fingerprint
`ce705eea427369763b5591b0116236cf95fc19f74aea234c6fc0cef5355c30d4`.
That fingerprint includes the six numerical input files, the plot manifest,
Figure 3 PDF, plotting/comparison processors, physics reference and comparison
record. Changed inputs or rendering require a new assessment. The snapshot's
capture manifest and plot files remain unchanged by this later review.
