#!/usr/bin/env python3
"""Run full first-flood numerical checks, separately from manuscript simulations."""
import argparse
import array
import concurrent.futures
import csv
import datetime
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import struct
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = {
    'baseline250': {},
    'coarse500': {'dx': '500'},
    'fine125': {'dx': '125'},
    'time250_cfl02': {'cfl': '0.2'},
    'tau005': {'tau-critical': '0.05'},
    'tau020': {'tau-critical': '0.2'},
    'concentration_half': {'concentration-scale': '0.0005'},
    'concentration_double': {'concentration-scale': '0.002'},
}


def utc():
    return datetime.datetime.utcnow().isoformat() + 'Z'


def digest(path):
    h = hashlib.sha256()
    with open(str(path), 'rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def prepare(output, executable, config):
    inputs = output / '_inputs'
    inputs.mkdir(parents=True, exist_ok=True)
    blob = executable.read_bytes()
    binary_hash = hashlib.sha256(blob).hexdigest()
    frozen = ROOT / 'validation' / '.bin' / ('ridge-' + binary_hash)
    frozen.parent.mkdir(parents=True, exist_ok=True)
    if not frozen.exists():
        frozen.write_bytes(blob)
        frozen.chmod(0o755)
    sources = sorted(list((ROOT / 'src').glob('*.cpp')) + list((ROOT / 'src').glob('*.hpp')))
    if any(f.stat().st_mtime > executable.stat().st_mtime for f in sources):
        raise RuntimeError('sources are newer than executable: build before preparing validation')
    provenance = {'utc_created': utc(), 'binary_sha256': binary_hash,
                  'executable': str(frozen.relative_to(ROOT)),
                  'source_sha256': {str(f.relative_to(ROOT)): digest(f) for f in sources},
                  'source_hash_scope': 'files observed when the built executable was frozen'}
    for source, name in ((config, 'physics.txt'), (ROOT / 'config/runs.csv', 'runs.csv')):
        shutil.copy2(str(source), str(inputs / name))
        provenance[name + '_sha256'] = digest(source)
    save(inputs / 'provenance.json', provenance)
    return provenance


def parameters(path):
    result = {}
    for line in path.read_text().splitlines():
        key, value = line.split(' ', 1)
        if key != 'command':
            result[key] = float(value)
    return result


def fields(path):
    with open(str(path), 'rb') as stream:
        nx, ny, nodes, flood = struct.unpack('=4i', stream.read(16))
        dx, elapsed, slope = struct.unpack('=3d', stream.read(24))
        values = array.array('f')
        values.frombytes(stream.read())
    if len(values) != 4 * nx * ny:
        raise RuntimeError('incorrect field payload length: ' + str(path))
    return {'nx': nx, 'ny': ny, 'nodes': nodes, 'flood': flood,
            'dx': dx, 'elapsed_seconds': elapsed, 'slope': slope}, values


def inspect_case(folder):
    status_file = folder / 'status.txt'
    if not status_file.exists() or status_file.read_text().strip() != 'complete 1 floods':
        process_file = folder / 'process_status.json'
        if process_file.exists():
            process = json.loads(process_file.read_text())
            if process.get('state') == 'failed':
                log = (folder / 'run.log').read_text().splitlines()
                return {'state': 'failed', 'exit_code': process['exit_code'],
                        'reason': log[-1] if log else 'model process failed without log output'}
        return {'state': 'incomplete', 'reason': 'missing complete first-flood status'}
    rows = list(csv.DictReader(open(str(folder / 'summary.csv'))))
    if len(rows) != 1 or int(rows[0]['flood']) != 1:
        return {'state': 'invalid', 'reason': 'expected exactly one full flood'}
    metadata, unused = fields(folder / 'fields_0001.bin')
    p = parameters(folder / 'parameters.txt')
    if abs(metadata['elapsed_seconds'] - 1728000) > 1e-6 or p['duration'] != 1728000:
        return {'state': 'invalid', 'reason': 'the 20-day flood was not completed'}
    if p['length'] != 72000 or p['width'] != 48000:
        return {'state': 'invalid', 'reason': 'the documented full domain was not used'}
    metrics = {}
    for key, value in rows[0].items():
        number = float(value)
        metrics[key] = number if math.isfinite(number) else None
    # Independent normalization scales: prescribed upstream water and sediment
    # over this first flood. Budgets themselves are the model's double outputs.
    water_input = p['duration'] * (p['qmin'] + p['qmax']) / 2
    integral = 0.0
    n = 20000
    for i in range(n + 1):
        discharge = p['qmin'] + (p['qmax'] - p['qmin']) * math.sin(math.pi * i / n) ** 2
        integral += (1 if i in (0, n) else 4 if i % 2 else 2) * discharge ** 2.5
    sediment_input = integral * p['duration'] / (3 * n) * p['C'] * p['concentration_scale']
    budgets = {'prescribed_water_input_m3': water_input, 'prescribed_sediment_input_kg': sediment_input,
               'water_residual_over_input': metrics['water_residual'] / water_input}
    for key in ('sediment_residual', 'solid_sediment_residual'):
        budgets[key + '_over_input'] = metrics[key] / sediment_input if sediment_input else None
    return {'state': 'complete', 'parameters': p, 'metrics': metrics,
            'snapshot': metadata, 'budgets': budgets}


def compare_fields(first, second):
    a, av = fields(first / 'fields_0001.bin')
    b, bv = fields(second / 'fields_0001.bin')
    if a['dx'] < b['dx']:
        a, b, av, bv = b, a, bv, av
    ratio = int(round(a['dx'] / b['dx']))
    if a['nx'] * ratio != b['nx'] or a['ny'] * ratio != b['ny']:
        raise RuntimeError('comparison grids are not nested')
    count = 0
    total = [0.0] * 3
    maximum = [0.0] * 3
    for j in range(a['ny']):
        for i in range(a['nx']):
            coarse = 4 * (j * a['nx'] + i)
            fine = [4 * ((j * ratio + dj) * b['nx'] + i * ratio + di)
                    for dj in range(ratio) for di in range(ratio)]
            if av[coarse + 3] or any(bv[k + 3] for k in fine):
                continue
            count += 1
            for field in range(3):
                error = abs(av[coarse + field] - sum(bv[k + field] for k in fine) / len(fine))
                total[field] += error
                maximum[field] = max(maximum[field], error)
    return {'coarse_dx_m': a['dx'], 'fine_dx_m': b['dx'],
            'common_floodplain_area_m2': count * a['dx'] ** 2,
            'mean_absolute_difference_m': dict(zip(('bed', 'water_depth', 'deposition'),
                                                   [v / count if count else None for v in total])),
            'maximum_absolute_difference_m': dict(zip(('bed', 'water_depth', 'deposition'), maximum))}


def analyze(output, baseline_from=None):
    if baseline_from and not (output / 'baseline250').exists():
        ready = inspect_case(baseline_from)
        if ready['state'] == 'complete':
            shutil.copytree(str(baseline_from), str(output / 'baseline250'))
            save(output / 'baseline250' / 'import.json',
                 {'source': str(baseline_from), 'utc_imported': utc(),
                  'reason': 'reuse an independently generated first flood from the same verified binary'})
    records = {}
    for name in CASES:
        folder = output / name
        if folder.exists():
            records[name] = inspect_case(folder)
    reference = records.get('baseline250', {})
    if reference.get('state') == 'complete':
        for name, result in records.items():
            if name == 'baseline250' or result['state'] != 'complete':
                continue
            result['relative_metric_change_percent'] = {}
            for key in ('alpha', 'interface_fraction', 'mean_water', 'beta', 'ridge_height',
                        'channel_depth', 'water_storage'):
                base, value = reference['metrics'][key], result['metrics'][key]
                result['relative_metric_change_percent'][key] = 100 * (value / base - 1) if base and value is not None else None
            result['field_comparison'] = compare_fields(output / 'baseline250', output / name)
    save(output / 'comparison.json', {'utc_analyzed': utc(), 'scope': 'full first flood; not manuscript panels', 'cases': records})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='validation/runs')
    parser.add_argument('--executable', default='build/ridge')
    parser.add_argument('--config', default='config/physics.txt')
    parser.add_argument('--cases', default='baseline250,coarse500,fine125,time250_cfl02')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--prepared', action='store_true', help='use the already frozen executable and inputs')
    parser.add_argument('--baseline-from', help='reuse a verified completed baseline directory')
    parser.add_argument('--analyze-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 2:
        parser.error('validation concurrency must be one or two jobs')
    output = (ROOT / args.output).resolve()
    if not re.match(r'^/data/data[0-7]/', str(output) + '/'):
        parser.error('outputs must remain on a /data/data[n] volume')
    output.mkdir(parents=True, exist_ok=True)
    baseline = (ROOT / args.baseline_from).resolve() if args.baseline_from else None
    if args.analyze_only:
        analyze(output, baseline)
        return 0
    names = args.cases.split(',')
    if baseline:
        names = [name for name in names if name != 'baseline250']
    if any(name not in CASES for name in names) or len(set(names)) != len(names):
        parser.error('unknown or repeated case name')
    inputs = output / '_inputs'
    if args.prepared:
        provenance = json.loads((inputs / 'provenance.json').read_text())
    else:
        if (inputs / 'provenance.json').exists():
            parser.error('inputs already frozen: use --prepared or a new output directory')
        provenance = prepare(output, ROOT / args.executable, ROOT / args.config)
    frozen = ROOT / provenance['executable']
    if digest(frozen) != provenance['binary_sha256']:
        raise RuntimeError('immutable binary digest changed')
    for name in ('physics.txt', 'runs.csv'):
        if digest(inputs / name) != provenance[name + '_sha256']:
            raise RuntimeError('frozen input changed: ' + name)
    if baseline:
        proof_path = inputs / 'baseline-process.json'
        if not proof_path.exists():
            proof_path = baseline / 'process_status.json'
        proof = json.loads(proof_path.read_text())
        if proof.get('executable_sha256', proof.get('binary_sha256')) != provenance['binary_sha256']:
            raise RuntimeError('the reused baseline does not have the same verified executable')
    for name in names:
        if (output / name).exists():
            parser.error('case directory already exists; inspect its live process or analyze existing output: ' + name)
    manifest = {'utc_started': utc(), 'provenance': provenance, 'jobs': args.jobs,
                'scope': 'full first flood; floodplain grid varies, channel node spacing remains 250 m',
                'baseline_from': str(baseline) if baseline else None, 'cases': []}
    save(output / 'validation_manifest.json', manifest)

    def run(name):
        folder = output / name
        folder.mkdir()
        command = [str(frozen), '--config', str(inputs / 'physics.txt'), '--runs', str(inputs / 'runs.csv'),
                   '--run', '11', '--floods', '1', '--out', str(folder)]
        for key, value in CASES[name].items():
            command.extend(('--' + key, value))
        record = {'name': name, 'command': command, 'utc_started': utc(), 'state': 'running',
                  'binary_sha256': provenance['binary_sha256']}
        started = time.time()
        env = dict(os.environ, TMPDIR=str(ROOT / 'tmp'))
        with open(str(folder / 'run.log'), 'w') as log:
            process = subprocess.Popen(command, cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
            record['pid'] = process.pid
            save(folder / 'process_status.json', record)
            print('started %s pid=%d' % (name, process.pid), flush=True)
            record['exit_code'] = process.wait()
        record.update(utc_finished=utc(), wall_seconds=time.time() - started)
        record['state'] = 'complete' if record['exit_code'] == 0 and inspect_case(folder)['state'] == 'complete' else 'failed'
        record['artifact_sha256'] = {str(f.name): digest(f) for f in folder.iterdir() if f.is_file() and f.name != 'process_status.json'}
        save(folder / 'process_status.json', record)
        print('finished %s state=%s wall=%.1fs' % (name, record['state'], record['wall_seconds']), flush=True)
        return record

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = [pool.submit(run, name) for name in names]
        for future in concurrent.futures.as_completed(pending):
            manifest['cases'].append(future.result())
            save(output / 'validation_manifest.json', manifest)
            analyze(output, baseline)
    manifest['utc_finished'] = utc()
    save(output / 'validation_manifest.json', manifest)
    analyze(output, baseline)
    return int(any(case['state'] != 'complete' for case in manifest['cases']))


if __name__ == '__main__':
    raise SystemExit(main())
