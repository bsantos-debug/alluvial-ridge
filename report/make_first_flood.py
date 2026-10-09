#!/usr/bin/env python3
"""Render the retained first-flood observations without reading live run files."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OBSERVATION = 'production-observation-20261009T213916.json'
REQUIRED = ('audit.py', 'audit.json', 'initial-observation.json',
            'two-resolution.py', 'two-resolution.json',
            'production-observation.py', OBSERVATION)


def sha(path):
    with path.open('rb') as stream:
        return digest(stream)


def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1048576), b''):
        value.update(block)
    return value.hexdigest()


def label(path):
    return str(path.resolve().relative_to(ROOT))


def tex(value):
    return ''.join({'_': r'\_', '%': r'\%', '&': r'\&', '#': r'\#',
                    '{': r'\{', '}': r'\}', '$': r'\$',
                    '\\': r'\textbackslash{}'}.get(c, c) for c in str(value))


def number(value, digits=6):
    if value == 0:
        return '0'
    mantissa, exponent = ('%.*e' % (digits - 1, value)).split('e')
    return r'%s\times10^{%d}' % (mantissa.rstrip('0').rstrip('.'), int(exponent))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_members(path, expected, members):
    seen, process_records = set(), {}
    # Read member bytes in place; never extract or consult the changing live paths.
    with tarfile.open(str(path), mode='r|*') as archive:
        for member in archive:
            require(member.isfile() and member.name in expected and member.name not in seen,
                    'unexpected or duplicate input-archive member: ' + member.name)
            stream = archive.extractfile(member)
            if member.name.endswith('/process_status.json'):
                data = stream.read()
                actual = hashlib.sha256(data).hexdigest()
                process_records[member.name] = json.loads(data.decode())
            else:
                actual = digest(stream)
            require(actual == expected[member.name],
                    'captured input hash mismatch: ' + member.name)
            seen.add(member.name)
    require(seen == set(expected) and len(seen) == members,
            'incomplete captured input archive')
    return process_records


def verify_archive(folder, evidence):
    manifest_path = folder / 'capture-provenance.json'
    manifest = json.loads(manifest_path.read_text())
    evidence['capture_manifest_sha256'] = sha(manifest_path)
    files = manifest['files_sha256']
    require(all(name in files for name in REQUIRED), 'incomplete capture manifest')
    for name, expected in files.items():
        require(Path(name).name == name, 'capture entries must be archive basenames')
        path = folder / name
        actual = sha(path)
        evidence['archive_sha256'][name] = actual
        require(actual == expected, 'archive hash mismatch: ' + name)
    comparison = json.loads((folder / 'two-resolution.json').read_text())
    observation = json.loads((folder / OBSERVATION).read_text())
    retained = manifest['production_input_archive']
    require(retained['observation'] == OBSERVATION, 'unexpected input-archive observation')
    require(retained['file'] in files, 'input archive is not hash-bound')
    expected = observation['input_sha256']
    verify_members(folder / retained['file'], expected, retained['members'])
    evidence['verified_production_input_count'] = len(expected)
    evidence['production_input_sha256'] = expected
    retained = manifest['sensitivity_input_archive']
    require(retained['file'] in files, 'sensitivity input archive is not hash-bound')
    expected = retained['files_sha256']
    required_members = set()
    for name in ('baseline250', 'coarse500'):
        prefix = 'validation/runs/' + name + '/'
        required_members.add(prefix + 'process_status.json')
        for filename, checksum in comparison['cases'][name]['process']['artifact_sha256'].items():
            key = prefix + filename
            require(expected.get(key) == checksum, 'sensitivity artifact identity differs: ' + key)
            required_members.add(key)
    require(set(expected) == required_members, 'unexpected sensitivity input set')
    records = verify_members(folder / retained['file'], expected, retained['members'])
    for name in ('baseline250', 'coarse500'):
        key = 'validation/runs/' + name + '/process_status.json'
        require(records[key] == comparison['cases'][name]['process'],
                'retained sensitivity process record differs: ' + name)
    evidence['verified_sensitivity_input_count'] = len(expected)
    evidence['sensitivity_input_sha256'] = expected
    return comparison, observation


def measurements(comparison, observation):
    require(comparison['all_completed_artifact_hashes_verified'] is True,
            'completed sensitivity artifact verification was not recorded')
    cases = comparison['cases']
    fine, coarse = cases['baseline250'], cases['coarse500']
    for case, spacing in ((fine, 250), (coarse, 500)):
        require(case['state'] == case['process']['state'] == 'complete'
                and case['process']['exit_code'] == 0, 'sensitivity case is incomplete')
        require(case['parameters']['dx'] == spacing and case['snapshot']['flood'] == 1
                and case['snapshot']['elapsed_seconds'] == 1728000,
                'unexpected sensitivity grid or sampling time')
        require(case['peak']['clock_seconds'] == 1036800
                and case['end']['clock_seconds'] == 1728000,
                'unexpected peak or end-flood sampling time')
        require(case['process']['binary_sha256'] == observation['binary_sha256'],
                'sensitivity and production executable identities differ')
    require({k: v for k, v in fine['parameters'].items() if k != 'dx'} ==
            {k: v for k, v in coarse['parameters'].items() if k != 'dx'},
            'sensitivity parameters differ beyond floodplain spacing')
    require(observation['all_live_identity_checks_passed'] is True
            and observation['all_finite_positivity_signature_checks_passed'] is True,
            'production capture did not pass its recorded checks')
    rows = observation['records']
    require(sorted(r['run'] for r in rows) == list(range(1, 32)),
            'production capture does not contain each of the 31 cases once')
    require(all(r['completed_floods'] == 1 and r['progress_flood'] == 2 for r in rows),
            'unexpected production capture window')
    require(all(math.isfinite(v) for r in rows for v in r.values()
                if isinstance(v, (int, float))), 'nonfinite production observation')
    budgets = []
    for key, title, unit in (
            ('post_water_residual', 'Water', r'm$^3$'),
            ('post_sediment_residual', 'Suspension + deposited sediment', 'kg'),
            ('post_solid_sediment_residual', 'Full solid inventory', 'kg')):
        maximum = max(rows, key=lambda r: abs(r[key]))
        relative_key = key + '_relative_input'
        normalized = max(rows, key=lambda r: abs(r[relative_key]))
        budgets.append(dict(quantity=title, unit=unit,
                            maximum_absolute=abs(maximum[key]), run=maximum['run'],
                            maximum_relative_input=abs(normalized[relative_key]),
                            relative_run=normalized['run']))
    zeros = ('captured_cells', 'abandoned_cells', 'bank_mass', 'water_correction',
             'mass_correction', 'cutoffs', 'recycled_mass')
    require(all(r[k] == 0 for r in rows for k in zeros),
            'captured bank, correction, or cutoff records changed')
    deposit_change = 100 * (coarse['checkpoint']['deposited_mass_kg'] /
                            fine['checkpoint']['deposited_mass_kg'] - 1)
    forcing_min = min(rows, key=lambda r: r['bed_forcing_mass'])
    forcing_max = max(rows, key=lambda r: r['bed_forcing_mass'])
    return dict(production_utc=observation['utc'], production_count=len(rows),
                post_remap_budgets=budgets, all_zero_quantities=list(zeros),
                coarse_deposit_mass_change_percent=deposit_change,
                signed_bed_forcing_kg=dict(minimum=forcing_min['bed_forcing_mass'],
                                          minimum_run=forcing_min['run'],
                                          maximum=forcing_max['bed_forcing_mass'],
                                          maximum_run=forcing_max['run']),
                minimum_channel_depth_m=min(r['min_channel_h'] for r in rows),
                binary_sha256=observation['binary_sha256'])


def render(comparison, measured):
    cases = comparison['cases']
    fine, coarse = cases['baseline250'], cases['coarse500']
    lines = [r'\subsection{Archived first-flood validation}',
             r'\label{sec:first-flood-validation}',
             'The corrected rebuild 002 provides provisional evidence over the first',
             '20-day hydrograph. These archived observations establish a limited',
             'numerical check; they do not supply any requested manuscript panel.',
             'The 250 m and 500 m floodplain cases use configuration 11 and the full',
             '72 km by 48 km domain. Their recorded parameters differ only in',
             'floodplain spacing; channel-node spacing remains 250 m. The capture',
             'verified both completed process records and their output hashes.',
             '', r'\begin{center}\small', r'\begin{tabular}{lrr}', r'\toprule',
             r'Quantity & 250 m grid & 500 m grid \\', r'\midrule']
    for title, group, key in (
            (r'Day-12 connectivity $\alpha$ (m)', 'metrics', 'alpha'),
            (r'End-flood ridge height (m)', 'metrics', 'ridge_height'),
            (r'End-flood relative relief $\beta$', 'metrics', 'beta'),
            (r'Deposited mineral mass (kg)', 'checkpoint', 'deposited_mass_kg'),
            (r'New channel cells after remap', 'checkpoint', 'new_channel_cells'),
            (r'Bank reservoir after remap (kg)', 'checkpoint', 'bank_mass_kg')):
        values = [case[group][key] for case in (fine, coarse)]
        formatted = [str(int(v)) if key == 'new_channel_cells' else '$' + number(v) + '$'
                     for v in values]
        lines.append(title + ' & ' + ' & '.join(formatted) + r' \\')
    lines += [r'\bottomrule\end{tabular}\end{center}',
              'Deposited mass is the accumulated deposition source ledger retained',
              'in the checkpoint, not a post-remap integral of the remaining deposit.',
              'The coarse-grid deposited mass exceeds the fine-grid value by',
              r'%.2f\%%. Both day-12 inundated interface fractions equal one.' %
              measured['coarse_deposit_mass_change_percent']]
    require(fine['metrics']['interface_fraction'] == coarse['metrics']['interface_fraction'] == 1,
            'unexpected inundated interface fractions')
    common = comparison['common_floodplain_fields']
    lines += ['The end-flood comparison averages each two-by-two block of fine cells',
              'onto the coarse grid and excludes blocks containing any channel cell.',
              'Over the resulting %.0f km$^2$ common floodplain, water-depth differences' %
              (common['common_floodplain_area_m2'] / 1e6),
              'have mean absolute value %.6f m and maximum %.6f m.' %
              (common['mean_absolute_difference_m']['water_depth'],
               common['maximum_absolute_difference_m']['water_depth']),
              'These averages include dry areas and omit the excluded channel blocks.',
              '',
              'The coarser grid captures %d bank cells after the first hydrograph,' %
              coarse['checkpoint']['new_channel_cells'],
              'whereas the finer grid captures none. This difference changes the',
              'reservoir available for later recycling. Capture occurs after the',
              'hydrograph and therefore cannot explain the first-flood deposit-mass',
              'difference. The adaptive time steps also change with floodplain',
              'spacing. Two first-flood cases with fixed channel spacing do not',
              'establish spatial or temporal convergence, nor do they test recycling',
              'through a subsequent complete hydrograph.',
              '',
              'The historical production observation at %s records all 31 cases' %
              tex(measured['production_utc']),
              'after their first remap, while their live progress records indicated',
              'flood 2. The recorded process identities, finite-value checks,',
              'positivity checks, and checkpoint signatures passed. Every case had',
              'zero captured or abandoned raster cells, bank reservoir, recycled',
              'mass, cutoff count, and water or mass correction ledger.',
              'The largest absolute post-remap residuals across those cases were:',
              '', r'\begin{center}\small', r'\begin{tabular}{lrrrr}', r'\toprule',
              r'Inventory & Absolute residual & Run & Relative to input & Run \\', r'\midrule']
    for row in measured['post_remap_budgets']:
        lines.append(r'%s & $%s$ %s & %02d & $%s$ & %02d \\' %
                     (row['quantity'], number(row['maximum_absolute']), row['unit'],
                      row['run'], number(row['maximum_relative_input']), row['relative_run']))
    lines += [r'\bottomrule\end{tabular}\end{center}',
              'Absolute and normalized maxima are selected separately and can occur',
              'in different runs. Normalization uses the prescribed cumulative',
              'upstream water or sediment input through the first hydrograph.',
              'It excludes recycled bank material and independent signed bed forcing',
              'from the denominator; it is neither current storage nor net input.',
              'The full-solid residual includes bank and bed accounting with the',
              'prescribed signed bed forcing subtracted. These small first-flood',
              'residuals constrain conservation over the captured interval only.',
              'The separately recorded signed bed forcing ranges from $%s$ kg' %
              number(measured['signed_bed_forcing_kg']['minimum']),
              '(run %02d) to $%s$ kg (run %02d).' %
              (measured['signed_bed_forcing_kg']['minimum_run'],
               number(measured['signed_bed_forcing_kg']['maximum']),
               measured['signed_bed_forcing_kg']['maximum_run']),
              'This prescribed geometry and aggradation forcing contributes to',
              'solid-inventory change independently of suspended transport.',
              '',
              'The earlier coarse-grid observations remain in the same archive.',
              'This section verifies the capture manifest, archived analysis scripts',
              'and JSON records, together with all %d retained production-input' %
              measured['verified_production_input_count'],
              'and %d completed sensitivity-input file hashes.' %
              measured['verified_sensitivity_input_count'],
              'It reads no live process or checkpoint. Artifact and generator',
              r'identities are recorded in \path{report/generated/first_flood_evidence.json};',
              r'the retained sources are in \path{validation/first-flood-audit-002}.',
              'Later conservation drift, bank recycling, finer-grid and time-step',
              'sensitivity, and long-term morphology require further assessment.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-root', type=Path, default=ROOT / 'validation/first-flood-audit-002')
    parser.add_argument('--output', type=Path, default=ROOT / 'report/generated')
    args = parser.parse_args()
    args.output.resolve().relative_to(ROOT)
    evidence = dict(status='pending', archive=label(args.archive_root),
                    generator_sha256=sha(Path(__file__)), archive_sha256={})
    try:
        comparison, observation = verify_archive(args.archive_root, evidence)
        measured = measurements(comparison, observation)
        measured['verified_production_input_count'] = evidence['verified_production_input_count']
        measured['verified_sensitivity_input_count'] = evidence['verified_sensitivity_input_count']
        content = render(comparison, measured)
        evidence.update(status='verified historical observations', measurements=measured,
                        scope='first flood only; no manuscript-panel assessment')
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        reason = ('Missing retained file: ' + Path(error.filename).name
                  if isinstance(error, FileNotFoundError) else str(error))
        evidence['reason'] = reason
        content = (r'\subsection{Archived first-flood validation}' + '\n' +
                   r'\pending{The archived first-flood evidence could not be verified: ' +
                   tex(reason) + '. No numerical claim is rendered from this archive.}\n')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'first_flood.tex').write_text(content)
    evidence['rendered_tex_sha256'] = sha(args.output / 'first_flood.tex')
    (args.output / 'first_flood_evidence.json').write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    print(evidence['status'])


if __name__ == '__main__':
    main()
