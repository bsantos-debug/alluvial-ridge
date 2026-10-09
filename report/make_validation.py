#!/usr/bin/env python3
"""Render measured sensitivity and conservation evidence, including pending cases."""
import argparse
import csv
import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
CASES = ('baseline250', 'coarse500', 'fine125', 'time250_cfl02',
         'tau005', 'tau020', 'concentration_half', 'concentration_double')
GROUP = {name: ('reference' if name == 'baseline250' else 'numerical resolution'
               if name in CASES[1:4] else 'physical assumption') for name in CASES}
PRE = ('water_residual', 'sediment_residual', 'solid_sediment_residual')
POST = ('post_water_residual', 'post_sediment_residual', 'post_solid_sediment_residual')
LOCAL = ('water_transfer_residual', 'sand_transfer_residual', 'silt_transfer_residual',
         'clay_transfer_residual', 'solid_transfer_residual')


def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def label(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path, inputs):
    if not path.exists():
        return {}
    inputs.add(path)
    return json.loads(path.read_text())


def parameters(path, inputs):
    if not path.exists():
        return {}, []
    inputs.add(path)
    result, commands = {}, []
    for line in path.read_text().splitlines():
        key, value = line.split(None, 1)
        if key == 'command':
            commands.append(value)
        else:
            result[key.replace('-', '_')] = finite(value)
    return result, commands


def history(path, inputs):
    if not path.exists():
        return [], ['missing ' + path.name]
    inputs.add(path)
    values, errors = [], []
    with path.open(newline='') as stream:
        for row in csv.DictReader(stream):
            try:
                flood = int(row['flood'])
                if flood < 1 or (values and flood <= values[-1]['flood']):
                    raise ValueError('flood indices must increase without duplicates')
                parsed = {key: finite(value) for key, value in row.items()}
                parsed['flood'] = flood
                values.append(parsed)
            except (ValueError, KeyError) as error:
                errors.append(str(error))
    if values and [r['flood'] for r in values] != list(range(1, values[-1]['flood'] + 1)):
        errors.append('history has missing floods')
    return values, errors


def input_per_flood(p):
    needed = ('duration', 'qmin', 'qmax', 'C', 'concentration_scale')
    if any(p.get(key) is None for key in needed):
        return None
    if p['duration'] <= 0 or p['qmin'] <= 0 or p['qmax'] < p['qmin']:
        return None
    if p['C'] < 0 or p['concentration_scale'] < 0:
        return None
    # Prescribed sin^2 hydrograph; Simpson quadrature of the external Q^(5/2) supply.
    total, intervals = 0., 20000
    for i in range(intervals + 1):
        q = p['qmin'] + (p['qmax'] - p['qmin']) * math.sin(math.pi * i / intervals) ** 2
        total += (1 if i in (0, intervals) else 4 if i % 2 else 2) * q ** 2.5
    return dict(water_m3=p['duration'] * (p['qmin'] + p['qmax']) / 2,
                external_sediment_kg=total * p['duration'] / (3 * intervals) * p['C'] * p['concentration_scale'])


def residuals(rows, columns, supply):
    result = {}
    for key in columns:
        valid = [r for r in rows if r.get(key) is not None]
        item = dict(finite_count=len(valid), expected_count=len(rows), state='pending')
        if valid:
            maximum = max(valid, key=lambda r: abs(r[key]))
            item.update(maximum_absolute=abs(maximum[key]), maximum_at_flood=maximum['flood'])
            if rows[-1].get(key) is not None:
                item.update(terminal_signed=rows[-1][key], terminal_flood=rows[-1]['flood'])
            item['state'] = 'complete recorded window' if len(valid) == len(rows) else 'partial finite window'
            denominator = (supply or {}).get('water_m3' if 'water' in key else 'external_sediment_kg')
            if denominator and key not in LOCAL:
                normalized = [(abs(r[key]) / (r['flood'] * denominator), r['flood']) for r in valid]
                item['maximum_absolute_over_cumulative_input'], item['normalized_maximum_at_flood'] = max(normalized)
                if 'terminal_signed' in item:
                    item['terminal_signed_over_cumulative_input'] = item['terminal_signed'] / (item['terminal_flood'] * denominator)
        result[key] = item
    return result


