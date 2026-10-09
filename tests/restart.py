#!/usr/bin/env python3
"""Exercise checkpoint/resume through the real model executable."""
import hashlib, pathlib, shutil, subprocess
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
with open(str(base / 'resumed/summary.csv'), 'a') as f: f.write('2,999,999\n')
run('resumed', 2, ['--resume', '1'])
for name in ['fields_0002.bin', 'channel_0002.csv', 'checkpoint.bin']:
    a = (base / 'continuous' / name).read_bytes(); b = (base / 'resumed' / name).read_bytes()
    assert a == b, 'restart mismatch: ' + name
    print('restart_identical', name, hashlib.sha256(a).hexdigest())
lines = (base / 'resumed/summary.csv').read_text().splitlines()
assert len(lines) == 3 and lines[-1].startswith('2,') and '999' not in lines[-1]
print('uncheckpointed_diagnostic_row_regenerated pass')
text = run('resumed', 3, ['--resume', '1', '--C', '.01'], expect=1)
assert 'checkpoint parameters do not match' in text
print('changed_checkpoint_parameters_rejected pass')
