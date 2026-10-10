#!/usr/bin/env python3
"""Offline case-30 flood-6/7 inventory differences from two pinned capsules."""
import argparse
import ast
import csv
import hashlib
import io
import json
import math
import struct
import tarfile
from pathlib import Path

BINARY = 'b3d984881a2f82757ff9bb6ca7c15f9e3c28e3d34106ae477fe7c06af6f8099c'
DECODER = 'd6dc1e7833783c09039d7ce41854ac51de3642c6cfd046298dc5c2b35b1f31fd'
SOURCES = {
    'src/finite_volume.hpp': '57ac8606cd856046e13563fc0f07417943990fbc4f43340baf6f44aad427775d',
    'src/main.cpp': '812058d4ff97b618da08830e44a8704e4dc3a1431e0245136a301a0cd4375c90',
    'src/migration.hpp': '047475c7a53b933ccc83273e0576a820f681382fdf22b244a501006c68bf7196',
    'src/model.hpp': 'e12bb6c79a9e70ca53d555fc2d5cfcefed9b0cf2f8a3f7567defd650cc039a15',
    'src/sediment.hpp': '3c698eaf05771c09a26a152697fdcdacacf59b08ad18345efcdcaf1e35ccd4d2'}
PINS = [
    (6, 'sixth', 'ed4b93c0ad68664172a3abe58dc3454aee4b268447e3f718946369bb9e8c95e2',
     '3dc5f8ebec960afbccb1effbce0dfd47cc9d4d94c78c2d130dad9e1e3ddc6893',
     '2558a39aa6ec4fc16eb842261a3e565a3b4d8b348fa3e399a0a052c939fe24ed'),
    (7, 'seventh', 'ca48b47e7d7731184c8885a7a4e592f581cb27d6c85b28ac5befcf65b5dd15cd',
     'dfb8a935b69a3e28c486f6fd0053327adb1806c097a23db4118bc8a4cb5aa161',
     '02ffa75cc99a069634eb69db64c7dfe5b37ab6b2769065f7d2f6f38139c9ce4c')]
KEYS = ('length width dx channel_width slope initial_depth duration qmin qmax '
        'channel_chezy floodplain_chezy A C E migration_scale perturbation cfl max_dt '
        'porosity rho_s tau_critical sand_d silt_ws clay_d diffusion_scale '
        'concentration_scale seed run fine migration viscosity').split()
ARTIFACTS = ('checkpoint.bin', 'parameters.txt', 'process_status.json', 'summary.csv', 'remap_budget.csv')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def sequential_sum(values):
    total = 0.
    for value in values:
        total += value
    return total


def finite(value):
    if isinstance(value, dict):
        return all(finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite(v) for v in value)
    return not isinstance(value, (int, float)) or math.isfinite(value)