def production(data, requested, inputs):
    suite = read_json(data / 'suite_manifest.json', inputs)
    expected, unused = parameters(data / '_inputs/physics.txt', inputs)
    table_path = data / '_inputs/runs.csv'
    configs = {}
    if table_path.exists():
        inputs.add(table_path)
        with table_path.open(newline='') as stream:
            configs = {int(r['run']): r for r in csv.DictReader(stream)}
    result = []
    for number in range(1, 32):
        folder = data / ('run%02d' % number)
        p, commands = parameters(folder / 'parameters.txt', inputs)
        rows, notes = history(folder / 'summary.csv', inputs)
        history_errors = list(notes)
        checks = dict(expected)
        checks.pop('floods', None)
        config = configs.get(number)
        if config:
            checks.update(run=number, A=float(config['A_m_per_flood']), C=float(config['C']),
                          E=float(config['E']), fine=int(config['load'] == 'fine'))
        else:
            notes.append('frozen configuration table unavailable for this run')
        if not expected:
            notes.append('frozen physical inputs unavailable')
        differences = [key for key, value in checks.items() if p.get(key) is None or value is None
                       or not math.isclose(p[key], value, rel_tol=1e-10, abs_tol=1e-12)]
        if differences:
            notes.append('parameters differ or are unrecorded: ' + ', '.join(differences))
        canonical = bool(config and expected) and not differences
        supply = input_per_flood(p)
        if supply is None:
            notes.append('prescribed cumulative-input normalization unavailable')
        resumed = len(commands) > 1 or any('--resume 1' in command for command in commands)
        if resumed:
            notes.append('resumed history: cumulative residual baselines reset at process restart')
        status_path = folder / 'status.txt'
        completed = status_path.exists() and status_path.read_text().strip() == 'complete {} floods'.format(requested)
        if status_path.exists():
            inputs.add(status_path)
        full = ([r['flood'] for r in rows] == list(range(1, requested + 1)) and completed and canonical
                and not history_errors and all(r.get(k) is not None for r in rows for k in PRE))
        remap_rows, remap_notes = history(folder / 'remap_budget.csv', inputs)
        for key in LOCAL + POST:
            if remap_rows and any(r.get(key) is None for r in remap_rows):
                remap_notes.append('missing/nonfinite values in ' + key)
        result.append(dict(run=number, state='complete requested history' if full else 'partial history' if rows else 'pending',
                           rows=len(rows), last_flood=rows[-1]['flood'] if rows else None,
                           configuration_verified=canonical, resumed=resumed, notes=notes,
                           input_per_flood=supply, pre_remap=residuals(rows, PRE, supply),
                           remap=dict(rows=len(remap_rows), notes=remap_notes,
                                      complete_requested_history=[r['flood'] for r in remap_rows] == list(range(1, requested + 1)),
                                      local=residuals(remap_rows, LOCAL, supply),
                                      post=residuals(remap_rows, POST, supply))))
    return result, suite.get('provenance', {}).get('binary_sha256')


