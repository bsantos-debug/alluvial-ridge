#!/usr/bin/env python3
"""Render retained production recycling and initial-inventory diagnostics."""
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
INITIAL_FILES = ('replay.py', 'replay.json', 'capture.json', 'compile-provenance.json',
                 'physics.txt', 'runs.csv', 'peak-channel-initial-geometry.csv',
                 'rng-witness.cpp', 'rng-witness.csv', 'rng-provenance.json')
FINE_FILES = ('replay.py', 'replay.json', 'capture.json', 'capture-observation.json') + tuple(
    'inputs/' + name for name in ('accepted.json', 'checkpoint.bin', 'comparison.json',
        'observer-seed.json', 'parameters.txt', 'peak_channel_0001.csv', 'prior-scalar.json',
        'process_status.json', 'remap_budget.csv', 'scalar.json', 'summary.csv'))


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


def render_initial(data):
    initial = data['initial_inventories']['source_order']
    geometry = data['initial_geometry']
    ordered = data['budget_diagnostics']['source_order']
    compensated = data['budget_diagnostics']['compensated']
    lines = [r'\subsection{Reconstructed initial inventory at production flood 19}',
             'A separate replay reconstructs the initial water and signed bed inventories',
             r'for case 29 ($A=0.012$ m per flood, $C=0.0003$, $E=0.5$, 250 m grid).',
             'The retained command, configuration and compiler provenance establish a',
             'fresh start. An independent integer implementation of the seeded random',
             'generator matches all 574 words and 287 doubles from a retained GNU 8',
             'standard-library witness. Reconstructed coordinates, prescribed channel',
             'bed and control areas match all 1156 tokens in the first-peak geometry',
             'file at its 12-significant-digit precision. The evolved peak water',
             'depth and velocity are excluded from that comparison.',
             '',
             r'The initial hydraulic depth is $%s$ m; the specified 8 m is bed incision.' %
             number(geometry['initial_water_depth_m'], 9),
             r'Integration over %d channel control areas gives $W_0=%s$ m$^3$.' %
             (geometry['channel_nodes'], number(initial['water_m3'], 12)),
             r'The signed raster-bed inventory relative to the unincised plane is',
             r'$T_0=%s$ kg. Initial suspension, bank reservoirs and cumulative' %
             number(initial['total_solid_kg'], 12),
             'exchange ledgers are zero. Mapped channel raster cells contribute bed',
             'mass, while their interpolated water states are excluded from storage.',
             '',
             r'Using the preceding notation and $T=S+M+K$, the endpoint residuals are',
             r'\begin{align*}',
             r' r_W &= W_{19}-W_0-N_W-C_W,\\',
             r' r_{S+D} &= S_{19}+D_{19}-N_S-C_S,\\',
             r' r_T &= T_{19}-T_0+R-F-N_S-C_S.',
             r'\end{align*}',
             'The external flux, signed forcing, recycling and correction terms are',
             'recorded ledgers; boundary exchanges are not independently reintegrated.',
             r'The table compares the reconstructed residual $r$ with the recorded',
             r'post-remap residual $e$. Ordered calculations follow the source additions;',
             'compensated calculations sum the same inventory and budget terms separately.',
             r'\begin{center}\small', r'\begin{tabular}{lrrr}', r'\toprule',
             r'Inventory & Ordered $r$ & Ordered $r-e$ & Compensated $r-e$ \\',
             r'\midrule']
    for label, key in ((r'Water (m$^3$)', 'water'),
                       ('Suspension + deposition (kg)', 'suspension'),
                       ('Full solids (kg)', 'full_solid')):
        lines.append(r'%s & $%s$ & $%s$ & $%s$ \\' %
                     (label, number(ordered[key]['residual']),
                      number(ordered[key]['reconstruction_minus_recorded']),
                      number(compensated[key]['reconstruction_minus_recorded'])))
    lines += [r'\bottomrule\end{tabular}\end{center}',
              'Ordered water and full-solid residuals agree numerically with the retained',
              'ledger in this replay. The compensated full-solid residual is',
              r'$%s$ kg, with a discrepancy of $%s$ kg, or $%s$ of the' %
              (number(compensated['full_solid']['residual']),
               number(compensated['full_solid']['reconstruction_minus_recorded']),
               number(compensated['full_solid']['normalized_reconstruction_minus_recorded'])),
              'prescribed sediment input over 19 floods. Full-solid acceptance remains',
              'unassessed: no numerical threshold is assigned. The existing strict',
              r'$10^{-3}$ m$^3$ water-storage and $10^{-3}$ kg suspension guards',
              'belong to the original endpoint replay and remain unchanged.',
              '',
              'Rounded geometry and the new random-generator witness do not establish',
              'historical compiled-model bit identity. This endpoint calculation does',
              'not establish convergence or manuscript-panel agreement. The original',
              'flood-19 archive remains unchanged; the extension and its regenerated',
              r'results are bound in \path{report/generated/initial_reference_evidence.json}.']
    return '\n'.join(lines) + '\n'


