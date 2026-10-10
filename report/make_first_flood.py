#!/usr/bin/env python3
"""Render the retained first-flood observations without reading live run files."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct
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


def verify_figure(folder, comparison, evidence, manifest_path):
    manifest = json.loads(manifest_path.read_text())
    require(manifest['format'] == 1 and manifest['scope'] ==
            'archived first-flood validation only; no manuscript-panel assessment',
            'unexpected validation figure format or scope')
    require(manifest['processor_sha256'] == sha(ROOT / 'scripts/plot_first_flood.py'),
            'validation figure processor changed')
    expected = {label(folder / name): evidence['archive_sha256'][name]
                for name in ('two-resolution.json', 'two-resolution.py', 'resolution-inputs.tar.xz')}
    expected[label(folder / 'capture-provenance.json')] = evidence['capture_manifest_sha256']
    require(manifest['input_sha256'] == expected and
            manifest['member_sha256'] == evidence['sensitivity_input_sha256'],
            'validation figure input identities differ from the verified archive')
    for name in ('baseline250', 'coarse500'):
        case = comparison['cases'][name]
        snapshot = case['snapshot']
        expected = dict(state='complete', exit_code=0,
                        binary_sha256=case['process']['binary_sha256'],
                        snapshot=dict(nx=snapshot['nx'], ny=snapshot['ny'],
                                      channel_nodes=snapshot['nodes'], flood=snapshot['flood'],
                                      dx_m=snapshot['dx'], elapsed_seconds=snapshot['elapsed_seconds']))
        require(manifest['verified_case_records'][name] == expected,
                'validation figure case metadata differs: ' + name)
    common = comparison['common_floodplain_fields']
    require(manifest['comparison']['common_floodplain_area_m2'] == common['common_floodplain_area_m2'],
            'validation figure comparison area differs')
    for metric in ('mean_absolute_difference_m', 'maximum_absolute_difference_m'):
        for field in ('bed', 'water_depth', 'deposition'):
            require(math.isclose(manifest['comparison'][metric][field], common[metric][field],
                                 rel_tol=1e-10, abs_tol=1e-14),
                    'validation figure comparison differs: ' + metric + '/' + field)
    conventions = manifest['plotting_conventions']
    for name, expected in dict(extent_km=[0, 72, 0, 48], origin='lower', interpolation='nearest',
                               water_depth_limits_m=[0, .5], water_difference_limits_m=[-.4, .4],
                               deposition_log_limits_m=[1e-6, .5],
                               deposition_difference_symlog_limits_m=[-.15, .15],
                               deposition_difference_linear_core_m=1e-4,
                               deposition_difference_symlog_base=10,
                               snapshot_phase='flood 1, day 20, before first remap',
                               absolute_mask='active channel cells gray; floodplain values retained',
                               below_deposition_display_threshold='values below 1e-6 m white; no clipping in metrics',
                               difference_sign='coarse minus arithmetic mean of four fine cells',
                               difference_mask='exclude coarse blocks containing any active channel cell in either grid',
                               dry_cells='retained in common-floodplain comparisons',
                               scientific_scope='one first flood; no manuscript-panel reproduction or convergence inference').items():
        require(conventions[name] == expected, 'validation figure display convention differs: ' + name)
    outputs = manifest['outputs_sha256']
    require(set(outputs) == {'figures/first_flood_validation.pdf', 'figures/first_flood_validation.png'},
            'unexpected validation figure outputs')
    for name, expected in outputs.items():
        require(sha(ROOT / name) == expected, 'validation figure output changed: ' + name)
    return dict(status='verified', manifest=label(manifest_path), manifest_sha256=sha(manifest_path),
                processor_sha256=manifest['processor_sha256'], outputs_sha256=outputs,
                plotting_conventions=conventions)


def verify_definitions(folder, comparison, evidence):
    path = ROOT / 'figures/first_flood_diagnostic_sensitivity.json'
    analysis = json.loads(path.read_text())
    require(analysis['format'] == 1 and analysis['status'] == 'verified' and analysis['scope'] ==
            'archived first-flood diagnostic sensitivity only; no manuscript-panel assessment',
            'unexpected diagnostic sensitivity format or scope')
    require(analysis['processor_sha256'] == sha(ROOT / 'scripts/diagnostic_sensitivity.py'),
            'diagnostic sensitivity processor changed')
    dependencies = analysis['dependency_sha256']
    require(set(dependencies) == {'scripts/plot_first_flood.py', 'scripts/inundation_metrics.py',
                                  'src/model.hpp'}, 'unexpected diagnostic sensitivity dependencies')
    require(all(sha(ROOT / name) == expected for name, expected in dependencies.items()),
            'diagnostic sensitivity dependency changed')
    expected = {label(folder / name): evidence['archive_sha256'][name]
                for name in ('two-resolution.json', 'two-resolution.py', 'resolution-inputs.tar.xz')}
    expected[label(folder / 'capture-provenance.json')] = evidence['capture_manifest_sha256']
    require(analysis['input_sha256'] == expected and
            analysis['member_sha256'] == evidence['sensitivity_input_sha256'],
            'diagnostic sensitivity input identities differ from the verified archive')
    require(set(analysis['cases']) == {'baseline250', 'coarse500'},
            'unexpected diagnostic sensitivity cases')
    for name, case in analysis['cases'].items():
        require(case['dx_m'] == comparison['cases'][name]['parameters']['dx']
                and case['binary_sha256'] == comparison['cases'][name]['process']['binary_sha256']
                and case['flood'] == 1 and case['beta_elapsed_seconds'] == 1728000
                and case['alpha_elapsed_seconds'] == 1036800,
                'diagnostic sensitivity case or sampling metadata differs: ' + name)
        for quantity in ('alpha', 'beta', 'ridge_height', 'channel_depth'):
            row = case['summary_reconstruction'][quantity]
            original = comparison['cases'][name]['metrics'][quantity]
            lo, hi = row['rounding_bounds']
            tolerance = row['summary_rounding_half_width'] + row['float64_arithmetic_allowance']
            require(all(math.isfinite(v) for v in (lo, hi, tolerance, row['reconstructed']))
                    and tolerance >= 0 and lo <= row['reconstructed'] <= hi
                    and row['recorded_summary'] == original and lo - tolerance <= original <= hi + tolerance
                    and row['summary_within_rounding_bounds'] is True,
                    'diagnostic reconstruction disagrees with the recorded summary: ' + name + '/' + quantity)
        variants = case['beta_definition_variants']
        require(len(variants) == 9 and
                {(v['central_percent'], v['distal_percent_each_side']) for v in variants} ==
                {(reach, distal) for reach in (60, 80, 100) for distal in (5, 10, 20)},
                'unexpected ridge-definition sensitivity design')
        require(len(case['denominator_only_variants']) == 3 and
                {v['central_percent'] for v in case['denominator_only_variants']} == {60, 80, 100},
                'unexpected channel-depth sensitivity design')
        require(len(case['alpha_threshold_variants']) == 3 and
                {v['threshold_m'] for v in case['alpha_threshold_variants']} == {.0001, .001, .01},
                'unexpected wetness-threshold sensitivity design')
        reference = case['summary_reconstruction']['beta']['reconstructed']
        depth = case['summary_reconstruction']['channel_depth']['reconstructed']
        ridge = case['summary_reconstruction']['ridge_height']['reconstructed']
        require(reference != 0 and depth > 0 and case['full_interface_channel_depth_m'] == depth,
                'invalid default diagnostic denominator')
        close = lambda a, b: math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-14)
        require(close(reference, ridge / depth), 'default beta differs from ridge/depth')
        snapshot = comparison['cases'][name]['snapshot']
        for row in variants:
            change = 100 * (row['beta'] / reference - 1)
            require(close(row['beta'], row['ridge_height_m'] / depth) and
                    close(row['beta_change_percent_of_reconstructed_default'], change),
                    'inconsistent ridge-definition values')
            trim = snapshot['nx'] * (100 - row['central_percent']) // 200
            band = snapshot['ny'] * row['distal_percent_each_side'] // 100
            require(row['trim_columns_each_end'] == trim and row['distal_rows_each_side'] == band and
                    row['actual_central_length_m'] == (snapshot['nx'] - 2 * trim) * case['dx_m'] and
                    row['actual_distal_band_width_m'] == band * case['dx_m'],
                    'diagnostic averaging window differs from the recorded grid')
            if row['central_percent'] == 80 and row['distal_percent_each_side'] == 10:
                require(close(row['beta'], reference), 'default variant differs from reconstruction')
        for row in case['denominator_only_variants']:
            require(row['bankfull_depth_m'] > 0 and
                    close(row['beta_with_default_ridge'], ridge / row['bankfull_depth_m']) and
                    close(row['beta_change_percent_of_full_interface_depth'],
                          100 * (depth / row['bankfull_depth_m'] - 1)),
                    'inconsistent channel-depth sensitivity values')
        alpha_reference = case['summary_reconstruction']['alpha']['reconstructed']
        mean_reference = next(row['mean_water_m'] for row in case['alpha_threshold_variants']
                              if row['threshold_m'] == .001)
        require(case['full_interface_faces'] == comparison['cases'][name]['peak']['bank_length_m'] / case['dx_m'],
                'diagnostic bank-face count differs from the archived comparison')
        for row in case['alpha_threshold_variants']:
            interface = row['interface']
            require(interface['interface_faces'] == case['full_interface_faces'] and
                    interface['wet_faces'] > 0 and
                    close(interface['fraction'], interface['wet_faces'] / interface['interface_faces']) and
                    close(row['mean_water_m'], mean_reference) and
                    close(row['alpha_m'], row['mean_water_m'] / interface['fraction']),
                    'inconsistent wetness-threshold values')
            if row['threshold_m'] == .001:
                require(close(row['alpha_m'], alpha_reference), 'default alpha differs from reconstruction')
    return dict(status='verified', file=label(path), sha256=sha(path),
                processor_sha256=analysis['processor_sha256'], cases=analysis['cases'])


def render_definitions(analysis):
    lines = ['', r'\paragraph{Sensitivity to diagnostic definitions.}']
    if analysis['status'] != 'verified':
        return '\n'.join(lines + [r'\pending{The saved diagnostic-definition analysis is unavailable: ' +
                                  tex(analysis['reason']) + '.}\n'])
    cases = analysis['cases']
    lines += ['The published description does not fix all spatial averages in',
              r'$\beta$. Reprocessing the same archived day-20 fields gives:',
              '', r'\begin{center}\small', r'\begin{tabular}{lrrrr}', r'\toprule',
              r'Nominal central reach & $\beta$, 250 m & Change (\%) & $\beta$, 500 m & Change (\%) \\',
              r'\midrule']
    for reach in (60, 80, 100):
        values = []
        for name in ('baseline250', 'coarse500'):
            case = cases[name]
            row = next(v for v in case['beta_definition_variants']
                       if v['central_percent'] == reach and v['distal_percent_each_side'] == 10)
            reference = case['summary_reconstruction']['beta']['reconstructed']
            values.extend(['$' + number(row['beta'], 4) + '$', '%.2f' % (100 * (row['beta'] / reference - 1))])
        lines.append(str(reach) + r'\% & ' + ' & '.join(values) + r' \\')
    lines += [r'\bottomrule\end{tabular}\end{center}',
              'Only the reach used for the transverse relief profile changes in this',
              r'table. The distal bands remain at nominal 10\% of the domain width at each side,',
              'and the denominator remains the full-interface mean bankfull depth.',
              'Changes are relative to the raster reconstruction of the default',
              r'central-80\% estimator. Integer trimming gives central lengths of',
              r'43.5 and 44 km at nominal 60\%, respectively; both grids use 58 km',
              r'at nominal 80\% and 72 km at 100\%. Their default distal bands are',
              '4.75 and 4.5 km wide on each side.',
              'Thus including the end regions materially changes first-flood ridge',
              'relief. This comparison identifies sensitivity to the averaging',
              'definition; it does not isolate a boundary-condition mechanism.', '']
    distal_max = max(abs(100 * (v['beta'] / case['summary_reconstruction']['beta']['reconstructed'] - 1))
                     for case in cases.values() for v in case['beta_definition_variants']
                     if v['central_percent'] == 80)
    denominator_max = max(abs(100 * (case['full_interface_channel_depth_m'] / v['bankfull_depth_m'] - 1))
                          for case in cases.values() for v in case['denominator_only_variants'])
    lines += [r'At the default reach, changing each distal band to 5\%, 10\%, or 20\%',
              r'changes $\beta$ by at most %.2f\%%.' % distal_max,
              'Holding the default ridge relief fixed and restricting the channel-depth',
              r'average to bank faces in the nominal central 60\%, 80\%, or full reach',
              r'changes $\beta$ by at most %.2f\%%.' % denominator_max,
              'The source record retains all nine reach/band combinations and the',
              'three separate denominator variants.', '']
    thresholds = [v for case in cases.values() for v in case['alpha_threshold_variants']]
    require(all(v['interface']['fraction'] == 1 and
                v['interface']['definitely_wet_faces'] == v['interface']['possibly_wet_faces']
                and v['ambiguous_wet_area_cells'] == 0 for v in thresholds),
            'first-flood threshold interpretation changed')
    lines += [r'For day-12 $\alpha$, thresholds of 0.1, 1, and 10 mm leave every',
              'sampled bank face wet in both cases. The full-domain mean depth,',
              r'including dry cells, is unchanged, so $\alpha$ is unchanged.',
              'The nominal wet floodplain area nevertheless varies with the threshold:',
              '%.3f--%.3f km$^2$ at 250 m and %.3f--%.3f km$^2$ at 500 m.' % tuple(
                  f(v['wet_area_m2'] / 1e6 for v in cases[name]['alpha_threshold_variants'])
                  for name in ('baseline250', 'coarse500') for f in (min, max)),
              'No tested wetness classification is ambiguous within float32 rounding.',
              '',
              'The default reconstructions of ridge relief, channel depth,',
              r'$\beta$, and $\alpha$ agree with the double-precision summaries',
              'within propagated half-ULP snapshot bounds and the recorded arithmetic',
              'and CSV rounding allowances. These bounds describe representation',
              'precision, not discretization or physical uncertainty. The scenarios',
              'do not select a preferred estimator and do not establish robustness',
              'of the late 20-flood or 200-flood manuscript statistics.',
              r'\path{figures/first_flood_diagnostic_sensitivity.json} records the',
              'definitions, effective grid windows, bounds, and input identities.']
    return '\n'.join(lines) + '\n'


def render(comparison, measured, figure):
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
              '']
    if figure['status'] == 'verified':
        lines += ['Validation figure V1 maps these end-flood fields and their differences.',
                  r'\begin{figure}[p]\centering',
                  r'\includegraphics[width=\linewidth]{figures/first_flood_validation.pdf}',
                  r'\par\smallskip\begingroup\small\noindent\textbf{Validation figure V1.}',
                  'Independent first-flood calculation for configuration 11 over the',
                  '72 km by 48 km domain. Rows show day-20 water depth and event-deposit',
                  'thickness before migration and remapping. The first two columns use',
                  '250 m and 500 m floodplain grids; both retain 250 m channel-node spacing.',
                  'The third column subtracts the arithmetic mean of each two-by-two',
                  'fine block from the coarse cell. Gray marks active channel cells,',
                  'or excluded comparison blocks containing any channel cell in either grid.',
                  'Dry cells remain in the comparisons. Depth scales are linear;',
                  r'deposit scales are logarithmic from $10^{-6}$ to 0.5 m, with smaller',
                  'deposits white. Signed deposit differences use a base-10 symmetric',
                  r'logarithmic scale with a linear core of $\pm10^{-4}$ m.',
                  'Display thresholds do not modify the reported differences.',
                  'These two first-flood cases establish neither convergence nor',
                  'reproduction of a manuscript panel.',
                  r'\par\endgroup\end{figure}', '']
    else:
        lines += [r'\pending{Validation figure V1 is unavailable: ' + tex(figure['reason']) +
                  '. The verified numerical tables remain available.}', '']
    lines += [
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
              'Later conservation drift, bank recycling, finer-grid sensitivity,',
              'and long-term morphology require further assessment.']
    return '\n'.join(lines) + '\n'


def verify_time_step(folder):
    method = folder / 'time-step.py'
    comparison = runpy.run_path(str(method))['verify'](folder)
    require(comparison == json.loads((folder / 'time-step.json').read_text()),
            'saved time-step comparison differs from archived inputs')
    return dict(status='verified', comparison=comparison,
                files_sha256={name: sha(folder / name) for name in
                              ('time-step.py', 'time-step.json', 'time-step-capture.json',
                               'time-step-inputs.tar.xz')})


def render_time_step(evidence):
    lines = ['', r'\subsection{Completed first-flood time-step sensitivity}']
    if evidence['status'] != 'verified':
        lines.append(r'\pending{The retained time-step comparison could not be verified: ' +
                     tex(evidence['reason']) + '. No numerical time-step claim is rendered.}')
        return '\n'.join(lines) + '\n'
    comparison = evidence['comparison']
    names = ('baseline250', 'time250_cfl02')
    cases = [comparison['cases'][name] for name in names]
    require(comparison['parameter_differences'] == {'cfl': [0.4, 0.2]},
            'time-step parameters differ beyond the CFL limit')
    lines += ['A later completed case reduces the CFL limit from 0.4 to 0.2 while',
              'holding the corrected executable, configuration 11, 250 m floodplain',
              'grid, and 250 m initial channel spacing fixed. Both calculations',
              'complete the full 20-day hydrograph with exit code zero. The retained',
              'archive contains both original process records and all recorded',
              'outputs. Macrosteps increase from %s to %s and channel substeps from' %
              tuple(format(int(case['summary']['steps']), ',') for case in cases),
              '%s to %s; adaptive steps are not uniformly halved at every time.' %
              tuple(format(int(case['summary']['channel_steps']), ',') for case in cases),
              '', r'\begin{center}\small', r'\begin{tabular}{lrrr}', r'\toprule',
              r'Quantity & CFL 0.4 & CFL 0.2 & Change (\%) \\', r'\midrule']
    for title, key in ((r'Day-12 connectivity $\alpha$ (m)', 'alpha'),
                       (r'End-flood ridge height (m)', 'ridge_height'),
                       (r'End-flood relative relief $\beta$', 'beta'),
                       (r'Mean bankfull channel depth (m)', 'channel_depth'),
                       (r'End-flood water storage (m$^3$)', 'water_storage')):
        values = [case['summary'][key] for case in cases]
        change = 100 * (values[1] / values[0] - 1)
        lines.append(title + ' & ' + ' & '.join('$' + number(v) + '$' for v in values) +
                     ' & %+.5f' % change + r' \\')
    deposited = [case['checkpoint']['deposited_mass_kg'] for case in cases]
    lines.append('Deposited mineral mass (kg) & ' +
                 ' & '.join('$' + number(v) + '$' for v in deposited) +
                 ' & %+.5f' % (100 * (deposited[1] / deposited[0] - 1)) + r' \\')
    common = comparison['same_grid_fields']['end']
    water, deposit = (common['fields'][key] for key in ('water_depth', 'event_deposit'))
    remap = cases[1]['remap']
    lines += [r'\bottomrule\end{tabular}\end{center}',
              'Percentage changes use the CFL 0.4 value as denominator. Connectivity',
              'is sampled on day 12; ridge height, relative relief, channel depth,',
              'and water storage are sampled on day 20 before migration/remapping.',
              'Deposited mineral mass is the accumulated source ledger retained in',
              'the post-remap checkpoint, not an integral of the remaining deposit.',
              'Both inundated interface fractions equal one, so the connectivity',
              'change is the change in mean floodplain depth.',
              '',
              'The end-flood masks agree. Over all %.0f km$^2$ of floodplain,' %
              (common['floodplain_area_m2'] / 1e6),
              'including dry cells, water-depth differences have mean absolute value',
              '%.8f m and maximum %.8f m. Event-deposit thickness differences have' %
              (water['mean_absolute_difference_m'], water['maximum_absolute_difference_m']),
              'mean absolute value %.8f m and maximum %.8f m.' %
              (deposit['mean_absolute_difference_m'], deposit['maximum_absolute_difference_m']),
              'The respective bounds from float32 storage on these mean differences',
              'are $%s$ m and $%s$ m; they exclude discretization and separate' %
              (number(water['mean_difference_storage_bound_m']),
               number(deposit['mean_difference_storage_bound_m'])),
              'floating-point arithmetic error.',
              '',
              'The half-CFL post-remap residuals are $%s$ m$^3$ water,' %
              number(remap['post_water_residual']),
              '$%s$ kg suspension plus deposition, and $%s$ kg total solids.' %
              (number(remap['post_sediment_residual']), number(remap['post_solid_sediment_residual'])),
              'Normalized by prescribed upstream inputs of $%s$ m$^3$ and' %
              number(cases[1]['prescribed_inputs']['prescribed_water_input_m3']),
              '$%s$ kg, their magnitudes are below $2.7\\times10^{-11}$.' %
              number(cases[1]['prescribed_inputs']['prescribed_sediment_input_kg']),
              'These denominators exclude recycling, outflow, and signed bed forcing.',
              'Both first remaps have zero captured or abandoned cells, bank reservoir,',
              'recycled mass, cutoffs, and water or mass corrections. Signed bed',
              'forcing is retained as a separate ledger in the comparison.',
              '',
              'The distinct sensitivities of water storage and ridge height require',
              'both hydraulic and deposition quantities to be assessed. Two CFL',
              'limits do not determine a temporal convergence order or establish',
              'time-step independence. This first-flood comparison does not test',
              'later recycling, 580-flood evolution, or manuscript-panel agreement.',
              r'The portable replay command is:',
              r'\par\noindent\texttt{python3 -B}\ \path{validation/first-flood-audit-002/time-step.py}']
    require(all(case['summary']['interface_fraction'] == 1 for case in cases),
            'time-step inundated interface fractions changed')
    require(all(case['checkpoint'][key] == 0 for case in cases for key in
                ('captured_floodplain_cells', 'abandoned_channel_cells', 'bank_mass_kg',
                 'recycled_mass_kg', 'cutoffs', 'water_correction_m3', 'mass_correction_kg')),
            'time-step first-remap activity changed')
    require(all(abs(cases[1]['signed_residuals_over_prescribed_input'][key]) < 2.7e-11
                for key in ('post_water', 'post_suspension_plus_deposition', 'post_full_solid')),
            'time-step normalized residual bound changed')
    return '\n'.join(lines) + '\n'


def verify_threshold(folder):
    comparison = runpy.run_path(str(folder / 'threshold.py'))['verify'](folder)
    require(comparison == json.loads((folder / 'threshold.json').read_text()),
            'saved threshold comparison differs from archived inputs')
    return dict(status='verified', comparison=comparison,
                files_sha256={name: sha(folder / name) for name in
                              ('threshold.py', 'threshold.json', 'threshold-capture.json',
                               'threshold-inputs.tar.xz', 'time-step.py')})


def render_threshold(evidence):
    lines = ['', r'\subsection{Completed first-flood deposition-threshold sensitivity}']
    if evidence['status'] != 'verified':
        lines.append(r'\pending{The retained threshold comparison could not be verified: ' +
                     tex(evidence['reason']) + '. No numerical threshold claim is rendered.}')
        return '\n'.join(lines) + '\n'
    comparison = evidence['comparison']
    names = ('baseline250', 'tau005', 'tau020')
    require(comparison['format'] == 2 and comparison['baseline_case'] == names[0] and
            set(comparison['cases']) == set(names) and
            set(comparison['comparisons']) == set(names[1:]),
            'unexpected three-case threshold comparison schema')
    cases = [comparison['cases'][name] for name in names]
    candidates = [comparison['comparisons'][name] for name in names[1:]]
    thresholds = [case['parameters']['tau_critical'] for case in cases]
    require(thresholds == [0.1, 0.05, 0.2] and
            all(candidate['parameter_differences'] == {'tau_critical': [0.1, threshold]}
                for candidate, threshold in zip(candidates, thresholds[1:])),
            'threshold parameters differ beyond critical deposition stress')
    lines += [r'This comparison varies the assumed critical deposition stress $\tau_c$',
              r'from a 0.1 Pa baseline to 0.05 and 0.2 Pa. The silt and clay settling',
              r'rates contain the factor $\max(0,1-\tau_b/\tau_c)$, where $\tau_b$',
              r'is bed shear stress. At fixed shear stress and concentration, lowering',
              r'$\tau_c$ suppresses settling; raising it enhances settling where the',
              'shear reduction is active. Sand settling has no shear reduction.',
              'All three cases use the corrected executable, configuration',
              '11, 250 m floodplain grid, 250 m initial channel spacing, CFL limit',
              '0.4, and one complete 20-day hydrograph. All other numerical parameters',
              'agree. All three recorded processes exit successfully.',
              '', r'\begin{center}\small\setlength{\tabcolsep}{4pt}',
              r'\begin{tabular}{lrrr}', r'\toprule',
              r'Quantity & $\tau_c=0.1$ Pa & $\tau_c=0.05$ Pa & $\tau_c=0.2$ Pa \\',
              r'\midrule']
    metrics = ((r'Day-12 connectivity $\alpha$ (m)', 'alpha'),
               (r'End-flood ridge height (m)', 'ridge_height'),
               (r'End-flood relative relief $\beta$', 'beta'),
               (r'Mean bankfull depth (m)', 'channel_depth'),
               (r'End-flood water storage (m$^3$)', 'water_storage'),
               (r'Deposited mineral mass (kg)', 'deposited_mass'))
    for title, key in metrics:
        values = [case['checkpoint']['deposited_mass_kg'] if key == 'deposited_mass'
                  else case['summary'][key] for case in cases]
        lines.append(title + ' & ' + ' & '.join('$' + number(v) + '$' for v in values) + r' \\')
    lines += [r'\bottomrule\end{tabular}\end{center}',
              r'\begin{center}\small', r'\begin{tabular}{lrr}', r'\toprule',
              r'Percentage change from 0.1 Pa & $\tau_c=0.05$ Pa & $\tau_c=0.2$ Pa \\',
              r'\midrule']
    for title, key in metrics:
        lines.append(title + ' & ' + ' & '.join('%+.5f' %
                     candidate['threshold_relative_to_baseline_percent'][key]
                     for candidate in candidates) + r' \\')
    lines += [r'\bottomrule\end{tabular}\end{center}',
              'Changes are each candidate minus the 0.1 Pa baseline; percentages',
              'use the baseline value as denominator. Connectivity',
              'is sampled on day 12; ridge height, relative relief, channel depth,',
              'and water storage are sampled on day 20 before migration/remapping.',
              'The post-remap checkpoint ledger records mineral mass added by',
              'deposition; the raster stores remaining event-deposit thickness,',
              'including pore space. All three day-12 inundated interface fractions',
              'equal one, so the connectivity difference is a mean-depth difference.',
              '']
    for threshold, candidate in zip(thresholds[1:], candidates):
        changes = candidate['threshold_relative_to_baseline_percent']
        lines += ['At %.2g Pa, ridge height changes by %+.3f\\%% and deposited' %
                  (threshold, changes['ridge_height']),
                  'mineral mass by %+.3f\\%% relative to the baseline.' % changes['deposited_mass']]
    lines += ['Ridge relief and integrated deposition respond differently in these',
              'calculations. The local settling factor alone does not determine the',
              'sign of the coupled spatial response.', '',
              'The channel/floodplain classification masks agree across all three',
              'cases at peak and end flood. The field',
              'comparisons below cover all %.0f km$^2$ of floodplain, including dry' %
              (candidates[0]['same_grid_fields']['end']['floodplain_area_m2'] / 1e6),
              'cells. Each difference is the candidate minus the baseline. The',
              'last column bounds float32 storage error in the mean difference;',
              'it excludes discretization, separate floating-point arithmetic error,',
              'and rounding of the tabulated values. All entries are in metres.']
    for threshold, candidate in zip(thresholds[1:], candidates):
        lines += ['', r'\begin{center}\small\setlength{\tabcolsep}{4pt}',
                  r'$\tau_c=%.2g$ Pa relative to 0.1 Pa\par\smallskip' % threshold,
                  r'\begin{tabular}{llrrr}', r'\toprule',
                  r'Phase & Field & Mean $|\Delta|$ & Max. $|\Delta|$ & Mean storage bound \\',
                  r'\midrule']
        for phase, phase_title in (('peak', 'Day 12'), ('end', 'Day 20')):
            for key, title in (('water_depth', 'Water depth'), ('event_deposit', 'Event deposit')):
                field = candidate['same_grid_fields'][phase]['fields'][key]
                values = [field[key] for key in ('mean_absolute_difference_m',
                          'maximum_absolute_difference_m', 'mean_difference_storage_bound_m')]
                lines.append(phase_title + ' & ' + title + ' & ' +
                             ' & '.join('$' + number(value) + '$' for value in values) + r' \\')
        lines += [r'\bottomrule\end{tabular}\end{center}']
    lines += ['', 'Post-remap residuals retain their signs. The water denominator is',
              'the prescribed upstream input of $%s$ m$^3$; both sediment denominators' %
              number(cases[0]['prescribed_inputs']['prescribed_water_input_m3']),
              'are the prescribed upstream mineral input of $%s$ kg.' %
              number(cases[0]['prescribed_inputs']['prescribed_sediment_input_kg']),
              'These common denominators exclude recycling, outflow, and signed bed',
              'forcing; they are neither current storage nor net external input.',
              '', r'\begin{center}\small\setlength{\tabcolsep}{4pt}',
              r'\begin{tabular}{rlrr}', r'\toprule',
              r'$\tau_c$ (Pa) & Inventory & Signed residual & Residual/input \\', r'\midrule']
    for threshold, case in zip(thresholds, cases):
        for title, raw, normalized in (
                (r'Water (m$^3$)', 'post_water_residual', 'post_water'),
                ('Suspension + deposition (kg)', 'post_sediment_residual', 'post_suspension_plus_deposition'),
                ('Full solids (kg)', 'post_solid_sediment_residual', 'post_full_solid')):
            lines.append(r'%.2g & %s & $%s$ & $%s$ \\' %
                         (threshold, title, number(case['remap'][raw]),
                          number(case['signed_residuals_over_prescribed_input'][normalized])))
    lines += [r'\bottomrule\end{tabular}\end{center}',
              'All three first remaps have zero captured or abandoned cells, bank',
              'mass, recycled mass, cutoffs, and water or mass correction terms.',
              'The signed bed-forcing ledgers are %s kg for 0.1, 0.05, and 0.2 Pa,' %
              ', '.join('$' + number(case['checkpoint']['bed_forcing_mass_kg']) + '$' for case in cases),
              'respectively. This forcing contributes to solid-inventory change',
              'independently of suspended transport and is subtracted in the',
              'full-solid residual.', '',
              'This result quantifies sensitivity to an assumed deposition parameter.',
              'It does not constrain the appropriate physical threshold, numerical',
              'convergence, later bank recycling, 580-flood behavior, or agreement',
              'with a manuscript panel.',
              r'The portable replay command is:',
              r'\par\noindent\texttt{python3 -B}\ \path{validation/first-flood-audit-002/threshold.py}']
    require(all(case['summary']['interface_fraction'] == 1 for case in cases),
            'threshold comparison interface fractions changed')
    require(all(case['prescribed_inputs'] == cases[0]['prescribed_inputs'] for case in cases),
            'threshold comparison prescribed inputs differ')
    require(all(case['checkpoint'][key] == 0 for case in cases for key in
                ('captured_floodplain_cells', 'abandoned_channel_cells', 'bank_mass_kg',
                 'recycled_mass_kg', 'cutoffs', 'water_correction_m3', 'mass_correction_kg')),
            'threshold comparison first-remap activity changed')
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
        try:
            figure = verify_figure(args.archive_root, comparison, evidence,
                                   ROOT / 'figures/first_flood_validation_manifest.json')
        except (OSError, ValueError, KeyError, TypeError) as error:
            reason = ('Missing retained file: ' + Path(error.filename).name
                      if isinstance(error, FileNotFoundError) else str(error))
            figure = dict(status='pending', reason=reason)
        evidence['validation_figure'] = figure
        content = render(comparison, measured, figure)
        try:
            definitions = verify_definitions(args.archive_root, comparison, evidence)
            definitions_tex = render_definitions(definitions)
        except (OSError, ValueError, KeyError, TypeError, StopIteration, ZeroDivisionError) as error:
            reason = ('Missing retained file: ' + Path(error.filename).name
                      if isinstance(error, FileNotFoundError) else str(error))
            definitions = dict(status='pending', reason=reason)
            definitions_tex = render_definitions(definitions)
        evidence['diagnostic_definitions'] = {key: value for key, value in definitions.items() if key != 'cases'}
        content += definitions_tex
        try:
            time_step = verify_time_step(args.archive_root)
            time_step_tex = render_time_step(time_step)
        except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError,
                RuntimeError, ZeroDivisionError, struct.error, tarfile.TarError) as error:
            reason = ('Missing retained file: ' + Path(error.filename).name
                      if isinstance(error, FileNotFoundError) else str(error))
            time_step = dict(status='pending', reason=reason)
            time_step_tex = render_time_step(time_step)
        evidence['time_step'] = time_step
        content += time_step_tex
        try:
            threshold = verify_threshold(args.archive_root)
            threshold_tex = render_threshold(threshold)
        except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError,
                RuntimeError, ZeroDivisionError, struct.error, tarfile.TarError) as error:
            reason = ('Missing retained file: ' + Path(error.filename).name
                      if isinstance(error, FileNotFoundError) else str(error))
            threshold = dict(status='pending', reason=reason)
            threshold_tex = render_threshold(threshold)
        evidence['threshold'] = threshold
        content += threshold_tex
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
