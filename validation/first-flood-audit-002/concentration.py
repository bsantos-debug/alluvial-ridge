#!/usr/bin/env python3
"""Replay the completed first-flood concentration comparison from adjacent retained files."""
import sys
sys.dont_write_bytecode = True
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import tarfile

CASES = ('baseline250', 'concentration_half', 'concentration_double')
BINARY = 'b3d984881a2f82757ff9bb6ca7c15f9e3c28e3d34106ae477fe7c06af6f8099c'
HELPER_SHA256 = '7e304445cbc8fab0c6eb9068328d3707a9f47906ca21371c5f5b258fd0427073'
FROZEN_SOURCE_SHA256 = {
    'src/finite_volume.hpp': '57ac8606cd856046e13563fc0f07417943990fbc4f43340baf6f44aad427775d',
    'src/main.cpp': '812058d4ff97b618da08830e44a8704e4dc3a1431e0245136a301a0cd4375c90',
    'src/migration.hpp': '047475c7a53b933ccc83273e0576a820f681382fdf22b244a501006c68bf7196',
    'src/model.hpp': 'e12bb6c79a9e70ca53d555fc2d5cfcefed9b0cf2f8a3f7567defd650cc039a15',
    'src/sediment.hpp': '3c698eaf05771c09a26a152697fdcdacacf59b08ad18345efcdcaf1e35ccd4d2'}