def initial_archive(folder, output):
    evidence = dict(status='pending', archive=str(folder.resolve().relative_to(ROOT)),
                    generator_sha256=sha(Path(__file__)), files_sha256={},
                    scope='case 29 initial inventory and flood-19 budget diagnostics; full-solid acceptance unassessed')
    try:
        evidence['files_sha256'] = {name: sha(folder / name) for name in INITIAL_FILES}
        data = runpy.run_path(str(folder / 'replay.py'))['analyze'](folder)
        if data != json.loads((folder / 'replay.json').read_text()):
            raise ValueError('saved initial reconstruction differs from replay of retained inputs')
        if any(sha(folder / name) != digest for name, digest in evidence['files_sha256'].items()):
            raise ValueError('retained initial-reference input changed during replay')
        content = render_initial(data)
        evidence.update(status='verified initial reconstruction with budget diagnostics', comparison=data)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError, SyntaxError,
            RuntimeError, ZeroDivisionError, struct.error, tarfile.TarError) as error:
        reason = ('Missing retained file: ' + Path(error.filename).name
                  if isinstance(error, FileNotFoundError) else str(error))
        evidence['reason'] = reason
        content = (r'\subsection{Reconstructed initial inventory at production flood 19}' + '\n' +
                   r'\pending{The retained initial reconstruction could not be verified: ' +
                   tex(reason) + '. No numerical claim is rendered from this archive.}\n')
    (output / 'initial_reference.tex').write_text(content)
    evidence['rendered_tex_sha256'] = sha(output / 'initial_reference.tex')
    (output / 'initial_reference_evidence.json').write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return evidence['status']


