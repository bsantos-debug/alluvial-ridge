#!/usr/bin/env python3
"""Pure retained case26/flood14 inventory and initial-reference reconciliation."""
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

CAPTURE = '285b6d5017c381c42cef2a9f2bffefeae924b9b985278962996ae436e0abb66d'
KEYS = ('length width dx channel_width slope initial_depth duration qmin qmax '
        'channel_chezy floodplain_chezy A C E migration_scale perturbation cfl max_dt '
        'porosity rho_s tau_critical sand_d silt_ws clay_d diffusion_scale '
        'concentration_scale seed run fine migration viscosity').split()
SCALARS = ('checkpoint', 'summary', 'remap', 'prescribed_hydrographs',
           'post_normalized_residuals', 'last_scalar_identity_errors', 'max_abs_scalar_identity_errors')
INITIAL_KEYS = ('length width dx channel_width slope initial_depth qmin channel_chezy '
                'porosity rho_s seed perturbation').split()
PURE_INITIAL = ['mt19937_words', 'noise_values', 'initial_state', 'ordered', 'geometry_witness', 'budgets']


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


def functions_only(blob, names, namespace):
    tree = ast.parse(blob)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    require(len(nodes) == len(names) and {n.name for n in nodes} == set(names), 'pure definitions differ')
    module = ast.Module(body=nodes)
    if 'type_ignores' in ast.Module._fields:
        module.type_ignores = []
    exec(compile(module, '<pinned-pure-functions>', 'exec'), namespace)


def retained_inputs(folder):
    blob = (folder/'capture.json').read_bytes()
    require(sha(blob) == CAPTURE, 'capture manifest changed')
    capture = json.loads(blob)
    require((capture['format'], capture['case'], capture['flood']) == (1, 26, 14), 'capture endpoint differs')
    blobs = {}
    for name, pin in dict(capture['files'], **capture['dependencies']).items():
        data = (folder/name).read_bytes()
        require(sha(data) == pin['sha256'] and len(data) == pin['size_bytes'], 'retained input changed: '+name)
        blobs[name] = data
    native = json.loads(blobs['../run29-flood19/capture.json'])
    archive = blobs['../run29-flood19/inputs.tar.xz']
    require(sha(archive) == native['archive_sha256'] and len(archive) == native['archive_bytes'], 'archive differs')
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:xz') as tar:
        entries = tar.getmembers()
        require(len(entries) == len(native['member_sha256']) == 19 and
                {m.name for m in entries} == set(native['member_sha256']), 'archive member set differs')
        require(all(m.isfile() and m.type in (tarfile.REGTYPE, tarfile.AREGTYPE) for m in entries),
                'nonregular archive member')
        archived = {m.name: tar.extractfile(m).read() for m in entries}
    for name, data in archived.items():
        require(sha(data) == native['member_sha256'][name] and len(data) == native['member_bytes'][name],
                'archive member changed: '+name)
    for name, pin in capture['reused_archive_members'].items():
        require(sha(archived[name]) == pin['sha256'] and len(archived[name]) == pin['size_bytes'],
                'reused member changed: '+name)
    initial = {Path(n).name: data for n, data in blobs.items() if n.startswith('../run29-initial-reference/')}
    local = {n[7:]: data for n, data in blobs.items() if n.startswith('inputs/')}
    return capture, local, initial, archived, json.loads(blobs['capture-observation.json'])


def parameter_tokens(blob):
    result = {}
    for line in blob.decode().splitlines():
        key, value = line.split(' ', 1)
        require(key not in result, 'duplicate parameter')
        result[key] = value
    return result