def load_capsule(pin, folder):
    flood, ordinal, manifest_sha, archive_sha, scalar_sha = pin
    folder = Path(folder)
    manifest_blob = (folder / 'run30-inventory-capture.json').read_bytes()
    require(sha(manifest_blob) == manifest_sha, 'capture manifest changed')
    manifest = json.loads(manifest_blob)
    archive_blob = (folder / 'run30-inventory-inputs.tar.xz').read_bytes()
    require(manifest['archive'] == 'run30-inventory-inputs.tar.xz', 'archive name changed')
    require(sha(archive_blob) == manifest['archive_sha256'] == archive_sha, 'archive changed')
    require(len(archive_blob) == manifest['archive_bytes'], 'archive length changed')
    scalar_name = 'run30-flood%d.json' % flood
    expected = set(SOURCES) | {'decoder-source.py', scalar_name, 'run30-inventory.py',
                               'run30-inventory.json'} | {'inputs/' + n for n in ARTIFACTS}
    require(len(expected) == 14 and set(manifest['member_sha256']) == expected, 'member manifest differs')
    with tarfile.open(fileobj=io.BytesIO(archive_blob), mode='r:xz') as archive:
        entries = archive.getmembers()
        require(len(entries) == 14 and {m.name for m in entries} == expected, 'missing/duplicate archive members')
        require(all(m.isfile() and m.type in (tarfile.REGTYPE, tarfile.AREGTYPE) for m in entries),
                'archive contains nonregular members')
        blobs = {m.name: archive.extractfile(m).read() for m in entries}
    require(all(sha(v) == manifest['member_sha256'][k] for k, v in blobs.items()), 'member digest differs')
    require(all(sha(blobs[k]) == v for k, v in SOURCES.items()), 'frozen source differs')
    require(sha(blobs['decoder-source.py']) == DECODER, 'reviewed decoder changed')
    require(sha(blobs[scalar_name]) == scalar_sha, 'scalar audit changed')
    audit = json.loads(blobs[scalar_name]); row = audit['cases']['30']
    observer = json.loads(blobs['run30-inventory.json'])
    process = json.loads(blobs['inputs/process_status.json'])
    require(finite([manifest, audit, observer, process]), 'nonfinite JSON input')
    require(audit['frozen_source_sha256'] == SOURCES and audit['binary_sha256'] == BINARY,
            'scalar source/binary identity differs')
    require(observer['scalar_audit_sha256'] == scalar_sha and observer['reviewed_decoder_source_sha256'] == DECODER,
            'observer input identity differs')
    require(observer['script_sha256'] == sha(blobs['run30-inventory.py']), 'observer source identity differs')
    require(row['hashes'] == observer['artifact_sha256'] ==
            {n: sha(blobs['inputs/' + n]) for n in ARTIFACTS}, 'observed artifact hashes disagree')
    identity = row['identity']
    require(identity['exe_sha256'] == BINARY and identity['argv_exact'], 'recorded executable identity differs')
    require(identity['argv'] == process['command'] == process['current_attempt']['command'], 'recorded argv differs')
    require(identity['pid'] == process['pid'] and identity['start_ticks'] == int(process['process_start_ticks']),
            'recorded process identity differs')
    for key in ('pid', 'start_ticks', 'argv', 'exe_sha256', 'cwd', 'exe', 'parent'):
        require(observer['process_identity'][key] == identity[key], 'observer process identity differs: ' + key)
    p = {}
    for line in blobs['inputs/parameters.txt'].decode().splitlines():
        key, value = line.split(' ', 1)
        if key != 'command':
            require(key not in p, 'duplicate parameter'); p[key] = float(value)
    require(set(p) == set(KEYS) | {'floods'} and finite(p), 'invalid parameters')
    require(p['run'] == 30 and p['floods'] == 580 and p['duration'] == 1728000 and
            p['dx'] == 250 and p['length'] == 72000 and p['width'] == 48000 and
            p['A'] == .012 and p['C'] == .0003 and p['E'] == 1.5, 'case scope differs')
    blob = blobs['inputs/checkpoint.bin']; slen = struct.unpack_from('<Q', blob)[0]
    require(0 < slen <= 4096, 'invalid signature length')
    signature = blob[8:8+slen].decode(); words = signature.split()
    require(len(words) == 32 and words[0] == 'ridge-checkpoint-v2' and
            all(float(v) == p[k] for k, v in zip(KEYS, words[1:])), 'checkpoint signature differs')
    fmt = '<idqqi4d3d5dQ'; header = struct.unpack_from(fmt, blob, 8+slen)
    cp = row['checkpoint']; n = header[-1]; offset = 8+slen+struct.calcsize(fmt)
    values = [cp['flood'], cp['clock'], cp['steps'], cp['channel_steps'], cp['cutoffs'],
              cp['net_external_water']] + cp['net_external_sediment'] + cp['bank'] + [
                  cp['deposited'], cp['signed_bed_forcing'], cp['recycled'], cp['water_correction'],
                  cp['mass_correction'], cp['nodes']]
    require(list(header) == values and finite(header), 'checkpoint header differs from scalar audit')
    require(header[0] == flood and header[1] == flood*p['duration'] and 2 <= n <= 100000,
            'checkpoint endpoint differs')
    size = int(p['length']/p['dx'])*int(p['width']/p['dx'])
    require(len(blob) == offset+64*n+56*size == cp['size_bytes'], 'checkpoint payload length differs')
    for name, key in (('summary.csv', 'summary'), ('remap_budget.csv', 'remap')):
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(io.StringIO(blobs['inputs/'+name].decode()))]
        require(finite(rows) and [r['flood'] for r in rows] == list(range(1, flood+1)), 'invalid scalar history')
        require(rows[-1] == row[key], 'scalar row differs from pinned audit')
    require(row['history'] == list(range(1, flood+1)), 'audit history differs')
    tree = ast.parse(blobs['decoder-source.py'])
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'decode_arrays']
    require(len(functions) == 1, 'reviewed decoder missing/duplicated')
    namespace = {'require': require, 'math': math, 'struct': struct}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<pinned-decode_arrays-only>', 'exec'), namespace)
    arrays = namespace['decode_arrays'](blob, p)
    require(finite(arrays), 'nonfinite decoded inventories')
    # Decode only payload views needed to distinguish temporal subtraction from
    # the unchanged decoder's independently aggregated endpoint inventories.
    line = list(struct.iter_unpack('<2d', blob[offset:offset+16*n])); offset += 16*n
    channel = list(struct.iter_unpack('<6d', blob[offset:offset+48*n])); offset += 48*n
    bed = [v[0] for v in struct.iter_unpack('<d', blob[offset:offset+8*size])]; offset += 8*size
    q = list(struct.iter_unpack('<6d', blob[offset:]))
    provenance = dict(flood=flood, manifest_sha256=manifest_sha, manifest_bytes=len(manifest_blob),
                      archive_sha256=archive_sha, archive_bytes=len(archive_blob),
                      member_sha256=manifest['member_sha256'], captured_utc=manifest['captured_utc'])
    return dict(blobs=blobs, row=row, p=p, signature=signature, arrays=arrays, bed=bed,
                line=line, channel=channel, q=q, provenance=provenance)


