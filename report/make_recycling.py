#!/usr/bin/env python3
"""Render the archived case-30 flood-6/7 bank-recycling comparison."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('replay.py', 'replay.json',
         'flood6/run30-inventory-capture.json', 'flood6/run30-inventory-inputs.tar.xz',
         'flood7/run30-inventory-capture.json', 'flood7/run30-inventory-inputs.tar.xz')


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    return value.hexdigest()


def tex(value):
    return ''.join({'_': r'\_', '%': r'\%', '&': r'\&', '#': r'\#',
                    '{': r'\{', '}': r'\}', '$': r'\$',
                    '\\': r'\textbackslash{}'}.get(c, c) for c in str(value))


def number(value, digits=6):
    if value == 0:
        return '0'
    mantissa, exponent = ('%.*e' % (digits - 1, value)).split('e')
    return r'%s\times10^{%d}' % (mantissa.rstrip('0').rstrip('.'), int(exponent))


def render(data):
    bank = data['bank_balance']
    masks = data['raster_transitions']
    arithmetic = data['arithmetic_diagnostics']
    hydrograph = data['one_prescribed_hydrograph']
    lines = [r'\subsection{Archived production bank recycling}',
             'Retained post-remap checkpoints for case 30 bracket flood 7 of rebuild 002',
             r'($A=0.012$ m per flood, $C=0.0003$, $E=1.5$, 250 m grid).',
             'Independent endpoint raster masks contain %d channel cells at each time,' %
             masks['old_channel_cells'],
             'with %d common, %d newly occupied, and %d abandoned cells.' %
             (masks['common_channel_count'], masks['captured_count'], masks['abandoned_count']),
             r'The post-flood-6 bank reservoir contains $%s$ kg;' %
             number(bank['post6_bank_kg'], 9),
             r'$%s$ kg enters the upstream boundary during flood 7, leaving' %
             number(bank['recycled_during7_kg'], 9),
             r'$%s$ kg before remapping. The ledger-derived remap addition is $%s$ kg.' %
             (number(bank['pre7_remap_bank_kg_from_12_digit_summary']),
              number(bank['ledger_derived_remap7_bank_addition_kg'])),
             r'The reservoir balance differs from the rounded pre-remap summary by $%s$ kg.' %
             number(bank['post6_minus_recycled_minus_pre7_kg']),
             '',
             r'Let $\Delta$ denote post-flood-7 minus post-flood-6. Water inventory is $W$,',
             r'total suspension $S$, deposited-source mass $D$, signed bed inventory $M$,',
             r'and stored bank mass $K$. The net external ledgers are $N_W,N_S$,',
             r'numerical corrections $C_W,C_S$, signed bed forcing $F$, and cumulative',
             r'recycling $R$. Independent temporal residuals are',
             r'\begin{align*}',
             r' r_W &= \Delta W-\Delta N_W-\Delta C_W,\\',
             r' r_{S+D} &= \Delta(S+D)-\Delta N_S-\Delta C_S,\\',
             r' r_T &= \Delta(S+M+K)+\Delta R-\Delta F-\Delta N_S-\Delta C_S.',
             r'\end{align*}',
             r'Recycling enters the external inlet ledger; $+\Delta R$ removes its',
             'duplicate contribution when the bank reservoir is included.',
             r'The table compares $r$ with the difference $\Delta e$ of recorded',
             'post-remap residuals. Normalization uses one prescribed hydrograph:',
             r'$%s$ m$^3$ water and $%s$ kg sediment, excluding recycling.' %
             (number(hydrograph['water_m3']), number(hydrograph['sediment_kg'])),
             r'\begin{center}\small', r'\begin{tabular}{lrrr}', r'\toprule',
             r'Inventory & $r$ & $r-\Delta e$ & $(r-\Delta e)$/input \\', r'\midrule']
    for title, key in ((r'Water (m$^3$)', 'water'),
                       ('Suspension + deposition (kg)', 'suspension_plus_deposition'),
                       ('Full solids (kg)', 'full_solid')):
        row = data['temporal_balances'][key]
        lines.append(r'%s & $%s$ & $%s$ & $%s$ \\' %
                     (title, number(row['inventory_based']), number(row['signed_discrepancy']),
                      number(row['discrepancy_over_one_hydrograph'])))
    lines += [r'\bottomrule\end{tabular}\end{center}',
              'The full-solid discrepancy remains',
              r'$%s$ kg when bed changes are summed cell by cell.' %
              number(arithmetic['stable_cellwise_full_solid_balance']['signed_discrepancy']),
              'Replaying the frozen diagnostic addition order in Python gives',
              r'$%s$ kg; this diagnoses summation-order sensitivity without claiming' %
              number(arithmetic['source_order_temporal_balances']['full_solid']['signed_discrepancy']),
              'compiled bit identity or a numerical pass threshold.',
              '',
              'These are endpoint raster transitions, not continuous swept-bank area',
              'or counts of physical erosion events. The pre-remap flood-7 bed is absent,',
              'so excavation mass by cell is unavailable. Current and incremental',
              'inventory checks require no regenerated initial reference. This single',
              'production interval establishes neither convergence, long-term behavior,',
              'nor manuscript-panel agreement. The offline replay verifies both saved',
              'capsules and reproduces the retained comparison; source and artifact pins',
              r'are in \path{report/generated/recycling_evidence.json}.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-root', type=Path, default=ROOT / 'validation/production-recycling-002')
    parser.add_argument('--output', type=Path, default=ROOT / 'report/generated')
    args = parser.parse_args()
    args.output.resolve().relative_to(ROOT)
    evidence = dict(status='pending', archive=str(args.archive_root.resolve().relative_to(ROOT)),
                    generator_sha256=sha(Path(__file__)), files_sha256={},
                    scope='case 30 post-flood-6/7 comparison; no manuscript-panel assessment')
    try:
        evidence['files_sha256'] = {name: sha(args.archive_root / name) for name in FILES}
        analyze = runpy.run_path(str(args.archive_root / 'replay.py'))['analyze']
        data = analyze(args.archive_root / 'flood6', args.archive_root / 'flood7')
        if data != json.loads((args.archive_root / 'replay.json').read_text()):
            raise ValueError('saved comparison differs from replay of retained inputs')
        if any(sha(args.archive_root / name) != value for name, value in evidence['files_sha256'].items()):
            raise ValueError('retained input changed during replay')
        content = render(data)
        evidence.update(status='verified archived comparison', comparison=data)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError, SyntaxError,
            RuntimeError, ZeroDivisionError, struct.error, tarfile.TarError) as error:
        reason = ('Missing retained file: ' + Path(error.filename).name
                  if isinstance(error, FileNotFoundError) else str(error))
        evidence['reason'] = reason
        content = (r'\subsection{Archived production bank recycling}' + '\n' +
                   r'\pending{The retained bank-recycling comparison could not be verified: ' +
                   tex(reason) + '. No numerical claim is rendered from this archive.}\n')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'recycling.tex').write_text(content)
    evidence['rendered_tex_sha256'] = sha(args.output / 'recycling.tex')
    (args.output / 'recycling_evidence.json').write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(evidence['status'])


if __name__ == '__main__':
    main()
