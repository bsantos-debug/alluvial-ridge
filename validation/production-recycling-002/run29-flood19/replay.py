#!/usr/bin/env python3
"""Offline native-inventory reconciliation of the retained run29/flood19 endpoint."""
import argparse
import ast
import csv
import hashlib
import io
import json
import math
import os
import struct
import tarfile
from pathlib import Path

CAPTURE = 'e41539cb8ef637c4191847442ce92c17c4aef47c17bbe13bf6a314c1748f6ee6'
ARCHIVE = '496afe873e715c04633b304c0e69e0d364ea9ee98874871f87067fd604c66534'
SOURCES = {
    'src/finite_volume.hpp': '57ac8606cd856046e13563fc0f07417943990fbc4f43340baf6f44aad427775d',
    'src/main.cpp': '812058d4ff97b618da08830e44a8704e4dc3a1431e0245136a301a0cd4375c90',
    'src/migration.hpp': '047475c7a53b933ccc83273e0576a820f681382fdf22b244a501006c68bf7196',
    'src/model.hpp': 'e12bb6c79a9e70ca53d555fc2d5cfcefed9b0cf2f8a3f7567defd650cc039a15',
    'src/sediment.hpp': '3c698eaf05771c09a26a152697fdcdacacf59b08ad18345efcdcaf1e35ccd4d2'}
PINS = dict(SOURCES, **{
    'ridge': 'b3d984881a2f82757ff9bb6ca7c15f9e3c28e3d34106ae477fe7c06af6f8099c',
    'decoder-source.py': 'd6dc1e7833783c09039d7ce41854ac51de3642c6cfd046298dc5c2b35b1f31fd',
    'inventory-helper-source.py': 'c9bee19b0d821c466809e84081fd46a3215c89b35f9cc98af3f838733a10e987',
    'guard-source.py': '035304ef672a640e3c3053a16e137dbb19c8844471c1e8da6adbdcec2c579039',
    'inputs/checkpoint.bin': 'bdcca2174098893b69c6483ea09193b26bbede104a7ca967e5a6d8a63e3ff66e',
    'inputs/parameters.txt': 'b2152d0382a5c8c009032db24ffc4aec535e0dfb331f4bbbcab8ba711076b724',
    'inputs/process_status.json': '650916687250621549e9dff966c79e8c5c47ca3c8289d867db20bd219ee8b0f2',
    'inputs/summary.csv': '6029e6d0d4be23e63c40440985eecb20d33993e8a91e41be09773768f65e73d8',
    'inputs/remap_budget.csv': '9edc35abfa08cbfa0b656e9b5dbbd751f2ae53887c3caf43c58a8451d082b12e',
    'observations/scalar.json': '928b7093d1387dd93936288f2c6e8bed6527117e627ef1800416a14dfcc76a9a',
    'observations/comparison.json': '729a2dbc45cc3ae2c5c412773d41591bb3150425c948e4c1b2d90ea16201f2fe',
    'observations/seed.json': 'bdbe219c973a193cbb597d4bfe95bf44dabe0d9c3bdea6a9b21f8c00edc9a280',
    'observations/original-review.py': '28e36e5c11b32dfa6d22201cf11902ef47776e50a10c8a1a22db80afbfc85086',
    'observations/original-result.json': '1a1762a745f70953a2ee2a0ea166d80b383b82986ec8096234a0d6b64f53a4db'})
KEYS = ('length width dx channel_width slope initial_depth duration qmin qmax '
        'channel_chezy floodplain_chezy A C E migration_scale perturbation cfl max_dt '
        'porosity rho_s tau_critical sand_d silt_ws clay_d diffusion_scale '
        'concentration_scale seed run fine migration viscosity').split()
