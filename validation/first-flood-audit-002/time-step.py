#!/usr/bin/env python3
"""Replay the completed first-flood CFL comparison using only adjacent retained files."""
import sys
sys.dont_write_bytecode = True
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import tarfile

CASES = ('baseline250', 'time250_cfl02')
BINARY = 'b3d984881a2f82757ff9bb6ca7c15f9e3c28e3d34106ae477fe7c06af6f8099c'
ARTIFACTS = ('channel_0001.csv', 'checkpoint.bin', 'fields_0001.bin', 'parameters.txt',
             'peak_channel_0001.csv', 'peak_fields_0001.bin', 'progress.json',
             'remap_budget.csv', 'run.log', 'status.txt', 'summary.csv')
SIGNATURE_KEYS = ('length width dx channel_width slope initial_depth duration qmin qmax '
                  'channel_chezy floodplain_chezy A C E migration_scale perturbation cfl '
                  'max_dt porosity rho_s tau_critical sand_d silt_ws clay_d diffusion_scale '
                  'concentration_scale seed run fine migration viscosity').split()
SCOPE = ('Completed first-flood CFL sensitivity only; no temporal-convergence order, '
         '580-flood behavior, or manuscript-panel assessment.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def csv_rows(blob):
    rows = list(csv.DictReader(io.StringIO(blob.decode())))
    require(all(None not in row and all(value is not None for value in row.values()) for row in rows),
            'malformed CSV row')
    return [{key: float(value) for key, value in row.items()} for row in rows]


def one_row(blob):
    rows = csv_rows(blob)
    require(len(rows) == 1 and rows[0]['flood'] == 1 and
            all(math.isfinite(v) for v in rows[0].values()), 'expected one finite first-flood row')
    return rows[0]


def half_ulp(value):
    """Conservative float32 storage error; excludes separate arithmetic error."""
    bits = struct.unpack('<I', struct.pack('<f', value))[0]
    if value == 0:
        return 2. ** -150
    up = struct.unpack('<f', struct.pack('<I', bits + (-1 if value < 0 else 1)))[0]
    down = struct.unpack('<f', struct.pack('<I', bits + (1 if value < 0 else -1)))[0]
    return .5 * max(abs(up - value), abs(value - down))


def field(blob, parameters, phase):
    require(len(blob) >= 40, 'truncated raster header')
    nx, ny, nodes, flood, dx, clock, slope = struct.unpack('<4i3d', blob[:40])
    require((nx, ny, nodes, flood, dx, clock, slope) ==
            (288, 192, 289, 1, 250., phase * parameters['duration'], parameters['slope']),
            'unexpected raster geometry or clock')
    require(len(blob) == 40 + 16 * nx * ny, 'incorrect raster payload size')
    cells = list(struct.iter_unpack('<4f', blob[40:]))
    require(all(all(math.isfinite(v) for v in c) and c[1] >= 0 and c[2] >= 0 and
                c[3] in (0, 1) for c in cells), 'negative/nonfinite raster or nonbinary mask')
    return dict(nx=nx, ny=ny, channel_nodes=nodes, flood=flood, dx_m=dx,
                elapsed_seconds=clock, slope=slope), cells


def snapshot(metadata, cells):
    nx, ny, dx = metadata['nx'], metadata['ny'], metadata['dx_m']
    fp = [c for c in cells if c[3] == 0]
    count = len(fp)
    mean = math.fsum(c[1] for c in fp) / count
    mean_error = math.fsum(half_ulp(c[1]) for c in fp) / count
    faces = wet = certain = possible = 0
    for j in range(ny):
        for i in range(nx):
            k = j * nx + i
            for n in ((k + 1,) if i + 1 < nx else ()) + ((k + nx,) if j + 1 < ny else ()):
                a, b = cells[k], cells[n]
                if a[3] == b[3]:
                    continue
                channel, bank = (a, b) if a[3] else (b, a)
                stage = channel[0] + channel[1] - bank[0]
                dh = half_ulp(bank[1])
                ds = half_ulp(channel[0]) + half_ulp(channel[1]) + half_ulp(bank[0])
                faces += 1
                wet += int(bank[1] > .001 and stage > .001)
                certain += int(bank[1] - dh > .001 and stage - ds > .001)
                possible += int(bank[1] + dh > .001 and stage + ds > .001)
    require(faces > 0, 'snapshot has no bank interface')
    wet_count = sum(c[1] > .001 for c in fp)
    return dict(metadata=metadata, floodplain_cells=count, floodplain_area_m2=count * dx ** 2,
                mean_floodplain_depth_m=mean, mean_depth_storage_bound_m=mean_error,
                interface_faces=faces, wet_faces=wet, definitely_wet_faces=certain,
                possibly_wet_faces=possible, reconstructed_alpha_m=mean * faces / wet if wet else None,
                alpha_storage_interval_m=[(mean - mean_error) * faces / possible if possible else None,
                                          (mean + mean_error) * faces / certain if certain else None],
                floodplain_water_volume_m3=math.fsum(c[1] for c in fp) * dx ** 2,
                inundated_area_m2=wet_count * dx ** 2,
                inundated_area_storage_interval_m2=[
                    sum(c[1] - half_ulp(c[1]) > .001 for c in fp) * dx ** 2,
                    sum(c[1] + half_ulp(c[1]) > .001 for c in fp) * dx ** 2],
                event_deposit_bulk_volume_m3=math.fsum(c[2] for c in fp) * dx ** 2,
                event_deposit_bulk_volume_storage_bound_m3=math.fsum(half_ulp(c[2]) for c in fp) * dx ** 2)


def checkpoint(blob, parameters, end_cells):
    at = 0
    def get(fmt):
        nonlocal at
        require(at + struct.calcsize('<' + fmt) <= len(blob), 'truncated checkpoint payload')
        value = struct.unpack_from('<' + fmt, blob, at)
        at += struct.calcsize('<' + fmt)
        return value[0] if len(value) == 1 else value
    length = get('Q')
    require(0 < length <= 4096, 'invalid checkpoint signature size')
    signature = blob[at:at + length].decode().split()
    at += length
    require(len(signature) == len(SIGNATURE_KEYS) + 1 and signature[0] == 'ridge-checkpoint-v2',
            'unrecognized checkpoint signature')
    require(all(float(value) == parameters[key] for key, value in zip(SIGNATURE_KEYS, signature[1:])),
            'checkpoint signature differs from archived parameters')
    flood, clock, steps, channel_steps, cutoffs = get('i'), get('d'), get('q'), get('q'), get('i')
    external, bank = get('4d'), get('3d')
    deposited, forcing, recycled, water_correction, mass_correction = get('5d')
    nodes = get('Q')
    size = len(end_cells)
    require(flood == 1 and clock == parameters['duration'] and 2 <= nodes <= 100000 and
            len(blob) == at + 64 * nodes + 56 * size, 'checkpoint clock or complete payload size differs')
    line = [get('2d') for _ in range(nodes)]
    channel = [get('6d') for _ in range(nodes)]
    bed = [get('d') for _ in range(size)]
    water = [get('6d') for _ in range(size)]
    require(at == len(blob), 'unexpected checkpoint trailing bytes')
    scalars = list(external) + list(bank) + [deposited, forcing, recycled, water_correction, mass_correction]
    require(all(math.isfinite(v) for v in scalars + bed) and
            all(all(math.isfinite(v) for v in row) for row in line + channel + water),
            'nonfinite checkpoint state')
    require(all(row[i] >= 0 for row in channel + water for i in (0, 3, 4, 5)) and
            all(v >= 0 for v in bank) and deposited >= 0, 'negative checkpoint inventory')
    dx, radius = parameters['dx'], parameters['channel_width'] / 2
    nx, ny = int(parameters['length'] / dx), int(parameters['width'] / dx)
    mask = [False] * size
    for a, b in zip(line, line[1:]):
        vx, vy = b[0] - a[0], b[1] - a[1]
        square = vx * vx + vy * vy
        require(square > 0, 'duplicate checkpoint channel nodes')
        for j in range(max(0, int(math.floor((min(a[1], b[1]) - radius) / dx))),
                       min(ny - 1, int(math.floor((max(a[1], b[1]) + radius) / dx))) + 1):
            for i in range(max(0, int(math.floor((min(a[0], b[0]) - radius) / dx))),
                           min(nx - 1, int(math.floor((max(a[0], b[0]) + radius) / dx))) + 1):
                px, py = (i + .5) * dx - a[0], (j + .5) * dx - a[1]
                w = max(0., min(1., (px * vx + py * vy) / square))
                if math.hypot(px - w * vx, py - w * vy) <= radius:
                    mask[j * nx + i] = True
    return dict(format='ridge-checkpoint-v2', parameter_signature_verified=True,
                complete_payload_verified=True, finite_payload=True,
                water_and_suspended_inventory_nonnegative=True, flood=flood, elapsed_seconds=clock,
                steps=steps, channel_steps=channel_steps, cutoffs=cutoffs,
                net_external_water_m3=external[0], net_external_sediment_by_class_kg=list(external[1:]),
                bank_by_class_kg=list(bank), bank_mass_kg=math.fsum(bank), deposited_mass_kg=deposited,
                bed_forcing_mass_kg=forcing, recycled_mass_kg=recycled,
                water_correction_m3=water_correction, mass_correction_kg=mass_correction,
                post_channel_nodes=nodes, post_channel_min_depth_m=min(c[0] for c in channel),
                post_channel_max_depth_m=max(c[0] for c in channel),
                captured_floodplain_cells=sum(c[3] == 0 and m for c, m in zip(end_cells, mask)),
                abandoned_channel_cells=sum(c[3] == 1 and not m for c, m in zip(end_cells, mask)))


def normalization(parameters):
    p, n = parameters, 20000
    integral = math.fsum((1 if i in (0, n) else 4 if i % 2 else 2) *
                        (p['qmin'] + (p['qmax'] - p['qmin']) * math.sin(math.pi * i / n) ** 2) ** 2.5
                        for i in range(n + 1)) * p['duration'] / (3 * n)
    return dict(prescribed_water_input_m3=p['duration'] * (p['qmin'] + p['qmax']) / 2,
                prescribed_sediment_input_kg=p['C'] * p['concentration_scale'] * integral,
                sediment_simpson_intervals=n)


def compare_fields(a, b, dx):
    require([c[3] for c in a] == [c[3] for c in b], 'comparison channel masks differ')
    pairs = [(x, y) for x, y in zip(a, b) if x[3] == 0]
    out = dict(floodplain_cells=len(pairs), floodplain_area_m2=len(pairs) * dx ** 2, fields={})
    for index, name in enumerate(('bed', 'water_depth', 'event_deposit')):
        delta = [y[index] - x[index] for x, y in pairs]
        error = [half_ulp(x[index]) + half_ulp(y[index]) for x, y in pairs]
        out['fields'][name] = dict(mean_signed_difference_m=math.fsum(delta) / len(delta),
                                  mean_absolute_difference_m=math.fsum(abs(v) for v in delta) / len(delta),
                                  maximum_absolute_difference_m=max(abs(v) for v in delta),
                                  mean_difference_storage_bound_m=math.fsum(error) / len(error),
                                  maximum_difference_storage_bound_m=max(error))
    return out


def verify(folder):
    """Return analysis/evidence from the retained archive; never consult original paths."""
    folder = Path(folder)
    capture_bytes = (folder / 'time-step-capture.json').read_bytes()
    capture = json.loads(capture_bytes.decode())
    archive_bytes = (folder / 'time-step-inputs.tar.xz').read_bytes()
    require(capture['archive']['file'] == 'time-step-inputs.tar.xz' and
            len(archive_bytes) == capture['archive']['bytes'] and
            sha(archive_bytes) == capture['archive']['sha256'], 'retained archive size or hash differs')
    require(capture['source_identity']['corrected_binary_sha256'] == BINARY and
            capture['source_identity']['byte_order'] == 'little' and
            capture['source_identity']['pointer_and_size_t_bytes'] == 8, 'incorrect captured executable/layout identity')
    expected = capture['archive']['member_sha256']
    required = {'validation/runs/' + case + '/' + filename
                for case in CASES for filename in ARTIFACTS + ('process_status.json',)}
    require(set(expected) == required and capture['archive']['members'] == 24,
            'capture does not describe exactly the two corrected completed cases')
    members = {}
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:xz') as archive:
        for item in archive:
            require(item.isfile() and item.name in required and item.name not in members,
                    'unsafe, duplicate, or unexpected archive member')
            blob = archive.extractfile(item).read()
            require(sha(blob) == expected[item.name], 'archive member hash differs: ' + item.name)
            members[item.name] = blob
    require(set(members) == required, 'retained archive is incomplete')
    cases, arrays, geometry = {}, {}, {}
    for name, cfl in zip(CASES, (.4, .2)):
        prefix = 'validation/runs/' + name + '/'
        data = {filename: members[prefix + filename] for filename in ARTIFACTS + ('process_status.json',)}
        process = json.loads(data['process_status.json'].decode())
        require(process['state'] == 'complete' and process['exit_code'] == 0 and
                process['binary_sha256'] == BINARY and process['name'] == name,
                'case lacks the corrected completed process identity')
        require(set(process['artifact_sha256']) == set(ARTIFACTS) and
                all(sha(data[f]) == process['artifact_sha256'][f] for f in ARTIFACTS),
                'completed process artifact hashes differ')
        identity = capture['source_identity']['cases'][name]
        require(identity['process_pid'] == process['pid'] and
                identity['original_command'] == process['command'] and
                identity['utc_started'] == process['utc_started'] and
                identity['utc_finished'] == process['utc_finished'] and
                all(identity['source_files'][f]['sha256'] == sha(blob) and
                    identity['source_files'][f]['bytes'] == len(blob) for f, blob in data.items()),
                'capture identity differs from retained terminal records')
        command = process['command']
        for flag, expected_value in (('--floods', '1'), ('--run', '11')):
            require(flag in command and command.index(flag) + 1 < len(command) and
                    command[command.index(flag) + 1] == expected_value, 'unexpected original process command')
        parameters = {}
        for line in data['parameters.txt'].decode().splitlines():
            key, value = line.split(' ', 1)
            if key != 'command':
                require(key not in parameters, 'duplicate numerical parameter')
                parameters[key] = float(value)
        require(all(math.isfinite(v) for v in parameters.values()) and
                all(parameters[k] == v for k, v in dict(cfl=cfl, floods=1, run=11, dx=250,
                    length=72000, width=48000, duration=1728000, A=0, C=.003, E=1, fine=0).items()),
                'unexpected first-flood parameters')
        require(data['status.txt'].decode().strip() == 'complete 1 floods', 'case status is incomplete')
        summary, remap = one_row(data['summary.csv']), one_row(data['remap_budget.csv'])
        phases, arrays[name], geometry[name] = {}, {}, {}
        for phase, fraction, prefix_file in (('peak', .6, 'peak_'), ('end', 1., '')):
            metadata, cells = field(data[prefix_file + 'fields_0001.bin'], parameters, fraction)
            rows = csv_rows(data[prefix_file + 'channel_0001.csv'])
            require(len(rows) == metadata['channel_nodes'] and
                    all(all(math.isfinite(v) for v in row.values()) and row['water_depth'] >= 0 and
                        row['control_area'] > 0 for row in rows), 'invalid matching channel snapshot')
            geometry[name][phase] = [(r['x'], r['y']) for r in rows]
            phases[phase], arrays[name][phase] = snapshot(metadata, cells), cells
        require(geometry[name]['peak'] == geometry[name]['end'] and
                [c[3] for c in arrays[name]['peak']] == [c[3] for c in arrays[name]['end']],
                'channel geometry changed within the first flood')
        inputs = normalization(parameters)
        water, sediment = inputs['prescribed_water_input_m3'], inputs['prescribed_sediment_input_kg']
        normalized = dict(pre_water=summary['water_residual'] / water,
                          pre_suspension_plus_deposition=summary['sediment_residual'] / sediment,
                          pre_full_solid=summary['solid_sediment_residual'] / sediment,
                          post_water=remap['post_water_residual'] / water,
                          post_suspension_plus_deposition=remap['post_sediment_residual'] / sediment,
                          post_full_solid=remap['post_solid_sediment_residual'] / sediment)
        stored = checkpoint(data['checkpoint.bin'], parameters, arrays[name]['end'])
        require(stored['steps'] == summary['steps'] and stored['channel_steps'] == summary['channel_steps'],
                'checkpoint and completed summary step counts differ')
        cases[name] = dict(parameters=parameters, process=process, summary=summary, remap=remap,
                           prescribed_inputs=inputs, signed_residuals_over_prescribed_input=normalized,
                           checkpoint=stored, peak=phases['peak'], end=phases['end'])
    baseline, candidate = (cases[name] for name in CASES)
    differences = {key: [baseline['parameters'].get(key), candidate['parameters'].get(key)]
                   for key in set(baseline['parameters']) | set(candidate['parameters'])
                   if baseline['parameters'].get(key) != candidate['parameters'].get(key)}
    require(differences == {'cfl': [.4, .2]} and geometry[CASES[0]] == geometry[CASES[1]],
            'cases differ in more than CFL or initial channel geometry')
    metrics = ('alpha', 'interface_fraction', 'mean_water', 'beta', 'ridge_height', 'channel_depth',
               'water_storage', 'steps', 'channel_steps', 'wall_seconds')
    percentages = {key: 100 * (candidate['summary'][key] / baseline['summary'][key] - 1)
                   if baseline['summary'][key] else None for key in metrics}
    percentages['deposited_mass'] = 100 * (candidate['checkpoint']['deposited_mass_kg'] /
                                         baseline['checkpoint']['deposited_mass_kg'] - 1)
    return dict(format=1, status='verified', scope=SCOPE, processor_sha256=sha(Path(__file__).read_bytes()),
                evidence=dict(captured_utc=capture['captured_utc'], capture_sha256=sha(capture_bytes),
                              archive_sha256=sha(archive_bytes), member_sha256=expected,
                              binary_sha256=BINARY, original_source_identity=capture['source_identity']),
                parameter_differences=differences, cases=cases,
                half_cfl_relative_to_baseline_percent=percentages,
                same_grid_fields={phase: compare_fields(arrays[CASES[0]][phase], arrays[CASES[1]][phase], 250.)
                                  for phase in ('peak', 'end')},
                method=dict(difference='half-CFL minus baseline; percentage denominator is baseline',
                    snapshot_phase='peak is day 12; end is day 20 before migration/aggradation; checkpoint is after remap',
                    field_domain='identical physical floodplain cells, including dry cells; fixed within-flood channel mask',
                    storage_bounds='Conservative float32 half-ULP storage bounds only; exclude discretization, separate float64 arithmetic error, and CSV rounding.',
                    deposit_volume='Bulk event-deposit volume includes pore space; peak deposition is cumulative through day 12.',
                    normalization='Gross prescribed upstream input for one sinusoidal flood, excluding recycling, outlet flux, and signed bed forcing. This is not the checkpoint net external ledger.',
                    time_step='CFL halves a stability bound; adaptive substeps and other limits need not halve every realized step.',
                    arithmetic='Saved float32 values promoted to Python float; reductions use math.fsum.',
                    checkpoint_layout='Captured little-endian v2, 64-bit size_t and step counters; full payload checked.'))


def main():
    require(len(sys.argv) <= 2, 'usage: time-step.py [retained-folder]')
    folder = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).resolve().parent
    result = verify(folder)
    require(json.loads((folder / 'time-step.json').read_text()) == result,
            'saved analysis differs from verified archive replay')
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
