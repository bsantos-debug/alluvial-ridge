# Rejected clean rebuild 001

This directory retains historical evidence for the interrupted attempt of
2026-10-09. It supplies no manuscript result or resumable production state.
The original files are unchanged inside [rebuild-001.tar.xz](rebuild-001.tar.xz);
[capture.json](capture.json) records their hashes and the later capture.

The original rebuild began at 19:06:36 UTC. Compilation and the then-existing
checks passed. A separate 250 m neck-cutoff fixture subsequently showed that
the old remap could withdraw more suspended mass than a channel section held:
its local support/control-area ratio was 1.354778, giving a negative class
target of about −38,069 kg. The [retained counterexample](../stress/README.md)
used the same headers as this attempt. This was a constructed verification
failure, not a failure observed during one of the production hydrographs.
The wrapper was interrupted at 19:14:19 UTC, before any production flood
finished. The corrected implementation started a separate rebuild 002.

All 31 production records retain `interrupted`, exit −15, and empty summaries.
The two sensitivity records retain their original stale `running` states;
their driver was interrupted before it finalized those records, and their
summaries are also empty. The sensitivity manifest has an empty case list.
The later process observation in `capture.json` records absent process IDs;
it does not rewrite the historical execution records. No production or
sensitivity checkpoint, field raster, manuscript plot, or report was produced.

The archive contains 229 files: six outer logs/records, the separate launch
log, all 39 frozen source files, and the original data and validation trees
except the empty suite lock. It includes the frozen executable, configuration,
compiler provenance, and all interrupted case records. Duplicate build products
and temporary component/restart-test workspaces remain outside this selected
archive. The original attempt remains in `tmp/full-rebuild-001/`; its old
absolute paths inside the records are historical provenance.

Archive metadata are normalized to zero time and owner/group IDs; file bytes
are preserved. The compressed archive is 213,388 bytes with SHA-256
`748d80d1af0b9790cd2602fe1f6aa2f30b772d888a50547ee0d0671a840c7377`.
Verify every retained member without extracting it, from the project root:

```sh
python3 -B - <<'PY'
from pathlib import Path
import hashlib, io, json, tarfile
p = Path('validation/rejected-rebuild-001')
m = json.loads((p / 'capture.json').read_text())
b = (p / m['archive']).read_bytes()
sha = lambda data: hashlib.sha256(data).hexdigest()
assert sha(b) == m['archive_sha256']
with tarfile.open(fileobj=io.BytesIO(b), mode='r:xz') as archive:
    members = archive.getmembers()
    assert len(members) == m['member_count']
    assert all(member.isfile() for member in members)
    assert {member.name for member in members} == set(m['member_sha256'])
    for member in members:
        assert sha(archive.extractfile(member).read()) == m['member_sha256'][member.name]
print('Verified', len(members), 'rejected-attempt files')
PY
```

The saved-data finalizer copies this tracked directory alongside the remap
regression and corrected first-flood evidence. Its contents stay within this
labeled archive; they never populate the final workspace's canonical `data/`
or `validation/runs/` directories.