ARTIFACTS = ('checkpoint.bin', 'parameters.txt', 'process_status.json', 'summary.csv', 'remap_budget.csv')
SCALARS = ('checkpoint', 'summary', 'remap', 'prescribed_hydrographs',
           'post_normalized_residuals', 'last_scalar_identity_errors', 'max_abs_scalar_identity_errors')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def finite(value):
    if isinstance(value, dict):
        return all(finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite(v) for v in value)
    return not isinstance(value, (int, float)) or math.isfinite(value)


def archive_inputs(folder):
    capture_blob = (folder / 'capture.json').read_bytes()
    require(sha(capture_blob) == CAPTURE, 'capture manifest changed')
    capture = json.loads(capture_blob)
    archive_blob = (folder / 'inputs.tar.xz').read_bytes()
    require(capture['archive'] == 'inputs.tar.xz' and capture['case'] == 29 and capture['flood'] == 19,
            'capture endpoint differs')
    require(sha(archive_blob) == capture['archive_sha256'] == ARCHIVE, 'archive changed')
    require(len(archive_blob) == capture['archive_bytes'] == 2103992, 'archive size differs')
    require(capture['member_sha256'] == PINS and set(capture['member_bytes']) == set(PINS),
            'member manifest differs')
    with tarfile.open(fileobj=io.BytesIO(archive_blob), mode='r:xz') as archive:
        entries = archive.getmembers()
        require(len(entries) == len(PINS) == 19 and {m.name for m in entries} == set(PINS),
                'missing, duplicate or unexpected archive members')
        require(all(m.isfile() and m.type in (tarfile.REGTYPE, tarfile.AREGTYPE) for m in entries),
                'nonregular archive member')
        blobs = {m.name: archive.extractfile(m).read() for m in entries}
    require(all(sha(b) == PINS[n] and len(b) == capture['member_bytes'][n] for n, b in blobs.items()),
            'member bytes or digest differ')
    return capture, blobs


def functions_only(blob, names, namespace):
    # Only these already-reviewed pure definitions execute; no archived module
    # imports, top-level observers, models, or filesystem operations execute.
    tree = ast.parse(blob)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    require(len(functions) == len(names) and {n.name for n in functions} == set(names),
            'required pure function missing or duplicated')
    module = ast.Module(body=functions)
    if 'type_ignores' in ast.Module._fields:
        module.type_ignores = []
    exec(compile(module, '<pinned-pure-functions>', 'exec'), namespace)


