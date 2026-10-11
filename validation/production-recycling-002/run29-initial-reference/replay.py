#!/usr/bin/env python3
"""Reconstruct initial inventories and diagnose the retained case29/flood19 budget."""
import argparse
import ast
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path

CAPTURE = '23b008117d075c453a33c6befa42fb1246d71fd4c507c687ecf6dbe6f4bdb1fc'
FILES = {'rng-witness.cpp', 'rng-witness.csv', 'rng-provenance.json',
         'compile-provenance.json', 'physics.txt', 'runs.csv', 'peak-channel-initial-geometry.csv'}
ENDPOINT_FILES = {'capture.json', 'inputs.tar.xz', 'replay.py', 'replay.json'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def ordered(values):
    value = 0.0
    for item in values:
        value += item
    return value


def read_bound(folder, name, pin):
    path = folder / name
    require(path.is_file() and not path.is_symlink(), 'missing/nonregular/symlink input: ' + name)
    blob = path.read_bytes()
    require(len(blob) == pin['size_bytes'] and sha(blob) == pin['sha256'], 'input changed: ' + name)
    return blob


def endpoint_replay(folder, capture):
    endpoint = folder.parent / 'run29-flood19'
    require(capture['endpoint_folder'] == endpoint.name and not endpoint.is_symlink(), 'endpoint folder differs')
    require(set(capture['endpoint_files']) == ENDPOINT_FILES, 'endpoint input set differs')
    blobs = {name: read_bound(endpoint, name, pin) for name, pin in capture['endpoint_files'].items()}
    # Load only the hash-bound offline definitions/imports/constants. Its CLI
    # entry point is excluded; neither a model nor an auditor is imported.
    tree = ast.parse(blobs['replay.py'])
    body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign)) or
            isinstance(node, ast.FunctionDef) and node.name != 'main']
    module = ast.Module(body=body)
    if 'type_ignores' in ast.Module._fields:
        module.type_ignores = []
    namespace = {'__name__': 'bound_offline_endpoint_replay'}
    exec(compile(module, '<bound-offline-endpoint-replay>', 'exec'), namespace)
    result = namespace['analyze'](endpoint)
    require(result == json.loads(blobs['replay.json']), 'retained endpoint replay result differs')
    _, archived = namespace['archive_inputs'](endpoint)
    return result, archived