def bind_case(capture, local, initial, archived, observation):
    audit, comparison, prior, seed, marker, process = [json.loads(local[n]) for n in
        ('scalar.json', 'comparison.json', 'prior-scalar.json', 'observer-seed.json', 'accepted.json', 'process_status.json')]
    require(finite([audit, comparison, prior, seed, marker, process]), 'nonfinite provenance')
    require(audit['requested_flood'] == 14 and set(audit['cases']) == {'26'}, 'scalar endpoint differs')
    row = audit['cases']['26']; record = seed['cases']['26']; previous = prior['cases']['26']
    sources = {n: sha(data) for n, data in archived.items() if n.startswith('src/')}
    binary = sha(archived['ridge'])
    for document in (audit, seed, prior):
        require(document['frozen_source_sha256'] == sources and document['binary_sha256'] == binary,
                'frozen source/binary binding differs')
    require(row['hashes'] == {n: sha(local[n]) for n in row['hashes']} and
            set(row['hashes']) == {'checkpoint.bin', 'parameters.txt', 'process_status.json', 'summary.csv', 'remap_budget.csv'},
            'scalar artifact binding differs')
    require(row['history'] == list(range(1, 15)) and row['stable_seconds'] >= 2 and row['cpu_ticks_delta'] > 0,
            'scalar history/stability differs')
    require(comparison['case'] == marker['case'] == 26 and comparison['flood'] == marker['flood'] == 14 and
            marker['status'] == 'scalar_observer_verified', 'accepted scalar endpoint differs')
    for field, name in (('result_sha256', 'scalar.json'), ('seed_sha256', 'observer-seed.json'),
                        ('prior_sha256', 'prior-scalar.json')):
        require(comparison[field] == marker[field] == sha(local[name]), 'accepted dependency differs: '+field)
    require(marker['comparison_sha256'] == sha(local['comparison.json']) and
            comparison['current_scalar_maps'] == {k: row[k] for k in SCALARS} and
            comparison['prior_scalar_maps'] == {k: previous[k] for k in SCALARS} and
            prior['requested_flood'] == previous['checkpoint']['flood'] == 13, 'scalar maps differ')
    identity = row['identity']; stable_identity = record['identity']
    require({k: identity[k] for k in stable_identity} == stable_identity and
            comparison['current_identity'] == identity and identity['argv_exact'], 'recorded identity differs')
    for key in ('identity_before', 'identity_after'):
        current = observation[key]
        require({k: current[k] for k in stable_identity} == stable_identity and
                (current['pid'], current['start_ticks'], current['parent']) == (3805586, 51544923, 3805340),
                'capture identity differs')
    require(observation['stable_seconds'] >= 2 and observation['cpu_ticks_delta'] > 0 and
            observation['identity_after']['cpu_ticks']-observation['identity_before']['cpu_ticks'] == observation['cpu_ticks_delta'],
            'capture progress differs')
    argv = identity['argv']
    require(argv == process['command'] == process['current_attempt']['command'] and
            process['pid'] == process['current_attempt']['pid'] == identity['pid'] and
            int(process['process_start_ticks']) == int(process['current_attempt']['process_start_ticks']) == identity['start_ticks'] and
            process['attempts'] == [] and process['state'] == process['current_attempt']['state'] == 'running',
            'original attempt binding differs')
    require(record['parameters_sha256'] == sha(local['parameters.txt']) and
            record['process_status_sha256'] == sha(local['process_status.json']), 'seed binding differs')
    tokens = parameter_tokens(local['parameters.txt'])
    p = {k: float(v) for k, v in tokens.items() if k != 'command'}
    require(set(p) == set(KEYS)|{'floods'} and finite(p), 'numerical parameter set differs')
    selected = {k: tokens[k] for k in ('A', 'C', 'E', 'fine', 'concentration_scale')}
    require(selected == record['parameter_tokens'] == comparison['parameter_tokens'] and
            (p['run'], p['A'], p['C'], p['E'], p['fine']) == (26, .036, .003, 1, 1), 'case26 parameters differ')
    require(record['fractions'] == comparison['class_fractions'] == [.05, .20, .75], 'fine fractions differ')
    for name, section in (('summary.csv', 'summary'), ('remap_budget.csv', 'remap')):
        blob = local[name]; rows = list(csv.DictReader(io.StringIO(blob.decode())))
        values = [{k: float(v) for k, v in r.items()} for r in rows]; prefix = comparison['csv_prefixes'][name]
        require(finite(values) and [r['flood'] for r in values] == list(range(1, 15)) and
                values[-1] == row[section] and rows[-1] == comparison['current_csv_last_tokens'][name], 'CSV history differs')
        require(prefix['exact_prefix'] and len(blob) == prefix['current_bytes'] and
                sha(blob) == prefix['current_sha256'] == marker['retained_csv_sha256'][name] and
                sha(blob[:prefix['prior_bytes']]) == prefix['prior_sha256'] == previous['hashes'][name], 'CSV prefix differs')
    require(tokens['command'] == ' '.join(argv) and len(argv) % 2 == 1, 'parameter command differs')
    args = dict(zip(argv[1::2], argv[2::2]))
    require(len(args) == (len(argv)-1)//2 and set(args) == {'--config', '--runs', '--run', '--floods', '--out'} and
            args['--run'] == '26' and args['--floods'] == '580' and Path(args['--config']).name == 'physics.txt' and
            Path(args['--runs']).name == 'runs.csv', 'model argv differs')
    words = initial['physics.txt'].decode().split(); config = dict(zip(words[::2], words[1::2]))
    require(len(words) % 2 == 0 and len(config) == len(words)//2, 'physics tokens differ')
    effective = dict(args)
    for key, value in config.items():
        effective.setdefault('--'+key, value)
    require('--resume' not in effective, 'effective model resume is present')
    rows = list(csv.DictReader(io.StringIO(initial['runs.csv'].decode())))
    matches = [r for r in rows if int(r['run']) == 26]
    require(len(matches) == 1 and matches[0] == process['configuration'] and matches[0]['load'] == 'fine', 'run row differs')
    run = matches[0]
    # Exact defaults and overrides from the hash-bound model.hpp:18-24/main.cpp:6-31.
    expected = dict(length=72000., width=48000., dx=250., channel_width=500., slope=.0001, initial_depth=8.,
                    duration=1728000., qmin=2500., qmax=15000., channel_chezy=55., floodplain_chezy=10.,
                    migration_scale=400., perturbation=5., cfl=.4, max_dt=120., porosity=.4, rho_s=2650.,
                    tau_critical=.1, sand_d=.0002, silt_ws=.0002, clay_d=.000002, diffusion_scale=1.,
                    concentration_scale=.001, floods=580., seed=2018., run=26., fine=1., migration=1., viscosity=1.,
                    A=float(run['A_m_per_flood']), C=float(run['C']), E=float(run['E']))
    overrides = ('dx length width channel_width A C E cfl max_dt duration migration_scale perturbation qmin qmax '
                 'tau_critical channel_chezy floodplain_chezy sand_d silt_ws clay_d diffusion_scale concentration_scale '
                 'porosity initial_depth floods seed migration viscosity').split()
    for key in overrides:
        flag = '--'+key.replace('_', '-')
        if flag in effective:
            expected[key] = float(effective[flag])
    require(expected == p, 'effective numerical parameters differ')
    provenance = json.loads(initial['compile-provenance.json'])
    require(provenance['compile_exit_code'] == 0 and provenance['binary_sha256'] == binary and
            provenance['source_sha256'] == sources and all(provenance['frozen_sha256'][k] == v for k, v in sources.items()),
            'compile provenance differs')
    require(provenance['config_sha256'] == provenance['frozen_sha256']['physics.txt'] == sha(initial['physics.txt']) and
            provenance['runs_table_sha256'] == provenance['frozen_sha256']['runs.csv'] == sha(initial['runs.csv']),
            'frozen configuration differs')
    old_tokens = parameter_tokens(archived['inputs/parameters.txt'])
    require(all(tokens[k] == old_tokens[k] for k in INITIAL_KEYS) and p['A'] > 0 and 0*p['A'] == 0*float(old_tokens['A']) == 0.,
            'initializer dependency equivalence differs')
    equivalence = dict(dependency_tokens={k: tokens[k] for k in INITIAL_KEYS},
                       exact_token_match_with_retained_case29=True, zero_A_term_equal=True,
                       source='model.hpp initialization/geometry/storage/total_sediment_inventory; main.cpp fresh-start path',
                       explanation='All geometry/water/solid initializer dependencies match. A enters geometry as 0*A; C, E, fine and run do not enter the zero-sediment initial inventories. Equality is reconstructed Python arithmetic, not compiled-model bit identity.')
    fresh = dict(effective_resume=False, argv_resume_present=False, config_resume_present=False,
                 command=argv, effective_options=effective, parameters=p, run_row=run,
                 original_compile_provenance_sha256=sha(initial['compile-provenance.json']),
                 source='Frozen main.cpp:6-31,54-57; model.hpp:18-24. Suite orchestration resume is not a model option.')
    return row, p, selected, fresh, equivalence


def native_endpoint(local, archived, row, p, namespace):
    blob = local['checkpoint.bin']
    require(len(blob) >= 8, 'truncated checkpoint')
    slen = struct.unpack_from('<Q', blob)[0]
    require(0 < slen <= 4096, 'invalid signature length')
    signature = blob[8:8+slen].decode(); words = signature.split()
    require(len(words) == 32 and words[0] == 'ridge-checkpoint-v2' and
            all(float(v) == p[k] for k, v in zip(KEYS, words[1:])), 'checkpoint signature differs')
    fmt = '<idqqi4d3d5dQ'; offset = 8+slen+struct.calcsize(fmt)
    require(len(blob) >= offset, 'truncated checkpoint header')
    header = struct.unpack_from(fmt, blob, 8+slen); cp = row['checkpoint']; n = header[-1]
    expected = [cp['flood'], cp['clock'], cp['steps'], cp['channel_steps'], cp['cutoffs'], cp['net_external_water']]+cp['net_external_sediment']+cp['bank']+[
        cp['deposited'], cp['signed_bed_forcing'], cp['recycled'], cp['water_correction'], cp['mass_correction'], cp['nodes']]
    require(list(header) == expected and finite(header) and header[0] == 14 and header[1] == 24192000 == 14*p['duration'] and n == 290,
            'case26 native header differs')
    require(min(cp['bank']+[cp['deposited'], cp['recycled'], cp['cutoffs'], cp['steps'], cp['channel_steps']]) >= 0,
            'negative required header quantity')
    nx, ny = int(p['length']/p['dx']), int(p['width']/p['dx']); size = nx*ny
    require(nx*p['dx'] == p['length'] and ny*p['dx'] == p['width'] and
            len(blob) == offset+64*n+56*size == cp['size_bytes'] == 3115564, 'checkpoint payload length differs')
    functions_only(archived['decoder-source.py'], ['decode_arrays'], namespace)
    functions_only(archived['inventory-helper-source.py'], ['sequential_sum', 'source_order_inventory'], namespace)
    arrays = namespace['decode_arrays'](blob, p)
    line = list(struct.iter_unpack('<2d', blob[offset:offset+16*n])); offset += 16*n
    channel = list(struct.iter_unpack('<6d', blob[offset:offset+48*n])); offset += 48*n
    bed = [v[0] for v in struct.iter_unpack('<d', blob[offset:offset+8*size])]; offset += 8*size
    q = list(struct.iter_unpack('<6d', blob[offset:]))
    require(finite([arrays, line, channel, bed, q]) and
            all(0 <= x <= p['length'] and 0 <= y <= p['width'] for x, y in line), 'invalid native arrays')
    case = dict(p=p, row=row, arrays=arrays, line=line, channel=channel, bed=bed, q=q)
    storage_order, solid_order = namespace['source_order_inventory'](case)
    ordered = namespace['sequential_sum']; storage = arrays['inventory']; r = row['remap']; totals = row['prescribed_hydrographs']
    require(totals['count'] == 14 and totals['simpson_intervals'] == 20000 and min(totals['water'], totals['sediment']) > 0,
            'retained normalization scope differs')
    density = p['rho_s']*(1-p['porosity'])*p['dx']*p['dx']
    bed_terms = [(z-p['slope']*(p['length']-(i % nx+.5)*p['dx']))*density for i, z in enumerate(bed)]
    bed_comp = math.fsum(bed_terms); solid_comp = math.fsum([bed_comp]+storage[1:]+cp['bank'])
    water_error = storage[0]-r['post_water_storage']
    sediment_residual = math.fsum(storage[1:])+cp['deposited']-math.fsum(cp['net_external_sediment'])-cp['mass_correction']
    sediment_error = sediment_residual-r['post_sediment_residual']
    require(abs(water_error) < .001 and abs(sediment_error) < .001, 'existing native inventory/ledger guard failed')
    native = dict(compensated_storage_water_m3_then_suspended_classes_kg=storage,
                  source_order_storage_water_m3_then_suspended_classes_kg=storage_order,
                  bank_classes_kg=cp['bank'], bank_compensated_total_kg=math.fsum(cp['bank']),
                  bank_fraction_differences=[v/math.fsum(cp['bank'])-f for v, f in zip(cp['bank'], [.05, .20, .75])],
                  signed_bed_inventory_relative_to_initial_plane_compensated_kg=bed_comp,
                  signed_total_solid_inventory_compensated_kg=solid_comp,
                  signed_total_solid_inventory_source_order_python_kg=solid_order,
                  water_storage_minus_post_ledger_m3=water_error,
                  suspension_plus_deposition_residual_compensated_kg=sediment_residual,
                  independent_suspension_residual_minus_ledger_kg=sediment_error)
    require(finite(native) and min(storage) >= 0, 'invalid current native inventory')
    return dict(checkpoint=cp, checkpoint_signature=signature, checkpoint_signature_values_checked=31, native=native,
                scalar_reference={k: row[k] for k in SCALARS if k != 'checkpoint'},
                current_mask=dict(mapped_cells=sum(arrays['mask']), floodplain_cells=size-sum(arrays['mask']), event_counts_assessed=False),
                channel_geometry=dict(control_area_sum_m2=arrays['channel_area_total'], control_area_min_m2=arrays['channel_area_min'],
                                      control_area_max_m2=arrays['channel_area_max'], area_identity_error_m2=arrays['channel_area_identity_error']),
                physical_minima=arrays['physical_minima'],
                bed_arithmetic=dict(decoder_compensated_left_to_right_products_kg=arrays['bed_mass'], grouped_density_compensated_kg=bed_comp,
                                    grouped_density_sequential_kg=ordered(bed_terms), decoder_minus_grouped_compensated_kg=arrays['bed_mass']-bed_comp,
                                    explanation='Decoder left-to-right products, grouped-density products and summation order are distinct Python diagnostics; no compiled C++ bit identity is asserted.'),
                existing_reconciliation_guards=dict(source='run29-flood19/inputs.tar.xz:guard-source.py:77-80',
                    source_sha256=sha(archived['guard-source.py']), strict_less_than=True, absolute_water_m3=.001,
                    absolute_suspension_kg=.001, water_pass=True, suspension_pass=True, full_solid_guard=None))


def analyze(folder):
    capture, local, initial, archived, observation = retained_inputs(folder)
    row, p, tokens, fresh, equivalence = bind_case(capture, local, initial, archived, observation)
    namespace = dict(require=require, sha=sha, math=math, struct=struct, csv=csv, io=io, json=json)
    functions_only(initial['replay.py'], PURE_INITIAL, namespace)
    noise, rng = namespace['noise_values'](p, initial)
    inventories, geometry = namespace['initial_state'](p, noise)
    witness = namespace['geometry_witness'](geometry, local['peak_channel_0001.csv'])
    require(inventories == json.loads(initial['replay.json'])['initial_inventories'], 'common reconstructed initial reference differs')
    endpoint = native_endpoint(local, archived, row, p, namespace)
    endings, diagnostics = namespace['budgets'](inventories, endpoint)
    result = dict(endpoint, format=1, status='verified_native_inventory_and_independent_initial_reference', case=26, flood=14,
                  parameter_tokens=tokens, class_fractions=[.05, .20, .75], historical_identity=row['identity'],
                  effective_fresh_start=fresh, initializer_equivalence=equivalence, initial_inventories=inventories,
                  initial_geometry=dict(nodes=len(geometry['line']), nx=geometry['nx'], ny=geometry['ny'],
                    mapped_cells=sum(v is not None for v in geometry['mapping']), length_m=geometry['length'],
                    equilibrium_water_depth_m=geometry['depth'], channel_area_m2=math.fsum(geometry['areas'])),
                  geometry_witness=witness, rng_verification=rng, endpoint_inventories=endings, budget_diagnostics=diagnostics,
                  provenance=dict(capture_sha256=CAPTURE, captured_utc=capture['captured_utc'],
                    replay_source_sha256=sha(Path(__file__).read_bytes()), files=capture['files'], dependencies=capture['dependencies'],
                    reused_archive_members=capture['reused_archive_members'],
                    reused_pure_functions=PURE_INITIAL+['decode_arrays', 'sequential_sum', 'source_order_inventory']),
                  recorded_flux_ledgers={k: row['checkpoint'][k] for k in ('net_external_water', 'net_external_sediment',
                    'deposited', 'recycled', 'signed_bed_forcing', 'water_correction', 'mass_correction')},
                  scope='One retained post-remap case26/flood14 endpoint at C=.003, fine=1. Initial inventories are reconstructed from actual fresh-start inputs and the retained GNU8/MT19937 witness, never inferred from this evolved checkpoint. Current native arrays and initial references are independently reaggregated; boundary, deposition, forcing, recycling and correction ledgers and prescribed-input normalizers remain recorded quantities. Existing water/suspension reconciliation guards apply; full-solid acceptance is unassessed. No intermediate arrays, event counts, causal comparison, convergence, compiled-model bit identity or full580 completion is established.',
                  execution=dict(live_files_read=0, auditor_or_model_invocations=0, rng_executable_invocations=0,
                    archived_top_level_modules_executed=0, historical_paths_opened=0))
    require(finite(result), 'nonfinite replay result')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', nargs='?', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path, help='New JSON path; existing paths are refused')
    args = parser.parse_args()
    if args.output is not None:
        require(not os.path.lexists(str(args.output)), 'output already exists; refusing to overwrite')
    result = analyze(args.folder)
    encoded = json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+'\n'
    if args.output is None:
        print(encoded, end='')
    else:
        with args.output.open('x') as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())


if __name__ == '__main__':
    main()
