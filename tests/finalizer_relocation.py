#!/usr/bin/env python3
"""Test saved-data relocation with retained one-flood bytes; run no model.

Terminal production-shaped metadata is synthetic. These helper tests establish
no 580-flood production completion, checkpoint validity, or scientific agreement.
All fixture mutations occur in project/tmp and are removed after the test.
"""
import sys
sys.dont_write_bytecode = True

import contextlib
import copy
import csv
import fcntl
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('finalizer', ROOT / 'scripts/finalize_report.py')
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


refusals = []


def refused(label, operation, fragment=None):
    try:
        operation()
    except (ValueError, OSError, struct.error) as error:
        if fragment:
            assert fragment in str(error), (label, str(error))
        refusals.append(label)
        return
    raise AssertionError('accepted invalid evidence: ' + label)


@contextlib.contextmanager
def idle_writer(workspace, output):
    # This child only waits on stdin; its command tests the /proc writer guard.
    command = [sys.executable, '-B', '-c',
               'import sys; print("ready", flush=True); sys.stdin.buffer.read(1)',
               '--out', str(output)]
    child = subprocess.Popen(command, cwd=str(workspace), stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        assert child.stdout.readline() == b'ready\n'
        yield
    finally:
        child.communicate(input=b'\n', timeout=10)
        assert child.returncode == 0


audit = ROOT / 'validation/first-flood-audit-002'
archive_path = audit / 'resolution-inputs.tar.xz'
capture = json.loads((audit / 'capture-provenance.json').read_text())
archive_hash = sha(archive_path.read_bytes())
assert archive_hash == capture['files_sha256'][archive_path.name]
original = {}
with tarfile.open(archive_path) as archive:
    for member in archive.getmembers():
        if Path(member.name).parent == Path('validation/runs/coarse500'):
            assert member.isfile()
            data = archive.extractfile(member).read()
            assert sha(data) == capture['sensitivity_input_archive']['files_sha256'][member.name]
            if Path(member.name).name != 'process_status.json':
                original[Path(member.name).name] = data
assert len(original) == 11

(ROOT / 'tmp').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='finalizer-relocation-', dir=str(ROOT / 'tmp')) as temporary:
    base = Path(temporary)
    old = base / 'old-workspace'
    new = base / 'new-workspace'
    folder = old / 'data/run11'
    folder.mkdir(parents=True)
    for name, data in original.items():
        (folder / name).write_bytes(data)
    command = ['FIXTURE-NOT-EXECUTED', '--floods', '1', '--out', str(folder)]
    attempt = dict(state='complete', exit_code=0, requested_floods=1,
                   utc_end='2000-01-01T00:00:00Z', command=command,
                   artifacts_sha256={name: sha(data) for name, data in original.items()})
    process = dict(run=11, state='complete', exit_code=0, utc_end=attempt['utc_end'],
                   command=command, attempts=[attempt],
                   fixture_scope='SYNTHETIC TERMINAL METADATA; RETAINED ONE-FLOOD SENSITIVITY BYTES')
    process_path = folder / 'process_status.json'
    process_path.write_bytes(encoded(process))
    old.rename(new)
    old.symlink_to(new, target_is_directory=True)
    folder = new / 'data/run11'
    process_path = folder / 'process_status.json'
    record = dict(copy.deepcopy(process), state='incomplete',
                  error='all project paths must remain inside this /data project: ' + str(folder))
    suite_path = new / 'data/suite_manifest.json'
    suite_path.write_bytes(encoded(record))
    original_records = {process_path: process_path.read_bytes(), suite_path: suite_path.read_bytes()}

    def check(p=None, r=None, allow=True, historical=old, floods=1):
        p = copy.deepcopy(process) if p is None else p
        r = copy.deepcopy(record) if r is None else r
        process_path.write_bytes(encoded(p))
        suite_path.write_bytes(encoded(r))
        before = {path: path.read_bytes() for path in original_records}
        try:
            return finalizer.verify_case_record(folder, r, floods, historical, allow)
        finally:
            assert all(path.read_bytes() == data for path, data in before.items())
            for path, data in original_records.items():
                path.write_bytes(data)

    assert check(r=copy.deepcopy(process), allow=False) is None
    refused('relocation without opt-in', lambda: check(allow=False), 'records disagree')
    evidence = check()
    assert evidence['original_suite_state'] == 'incomplete'
    assert evidence['original_process_state'] == 'complete'
    assert evidence['historical_output'] == str(old / 'data/run11')
    assert evidence['verified_source_output'] == str(folder)
    assert evidence['packaged_case'] == 'data/run11'
    assert evidence['process_record_sha256'] == sha(original_records[process_path])
    assert evidence['completion']['completed_floods'] == 1
    assert 'checkpoint checked nonempty, not decoded' in evidence['scope']
    assert 'no scientific acceptance' in evidence['scope']

    def bad_record(label, mutate, fragment):
        p, r = copy.deepcopy(process), copy.deepcopy(record)
        mutate(p, r)
        refused(label, lambda: check(p, r), fragment)

    bad_record('wrong suite state', lambda p, r: r.update(state='failed'), 'records disagree')
    bad_record('wrong process state', lambda p, r: p.update(state='failed'), 'records disagree')
    bad_record('unrelated suite error', lambda p, r: r.update(error='model failure'), 'records disagree')
    bad_record('wrong run', lambda p, r: p.update(run=12), 'records disagree')
    bad_record('different attempts', lambda p, r: r['attempts'][0].update(exit_code=1), 'records disagree')
    bad_record('nonterminal record', lambda p, r: r.update(current_attempt={}), 'not terminal')
    for key, value in [('requested_floods', 2), ('state', 'failed'), ('exit_code', 1)]:
        def mutate(p, r, key=key, value=value):
            for item in (p, r):
                item['attempts'][0][key] = value
        bad_record('wrong attempt ' + key, mutate, 'completed attempt')

    bad_record('wrong process exit', lambda p, r: (p.update(exit_code=1), r.update(exit_code=1)),
               'completed attempt')
    refused('wrong requested count', lambda: check(floods=2), 'completed attempt')

    def replace_command(p, r, command):
        for item in (p, r):
            item['command'] = list(command)
            item['attempts'][0]['command'] = list(command)

    bad_record('wrong output', lambda p, r: replace_command(p, r, command[:-1] + [str(folder)]),
               'historical output alias')
    bad_record('duplicate output', lambda p, r: replace_command(p, r, command + ['--out', str(folder)]),
               'identical recorded output commands')
    bad_record('missing output argument', lambda p, r: replace_command(p, r, command[:-1]),
               'historical workspace or output path')
    bad_record('different recorded commands',
               lambda p, r: (p.update(command=['different']), r.update(command=['different'])),
               'identical recorded output commands')
    refused('missing historical workspace', lambda: check(historical=None), 'historical workspace')
    refused('relative historical workspace', lambda: check(historical=Path('old-workspace')),
            'historical output alias')

    def bad_file(label, name, replacement, fragment=None, refresh_hash=True):
        path = folder / name
        before = path.read_bytes()
        p, r = copy.deepcopy(process), copy.deepcopy(record)
        try:
            if replacement is None:
                path.unlink()
            else:
                path.write_bytes(replacement)
            if refresh_hash:
                for item in (p, r):
                    hashes = item['attempts'][0]['artifacts_sha256']
                    if replacement is None:
                        hashes.pop(name)
                    else:
                        hashes[name] = sha(replacement)
            refused(label, lambda: check(p, r), fragment)
        finally:
            path.write_bytes(before)

    header = original['summary.csv'].splitlines(keepends=True)[0]
    bad_file('missing completed history', 'summary.csv', header, 'each requested flood')
    bad_file('missing remap history', 'remap_budget.csv',
             original['remap_budget.csv'].splitlines(keepends=True)[0], 'each requested flood')
    rows = list(csv.DictReader(io.StringIO(original['summary.csv'].decode())))
    rows[0]['water_residual'] = 'nan'
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    bad_file('nonfinite diagnostic', 'summary.csv', text.getvalue().encode(), 'nonfinite conservation')
    bad_file('wrong model status', 'status.txt', b'complete 2 floods\n', 'completion status')
    bad_file('empty checkpoint', 'checkpoint.bin', b'', 'nonempty restart checkpoint')
    for name in ('fields_0001.bin', 'peak_fields_0001.bin'):
        changed = bytearray(original[name])
        struct.pack_into('=d', changed, 24, struct.unpack_from('=d', changed, 24)[0] + 1)
        bad_file('wrong clock ' + name, name, changed, 'does not match' if name.startswith('fields')
                 else 'do not match')
        bad_file('truncated header ' + name, name, original[name][:8])
    bad_file('missing peak snapshot', 'peak_fields_0001.bin', None)
    bad_file('artifact corruption', 'summary.csv', original['summary.csv'] + b'changed\n',
             'hash mismatch', refresh_hash=False)

    # Distinct descriptors must contend even though they belong to this test process.
    lock_path = new / 'data/.suite.lock'
    with lock_path.open('w+b') as holder, lock_path.open('rb') as contender:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refused('held suite lock', lambda: finalizer.lock_suite(contender), 'writer lock is held')
        fcntl.flock(holder, fcntl.LOCK_UN)
        finalizer.lock_suite(contender)
    for output in (folder, old / 'data/run11'):
        with idle_writer(new, output):
            refused('live writer ' + str(output.parent.parent.name),
                    lambda: finalizer.no_live_writers(new), 'live writer references')
    finalizer.no_live_writers(new)

    package = base / 'package'
    (package / 'workspace/report/generated').mkdir(parents=True)
    package_record = dict(original_rebuild_state='incomplete', commands=[],
                          relocation_reconciliations=[evidence], fixture_scope=process['fixture_scope'])
    before = encoded(package_record)
    finalizer.execution_tex(package, package_record)
    report_path = package / 'workspace/report/generated/rebuild.tex'
    report_before = report_path.read_bytes()
    old.unlink()
    unrelated = base / 'unrelated-workspace'
    (unrelated / 'data/run11').mkdir(parents=True)
    old.symlink_to(unrelated, target_is_directory=True)
    refused('historical alias points elsewhere', check, 'historical output alias')
    old.unlink()
    refused('removed historical alias', check)
    finalizer.execution_tex(package, package_record)
    assert report_path.read_bytes() == report_before
    assert encoded(package_record) == before
    report = report_before.decode()
    assert 'original clean rebuild ended with state \\texttt{incomplete}' in report
    assert 'original rebuild outcome remain unchanged' in report
    assert 'only a nonempty file, not a decoded valid state' in report
    assert 'neither grid convergence nor manuscript agreement' in report
    assert 'does not establish scientific agreement' in report
    assert all(path.read_bytes() == data for path, data in original_records.items())
    assert all((folder / name).read_bytes() == data for name, data in original.items())

assert sha(archive_path.read_bytes()) == archive_hash
print('finalizer relocation: accepted only the explicit one-flood relocation case; '
      + str(len(refusals)) + ' invalid/unsafe cases refused; original bytes preserved; '
      'report scope survives alias removal. No model run or 580-flood claim.')