def fresh_start(inputs, archived, endpoint):
    provenance = json.loads(inputs['compile-provenance.json'])
    process = json.loads(archived['inputs/process_status.json'])
    seed = json.loads(archived['observations/seed.json'])['cases']['29']
    tokens = dict(line.split(' ', 1) for line in archived['inputs/parameters.txt'].decode().splitlines())
    parameters = {k: float(v) for k, v in tokens.items() if k != 'command'}
    argv = process['command']
    require(argv == process['current_attempt']['command'] == seed['identity']['argv'] ==
            endpoint['historical_identity']['argv'], 'historical command binding differs')
    require(tokens['command'] == ' '.join(argv) and len(argv) % 2 == 1, 'parameter command differs')
    args = dict(zip(argv[1::2], argv[2::2]))
    require(len(args) == (len(argv)-1)//2 and set(args) ==
            {'--config', '--runs', '--run', '--floods', '--out'}, 'original options differ')
    require(args['--run'] == '29' and args['--floods'] == '580' and
            Path(args['--config']).name == 'physics.txt' and Path(args['--runs']).name == 'runs.csv',
            'original input targets differ')
    words = inputs['physics.txt'].decode().split()
    require(len(words) % 2 == 0, 'unpaired physics token')
    config = dict(zip(words[::2], words[1::2]))
    require(len(config) == len(words)//2, 'duplicate physics key')
    effective = dict(args)
    for key, value in config.items():
        effective.setdefault('--'+key, value)  # main.cpp:9, command takes precedence.
    require('--resume' not in effective, 'effective resume is present')
    runs = list(csv.DictReader(io.StringIO(inputs['runs.csv'].decode())))
    row = [r for r in runs if int(r['run']) == 29]
    require(len(row) == 1 and row[0]['load'] == 'default', 'case29 runs row differs')
    row = row[0]
    # Frozen model.hpp:18-24 defaults, main.cpp:13-27 selection and overrides.
    expected = dict(length=72000., width=48000., dx=250., channel_width=500., slope=.0001,
                    initial_depth=8., duration=1728000., qmin=2500., qmax=15000.,
                    channel_chezy=55., floodplain_chezy=10., migration_scale=400., perturbation=5.,
                    cfl=.4, max_dt=120., porosity=.4, rho_s=2650., tau_critical=.1,
                    sand_d=.0002, silt_ws=.0002, clay_d=.000002, diffusion_scale=1.,
                    concentration_scale=.001, floods=580., seed=2018., run=29.,
                    fine=0., migration=1., viscosity=1., A=float(row['A_m_per_flood']),
                    C=float(row['C']), E=float(row['E']))
    keys = ('dx length width channel_width A C E cfl max_dt duration migration_scale perturbation '
            'qmin qmax tau_critical channel_chezy floodplain_chezy sand_d silt_ws clay_d '
            'diffusion_scale concentration_scale porosity initial_depth floods seed migration viscosity').split()
    for key in keys:
        flag = '--'+key.replace('_', '-')
        if flag in effective:
            expected[key] = float(effective[flag])
    require(expected == parameters, 'effective numerical parameters differ')
    require(provenance['compile_exit_code'] == 0 and
            provenance['binary_sha256'] == endpoint['provenance']['member_sha256']['ridge'] and
            provenance['source_sha256'] == {name: digest for name, digest in
                endpoint['provenance']['member_sha256'].items() if name.startswith('src/')},
            'original compiler/source binding differs')
    require(provenance['config_sha256'] == provenance['frozen_sha256']['physics.txt'] == sha(inputs['physics.txt']) and
            provenance['runs_table_sha256'] == provenance['frozen_sha256']['runs.csv'] == sha(inputs['runs.csv']),
            'original configuration provenance differs')
    require(seed['parameters_sha256'] == sha(archived['inputs/parameters.txt']) and
            seed['process_status_sha256'] == sha(archived['inputs/process_status.json']), 'seed inputs differ')
    return parameters, dict(effective_resume=False, config_resume_present=False,
                           argv_resume_present=False, config_key_count=len(config),
                           command=argv, effective_options=effective, parameters=parameters,
                           source='Frozen main.cpp:6-31,54-57; model.hpp:18-24.',
                           original_compile_provenance_sha256=sha(inputs['compile-provenance.json']))


def mt19937_words(seed, count):
    # Independent integer recurrence: GNU8 random.h mt19937 parameters and
    # random.tcc seed/twist/temper definitions. No Python random dependency.
    state = [seed & 0xffffffff]
    for i in range(1, 624):
        state.append((1812433253*(state[-1] ^ (state[-1] >> 30))+i) & 0xffffffff)
    position = 624
    for _ in range(count):
        if position == 624:
            for i in range(624):
                y = (state[i] & 0x80000000) | (state[(i+1) % 624] & 0x7fffffff)
                state[i] = state[(i+397) % 624] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)
            position = 0
        value = state[position]; position += 1
        value ^= value >> 11
        value ^= (value << 7) & 0x9d2c5680
        value ^= (value << 15) & 0xefc60000
        value ^= value >> 18
        yield value & 0xffffffff


def noise_values(parameters, inputs):
    witness = list(csv.DictReader(io.StringIO(inputs['rng-witness.csv'].decode())))
    provenance = json.loads(inputs['rng-provenance.json'])
    original = json.loads(inputs['compile-provenance.json'])
    require(provenance['compile_exit_code'] == provenance['run_exit_code'] == 0 and
            provenance['source_sha256'] == sha(inputs['rng-witness.cpp']) and
            provenance['output_sha256'] == sha(inputs['rng-witness.csv']) and
            provenance['output_bytes'] == len(inputs['rng-witness.csv']) and
            provenance['compiler_version'].splitlines()[0] == original['compiler_version'],
            'RNG witness provenance differs')
    require(parameters['seed'] == provenance['seed'] == 2018 and
            len(witness) == provenance['distribution_count'] == 287 and provenance['raw_word_count'] == 574,
            'RNG witness scope differs')
    words = list(mt19937_words(int(parameters['seed']), 574)); values = []
    lower, upper = -math.sqrt(3.), math.sqrt(3.)
    for i, row in enumerate(witness):
        a, b = words[2*i:2*i+2]
        require(int(row['index']) == i and int(row['word0']) == a and int(row['word1']) == b,
                'MT19937 word mismatch at '+str(i))
        # GNU8 generate_canonical<double,53>: two base-2^32 draws, low word first.
        canonical = (float(a)+float(b)*4294967296.)/18446744073709551616.
        if canonical >= 1.:
            canonical = float.fromhex('0x1.fffffffffffffp-1')
        value = canonical*(upper-lower)+lower
        require(value == float.fromhex(row['noise_hex']) == float(row['noise_decimal']),
                'GNU double conversion mismatch at '+str(i))
        values.append(value)
    return values, dict(raw_words_checked=574, distribution_doubles_checked=287,
                        raw_words_exact=True, distribution_doubles_exact=True,
                        cpp_witness_source_sha256=sha(inputs['rng-witness.cpp']),
                        cpp_witness_output_sha256=sha(inputs['rng-witness.csv']),
                        gnu_headers=provenance['gnu_headers'],
                        scope='Exact comparison with the retained new GNU8 RNG-only witness; not compiled-model bit identity.')


