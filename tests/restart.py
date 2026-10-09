#!/usr/bin/env python3
"""Exercise checkpoint/resume through the real model executable."""
import csv, hashlib, pathlib, shutil, struct, subprocess
root = pathlib.Path(__file__).resolve().parents[1]
base = root / 'tmp/restart-validation'
if base.exists(): shutil.rmtree(str(base))
base.mkdir(parents=True)
common = [str(root / 'build/ridge'), '--run', '11', '--length', '6000', '--width', '4000', '--duration', '3600']
def run(folder, floods, extra=(), expect=0):
    cmd = common + ['--out', str(base / folder), '--floods', str(floods)] + list(extra)
    p = subprocess.run(cmd, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != expect: raise RuntimeError(p.stdout.decode())
    return p.stdout.decode()
run('continuous', 2)
run('resumed', 1)
# Simulate a row written after the latest valid checkpoint, as after interruption.
for name in ['summary.csv', 'remap_budget.csv']:
    with open(str(base / 'resumed' / name), 'a') as f: f.write('2,999,999\n')
run('resumed', 2, ['--resume', '1'])
for name in ['fields_0002.bin', 'channel_0002.csv', 'peak_fields_0002.bin', 'peak_channel_0002.csv', 'checkpoint.bin']:
    a = (base / 'continuous' / name).read_bytes(); b = (base / 'resumed' / name).read_bytes()
    assert a == b, 'restart mismatch: ' + name
    print('restart_identical', name, hashlib.sha256(a).hexdigest())
for name in ['summary.csv', 'remap_budget.csv']:
    lines = (base / 'resumed' / name).read_text().splitlines()
    assert len(lines) == 3 and lines[-1].startswith('2,')
    assert len(lines[-1].split(',')) == len(lines[0].split(','))
    assert lines[-1].split(',')[1] != '999'
print('uncheckpointed_diagnostic_row_regenerated pass')
with (base / 'continuous/peak_fields_0002.bin').open('rb') as f:
    f.seek(24); elapsed, = struct.unpack('=d', f.read(8))
assert abs(elapsed - 1.6 * 3600) < 1e-10
print('day12_snapshot_clock pass')
for folder in ['continuous', 'resumed']:
    with (base / folder / 'remap_budget.csv').open() as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in ['water_transfer_residual', 'sand_transfer_residual', 'silt_transfer_residual', 'clay_transfer_residual']:
            assert abs(float(row[key])) < 1e-6, (folder, key, row[key])
        assert abs(float(row['solid_transfer_residual'])) < 1e-3
print('post_remap_budget_closure pass')
text = run('resumed', 3, ['--resume', '1', '--C', '.01'], expect=1)
assert 'checkpoint parameters do not match' in text
print('changed_checkpoint_parameters_rejected pass')
shutil.copytree(str(base / 'resumed'), str(base / 'version_one'))
old = base / 'version_one/checkpoint.bin'
blob = old.read_bytes()
assert b'ridge-checkpoint-v2 ' in blob[:128]
old.write_bytes(blob.replace(b'ridge-checkpoint-v2 ', b'ridge-checkpoint-v1 ', 1))
text = run('version_one', 3, ['--resume', '1'], expect=1)
assert 'checkpoint parameters do not match' in text
print('rejected_remap_version_checkpoint_rejected pass')