def source_order_inventory(case):
    """Diagnostic replay of model.hpp:181–188,451–455, without model evolution."""
    p = case['p']; dx = p['dx']; nx = int(p['length']/dx)
    s = [0.]
    for a, b in zip(case['line'], case['line'][1:]):
        s.append(s[-1]+math.hypot(b[0]-a[0], b[1]-a[1]))
    area = [.5*(s[min(i+1, len(s)-1)]-s[max(i-1, 0)])*p['channel_width'] for i in range(len(s))]
    inventory = [0.]*4
    for i, row in enumerate(case['q']):
        if not case['arrays']['mask'][i]:
            for j, k in enumerate((0, 3, 4, 5)):
                inventory[j] += row[k]*dx*dx
    for row, a in zip(case['channel'], area):
        for j, k in enumerate((0, 3, 4, 5)):
            inventory[j] += row[k]*a
    total = sequential_sum(inventory[1:])+sequential_sum(case['row']['checkpoint']['bank'])
    density = p['rho_s']*(1-p['porosity'])*dx*dx
    for i, z in enumerate(case['bed']):
        initial = p['slope']*(p['length']-(i % nx+.5)*dx)
        total += (z-initial)*density
    return inventory, total


def analyze(prior_folder, current_folder):
    a, b = [load_capsule(pin, folder) for pin, folder in zip(PINS, (prior_folder, current_folder))]
    require(a['p'] == b['p'] and a['signature'] == b['signature'], 'parameters/signatures differ')
    for name in ('parameters.txt', 'process_status.json'):
        require(a['blobs']['inputs/'+name] == b['blobs']['inputs/'+name], 'common input bytes differ')
    for name in ('summary.csv', 'remap_budget.csv'):
        require(b['blobs']['inputs/'+name].startswith(a['blobs']['inputs/'+name]), 'history prefix changed')
    for key in ('pid', 'start_ticks', 'argv', 'exe_sha256', 'cwd', 'exe', 'parent'):
        require(a['row']['identity'][key] == b['row']['identity'][key], 'process identity changed')
    ca, cb = a['row']['checkpoint'], b['row']['checkpoint']
    require(cb['steps'] > ca['steps'] and cb['channel_steps'] > ca['channel_steps'] and
            cb['recycled'] >= ca['recycled'] and cb['cutoffs'] >= ca['cutoffs'], 'counter reversed')
    p = a['p']; nq = 20000
    integral = math.fsum((1 if i in (0, nq) else 4 if i % 2 else 2)*
                        (p['qmin']+(p['qmax']-p['qmin'])*math.sin(math.pi*i/nq)**2)**2.5
                        for i in range(nq+1))*p['duration']/(3*nq)
    water_input = p['duration']*(p['qmin']+p['qmax'])/2
    sediment_input = p['C']*p['concentration_scale']*integral
    ia, ib = a['arrays']['inventory'], b['arrays']['inventory']
    ba, bb = math.fsum(ca['bank']), math.fsum(cb['bank'])
    sa, sb = math.fsum(ia[1:]), math.fsum(ib[1:])
    fa = math.fsum([a['arrays']['bed_mass'], sa, ba])
    fb = math.fsum([b['arrays']['bed_mass'], sb, bb])
    delta_external = math.fsum(y-x for x, y in zip(ca['net_external_sediment'], cb['net_external_sediment']))
    delta_recycled = cb['recycled']-ca['recycled']
    delta_forcing = cb['signed_bed_forcing']-ca['signed_bed_forcing']
    delta_mass_correction = cb['mass_correction']-ca['mass_correction']
    def residuals(wa, wb, s0, s1, full_delta):
        return dict(water=math.fsum([wb-wa, -(cb['net_external_water']-ca['net_external_water']),
                                    -(cb['water_correction']-ca['water_correction'])]),
                    suspension_plus_deposition=math.fsum([s1-s0, cb['deposited']-ca['deposited'],
                                                         -delta_external, -delta_mass_correction]),
                    full_solid=math.fsum([full_delta, delta_recycled, -delta_forcing,
                                         -delta_external, -delta_mass_correction]))
    native = residuals(ia[0], ib[0], sa, sb, fb-fa)
    keys = dict(water='post_water_residual', suspension_plus_deposition='post_sediment_residual',
                full_solid='post_solid_sediment_residual')
    ledger = {k: b['row']['remap'][v]-a['row']['remap'][v] for k, v in keys.items()}
    def comparison(values):
        return {k: dict(inventory_based=value, recorded_residual_difference=ledger[k],
                        signed_discrepancy=value-ledger[k], absolute_discrepancy=abs(value-ledger[k]),
                        inventory_based_over_one_hydrograph=value/(water_input if k == 'water' else sediment_input),
                        discrepancy_over_one_hydrograph=(value-ledger[k])/(water_input if k == 'water' else sediment_input))
                for k, value in values.items()}
    density = p['rho_s']*(1-p['porosity'])*p['dx']*p['dx']
    stable_bed_delta = math.fsum((y-x)*density for x, y in zip(a['bed'], b['bed']))
    stable_full_delta = math.fsum([stable_bed_delta, sb-sa, bb-ba])
    stable = residuals(ia[0], ib[0], sa, sb, stable_full_delta)
    oa, ofa = source_order_inventory(a); ob, ofb = source_order_inventory(b)
    ordered = residuals(oa[0], ob[0], sequential_sum(oa[1:]), sequential_sum(ob[1:]), ofb-ofa)
    masks = [a['arrays']['mask'], b['arrays']['mask']]
    captured = [i for i, (x, y) in enumerate(zip(*masks)) if not x and y]
    abandoned = [i for i, (x, y) in enumerate(zip(*masks)) if x and not y]
    common = [i for i, (x, y) in enumerate(zip(*masks)) if x and y]
    pre_bank = b['row']['summary']['bank_mass']
    result = dict(scope='Offline differences of two retained post-remap checkpoints; no live observer or model execution.',
                  script_sha256=sha(Path(__file__).read_bytes()), input_provenance=[a['provenance'], b['provenance']],
                  frozen_source_sha256=SOURCES, recorded_binary_sha256=BINARY,
                  binary_pin_scope='Verified by the pinned capture observers; executable bytes are not capsule members.',
                  process_identity=a['row']['identity'], parameters=p,
                  endpoints=[dict(flood=c['row']['checkpoint']['flood'], clock=c['row']['checkpoint']['clock'],
                                  bank_by_class_kg=c['row']['checkpoint']['bank'],
                                  water_and_suspended_class_inventory=c['arrays']['inventory'],
                                  signed_bed_inventory_relative_to_common_plane_kg=c['arrays']['bed_mass'],
                                  signed_full_solid_inventory_kg=f,
                                  array_checks={k: v for k, v in c['arrays'].items() if k not in ('mask', 'inventory', 'bed_mass')})
                             for c, f in ((a, fa), (b, fb))],
                  one_prescribed_hydrograph=dict(water_m3=water_input, sediment_kg=sediment_input,
                                                simpson_intervals=nq, recycling_excluded=True),
                  temporal_balances=comparison(native),
                  temporal_deltas=dict(water_inventory_m3=ib[0]-ia[0],
                                       suspended_inventory_by_class_kg=[y-x for x, y in zip(ia[1:], ib[1:])],
                                       suspended_inventory_kg=sb-sa, deposited_kg=cb['deposited']-ca['deposited'],
                                       bank_inventory_kg=bb-ba, recycled_kg=delta_recycled,
                                       bed_forcing_kg=delta_forcing,
                                       external_water_m3=cb['net_external_water']-ca['net_external_water'],
                                       external_sediment_kg=delta_external,
                                       water_correction_m3=cb['water_correction']-ca['water_correction'],
                                       mass_correction_kg=delta_mass_correction),
                  arithmetic_diagnostics=dict(
                      stable_cellwise_bed_difference_kg=stable_bed_delta,
                      difference_of_endpoint_bed_inventories_kg=b['arrays']['bed_mass']-a['arrays']['bed_mass'],
                      stable_cellwise_minus_endpoint_bed_difference_kg=stable_bed_delta-(b['arrays']['bed_mass']-a['arrays']['bed_mass']),
                      stable_cellwise_full_solid_balance=comparison(stable)['full_solid'],
                      source_order_endpoint_water_and_class_inventories=[oa, ob],
                      source_order_endpoint_full_solid_kg=[ofa, ofb],
                      source_order_full_solid_minus_compensated_kg=[ofa-fa, ofb-fb],
                      source_order_temporal_balances=comparison(ordered),
                      interpretation='Ordered additions replay the frozen diagnostic expressions, not hydrodynamics. '
                      'This Python calculation is not claimed bitwise identical to compiled C++ arithmetic. '
                      'Stable cellwise bed differences avoid subtracting two large signed bed totals. '
                      'All discrepancies are reported without a fitted pass threshold; these are arithmetic diagnostics, '
                      'not discretization error bounds or independent evidence of long-term scientific agreement.'),
                  bank_balance=dict(post6_bank_kg=ba, recycled_during7_kg=delta_recycled,
                                    pre7_remap_bank_kg_from_12_digit_summary=pre_bank,
                                    post6_minus_recycled_minus_pre7_kg=ba-delta_recycled-pre_bank,
                                    post7_bank_kg=bb, ledger_derived_remap7_bank_addition_kg=bb-pre_bank),
                  raster_transitions=dict(indexing='zero-based row-major i=j*nx+x, nx=288; cell area 62500 m2',
                                          old_channel_cells=sum(masks[0]), new_channel_cells=sum(masks[1]),
                                          captured_ids=captured, captured_count=len(captured),
                                          abandoned_ids=abandoned, abandoned_count=len(abandoned),
                                          common_channel_ids=common, common_channel_count=len(common),
                                          common_floodplain_count=sum(not x and not y for x, y in zip(*masks)),
                                          mask_sha256=[sha(bytes(m)) for m in masks],
                                          recorded_cutoff_counters=[ca['cutoffs'], cb['cutoffs']]),
                  equations=dict(
                      water='Delta W - Delta external_water - Delta water_correction = Delta post_water_residual',
                      suspension='Delta suspended + Delta deposited - sum(Delta external_sediment) - Delta mass_correction = Delta post_sediment_residual',
                      solid='Delta(suspended + signed_bed + bank) + Delta recycled - Delta bed_forcing - sum(Delta external_sediment) - Delta mass_correction = Delta post_solid_sediment_residual',
                      bank='B7_pre = B6_post - (R7-R6) + floating-point error; B7_post = B7_pre + remap7_bank_addition',
                      bank_source='rho_s*(1-porosity)*dx^2 * sum_captured max(z_pre7 - z_new_before_prescribed_A, 0)',
                      source_lines={'src/main.cpp': '58-70,87-109', 'src/model.hpp': '125-146,170-173,181-188,320-334,339-354,383-449,451-455',
                                    'src/migration.hpp': '168-207'}),
                  limitations=[
                      'Post6 is the fixed geometry throughout flood7 transport; only the end-of-flood remap changes its raster mask.',
                      'Transitions are endpoint raster membership changes, not counts of physical erosion events or continuous swept-bank area.',
                      'Internal migration substeps and cutoff processing do not each remap fluid or add bank mass.',
                      'Pre-remap flood7 bed is absent. Flood7 deposition changes the post6 bed; captured cells are then overwritten.',
                      'No per-cell excavation volume or mass is inferred from post6 bed. The bank addition is ledger-derived.',
                      'No initial water or solid reference is inferred. Signed bed uses the same fixed plane at both endpoints.',
                      'Recycled bank enters the external sediment ledger and leaves bank inventory; the full-solid balance therefore adds Delta recycled.',
                      'The immutable reviewed decoder is AST-loaded alone; neither archived live observer is rerun.'])
    require(finite(result), 'nonfinite comparison result')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prior_folder', type=Path)
    parser.add_argument('current_folder', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_suffix('.json'))
    args = parser.parse_args()
    require(not args.output.exists(), 'output already exists; preserve prior evidence')
    result = analyze(args.prior_folder, args.current_folder)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n'
    with args.output.open('x') as stream:
        stream.write(payload)
    print(json.dumps(dict(output=str(args.output), sha256=sha(payload.encode()),
                          temporal_balances=result['temporal_balances'],
                          arithmetic_diagnostics=result['arithmetic_diagnostics'],
                          bank_balance=result['bank_balance'],
                          captured_count=result['raster_transitions']['captured_count'],
                          abandoned_count=result['raster_transitions']['abandoned_count']), sort_keys=True))


if __name__ == '__main__':
    main()