def sensitivity(folder, production_binary, inputs):
    evidence = read_json(folder / 'comparison.json', inputs)
    manifest = read_json(folder / 'validation_manifest.json', inputs)
    binary = manifest.get('provenance', {}).get('binary_sha256')
    cases = evidence.get('cases', {})
    result = []
    for name in CASES:
        source = cases.get(name, {})
        record = dict(name=name, group=GROUP[name], state='pending', reason=source.get('reason', 'case evidence unavailable'))
        if source.get('state') == 'complete':
            rows, errors = history(folder / name / 'summary.csv', inputs)
            p, unused = parameters(folder / name / 'parameters.txt', inputs)
            if len(rows) != 1 or rows[0]['flood'] != 1:
                errors.append('expected one completed flood')
            elif any(rows[0].get(key) != finite(value) for key, value in source.get('metrics', {}).items()):
                errors.append('comparison metrics differ from current saved summary')
            if p != source.get('parameters'):
                errors.append('comparison parameters differ from current saved parameters')
            process = read_json(folder / name / 'process_status.json', inputs)
            hashes = process.get('artifact_sha256', {})
            for filename in ('summary.csv', 'parameters.txt', 'fields_0001.bin', 'channel_0001.csv', 'status.txt'):
                path = folder / name / filename
                if not path.exists():
                    errors.append(filename + ' missing')
                else:
                    inputs.add(path)
                    if filename not in hashes or sha(path) != hashes[filename]:
                        errors.append(filename + ' lacks matching completed-case hash')
            if production_binary and binary != production_binary:
                errors.append('sensitivity executable differs from production executable')
            if not binary:
                errors.append('sensitivity executable identity unavailable')
            if errors:
                record['reason'] = '; '.join(errors)
            else:
                record.update(state='complete', reason='', metrics=source.get('metrics', {}),
                              budgets=source.get('budgets', {}),
                              changes_percent=source.get('relative_metric_change_percent', {}),
                              field_comparison=source.get('field_comparison', {}))
        result.append(record)
    baseline = next(r for r in result if r['name'] == 'baseline250')
    for record in result:
        if baseline['state'] != 'complete':
            record['changes_percent'] = {}
            record['field_comparison'] = {}
    return dict(binary_sha256=binary, matches_production=(binary == production_binary) if binary and production_binary else None,
                cases=result)


def tex(value):
    replace = {'\\': r'\textbackslash{}', '_': r'\_', '&': r'\&', '%': r'\%', '#': r'\#',
               '{': r'\{', '}': r'\}', '$': r'\$', '^': r'\textasciicircum{}', '~': r'\textasciitilde{}'}
    return ''.join(replace.get(c, c) for c in str(value))


def number(value):
    return '--' if value is None else '{:.4g}'.format(value)


def table(lines, columns, headings, rows):
    lines.append(r'\begingroup\small\begin{longtable}{' + columns + '}\n')
    lines.append(' & '.join(headings) + r' \\ \hline\endhead' + '\n')
    lines.extend(' & '.join(row) + r' \\' + '\n' for row in rows)
    lines.append('\\end{longtable}\\endgroup\n')


