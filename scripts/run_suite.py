#!/usr/bin/env python3
"""Compile frozen scientific inputs and run cases without replacing failed floods."""
import argparse
import concurrent.futures
import csv
import datetime
import fcntl
import hashlib
import json
import math
import os
import pathlib
import re
import shlex
import signal
import struct
import subprocess
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def utc():
    return datetime.datetime.utcnow().isoformat() + 'Z'


def inside(path):
    path = (ROOT / path).resolve()
    if ROOT not in path.parents or not re.match(r'^/data/data[0-7]/', str(ROOT) + '/'):
        raise ValueError('all project paths must remain inside this /data project: ' + str(path))
    return path


def environment():
    env = dict(os.environ)
    for key, folder in [('TMPDIR', 'tmp'), ('XDG_CACHE_HOME', 'tmp/cache'),
                        ('PYTHONPYCACHEPREFIX', 'tmp/pycache'), ('MPLCONFIGDIR', 'tmp/matplotlib'),
                        ('CCACHE_DIR', 'tmp/cache/ccache')]:
        path = inside(folder)
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    return env


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def process_identity(pid):
    try:
        fields = pathlib.Path('/proc/{}/stat'.format(pid)).read_text().rsplit(') ', 1)[1].split()
        return None if fields[0] in ('Z', 'X') else fields[19]
    except (OSError, IndexError):
        return None


def live_case(folder):
    """Also find children left alive if a runner died before recording its PID."""
    for path in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
        try:
            arguments = path.read_bytes().decode().strip('\0').split('\0')
            if arguments and '--out' in arguments:
                if arguments[arguments.index('--out') + 1] == str(folder) and process_identity(int(path.parent.name)):
                    return int(path.parent.name)
        except (OSError, UnicodeError, ValueError, IndexError):
            continue
    return None


def prepare(data, config, runs_table, env):
    inputs = data / '_inputs'
    inputs.mkdir()
    originals = sorted(path for path in (ROOT / 'src').rglob('*') if path.is_file())
    if not originals or not (ROOT / 'src/main.cpp').is_file():
        raise ValueError('model source files are missing')
    copied = {}
    for source, name in [(path, str(path.relative_to(ROOT))) for path in originals] + [
            (config, 'physics.txt'), (runs_table, 'runs.csv'), (pathlib.Path(__file__).resolve(), 'run_suite.py')]:
        source = inside(source)
        target = inputs / name
        target.parent.mkdir(parents=True, exist_ok=True)
        # Compile these bytes, rather than attributing current source to an older executable.
        target.write_bytes(source.read_bytes())
        copied[name] = digest(target)
        target.chmod(0o444)
    compiler = shlex.split(os.environ.get('CXX', 'g++'))
    flags = shlex.split(os.environ.get('CXXFLAGS', '-O3 -std=c++17 -Wall -Wextra -Wpedantic'))
    command = compiler + shlex.split(os.environ.get('CPPFLAGS', '')) + flags + [
        '-I' + str(inputs / 'src'), str(inputs / 'src/main.cpp'), '-o', str(inputs / 'ridge')]
    command += shlex.split(os.environ.get('LDFLAGS', '')) + shlex.split(os.environ.get('LDLIBS', '-lstdc++fs'))
    version = subprocess.check_output(compiler + ['--version'], env=env).decode().splitlines()[0]
    provenance = {'utc_prepared': utc(), 'source_sha256': {k: v for k, v in copied.items() if k.startswith('src/')},
                  'frozen_sha256': copied, 'compile_command': command, 'compiler_version': version,
                  'source_hash_scope': 'exact frozen bytes passed to the recorded compiler command'}
    with (inputs / 'compile.log').open('w') as log:
        result = subprocess.run(command, cwd=str(inputs), env=env, stdout=log, stderr=subprocess.STDOUT)
    provenance['compile_exit_code'] = result.returncode
    provenance['compile_log_sha256'] = digest(inputs / 'compile.log')
    if result.returncode:
        save(inputs / 'provenance.json', provenance)
        raise RuntimeError('frozen-source compilation failed; see ' + str(inputs / 'compile.log'))
    executable = inputs / 'ridge'
    executable.chmod(0o555)
    provenance['binary_sha256'] = digest(executable)
    provenance['config_sha256'] = copied['physics.txt']
    provenance['runs_table_sha256'] = copied['runs.csv']
    provenance['frozen_sha256']['ridge'] = provenance['binary_sha256']
    save(inputs / 'provenance.json', provenance)
    (inputs / 'provenance.json').chmod(0o444)
    return provenance