PROVENANCE_SHA256 = '66d040d7d9a77b6725efc3d1beaa1089ae6b82df072463ed6b80210401715a94'
SCOPE = ('Completed first-flood sediment-concentration sensitivity only; no grid or temporal '
         'convergence, 580-flood behavior, or manuscript-panel assessment.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def verify(folder):
    """Return recomputed analysis/evidence; never read live or historical source paths."""
    folder = Path(folder)
    helper_file = folder / 'time-step.py'
    require(sha(helper_file.read_bytes()) == HELPER_SHA256, 'retained numeric helper hash differs')
    helper = runpy.run_path(str(helper_file))
    artifacts = helper['ARTIFACTS']
    capture_bytes = (folder / 'concentration-capture.json').read_bytes()
    capture = json.loads(capture_bytes.decode())
    require(capture['format'] == 1 and capture['stability_check']['unchanged_files'] == 36 and
            capture['stability_check']['minimum_pause_seconds'] >= 2,
            'unsupported capture format or missing stable terminal capture')
    archive_bytes = (folder / 'concentration-inputs.tar.xz').read_bytes()
    require(capture['archive']['file'] == 'concentration-inputs.tar.xz' and
            len(archive_bytes) == capture['archive']['bytes'] and
            sha(archive_bytes) == capture['archive']['sha256'], 'retained archive size or hash differs')
    require(capture['source_identity']['corrected_binary_sha256'] == BINARY and
            capture['source_identity']['byte_order'] == 'little' and
            capture['source_identity']['pointer_and_size_t_bytes'] == 8 and
            capture['source_identity']['frozen_source_sha256'] == FROZEN_SOURCE_SHA256 and
            capture['source_identity']['validation_provenance_sha256'] == PROVENANCE_SHA256 and
            capture['helper_sha256'] == {'time-step.py': HELPER_SHA256} and
            set(capture['source_identity']['cases']) == set(CASES),
            'incorrect captured executable/layout/helper identity')
    expected = capture['archive']['member_sha256']
    required = {'validation/runs/' + case + '/' + filename
                for case in CASES for filename in artifacts + ('process_status.json',)}
    require(set(expected) == required and capture['archive']['members'] == len(required),
            'capture does not describe exactly the three corrected completed cases')
    members = {}
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:xz') as archive:
        for item in archive:
            require(item.isfile() and item.name in required and item.name not in members,
                    'unsafe, duplicate, or unexpected archive member')
            require((item.mode, item.uid, item.gid, item.uname, item.gname, item.mtime) ==
                    (0o644, 0, 0, '', '', 0), 'archive metadata is not normalized')
            blob = archive.extractfile(item).read()
            require(sha(blob) == expected[item.name], 'archive member hash differs: ' + item.name)
            members[item.name] = blob
    require(list(members) == sorted(required), 'retained archive is incomplete or not sorted')
    cases, arrays, geometry = {}, {}, {}
    for name, scale in zip(CASES, (.001, .0005, .002)):
        prefix = 'validation/runs/' + name + '/'
        data = {filename: members[prefix + filename] for filename in artifacts + ('process_status.json',)}
        process = json.loads(data['process_status.json'].decode())
        require(process['state'] == 'complete' and process['exit_code'] == 0 and
                process['binary_sha256'] == BINARY and process['name'] == name,
                'case lacks the corrected completed process identity')
        require(set(process['artifact_sha256']) == set(artifacts) and
                all(sha(data[f]) == process['artifact_sha256'][f] for f in artifacts),
                'completed process artifact hashes differ')
        identity = capture['source_identity']['cases'][name]
        require(identity['process_pid'] == process['pid'] and
                identity['process_pid_absent_at_capture'] is True and
                identity['original_command'] == process['command'] and
                identity['utc_started'] == process['utc_started'] and
                identity['utc_finished'] == process['utc_finished'] and
                set(identity['source_files']) == set(data) and
                all(identity['source_files'][f]['sha256'] == sha(blob) and
                    identity['source_files'][f]['bytes'] == len(blob) for f, blob in data.items()),
                'capture identity differs from retained terminal records')
        command = process['command']
        require(len(command) % 2 == 1 and Path(command[0]).name == 'ridge-' + BINARY,
                'unexpected original executable command')
        options = dict(zip(command[1::2], command[2::2]))
        flags = {'--config', '--runs', '--run', '--floods', '--out'}
        if name != CASES[0]:
            flags.add('--concentration-scale')
            require(options.get('--concentration-scale') == str(scale), 'incorrect concentration command')
        require(set(options) == flags and len(options) == len(command) // 2 and
                options['--floods'] == '1' and options['--run'] == '11' and
                Path(options['--out']).name == name, 'unexpected original process command')
        parameters = {}
        parameter_lines = data['parameters.txt'].decode().splitlines()
        require(parameter_lines[0] == 'command ' + ' '.join(command),
                'parameter command differs from terminal process record')
        for line in parameter_lines[1:]:
            key, value = line.split(' ', 1)
            require(key not in parameters, 'duplicate numerical parameter')
            parameters[key] = float(value)
        require(set(parameters) == set(helper['SIGNATURE_KEYS']) | {'floods'} and
                all(math.isfinite(v) for v in parameters.values()) and
                all(parameters[k] == v for k, v in dict(concentration_scale=scale, tau_critical=.1, cfl=.4,
                    floods=1, run=11, dx=250, length=72000, width=48000, duration=1728000,
                    A=0, C=.003, E=1, fine=0).items()), 'unexpected first-flood parameters')
        require(data['status.txt'].decode().strip() == 'complete 1 floods', 'case status is incomplete')
        summary = helper['one_row'](data['summary.csv'])
        remap = helper['one_row'](data['remap_budget.csv'])
        phases, arrays[name], geometry[name] = {}, {}, {}
        for phase, fraction, prefix_file in (('peak', .6, 'peak_'), ('end', 1., '')):
            metadata, cells = helper['field'](data[prefix_file + 'fields_0001.bin'], parameters, fraction)
            rows = helper['csv_rows'](data[prefix_file + 'channel_0001.csv'])
            require(len(rows) == metadata['channel_nodes'] and
                    all(all(math.isfinite(v) for v in row.values()) and row['water_depth'] >= 0 and
                        row['control_area'] > 0 for row in rows), 'invalid matching channel snapshot')
            geometry[name][phase] = [(r['x'], r['y']) for r in rows]
            phases[phase], arrays[name][phase] = helper['snapshot'](metadata, cells), cells
        require(geometry[name]['peak'] == geometry[name]['end'] and
                [c[3] for c in arrays[name]['peak']] == [c[3] for c in arrays[name]['end']],
                'channel geometry changed within the first flood')
        inputs = helper['normalization'](parameters)
        water, sediment = inputs['prescribed_water_input_m3'], inputs['prescribed_sediment_input_kg']
        normalized = dict(pre_water=summary['water_residual'] / water,
                          pre_suspension_plus_deposition=summary['sediment_residual'] / sediment,
                          pre_full_solid=summary['solid_sediment_residual'] / sediment,
                          post_water=remap['post_water_residual'] / water,
                          post_suspension_plus_deposition=remap['post_sediment_residual'] / sediment,
                          post_full_solid=remap['post_solid_sediment_residual'] / sediment)
        stored = helper['checkpoint'](data['checkpoint.bin'], parameters, arrays[name]['end'])
        require(all(math.isfinite(v) for v in normalized.values()) and water > 0 and sediment > 0,
                'invalid prescribed inputs or normalized residuals')
        require(stored['steps'] == summary['steps'] and stored['channel_steps'] == summary['channel_steps'] and
                stored['cutoffs'] == summary['cutoffs'], 'checkpoint and completed summary counts differ')
        cases[name] = dict(parameters=parameters, process=process, summary=summary, remap=remap,
                           prescribed_inputs=inputs, signed_residuals_over_prescribed_input=normalized,
                           checkpoint=stored, peak=phases['peak'], end=phases['end'])
    baseline, comparisons = cases[CASES[0]], {}
    metrics = ('alpha', 'interface_fraction', 'mean_water', 'beta', 'ridge_height', 'channel_depth',
               'water_storage', 'steps', 'channel_steps', 'wall_seconds')
    for name, scale in zip(CASES[1:], (.0005, .002)):
        candidate = cases[name]
        differences = {key: [baseline['parameters'][key], candidate['parameters'][key]]
                       for key in baseline['parameters']
                       if baseline['parameters'][key] != candidate['parameters'][key]}
        require(differences == {'concentration_scale': [.001, scale]} and geometry[CASES[0]] == geometry[name],
                'cases differ in more than concentration scale or initial channel geometry')
        percentages = {key: 100 * (candidate['summary'][key] / baseline['summary'][key] - 1)
                       if baseline['summary'][key] else None for key in metrics}
        percentages['deposited_mass'] = 100 * (candidate['checkpoint']['deposited_mass_kg'] /
                                             baseline['checkpoint']['deposited_mass_kg'] - 1)
        comparisons[name] = dict(parameter_differences=differences,
            concentration_relative_to_baseline_percent=percentages,
            same_grid_fields={phase: helper['compare_fields'](arrays[CASES[0]][phase], arrays[name][phase], 250.)
                              for phase in ('peak', 'end')})
    return dict(format=1, status='verified', scope=SCOPE, processor_sha256=sha(Path(__file__).read_bytes()),
                evidence=dict(captured_utc=capture['captured_utc'], capture_sha256=sha(capture_bytes),
                              archive_sha256=sha(archive_bytes), member_sha256=expected,
                              helper_sha256={'time-step.py': HELPER_SHA256}, binary_sha256=BINARY,
                              original_source_identity=capture['source_identity']),
                baseline_case=CASES[0], cases=cases, comparisons=comparisons,
                method=dict(difference='Candidate minus baseline250 (concentration_scale 0.001); percentage denominator is baseline250.',
                    snapshot_phase='peak is day 12; end is day 20 before migration/aggradation; checkpoint is after remap',
                    field_domain='identical physical floodplain cells, including dry cells; fixed within-flood channel mask',
                    storage_bounds='Conservative float32 half-ULP storage bounds only; exclude discretization, separate float64 arithmetic error, and CSV rounding.',
                    deposit_volume='Bulk event-deposit volume includes pore space; peak deposition is cumulative through day 12.',
                    deposited_mass='Cumulative mineral mass from deposition sources in the complete checkpoint; excludes pore space and is not the raster bulk-deposit volume.',
                    normalization='Gross prescribed upstream input for one sinusoidal flood, using the actual C and concentration_scale of each case; excludes recycling, outlet flux, and signed bed forcing. This is not the checkpoint net external ledger.',
                    post_remap='Retained remap-ledger residuals; checkpoint payload checked for layout, clocks, parameter signature, finite state, and nonnegative inventories. Physical inventory balances are not independently reconstructed here.',
                    arithmetic='Saved float32 values promoted to Python float; reductions use math.fsum.',
                    checkpoint_layout='Captured little-endian v2, 64-bit size_t and step counters; full payload checked.'))


def main():
    require(len(sys.argv) <= 2, 'usage: concentration.py [retained-folder]')
    folder = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).resolve().parent
    result = verify(folder)
    require(json.loads((folder / 'concentration.json').read_text()) == result,
            'saved analysis differs from verified archive replay')
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
