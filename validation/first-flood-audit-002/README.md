# First-flood validation evidence

These records describe the corrected executable in clean rebuild 002. They
retain first-flood validation observations while the 580-flood simulations
continue. The scientific interpretation is in
[first-flood-validation.md](../../docs/first-flood-validation.md).

- `audit.json` and `initial-observation.json` preserve the earlier 500 m audit.
- `two-resolution.json` compares the completed 250 m and 500 m cases. Its
  percentage differences use `100*(coarse500/baseline250 - 1)`.
- `production-observation-20261009T213916.json` records all 31 production
  cases at 2026-10-09 21:39:16 UTC, after one completed flood. Its 289 input
  hashes cover the frozen inputs, recorded process identities, parameters,
  first-flood fields, summaries, remap ledgers, and checkpoints.
- `production-inputs-20261009T213916.tar.xz` preserves those exact 289 files.
  Member names are relative to `tmp/full-rebuild-002/workspace`. Metadata
  timestamps and ownership are normalized; file contents are unchanged.
- `resolution-inputs.tar.xz` preserves the 24 files from the completed
  250 m and 500 m cases, including their checkpoints and process records.
- `capture-provenance.json` binds the retained scripts, observations, and
  input archive to their SHA-256 digests. The report checks this manifest
  before displaying the archived observations.
- `time-step.json` compares the completed corrected 250 m cases at CFL 0.4
  and 0.2. `time-step-inputs.tar.xz` retains their 24 original process/output
  files, bound by `time-step-capture.json`. This later capture preserves the
  earlier archives and manifests unchanged. `time-step.py` verifies the
  capture and recomputes the comparison without consulting live paths.
- `threshold.json` compares the completed corrected 250 m baseline,
  `tau005`, and `tau020` cases at critical deposition stresses of 0.1,
  0.05, and 0.2 Pa. `threshold-inputs.tar.xz` retains their 36 original files,
  bound by `threshold-capture.json`. `threshold.py` verifies the capture
  and recomputes the comparison, reusing the hash-checked numerical helpers
  from the unchanged `time-step.py`. The earlier 24 baseline and `tau005`
  member bytes are unchanged. Analysis format 2 names `baseline250` explicitly
  and stores each candidate's parameter, diagnostic, and field comparisons
  under `comparisons`.
- `concentration.json` compares the corrected 250 m baseline with the completed
  `concentration_half` case. Their sole parameter difference is the explicit
  inlet-concentration multiplier, from 0.001 to 0.0005. The 24 original files
  are retained in `concentration-inputs.tar.xz`, bound by
  `concentration-capture.json`. `concentration.py` checks the retained capture
  and replays the analysis using the unchanged, hash-checked `time-step.py`
  helpers. The baseline member bytes match the earlier archives. The report
  also binds its baseline process, parameters, and remap ledger to the verified
  resolution comparison. This capture leaves the prior evidence unchanged.

The original production observation checked live PIDs, start times and
executables. Those process identities describe that observation time. Later
checkpoints replace earlier checkpoints in the running suite; the archive
retains the bytes used for these first-flood checks. Historical command paths
are preserved even after a project relocation.

From the project root, check every retained file and archived input without
extracting or changing any simulation output:

```sh
python3 -B - <<'PY'
import hashlib, json, tarfile
from pathlib import Path
p = Path('validation/first-flood-audit-002')
m = json.loads((p / 'capture-provenance.json').read_text())
for name, expected in m['files_sha256'].items():
    assert hashlib.sha256((p / name).read_bytes()).hexdigest() == expected, name
production = m['production_input_archive']
sensitivity = m['sensitivity_input_archive']
sources = [(production, json.loads((p / production['observation']).read_text())['input_sha256']),
           (sensitivity, sensitivity['files_sha256'])]
for record, expected in sources:
    observed = {}
    with tarfile.open(str(p / record['file']), 'r:*') as archive:
        for member in archive:
            assert member.isfile() and member.name not in observed, member.name
            observed[member.name] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert observed == expected
    assert len(observed) == record['members']
    print('Verified', len(observed), 'input files in', record['file'])
PY
```

Recompute the two-resolution comparison while its completed source cases
remain available:

```sh
python3 -B validation/first-flood-audit-002/two-resolution.py .
```

The completed time-step comparison is portable and can be replayed entirely
from its retained archive:

```sh
python3 -B validation/first-flood-audit-002/time-step.py
```

The command verifies the original process records and artifact hashes,
requires the CFL limit to be the only parameter difference, and checks the
recomputed result against `time-step.json`. The report performs the same
verification before displaying the comparison. Percentages use the CFL 0.4
case as denominator. These two limits establish first-flood sensitivity,
without a temporal convergence order or a manuscript-panel assessment.

Replay the completed deposition-threshold comparison from its retained files:

```sh
python3 -B validation/first-flood-audit-002/threshold.py
```

The command verifies that critical deposition stress is each candidate's only
numerical parameter difference, then checks the saved comparison against its
replay. The report requires the same verification. Field differences are
candidate minus baseline; percentages use the 0.1 Pa case as denominator.
This is first-flood sensitivity to an assumed physical
parameter; it does not establish numerical convergence or constrain the
appropriate deposition threshold.

Replay the completed half-concentration comparison from its retained files:

```sh
python3 -B validation/first-flood-audit-002/concentration.py
```

This command reads only adjacent retained files, verifies both terminal process
records and all 24 archived inputs, requires the multiplier to be the sole
parameter change, and compares its replay with the saved analysis. It does not
read the original live paths. The report requires the same verification and
renders this comparison as pending if its evidence is missing, stale, or
altered. Percentage changes use the 0.001 baseline as denominator; field
differences subtract baseline from half concentration. The sediment residuals
use separate prescribed-input denominators of `5.473459038918808e10 kg` and
`2.736729519459404e10 kg`, calculated from the actual multipliers. These are
first-flood sensitivities to an explicit concentration assumption, without a
convergence claim, later-time prediction, or manuscript-panel assessment.
The separate double-concentration calculation remains unfinished.

`production-observation.py` is the retained live-observation procedure. It
requires the first-flood checkpoints and matching live processes, and refuses
later states. Full numerical regeneration follows the documented clean
[rebuild procedure](../../docs/rebuild.md). Neither an archive integrity check
nor these first-flood observations establish grid convergence, long-term
behavior, or manuscript-panel agreement.