def initial_state(p, noise):
    dx, width = p['dx'], p['channel_width']
    nx, ny = int(p['length']/dx), int(p['width']/dx)
    nc = int(p['length']/(width/2))
    require(nx*dx == p['length'] and ny*dx == p['width'] and nc == 288 and len(noise) == nc-1,
            'initial geometry dimensions differ')
    line = [(p['length']*i/nc, p['width']/2+(0. if i in (0, nc) else p['perturbation']*noise[i-1]))
            for i in range(nc+1)]
    s = [0.]
    for a, b in zip(line, line[1:]):
        s.append(s[-1]+math.hypot(b[0]-a[0], b[1]-a[1]))
    areas = [.5*(s[min(i+1, nc)]-s[max(i-1, 0)])*width for i in range(nc+1)]
    channel_bed = [p['slope']*p['length']*(1-s[i]/s[-1])-p['initial_depth']+0*p['A'] for i in range(nc+1)]
    plane = [p['slope']*(p['length']-(i+.5)*dx) for j in range(ny) for i in range(nx)]
    bed = list(plane); mapping = [None]*(nx*ny); best = [1e100]*(nx*ny); radius = .5*width
    for k, (a, b) in enumerate(zip(line, line[1:])):
        vx, vy = b[0]-a[0], b[1]-a[1]; ll = vx*vx+vy*vy
        i0 = max(0, math.floor((min(a[0], b[0])-radius)/dx))
        i1 = min(nx-1, math.floor((max(a[0], b[0])+radius)/dx))
        j0 = max(0, math.floor((min(a[1], b[1])-radius)/dx))
        j1 = min(ny-1, math.floor((max(a[1], b[1])+radius)/dx))
        for j in range(j0, j1+1):
            for i in range(i0, i1+1):
                px, py = (i+.5)*dx-a[0], (j+.5)*dx-a[1]
                weight = max(0., min(1., (px*vx+py*vy)/ll))
                distance = math.hypot(px-weight*vx, py-weight*vy); index = j*nx+i
                if distance <= radius and distance < best[index]:
                    best[index] = distance; mapping[index] = (k, weight)
    for index, match in enumerate(mapping):
        if match is not None:
            k, weight = match
            bed[index] = (1-weight)*channel_bed[k]+weight*channel_bed[k+1]
    slope = p['slope']*p['length']/s[-1]
    depth = math.pow(abs(p['qmin'])/(width*p['channel_chezy']*math.sqrt(slope)), 2./3.)
    water_terms = [depth*area for area in areas]
    density = p['rho_s']*(1-p['porosity'])*dx*dx
    bed_terms = [(z-z0)*density for z, z0 in zip(bed, plane)]
    inventories = {}
    for name, add in (('source_order', ordered), ('compensated', math.fsum)):
        solid = add(bed_terms)
        inventories[name] = dict(water_m3=add(water_terms), suspended_classes_kg=[0., 0., 0.],
                                 bank_classes_kg=[0., 0., 0.], signed_bed_kg=solid, total_solid_kg=solid,
                                 deposited_mass_kg=0., net_external_water_m3=0.,
                                 net_external_sediment_classes_kg=[0., 0., 0.], recycled_mass_kg=0.,
                                 signed_bed_forcing_kg=0., water_correction_m3=0., mass_correction_kg=0.)
    return inventories, dict(line=line, channel_bed=channel_bed, areas=areas, mapping=mapping,
                             nx=nx, ny=ny, length=s[-1], depth=depth, density=density)