def render(report):
    lines = [r'\subsection{Recorded verification and sensitivity}' + '\n']
    code = report['checks_exit_code']
    lines.append('Implementation-check exit code: ' + (tex(code) if code is not None else 'not supplied') + '.\\par\n')
    if report['kernel_log_present']:
        lines.append('The complete check log is \\texttt{validation/\\allowbreak kernel.txt}. Its named checks delimit the verification scope. Exit status alone does not establish manuscript agreement.\n\n')
    else:
        lines.append('The implementation-check log is unavailable; its verification scope remains pending.\n\n')
    cases = report['sensitivity']['cases']
    table(lines, 'lll', ['Case', 'Type', 'State'], [[tex(c['name']), tex(c['group']), tex(c['state'])] for c in cases])
    for case in cases:
        if case['state'] != 'complete':
            lines.append(tex(case['name']) + ': ' + tex(case['reason']) + '.\\par\n')
    match = report['sensitivity']['matches_production']
    lines.append('Sensitivity executable identity ' + ('matches the production executable.' if match else
                 'differs from the production executable.' if match is False else 'cannot yet be matched to a production executable.') + '\n\n')
    complete = [c for c in cases if c['state'] == 'complete']
    if complete:
        lines.append('First-flood residual/input ratios: water, suspended sediment, and combined solids, respectively.\\par\n')
        table(lines, 'lrrr', ['Case', 'Water', 'Suspension', 'Solids'],
              [[tex(c['name'])] + [number(c['budgets'].get(k + '_over_input')) for k in PRE] for c in complete])
    differences = [c for c in complete if c.get('changes_percent')]
    if differences:
        lines.append('Changes relative to baseline250 (percent); undefined ratios remain blank:\\par\n')
        table(lines, 'lrrrr', ['Case', r'$\alpha$', r'$\beta$', 'Ridge height', 'Channel depth'],
              [[tex(c['name'])] + [number(c['changes_percent'].get(k)) for k in ('alpha', 'beta', 'ridge_height', 'channel_depth')] for c in differences])
        table(lines, 'lrrr', ['Case', 'Wet fraction', 'Mean depth', 'Water storage'],
              [[tex(c['name'])] + [number(c['changes_percent'].get(k)) for k in ('interface_fraction', 'mean_water', 'water_storage')] for c in differences])
        field_rows = []
        for c in differences:
            fields = c.get('field_comparison', {})
            area = fields.get('common_floodplain_area_m2')
            for key in ('bed', 'water_depth', 'deposition'):
                field_rows.append([tex(c['name']), tex(key.replace('_', ' ')),
                                   number(fields.get('mean_absolute_difference_m', {}).get(key)),
                                   number(fields.get('maximum_absolute_difference_m', {}).get(key)),
                                   number(area / 1e6 if area is not None else None)])
        table(lines, 'llrrr', ['Case', 'Field', 'Mean error (m)', 'Max error (m)', r'Area (km$^2$)'], field_rows)
    else:
        lines.append('Grid, time-step, and physical-assumption differences remain pending because a verified baseline/case pair is unavailable.\n\n')
    lines.append('Field differences compare common floodplain cells after averaging the finer grid to the coarser grid; cells active in either channel mask are excluded. Physical-assumption contrasts are not convergence tests. These calculations cover one full flood with 250 m channel spacing; they do not establish long-term migration or grid independence.\n\n')
    lines.append(r'\subsection{Production conservation evidence}' + '\n')
    runs = report['production']
    lines.append('Complete requested histories: {}/31. Histories with completed-flood budget rows: {}/31. Missing histories remain pending.\n\n'.format(
        sum(r['state'] == 'complete requested history' for r in runs), sum(r['rows'] > 0 for r in runs)))
    lines.append('The denominator at flood $n$ is prescribed cumulative upstream input: $nT_f(Q_{\\min}+Q_{\\max})/2$ for water and $n C_s C\\int_0^{T_f}Q(t)^{5/2}\\,dt$ for external sediment, where $C_s$ is the recorded concentration conversion. The sediment integral uses Simpson quadrature with 20,000 intervals. This scale excludes recycled bank sediment and signed bed forcing; it is not net boundary flux or stored inventory.\n\n')
    lines.append('Summary residuals are sampled before migration/aggradation. Post-remap residuals, when available, include that flood\'s final update. Residual baselines reset at each process restart. Normalization still uses cumulative prescribed input from flood 1, so resumed histories do not establish accumulated full-history drift. Residual rows are not summed. No acceptance tolerance is inferred from finite values or small normalized residuals.\n\n')
    available = [r for r in runs if r['rows'] or r['remap']['rows']]
    if available:
        table(lines, 'rrll', ['Run', 'Last summary flood', 'History', 'Settings'],
              [[str(r['run']), number(r['last_flood']), tex(r['state']), 'verified' if r['configuration_verified'] else 'unverified'] for r in available])
        for phase, columns in [('pre_remap', PRE), ('post', POST)]:
            for key in columns:
                records = [(r, (r[phase] if phase == 'pre_remap' else r['remap'][phase])[key]) for r in available]
                records = [(r, m) for r, m in records if m.get('finite_count')]
                if not records:
                    continue
                unit = r'm$^3$' if 'water' in key else 'kg'
                lines.append(r'\paragraph{' + tex(key.replace('_', ' ')) + '} Absolute values in ' + unit + '; ratios are dimensionless. Maxima use all available finite rows; terminal values retain their sign.\\par\n')
                table(lines, 'rrrrrr', ['Run', 'Max absolute', 'Terminal signed', 'Max/input', 'Terminal/input', 'Finite/rows'],
                      [[str(r['run']), number(m.get('maximum_absolute')), number(m.get('terminal_signed')),
                        number(m.get('maximum_absolute_over_cumulative_input')), number(m.get('terminal_signed_over_cumulative_input')),
                        '{}/{}'.format(m['finite_count'], m['expected_count'])] for r, m in records])
        local_rows = []
        for r in available:
            if r['remap']['rows']:
                local_rows.append([str(r['run'])] + [number(r['remap']['local'][k].get('maximum_absolute')) for k in LOCAL])
        if local_rows:
            lines.append('Maximum absolute local before/after remap defects (water in m$^3$, sediment in kg):\\par\n')
            table(lines, 'rrrrrr', ['Run', 'Water', 'Sand', 'Silt', 'Clay', 'Combined solids'], local_rows)
        for r in available:
            if r['notes']:
                lines.append('Run {}: {}.\\par\n'.format(r['run'], tex('; '.join(r['notes']))))
            if r['remap']['rows'] and r['remap']['notes']:
                lines.append('Run {} remap ledger: {}.\\par\n'.format(r['run'], tex('; '.join(r['remap']['notes']))))
    absent_remaps = [r['run'] for r in runs if not r['remap']['rows']]
    if absent_remaps:
        lines.append('Post-remap evidence is pending for runs ' + ', '.join(map(str, absent_remaps)) + '.\n\n')
    lines.append('The optional remap ledger reports local water and suspended-class transfer defects plus the combined suspension--bed--bank solid defect after signed bed forcing. These checks do not establish conservation of grain identity through an untracked bed composition. Exact extrema locations, missing-field counts, provenance hashes, and pending reasons are retained in \\texttt{validation/report\\_summary.json}.\n')
    return ''.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', default='data')
    parser.add_argument('--sensitivity-root', default='validation/runs')
    parser.add_argument('--checks-exit-code', type=int)
    parser.add_argument('--floods', type=int, default=580)
    parser.add_argument('--tex', default='report/generated/validation.tex')
    parser.add_argument('--json', default='validation/report_summary.json')
    parser.add_argument('--strict', action='store_true', help='exit 2 after writing if required histories or sensitivity cases are pending')
    args = parser.parse_args()
    if args.floods < 1:
        parser.error('--floods must be positive')
    targets = [Path(args.tex).resolve(), Path(args.json).resolve()]
    if any(ROOT not in path.parents for path in targets):
        parser.error('report outputs must remain inside the /data project')
    inputs = {Path(__file__).resolve()}
    kernel = ROOT / 'validation/kernel.txt'
    if kernel.exists():
        inputs.add(kernel)
    runs, binary = production(Path(args.data_root).resolve(), args.floods, inputs)
    report = dict(utc_generated=datetime.datetime.utcnow().isoformat() + 'Z', command=sys.argv,
                  checks_exit_code=args.checks_exit_code, requested_floods=args.floods,
                  kernel_log_present=kernel.exists(),
                  data_root=label(Path(args.data_root).resolve()), production_binary_sha256=binary,
                  production=runs, sensitivity=sensitivity(Path(args.sensitivity_root).resolve(), binary, inputs))
    report['input_sha256'] = {label(path): sha(path) for path in sorted(inputs)}
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
    targets[0].write_text(render(report))
    targets[1].write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print('Wrote validation report; {}/31 production histories complete, {}/8 sensitivity cases verified.'.format(
        sum(r['state'] == 'complete requested history' for r in runs),
        sum(r['state'] == 'complete' for r in report['sensitivity']['cases'])))
    complete = (all(r['state'] == 'complete requested history' for r in runs)
                and all(r['state'] == 'complete' for r in report['sensitivity']['cases']))
    return 2 if args.strict and not complete else 0


if __name__ == '__main__':
    sys.exit(main())