def verify_inputs(data, provenance):
    if json.loads((data / '_inputs/provenance.json').read_text()) != provenance:
        raise RuntimeError('suite manifest and frozen provenance disagree')
    for name, expected in provenance['frozen_sha256'].items():
        path = inside(data / '_inputs' / name)
        if not path.is_file() or digest(path) != expected:
            raise RuntimeError('frozen input changed or missing: ' + str(path))


def verify_artifacts(folder, record):
    """Only terminal attempts have hashes; a killed writer may have advanced a checkpoint."""
    if record.get('attempts'):
        for name, expected in record['attempts'][-1].get('artifacts_sha256', {}).items():
            path = inside(folder / name)
            if not path.is_file() or digest(path) != expected:
                raise RuntimeError('recorded case artifact changed or missing: ' + str(path))


def completion(folder, floods):
    """Verify full history and the final saved model state, not just process exit."""
    if (folder / 'status.txt').read_text().strip() != 'complete {} floods'.format(floods):
        raise ValueError('model completion status does not match requested floods')
    if (folder / 'checkpoint.bin').stat().st_size == 0:
        raise ValueError('completed flood history lacks a nonempty restart checkpoint')
    with (folder / 'summary.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    if [int(row['flood']) for row in rows] != list(range(1, floods + 1)):
        raise ValueError('summary must contain each requested flood exactly once')
    for row in rows:
        for key in ('water_storage', 'water_residual', 'sediment_residual', 'solid_sediment_residual'):
            if not math.isfinite(float(row[key])):
                raise ValueError('nonfinite conservation diagnostic: ' + key)
    values = {}
    for line in (folder / 'parameters.txt').read_text().splitlines():
        key, value = line.split(' ', 1)
        if key != 'command':
            values[key] = value
    snapshot = folder / 'fields_{:04d}.bin'.format(floods)
    with snapshot.open('rb') as stream:
        nx, ny, nodes, number = struct.unpack('=4i', stream.read(16))
        dx, elapsed, slope = struct.unpack('=3d', stream.read(24))
    if number != floods or nx <= 0 or ny <= 0 or nodes < 2 or snapshot.stat().st_size != 40 + 16 * nx * ny:
        raise ValueError('invalid final snapshot header or length')
    if not all(math.isfinite(v) for v in (dx, elapsed, slope)):
        raise ValueError('nonfinite final snapshot metadata')
    if abs(elapsed - floods * float(values['duration'])) > 1e-5 or dx != float(values['dx']):
        raise ValueError('final snapshot time or resolution does not match completed run')
    with (folder / 'channel_{:04d}.csv'.format(floods)).open() as stream:
        if len(list(csv.DictReader(stream))) != nodes:
            raise ValueError('final channel snapshot has the wrong section count')
    return {'completed_floods': floods, 'final_elapsed_seconds': elapsed,
            'scope': 'completed numerical calculation; scientific agreement is assessed separately'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, default=8)
    parser.add_argument('--data-root', default='data')
    parser.add_argument('--runs', help='all, or comma-separated IDs; resume defaults to original selection')
    parser.add_argument('--floods', type=int, help='fresh default 580; resume may extend but never shorten')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--prepare-only', action='store_true', help='freeze and compile, without starting a case')
    parser.add_argument('--config', help='fresh default config/physics.txt')
    parser.add_argument('--runs-table', help='fresh default config/runs.csv')
    args = parser.parse_args()
    if args.jobs < 1 or (args.floods is not None and args.floods < 1):
        parser.error('jobs and floods must be positive')
    data = inside(args.data_root)
    env = environment()
    data.mkdir(parents=True, exist_ok=True)
    lock = (data / '.suite.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error('another suite runner holds this output directory')
    manifest_path = data / 'suite_manifest.json'
    if args.resume:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('format') != 2:
            parser.error('resume requires a frozen-source version-2 suite manifest')
        provenance = manifest['provenance']
        verify_inputs(data, provenance)
        for supplied, key in [(args.config, 'config_sha256'), (args.runs_table, 'runs_table_sha256')]:
            if supplied and digest(inside(supplied)) != provenance[key]:
                parser.error('explicit resume input differs from the frozen input: ' + key)
        floods = args.floods or manifest['requested_floods']
        if floods < manifest['requested_floods']:
            parser.error('resume cannot shorten the requested history')
    else:
        if any(path.name != '.suite.lock' for path in data.iterdir()):
            parser.error('fresh runs require an empty output root; use --resume for an existing suite')
        floods = args.floods or 580
        provenance = prepare(data, inside(args.config or 'config/physics.txt'), inside(args.runs_table or 'config/runs.csv'), env)
        manifest = {'format': 2, 'utc_created': utc(), 'provenance': provenance, 'cases': [], 'invocations': []}
    verify_inputs(data, provenance)
    inputs, executable = data / '_inputs', data / '_inputs/ridge'
    with (inputs / 'runs.csv').open() as stream:
        table = list(csv.DictReader(stream))
    available = {int(row['run']): row for row in table}
    if len(available) != len(table) or not available:
        parser.error('runs table has duplicate IDs or no cases')
    requested = args.runs or (','.join(map(str, manifest['selected_runs'])) if args.resume else 'all')
    wanted = sorted(available) if requested == 'all' else [int(value) for value in requested.split(',')]
    if not wanted or len(set(wanted)) != len(wanted) or any(ident not in available for ident in wanted):
        parser.error('unknown, duplicate, or empty run selection')
    if args.resume and any(ident not in manifest['selected_runs'] for ident in wanted):
        parser.error('resume cannot add cases outside the original suite selection')
    records = {record['run']: record for record in manifest['cases']}
    for ident in wanted:
        folder = inside(data / ('run%02d' % ident))
        pid = live_case(folder)
        if pid:
            parser.error('run%02d is still live as PID %d; do not start a duplicate' % (ident, pid))
        status_path = folder / 'process_status.json'
        if args.resume and status_path.exists():
            status = json.loads(status_path.read_text())
            if status.get('run') != ident or status.get('configuration') != available[ident]:
                raise RuntimeError('case status does not match its frozen configuration')
            if 'current_attempt' in status:
                interrupted_attempt = status.pop('current_attempt')
                interrupted_attempt.update(state='interrupted', utc_observed_terminal=utc(),
                                           error='recorded process is no longer live at resume audit')
                status['attempts'].append(interrupted_attempt)
                status['state'] = 'interrupted'
            else:
                verify_artifacts(folder, status)
            records[ident] = status
        records.setdefault(ident, {'run': ident, 'configuration': available[ident], 'state': 'prepared', 'attempts': []})
    manifest.update(requested_floods=floods, selected_runs=manifest.get('selected_runs', sorted(wanted)),
                    jobs=args.jobs, state='prepared' if args.prepare_only else 'running')
    invocation = {'utc_start': utc(), 'arguments': vars(args), 'runner_pid': os.getpid(),
                  'runner_start_ticks': process_identity(os.getpid()),
                  'runner_sha256': digest(pathlib.Path(__file__).resolve())}
    manifest['invocations'].append(invocation)
    manifest['cases'] = sorted(records.values(), key=lambda row: row['run'])
    save(manifest_path, manifest)
    if args.prepare_only:
        print('prepared exact-source executable: ' + str(executable), flush=True)
        return 0

    interrupted = threading.Event()
    children, guard = {}, threading.Lock()
    def stop(signum, unused):
        interrupted.set()
        with guard:
            for process in children.values():
                if process.poll() is None:
                    process.terminate()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    def run(ident):
        folder = inside(data / ('run%02d' % ident))
        record = json.loads(json.dumps(records[ident]))
        attempt = {'utc_start': utc(), 'state': 'running', 'requested_floods': floods}
        started = time.monotonic()
        try:
            try:
                evidence = completion(folder, floods)
                record.update(state='complete', verification=evidence)
                return record
            except (OSError, ValueError, KeyError, struct.error):
                pass
            checkpoint = folder / 'checkpoint.bin'
            if folder.exists() and not checkpoint.exists() and (folder / 'summary.csv').exists():
                with (folder / 'summary.csv').open() as stream:
                    rows = list(csv.DictReader(stream))
                if rows:
                    raise RuntimeError('completed diagnostics exist without a checkpoint; use a new output root')
                # A verified-terminal failure before the first complete flood has no restart state.
                stamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')
                archive = inside(data / '_failed_attempts' / ('run%02d-%s' % (ident, stamp)))
                archive.parent.mkdir(exist_ok=True)
                folder.rename(archive)
                attempt['preserved_failed_attempt'] = str(archive.relative_to(data))
            folder.mkdir(exist_ok=True)
            verify_inputs(data, provenance)
            command = [str(executable), '--config', str(inputs / 'physics.txt'), '--runs', str(inputs / 'runs.csv'),
                       '--run', str(ident), '--floods', str(floods), '--out', str(folder)]
            if checkpoint.exists():
                command += ['--resume', '1']
            attempt['command'] = command
            if interrupted.is_set():
                raise RuntimeError('suite interrupted before case launch')
            with (folder / 'run.log').open('a') as log:
                process = subprocess.Popen(command, cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
                with guard:
                    children[ident] = process
                attempt.update(pid=process.pid, process_start_ticks=process_identity(process.pid))
                record.update(state='running', pid=process.pid, process_start_ticks=attempt['process_start_ticks'], command=command)
                save(folder / 'process_status.json', dict(record, current_attempt=attempt))
                print('started run%02d pid=%d' % (ident, process.pid), flush=True)
                while True:
                    try:
                        attempt['exit_code'] = process.wait(timeout=1)
                        break
                    except subprocess.TimeoutExpired:
                        if interrupted.is_set():
                            process.terminate()
                with guard:
                    children.pop(ident, None)
            if attempt['exit_code']:
                raise RuntimeError('model process exited with code ' + str(attempt['exit_code']))
            attempt['verification'] = completion(folder, floods)
            attempt['state'] = 'complete'
        except Exception as error:
            attempt.update(state='interrupted' if interrupted.is_set() else 'failed', error=str(error))
        attempt.update(utc_end=utc(), wall_seconds=time.monotonic() - started)
        if folder.exists():
            attempt['artifacts_sha256'] = {str(path.relative_to(folder)): digest(path) for path in sorted(folder.iterdir())
                                          if path.is_file() and path.name not in ('process_status.json', 'checkpoint.tmp', 'progress.tmp')}
        record['attempts'].append(attempt)
        record.update(state=attempt['state'], exit_code=attempt.get('exit_code'), utc_end=attempt['utc_end'])
        if folder.exists():
            save(folder / 'process_status.json', record)
        print('finished run%02d state=%s wall=%.1fs' % (ident, record['state'], attempt['wall_seconds']), flush=True)
        return record

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run, ident) for ident in wanted]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            records[result['run']] = result
            manifest['cases'] = sorted(records.values(), key=lambda row: row['run'])
            save(manifest_path, manifest)
    # A subset resume must not mark unextended cases as completing a longer suite.
    for record in records.values():
        if record['state'] == 'complete':
            try:
                folder = inside(data / ('run%02d' % record['run']))
                verify_artifacts(folder, record)
                record['verification'] = completion(folder, floods)
            except (OSError, ValueError, RuntimeError, KeyError, struct.error) as error:
                record.update(state='incomplete', error=str(error))
    failed = any(record['state'] != 'complete' for record in records.values())
    manifest.update(utc_end=utc(), state='interrupted' if interrupted.is_set() else 'incomplete' if failed else 'complete')
    invocation['utc_end'] = utc()
    save(manifest_path, manifest)
    return int(failed or interrupted.is_set())


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print('ERROR: ' + str(error), flush=True)
        raise SystemExit(1)