def geometry_witness(geometry, blob):
    rows = list(csv.DictReader(io.StringIO(blob.decode())))
    require(len(rows) == len(geometry['line']) == 289, 'rounded geometry witness count differs')
    maxima = {k: 0. for k in ('x', 'y', 'bed', 'control_area')}
    for i, row in enumerate(rows):
        values = dict(x=geometry['line'][i][0], y=geometry['line'][i][1],
                      bed=geometry['channel_bed'][i], control_area=geometry['areas'][i])
        for key, value in values.items():
            require(format(value, '.12g') == row[key], 'rounded geometry token differs: node {} {}'.format(i, key))
            maxima[key] = max(maxima[key], abs(value-float(row[key])))
    return dict(sha256=sha(blob), nodes=289, columns=['x', 'y', 'bed', 'control_area'],
                decimal_tokens_checked=4*289, all_12_significant_digit_tokens_match=True,
                max_abs_reconstructed_minus_printed=maxima,
                difference_units=dict(x='m', y='m', bed='m', control_area='m2'),
                method="format(reconstructed_value, '.12g') equals each retained CSV token exactly",
                excluded_evolved_columns=['water_depth', 'velocity'],
                scope='First-flood peak precedes first remap. Rounded geometry agrees; no historical native-double bit identity or initial-depth inference from evolved peak water is claimed.')


def budgets(initial, endpoint):
    cp = endpoint['checkpoint']; native = endpoint['native']; remap = endpoint['scalar_reference']['remap']
    totals = endpoint['scalar_reference']['prescribed_hydrographs']; results = {}; endings = {}
    for name in ('source_order', 'compensated'):
        suffix = 'source_order_storage_water_m3_then_suspended_classes_kg' if name == 'source_order' else 'compensated_storage_water_m3_then_suspended_classes_kg'
        storage = native[suffix]
        solid = native['signed_total_solid_inventory_source_order_python_kg' if name == 'source_order' else 'signed_total_solid_inventory_compensated_kg']
        begin = initial[name]
        if name == 'source_order':
            water_residual = storage[0]-begin['water_m3']-cp['net_external_water']-cp['water_correction']
            suspension_residual = ordered(storage[1:])-ordered(begin['suspended_classes_kg'])+cp['deposited']
            full_residual = solid-begin['total_solid_kg']+cp['recycled']-cp['signed_bed_forcing']
            for value in cp['net_external_sediment']:
                suspension_residual -= value; full_residual -= value
            suspension_residual -= cp['mass_correction']; full_residual -= cp['mass_correction']
        else:
            water_residual = math.fsum([storage[0], -begin['water_m3'], -cp['net_external_water'], -cp['water_correction']])
            suspension_residual = math.fsum(storage[1:]+[-v for v in begin['suspended_classes_kg']]+[cp['deposited']]+[-v for v in cp['net_external_sediment']]+[-cp['mass_correction']])
            full_residual = math.fsum([solid, -begin['total_solid_kg'], cp['recycled'], -cp['signed_bed_forcing']]+[-v for v in cp['net_external_sediment']]+[-cp['mass_correction']])
        endings[name] = dict(water_m3=storage[0], suspended_classes_kg=storage[1:],
                             bank_classes_kg=cp['bank'], total_solid_kg=solid)
        result = {}
        for key, residual, ledger, norm, unit in (
                ('water', water_residual, remap['post_water_residual'], totals['water'], 'm3'),
                ('suspension', suspension_residual, remap['post_sediment_residual'], totals['sediment'], 'kg'),
                ('full_solid', full_residual, remap['post_solid_sediment_residual'], totals['sediment'], 'kg')):
            result[key] = dict(residual=residual, recorded_post_remap_residual=ledger,
                               reconstruction_minus_recorded=residual-ledger, unit=unit,
                               prescribed_input=norm, normalized_residual=residual/norm,
                               normalized_reconstruction_minus_recorded=(residual-ledger)/norm)
        result['full_solid_acceptance'] = 'unassessed; no full-solid pass threshold'
        results[name] = result
    return endings, results