def bindings(blobs):
    audit = json.loads(blobs['observations/scalar.json'])
    comparison = json.loads(blobs['observations/comparison.json'])
    seed = json.loads(blobs['observations/seed.json'])
    original = json.loads(blobs['observations/original-result.json'])
    process = json.loads(blobs['inputs/process_status.json'])
    require(finite([audit, comparison, seed, original, process]), 'nonfinite JSON')
    require(audit['requested_flood'] == 19 and set(audit['cases']) == {'29'}, 'scalar endpoint differs')
    row = audit['cases']['29']; record = seed['cases']['29']
    for document in (audit, seed):
        require(document['frozen_source_sha256'] == SOURCES and document['binary_sha256'] == PINS['ridge'],
                'source/executable binding differs')
    require(row['hashes'] == {n: PINS['inputs/' + n] for n in ARTIFACTS}, 'scalar artifact binding differs')
    require(row['history'] == list(range(1, 20)) and row['stable_seconds'] >= 2 and row['cpu_ticks_delta'] > 0,
            'recorded audit history/stability/CPU guard differs')
    require(comparison['case'] == 29 and comparison['flood'] == 19 and
            comparison['result_sha256'] == PINS['observations/scalar.json'] and
            comparison['seed_sha256'] == PINS['observations/seed.json'], 'comparison binding differs')
    require(comparison['current_scalar_maps'] == {k: row[k] for k in SCALARS}, 'scalar maps disagree')
    identity = row['identity']
    require({k: identity[k] for k in record['identity']} == record['identity'] and
            comparison['current_identity'] == identity and identity['argv_exact'], 'recorded identity differs')
    require((identity['pid'], identity['start_ticks'], identity['parent']) == (3805592, 51544957, 3805340),
            'original process differs')
    require(identity['exe_sha256'] == PINS['ridge'] and identity['argv'] == process['command'] ==
            process['current_attempt']['command'] and identity['pid'] == process['pid'] and
            identity['start_ticks'] == int(process['process_start_ticks']), 'status/argv binding differs')
    argv = identity['argv']
    require(argv[argv.index('--run') + 1] == '29' and argv[argv.index('--floods') + 1] == '580' and
            '--resume' not in argv, 'original run scope differs')
    require(record['parameters_sha256'] == PINS['inputs/parameters.txt'] and
            record['process_status_sha256'] == PINS['inputs/process_status.json'], 'seed input pins differ')
    tokens = {}
    for line in blobs['inputs/parameters.txt'].decode().splitlines():
        key, value = line.split(' ', 1)
        require(key not in tokens, 'duplicate parameter'); tokens[key] = value
    p = {k: float(v) for k, v in tokens.items() if k != 'command'}
    require(set(p) == set(KEYS) | {'floods'} and finite(p), 'invalid parameter set')
    require(p['run'] == 29 and p['floods'] == 580 and p['duration'] == 1728000 and
            p['length'] == 72000 and p['width'] == 48000 and p['dx'] == 250 and
            p['A'] == .012 and p['C'] == .0003 and p['E'] == .5 and p['fine'] == 0 and
            p['concentration_scale'] == .001, 'case parameters differ')
    selected = {k: tokens[k] for k in ('A', 'C', 'E', 'fine', 'concentration_scale')}
    fractions = [.05, .20, .75] if p['fine'] else [.05, .75, .20]  # pinned model.hpp:47
    require(selected == record['parameter_tokens'] == comparison['parameter_tokens'] ==
            original['actual_parameter_tokens'], 'parameter tokens differ')
    require(fractions == record['fractions'] == comparison['class_fractions'] == original['class_fractions'],
            'class fractions differ')
    for name, section in (('summary.csv', 'summary'), ('remap_budget.csv', 'remap')):
        blob = blobs['inputs/' + name]; prefix = comparison['csv_prefixes'][name]
        rows = list(csv.DictReader(io.StringIO(blob.decode())))
        values = [{k: float(v) for k, v in r.items()} for r in rows]
        require(finite(values) and [r['flood'] for r in values] == list(range(1, 20)), 'CSV history differs')
        require(rows[-1] == comparison['current_csv_last_tokens'][name] and values[-1] == row[section],
                'CSV endpoint tokens differ')
        require(prefix['exact_prefix'] and len(blob) == prefix['current_bytes'] and
                sha(blob) == prefix['current_sha256'] and
                sha(blob[:prefix['prior_bytes']]) == prefix['prior_sha256'], 'CSV prefix binding differs')
    require(original['status'] == 'verified_bound_current_checkpoint' and original['checkpoint_flood'] == 19 and
            original['checkpoint_sha256'] == PINS['inputs/checkpoint.bin'], 'original observation differs')
    require(original['checkpoint_open_count'] == 1 and original['auditor_or_model_invocations'] == 0 and
            original['files_written'] == 0, 'original observation scope differs')
    # The original record's historical paths are provenance strings, never opened.
    historical = {'observations/scalar.json': 'tmp/continuous-observer-002/run29-flood19.json',
                  'observations/comparison.json': 'tmp/continuous-observer-002/run29-flood19-comparison.json',
                  'observations/seed.json': 'tmp/continuous-observer-002/seed-20261011T092009Z.json',
                  'ridge': 'tmp/full-rebuild-002/workspace/data/_inputs/ridge'}
    historical.update({n: 'tmp/full-rebuild-002/workspace/' + n for n in SOURCES})
    for name in ARTIFACTS:
        historical['inputs/' + name] = ('tmp/continuous-observer-002/attempts/run29-flood19/' + name
                                        if name.endswith('.csv') else
                                        'tmp/full-rebuild-002/workspace/data/run29/' + name)
    require(original['pins'] == {path: PINS[name] for name, path in historical.items()},
            'original observation pins differ')
    return row, p, selected, fractions, original, comparison