def render_fine(data):
    native = data['native']
    ordered = data['budget_diagnostics']['source_order']
    compensated = data['budget_diagnostics']['compensated']
    lines = [r'\subsection{Later fine-sediment inventory check}',
             r'A retained flood-14 checkpoint for case 26 ($A=0.036$ m per flood,',
             r'$C=0.003$, $E=1$, 250 m grid) extends the inventory check to a later',
             'state with sand, silt and clay fractions of 0.05, 0.20 and 0.75.',
             r'The bank reservoir contains $%s$ kg, and cumulative recorded recycling' %
             number(native['bank_compensated_total_kg']),
             r'is $%s$ kg. The replay integrates the retained native arrays and' %
             number(data['checkpoint']['recycled']),
             'reconstructs the initial water and signed bed inventories from the',
             'fresh-start inputs. All initialization dependencies match case 29;',
             'the different sediment fractions act on zero initial suspension and',
             'bank inventories. The reconstructed initial geometry also matches',
             'the case-26 first-peak coordinates, bed and areas at printed precision.',
             '',
             'Applying the preceding budget definitions at flood 14 gives the',
             'following residuals. Boundary exchanges, deposition, signed forcing,',
             'recycling and correction terms remain recorded quantities.',
             r'\begin{center}\small', r'\begin{tabular}{lrrr}', r'\toprule',
             r'Inventory & Ordered $r$ & Ordered $r-e$ & Compensated $r-e$ \\',
             r'\midrule']
    for label, key in ((r'Water (m$^3$)', 'water'),
                       ('Suspension + deposition (kg)', 'suspension'),
                       ('Full solids (kg)', 'full_solid')):
        lines.append(r'%s & $%s$ & $%s$ & $%s$ \\' %
                     (label, number(ordered[key]['residual']),
                      number(ordered[key]['reconstruction_minus_recorded']),
                      number(compensated[key]['reconstruction_minus_recorded'])))
    lines += [r'\bottomrule\end{tabular}\end{center}',
              r'Native water storage differs from its recorded inventory by $%s$ m$^3$;' %
              number(native['water_storage_minus_post_ledger_m3']),
              r'the suspension-plus-deposition residual differs from its ledger by $%s$ kg.' %
              number(native['independent_suspension_residual_minus_ledger_kg']),
              r'Both satisfy the inherited strict $10^{-3}$ m$^3$ and $10^{-3}$ kg',
              'reconciliation guards. These guards constrain the discrepancy between',
              'inventories and ledgers, not the absolute budget residual. The table',
              'also distinguishes source-order and compensated budget arithmetic.',
              '',
              r'The compensated full-solid discrepancy is $%s$ of prescribed sediment' %
              number(compensated['full_solid']['normalized_reconstruction_minus_recorded']),
              'input over 14 floods. Full-solid acceptance remains unassessed, with',
              'no new threshold. Boundary fluxes are not independently reintegrated,',
              'and this single endpoint establishes neither event history, convergence,',
              'compiled-model bit identity nor manuscript-panel agreement. Retained',
              'bytes, reused pure functions and regenerated results are bound in',
              r'\path{report/generated/fine_inventory_evidence.json}.']
    return '\n'.join(lines) + '\n'


def fine_archive(folder, output):
    evidence = dict(status='pending', archive=str(folder.resolve().relative_to(ROOT)),
                    generator_sha256=sha(Path(__file__)), files_sha256={},
                    scope='case 26 flood-14 native inventories and reconstructed initial references; full-solid acceptance unassessed')
    try:
        evidence['files_sha256'] = {name: sha(folder / name) for name in FINE_FILES}
        data = runpy.run_path(str(folder / 'replay.py'))['analyze'](folder)
        if data != json.loads((folder / 'replay.json').read_text()):
            raise ValueError('saved fine-sediment reconstruction differs from retained-input replay')
        if any(sha(folder / name) != digest for name, digest in evidence['files_sha256'].items()):
            raise ValueError('retained fine-sediment input changed during replay')
        content = render_fine(data)
        evidence.update(status='verified later fine-sediment inventory reconciliation', comparison=data)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError, SyntaxError,
            RuntimeError, ZeroDivisionError, struct.error, tarfile.TarError) as error:
        reason = ('Missing retained file: ' + Path(error.filename).name
                  if isinstance(error, FileNotFoundError) else str(error))
        evidence['reason'] = reason
        content = (r'\subsection{Later fine-sediment inventory check}' + '\n' +
                   r'\pending{The retained fine-sediment reconstruction could not be verified: ' +
                   tex(reason) + '. No numerical claim is rendered from this archive.}\n')
    (output / 'fine_inventory.tex').write_text(content)
    evidence['rendered_tex_sha256'] = sha(output / 'fine_inventory.tex')
    (output / 'fine_inventory_evidence.json').write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return evidence['status']


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
    print(initial_archive(args.archive_root / 'run29-initial-reference', args.output))
    print(fine_archive(args.archive_root / 'run26-flood14', args.output))


if __name__ == '__main__':
    main()