def analyze(folder):
    folder = Path(folder)
    require(folder.is_dir() and not folder.is_symlink(), 'invalid capsule folder')
    capture_blob = (folder/'capture.json').read_bytes()
    require(sha(capture_blob) == CAPTURE, 'capture manifest changed')
    capture = json.loads(capture_blob)
    require(capture['format'] == 1 and capture['case'] == 29 and capture['endpoint_flood'] == 19 and
            set(capture['files']) == FILES, 'capture scope differs')
    inputs = {name: read_bound(folder, name, pin) for name, pin in capture['files'].items()}
    endpoint, archived = endpoint_replay(folder, capture)
    p, fresh = fresh_start(inputs, archived, endpoint)
    noise, rng = noise_values(p, inputs)
    initial, geometry = initial_state(p, noise)
    witness = geometry_witness(geometry, inputs['peak-channel-initial-geometry.csv'])
    endings, diagnostics = budgets(initial, endpoint)
    masks = [int(match is not None) for match in geometry['mapping']]
    require(sum(masks) == 576 and all(math.isfinite(x) for group in initial.values()
                                   for value in group.values() for x in (value if isinstance(value, list) else [value])),
            'initial inventory or mask differs')
    result = dict(format=1, status='verified_initial_reconstruction_with_budget_diagnostics', case=29, flood=19,
                  provenance=dict(capture_sha256=CAPTURE, added_input_sha256={k: v['sha256'] for k, v in capture['files'].items()},
                                  endpoint_files=capture['endpoint_files'], captured_utc=capture['captured_utc'],
                                  endpoint_replay_reproduced_exactly=True, numerical_sources=endpoint['provenance']['member_sha256']),
                  effective_fresh_start=fresh, rng_verification=rng, geometry_witness=witness,
                  initial_geometry=dict(channel_nodes=len(geometry['line']), raster_shape=[geometry['nx'], geometry['ny']],
                                        channel_length_m=geometry['length'], initial_water_depth_m=geometry['depth'],
                                        channel_area_source_order_m2=ordered(geometry['areas']),
                                        channel_area_compensated_m2=math.fsum(geometry['areas']),
                                        mapped_raster_cells=sum(masks), physical_floodplain_cells=len(masks)-sum(masks),
                                        row_major_mask_sha256=sha(bytes(masks)), grouped_solid_density_factor_kg_per_m=geometry['density']),
                  initial_inventories=initial, endpoint_inventories=endings, budget_diagnostics=diagnostics,
                  initial_compensated_minus_source_order=dict(water_m3=initial['compensated']['water_m3']-initial['source_order']['water_m3'],
                                                              total_solid_kg=initial['compensated']['total_solid_kg']-initial['source_order']['total_solid_kg']),
                  existing_endpoint_guards=endpoint['existing_reconciliation_guards'],
                  recorded_flux_ledgers=endpoint['checkpoint'], prescribed_inputs=endpoint['scalar_reference']['prescribed_hydrographs'],
                  arithmetic=dict(initial='Constructor/geometry/source-order operations followed explicitly; compensated sums applied separately to the same terms.',
                                  source_order_budget='Initial and endpoint source-order inventories; left-to-right main.cpp residual equations and class-ordered external subtraction.',
                                  compensated_budget='Compensated inventories, then math.fsum over signed budget terms.',
                                  post_remap_ledger='The recorded residual combines pre-remap residual and remap transfer operations; their historical floating-point intermediates are not reconstructed.'),
                  scope='Single retained flood19 endpoint. Initial inventories are independently reconstructed from source-bound parameters and verified RNG/rounded geometry witnesses. Budget residuals use recorded external flux, signed forcing, recycling and correction ledgers; boundary exchanges are not independently reintegrated. No full-solid pass threshold, compiled-model bit identity, PDE evolution, earlier event arrays, capture/abandonment or avulsion inference.',
                  execution=dict(model_or_auditor_invocations=0, rng_witness_executions_during_replay=0, live_files_read=0))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(), 'output already exists')
    endpoint = args.folder.resolve().parent/'run29-flood19'
    require(endpoint not in args.output.resolve().parents, 'cannot write into the existing endpoint capsule')
    result = analyze(args.folder)
    blob = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    with args.output.open('xb') as stream:
        stream.write(blob); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(dict(status=result['status'], output=str(args.output), bytes=len(blob), sha256=sha(blob)), sort_keys=True))


if __name__ == '__main__':
    main()