def checkpoint(blobs, row, p):
    blob = blobs['inputs/checkpoint.bin']; slen = struct.unpack_from('<Q', blob)[0]
    require(0 < slen <= 4096, 'invalid signature length')
    signature = blob[8:8+slen].decode(); words = signature.split()
    require(len(words) == 32 and words[0] == 'ridge-checkpoint-v2' and
            all(float(v) == p[k] for k, v in zip(KEYS, words[1:])), 'checkpoint signature differs')
    fmt = '<idqqi4d3d5dQ'; header = struct.unpack_from(fmt, blob, 8+slen)
    cp = row['checkpoint']; n = header[-1]; offset = 8+slen+struct.calcsize(fmt)
    expected = [cp['flood'], cp['clock'], cp['steps'], cp['channel_steps'], cp['cutoffs'],
                cp['net_external_water']] + cp['net_external_sediment'] + cp['bank'] + [
                    cp['deposited'], cp['signed_bed_forcing'], cp['recycled'], cp['water_correction'],
                    cp['mass_correction'], cp['nodes']]
    require(list(header) == expected and finite(header), 'checkpoint/scalar header differs')
    require(header[0] == 19 and header[1] == 32832000 == 19*p['duration'] and n == 290,
            'checkpoint endpoint differs')
    require(min(cp['bank'] + [cp['deposited'], cp['recycled'], cp['cutoffs']]) >= 0,
            'negative required header inventory')
    size = int(p['length']/p['dx'])*int(p['width']/p['dx'])
    require(len(blob) == offset+64*n+56*size == cp['size_bytes'] == 3115552,
            'checkpoint payload length differs')
    namespace = {'require': require, 'math': math, 'struct': struct}
    functions_only(blobs['decoder-source.py'], ['decode_arrays'], namespace)
    functions_only(blobs['inventory-helper-source.py'], ['sequential_sum', 'source_order_inventory'], namespace)
    arrays = namespace['decode_arrays'](blob, p)
    require(finite(arrays), 'nonfinite reconstructed inventory')
    # These views follow the existing inventory helper; they do not constitute
    # another mask or storage decoder.
    line = list(struct.iter_unpack('<2d', blob[offset:offset+16*n])); offset += 16*n
    channel = list(struct.iter_unpack('<6d', blob[offset:offset+48*n])); offset += 48*n
    bed = [v[0] for v in struct.iter_unpack('<d', blob[offset:offset+8*size])]; offset += 8*size
    q = list(struct.iter_unpack('<6d', blob[offset:]))
    require(all(0 <= x <= p['length'] and 0 <= y <= p['width'] for x, y in line), 'channel outside domain')
    case = dict(p=p, row=row, arrays=arrays, line=line, channel=channel, bed=bed, q=q)
    ordered_storage, ordered_solid = namespace['source_order_inventory'](case)
    return case, namespace['sequential_sum'], ordered_storage, ordered_solid, signature


