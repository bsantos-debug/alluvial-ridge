"""Cheap assessment checks: saved bytes and scalar statistics; no model runs."""
import csv
import hashlib
import io
import json
import pathlib
import statistics
import tarfile

root = pathlib.Path(__file__).resolve().parents[2]
evidence = pathlib.Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

m = json.loads((root / 'figures/first_flood_validation_manifest.json').read_text())
for group in ('input_sha256', 'outputs_sha256'):
    for name, expected in m[group].items():
        assert digest(root / name) == expected, name
summary = {}
with tarfile.open(str(root / 'validation/first-flood-audit-002/resolution-inputs.tar.xz')) as archive:
    observed = {}
    for member in archive:
        assert member.isfile()
        data = archive.extractfile(member).read()
        observed[member.name] = hashlib.sha256(data).hexdigest()
        if member.name.endswith('/summary.csv'):
            summary[member.name.split('/')[-2]] = list(csv.DictReader(io.StringIO(data.decode())))[0]
    assert observed == m['member_sha256']
preview = json.loads((root / 'figures/plot_manifest.json').read_text())
for name, expected in preview['files'].items():
    assert digest(root / name) == expected, name
stats = {}
for run in ('07', '15', '20'):
    path = root / ('validation/production-preview-20261011/data/run' + run + '/summary.csv')
    rows = list(csv.DictReader(path.open()))
    alpha = [float(r['alpha']) for r in rows if 1 <= int(r['flood']) <= 13]
    assert len(alpha) == 13
    stats[run] = dict(min=min(alpha), max=max(alpha), population_sd=statistics.pstdev(alpha))
panels = list(csv.DictReader((root / 'docs/panels.csv').open()))
assert len(panels) == 13 and len({r['panel'] for r in panels}) == 13
statuses = {s: sum(r['status'] == s for r in panels) for s in set(r['status'] for r in panels)}
inventory = json.loads((evidence / 'inventory.json').read_text())
for label in ('legacy-validation-runs', 'unique-renderer-checks'):
    record = inventory[label]
    archive_path = evidence / (label + '.tar.xz')
    assert digest(archive_path) == record['archive_sha256']
    with tarfile.open(str(archive_path)) as archive:
        hashes = {m.name: hashlib.sha256(archive.extractfile(m).read()).hexdigest() for m in archive if m.isfile()}
    assert hashes == record['members']
result = dict(first_flood_bindings=30, preview_bindings=len(preview['files']),
              summary=summary, common13_alpha=stats, panels=statuses,
              preservation_archives_verified=2,
              limits='No solver runs, physical-budget reconstruction, numerical convergence tests, or full provenance audit.')
print(json.dumps(result, indent=2, sort_keys=True))