def analyze(folder):
    capture, blobs = archive_inputs(folder)
    row, p, tokens, fractions, original, comparison = bindings(blobs)
    case, ordered, storage_order, solid_order, signature = checkpoint(blobs, row, p)
    arrays = case['arrays']; storage = arrays['inventory']; cp = row['checkpoint']; r = row['remap']
    totals = row['prescribed_hydrographs']; bank = cp['bank']; dx = p['dx']; nx = int(p['length']/dx)
    require(totals['count'] == 19 and totals['simpson_intervals'] == 20000 and
            totals['water'] > 0 and totals['sediment'] > 0, 'prescribed normalization differs')
    density = p['rho_s']*(1-p['porosity'])*dx*dx
    bed_terms = [(z-p['slope']*(p['length']-(i % nx+.5)*dx))*density for i, z in enumerate(case['bed'])]
    bed_comp = math.fsum(bed_terms); bed_order = ordered(bed_terms)
    solid_comp = math.fsum([bed_comp] + storage[1:] + bank)
    s = [0.]
    for a, b in zip(case['line'], case['line'][1:]):
        s.append(s[-1]+math.hypot(b[0]-a[0], b[1]-a[1]))
    n = len(s); area = [.5*(s[min(i+1, n-1)]-s[max(i-1, 0)])*p['channel_width'] for i in range(n)]
    fp = [math.fsum(v[k]*dx*dx for i, v in enumerate(case['q']) if not arrays['mask'][i]) for k in (0, 3, 4, 5)]
    ch = [math.fsum(v[k]*a for v, a in zip(case['channel'], area)) for k in (0, 3, 4, 5)]
    water_error = storage[0]-r['post_water_storage']
    residual = math.fsum(storage[1:])+cp['deposited']-math.fsum(cp['net_external_sediment'])-cp['mass_correction']
    residual_order = ordered(storage_order[1:])+cp['deposited']
    for value in cp['net_external_sediment']:
        residual_order -= value
    residual_order -= cp['mass_correction']
    sediment_error = residual-r['post_sediment_residual']
    # Existing absolute reconciliation guards: retained guard-source.py:77-80.
    # They apply to inventory/ledger agreement, not full-solid closure.
    require(abs(water_error) < .001 and abs(sediment_error) < .001, 'independent inventory/ledger discrepancy')
    native = dict(compensated_storage_water_m3_then_suspended_classes_kg=storage,
                  source_order_storage_water_m3_then_suspended_classes_kg=storage_order,
                  compensated_floodplain_storage=fp, compensated_channel_storage=ch,
                  bank_classes_kg=bank, bank_compensated_total_kg=math.fsum(bank), bank_ordinary_total_kg=ordered(bank),
                  bank_fraction_differences=[v/math.fsum(bank)-f for v, f in zip(bank, fractions)],
                  signed_bed_inventory_relative_to_initial_plane_compensated_kg=bed_comp,
                  signed_bed_inventory_sequential_sum_kg=bed_order,
                  signed_total_solid_inventory_compensated_kg=solid_comp,
                  signed_total_solid_inventory_source_order_python_kg=solid_order,
                  compensated_minus_source_order_total_solid_kg=solid_comp-solid_order,
                  water_storage_minus_post_ledger_m3=water_error,
                  water_reconciliation_normalized=water_error/totals['water'],
                  source_order_water_minus_post_ledger_m3=storage_order[0]-r['post_water_storage'],
                  suspension_plus_deposition_residual_compensated_kg=residual,
                  suspension_plus_deposition_residual_source_order_python_kg=residual_order,
                  recorded_suspension_plus_deposition_residual_kg=r['post_sediment_residual'],
                  independent_suspension_residual_minus_ledger_kg=sediment_error,
                  suspension_reconciliation_normalized=sediment_error/totals['sediment'],
                  source_order_suspension_residual_minus_ledger_kg=residual_order-r['post_sediment_residual'],
                  independent_suspension_plus_deposition_residual_normalized=residual/totals['sediment'],
                  signed_bed_forcing_kg=cp['signed_bed_forcing'], cumulative_recycled_kg=cp['recycled'],
                  corrections={'water': cp['water_correction'], 'mass': cp['mass_correction']},
                  implied_initial_water_m3=storage[0]-cp['net_external_water']-cp['water_correction']-r['post_water_residual'],
                  implied_initial_total_solid_kg=solid_comp+cp['recycled']-cp['signed_bed_forcing']-
                  math.fsum(cp['net_external_sediment'])-cp['mass_correction']-r['post_solid_sediment_residual'])
    require(finite(native) and min(storage) >= 0, 'nonfinite/negative native inventory')
    require(all(value == original[key] for key, value in native.items()), 'original numerical observation differs')
    geometry = dict(length_m=s[-1], control_area_sum_m2=arrays['channel_area_total'],
                    control_area_min_m2=arrays['channel_area_min'], control_area_max_m2=arrays['channel_area_max'])
    require(all(value == original['channel_geometry'][key] for key, value in geometry.items()),
            'original channel geometry differs')
    mapped = sum(arrays['mask']); size = len(arrays['mask'])
    require(mapped == original['array_layout']['current_mapped_cells'] and
            size-mapped == original['array_layout']['current_floodplain_cells'], 'original current mask differs')
    return dict(format=1, status='verified_native_inventory_reconciliation', case=29, flood=19,
                provenance=dict(capture_sha256=CAPTURE, archive_sha256=ARCHIVE,
                                archive_bytes=capture['archive_bytes'], captured_utc=capture['captured_utc'],
                                member_sha256=PINS, member_bytes=capture['member_bytes'],
                                original_observation_started_utc=original['started_utc'],
                                original_observation_completed_utc=original['completed_utc'],
                                original_observation_serialization=capture['original_observation_serialization'],
                                original_observation_integer_precision=capture['original_observation_integer_precision'],
                                reused_pure_functions=['decode_arrays', 'sequential_sum', 'source_order_inventory']),
                parameter_tokens=tokens, class_fractions=fractions, historical_identity=row['identity'],
                checkpoint=cp, checkpoint_signature=signature, checkpoint_signature_values_checked=31,
                native=native, channel_geometry=geometry, physical_minima=arrays['physical_minima'],
                current_mask=dict(mapped_cells=mapped, floodplain_cells=size-mapped, event_counts_assessed=False),
                bed_arithmetic=dict(decoder_compensated_left_to_right_products_kg=arrays['bed_mass'],
                                    grouped_density_compensated_kg=bed_comp,
                                    grouped_density_sequential_kg=bed_order,
                                    decoder_minus_grouped_compensated_kg=arrays['bed_mass']-bed_comp,
                                    explanation='The unchanged decoder multiplies each bed term by rho_s, (1-porosity), dx, dx left-to-right. The original observation and source-order helper first group those density factors. Product grouping and summation order are distinct diagnostics; Python does not assert compiled C++ bit identity.'),
                existing_reconciliation_guards=dict(source='guard-source.py:77-80',
                                                    source_sha256=PINS['guard-source.py'], strict_less_than=True,
                                                    absolute_water_m3=.001, absolute_suspension_kg=.001,
                                                    water_pass=True, suspension_pass=True, full_solid_guard=None),
                scalar_reference={k: row[k] for k in SCALARS if k != 'checkpoint'},
                original_observation_reproduction=dict(exact_numeric_fields=sorted(native),
                                                       current_mask_counts=True, channel_control_areas=True,
                                                       ghost_interpolation_and_radius_margin_recomputed=False),
                scope='Single retained post-remap endpoint. Native double arrays use physical floodplain cells plus 1D channel control areas; signed bed inventory uses every raster cell relative to the initial plane. Initial water/full-solid references are inferred from bound ledgers, not independently regenerated; independent full-solid closure is not established. No earlier arrays, capture/abandonment/avulsion counts or spatial cause are inferred. Historical identity is archive evidence, not a fresh process check. No float32 snapshot bounds apply.',
                execution=dict(live_files_read=0, auditor_or_model_invocations=0, archived_executable_invocations=0,
                               archived_top_level_modules_executed=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path, help='Folder containing the pinned capture.json and inputs.tar.xz')
    parser.add_argument('--output', type=Path, required=True, help='New output JSON; existing files are refused')
    args = parser.parse_args()
    require(not args.output.exists(), 'output already exists')
    result = analyze(args.folder)
    data = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    with args.output.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'status': result['status'], 'output': str(args.output), 'bytes': len(data), 'sha256': sha(data)}, sort_keys=True))


if __name__ == '__main__':
    main()
