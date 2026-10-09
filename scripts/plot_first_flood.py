#!/usr/bin/env python3
"""Plot archived first-flood grid diagnostics, separately from manuscript panels."""
import argparse
import copy
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
for key, name in (('MPLCONFIGDIR', 'matplotlib'), ('XDG_CACHE_HOME', 'cache'),
                  ('TMPDIR', 'first-flood-plot'), ('PYTHONPYCACHEPREFIX', 'pycache')):
    folder = ROOT / 'tmp' / name
    folder.mkdir(parents=True, exist_ok=True)
    os.environ[key] = str(folder)

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.patches import Patch

ARCHIVE = ROOT / 'validation/first-flood-audit-002'
CASES = ('baseline250', 'coarse500')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative(path):
    return str(path.resolve().relative_to(ROOT))


def load():
    capture_path = ARCHIVE / 'capture-provenance.json'
    capture_bytes = capture_path.read_bytes()
    capture = json.loads(capture_bytes.decode())
    archived = capture['sensitivity_input_archive']
    inputs = {relative(capture_path): sha(capture_bytes)}
    saved = {}
    for name in ('two-resolution.json', 'two-resolution.py', archived['file']):
        require(Path(name).name == name, 'archive paths must be basenames')
        blob = (ARCHIVE / name).read_bytes()
        require(sha(blob) == capture['files_sha256'][name], 'archive hash differs: ' + name)
        inputs[relative(ARCHIVE / name)] = sha(blob)
        saved[name] = blob
    reference = json.loads(saved['two-resolution.json'].decode())
    expected = archived['files_sha256']
    members = {}
    with tarfile.open(fileobj=io.BytesIO(saved[archived['file']]), mode='r:*') as archive:
        for item in archive:
            require(item.isfile() and item.name in expected and item.name not in members,
                    'unexpected or duplicate archive member: ' + item.name)
            blob = archive.extractfile(item).read()
            require(sha(blob) == expected[item.name], 'member hash differs: ' + item.name)
            members[item.name] = blob
    require(len(members) == archived['members'] and set(members) == set(expected),
            'incomplete sensitivity archive')
    required, cases = set(), {}
    for name, spacing in zip(CASES, (250., 500.)):
        prefix = 'validation/runs/' + name + '/'
        process = json.loads(members[prefix + 'process_status.json'].decode())
        recorded = reference['cases'][name]
        require(process == recorded['process'] and process['state'] == 'complete'
                and process['exit_code'] == 0 and recorded['state'] == 'complete',
                'case lacks identical completed process evidence: ' + name)
        required.add(prefix + 'process_status.json')
        for filename, checksum in process['artifact_sha256'].items():
            require(expected.get(prefix + filename) == checksum,
                    'case artifact map differs: ' + name + '/' + filename)
            required.add(prefix + filename)
        p = {}
        for line in members[prefix + 'parameters.txt'].decode().splitlines():
            key, value = line.split(' ', 1)
            if key != 'command':
                p[key] = float(value)
        require(p == recorded['parameters'], 'recorded case parameters differ: ' + name)
        require(all(p[k] == v for k, v in dict(dx=spacing, run=11, floods=1,
                    length=72000, width=48000, duration=1728000, A=0, C=.003, E=1, fine=0).items()),
                'unexpected first-flood configuration: ' + name)
        require(members[prefix + 'status.txt'].decode().strip() == 'complete 1 floods',
                'first flood is not complete: ' + name)
        rows = list(csv.DictReader(io.StringIO(members[prefix + 'summary.csv'].decode())))
        require(len(rows) == 1 and float(rows[0]['flood']) == 1,
                'unexpected summary window: ' + name)
        blob = members[prefix + 'fields_0001.bin']
        nx, ny, nodes, flood, dx, clock, slope = struct.unpack('=4i3d', blob[:40])
        require((nx * dx, ny * dx, dx, flood, clock, slope) ==
                (72000, 48000, spacing, 1, 1728000, p['slope']) and nodes >= 2,
                'invalid end-flood raster metadata: ' + name)
        require(len(blob) == 40 + nx * ny * 16, 'invalid raster length: ' + name)
        values = np.frombuffer(blob, dtype='=f4', offset=40).reshape(ny, nx, 4).astype('float64')
        require(np.isfinite(values).all() and (values[:, :, 1:3] >= 0).all()
                and np.isin(values[:, :, 3], [0, 1]).all(), 'invalid saved raster values: ' + name)
        cases[name] = dict(parameters=p, values=values, process=process,
                           snapshot=dict(nx=nx, ny=ny, channel_nodes=nodes, flood=flood,
                                         dx_m=dx, elapsed_seconds=clock))
    require(required == set(expected), 'archive contains an unbound case file')
    fine, coarse = (cases[name] for name in CASES)
    require(fine['process']['binary_sha256'] == coarse['process']['binary_sha256'],
            'the two cases used different executables')
    require({k: v for k, v in fine['parameters'].items() if k != 'dx'} ==
            {k: v for k, v in coarse['parameters'].items() if k != 'dx'},
            'the cases differ beyond floodplain spacing')
    return cases, reference, inputs, expected


def compare(cases, reference):
    fine, coarse = (cases[name]['values'] for name in CASES)
    ny, nx = coarse.shape[:2]
    require(fine.shape[:2] == (2 * ny, 2 * nx), 'grids are not nested two-to-one')
    blocks = fine.reshape(ny, 2, nx, 2, 4)
    averaged = blocks[:, :, :, :, :3].mean(axis=(1, 3), dtype=np.float64)
    excluded = blocks[:, :, :, :, 3].any(axis=(1, 3)) | (coarse[:, :, 3] != 0)
    difference = coarse[:, :, :3] - averaged
    statistics = dict(common_floodplain_area_m2=int((~excluded).sum()) * 500. ** 2,
                      mean_absolute_difference_m={}, maximum_absolute_difference_m={})
    for k, field in enumerate(('bed', 'water_depth', 'deposition')):
        error = np.abs(difference[:, :, k][~excluded])
        statistics['mean_absolute_difference_m'][field] = float(error.mean())
        statistics['maximum_absolute_difference_m'][field] = float(error.max())
        for metric in ('mean_absolute_difference_m', 'maximum_absolute_difference_m'):
            require(math.isclose(statistics[metric][field],
                                 reference['common_floodplain_fields'][metric][field],
                                 rel_tol=1e-10, abs_tol=1e-14),
                    'common-cell comparison differs from archive: ' + metric + '/' + field)
    require(statistics['common_floodplain_area_m2'] ==
            reference['common_floodplain_fields']['common_floodplain_area_m2'],
            'common comparison area differs from archive')
    return difference, excluded, statistics


def plot(cases, difference, excluded, stats, output):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 14,
                         'axes.titlesize': 16, 'axes.labelsize': 14,
                         'pdf.fonttype': 42, 'savefig.facecolor': 'white'})
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 10.6))
    fig.subplots_adjust(left=.065, right=.985, bottom=.23, top=.82, wspace=.19, hspace=.48)
    fig.suptitle('First-flood grid validation: run 11, day 20', y=.974, fontsize=21)
    fig.text(.5, .936, 'Full 72 km × 48 km domain; end-flood rasters precede migration and remapping',
             ha='center', fontsize=14)
    fig.text(.5, .904, 'A = 0 m/flood, C = 0.003, E = 1; channel-node spacing = 250 m in both cases',
             ha='center', fontsize=14)
    gray = '#646870'
    norms = (colors.Normalize(0, .5), colors.LogNorm(1e-6, .5))
    difference_norms = (colors.Normalize(-.4, .4),
                        colors.SymLogNorm(linthresh=1e-4, linscale=1, base=10, vmin=-.15, vmax=.15))
    quantities = ('Water depth (m)', 'Event deposit (m; log scale)')
    titles = ('250 m grid', '500 m grid', 'Coarse − mean(fine)')
    conventions = dict(extent_km=[0, 72, 0, 48], origin='lower', interpolation='nearest',
                       snapshot_phase='flood 1, day 20, before first remap',
                       water_depth_limits_m=[0, .5], water_difference_limits_m=[-.4, .4],
                       deposition_log_limits_m=[1e-6, .5],
                       deposition_difference_symlog_limits_m=[-.15, .15],
                       deposition_difference_linear_core_m=1e-4,
                       deposition_difference_symlog_base=10,
                       absolute_mask='active channel cells gray; floodplain values retained',
                       below_deposition_display_threshold='values below 1e-6 m white; no clipping in metrics',
                       difference_sign='coarse minus arithmetic mean of four fine cells',
                       difference_mask='exclude coarse blocks containing any active channel cell in either grid',
                       dry_cells='retained in common-floodplain comparisons',
                       scientific_scope='one first flood; no manuscript-panel reproduction or convergence inference')
    for row, index in enumerate((1, 2)):
        for col in range(3):
            ax = axes[row, col]
            if col < 2:
                field = cases[CASES[col]]['values']
                channel = field[:, :, 3] != 0
                values, mask = field[:, :, index], channel
                norm = norms[row]
                cmap = copy.copy(plt.get_cmap('Blues' if row == 0 else 'magma_r'))
                cmap.set_bad('white'); cmap.set_under('white')
                if row == 1:
                    mask = channel | (values < 1e-6)
                image = ax.imshow(np.ma.array(values, mask=mask), origin='lower', extent=[0, 72, 0, 48],
                                  interpolation='nearest', cmap=cmap, norm=norm)
                overlay = np.ma.masked_where(~channel, np.ones(channel.shape))
                ax.imshow(overlay, origin='lower', extent=[0, 72, 0, 48], interpolation='nearest',
                          cmap=colors.ListedColormap([gray]), vmin=0, vmax=1)
                ticks = [0, .1, .2, .3, .4, .5] if row == 0 else [1e-6, 1e-4, 1e-2, .5]
                bar_label = quantities[row]
            else:
                cmap = copy.copy(plt.get_cmap('RdBu_r')); cmap.set_bad(gray)
                image = ax.imshow(np.ma.array(difference[:, :, index], mask=excluded), origin='lower',
                                  extent=[0, 72, 0, 48], interpolation='nearest', cmap=cmap,
                                  norm=difference_norms[row])
                ticks = [-.4, -.2, 0, .2, .4] if row == 0 else [-.1, -.001, 0, .001, .1]
                bar_label = 'Depth difference (m)' if row == 0 else 'Deposit difference (m; symmetric log)'
            ax.set_title('(' + chr(97 + 3 * row + col) + ') ' + titles[col], pad=8)
            ax.set_xticks([0, 24, 48, 72]); ax.set_yticks([0, 24, 48])
            ax.set_xlabel('Downstream x (km)', labelpad=2)
            if col == 0:
                ax.set_ylabel('Cross-valley y (km)')
            bar = fig.colorbar(image, ax=ax, orientation='horizontal', fraction=.055, pad=.20, ticks=ticks)
            bar.set_label(bar_label, fontsize=14, labelpad=3)
            bar.ax.tick_params(labelsize=13)
            if row == 1:
                bar.ax.minorticks_off()
                bar.ax.set_xticklabels(['0.000001', '0.0001', '0.01', '0.5'] if col < 2
                                       else ['−0.1', '−0.001', '0', '0.001', '0.1'])
    fig.legend(handles=[Patch(facecolor=gray, label='Gray: active channel (a, b, d, e); excluded channel-containing blocks (c, f)'),
                        Patch(facecolor='white', edgecolor='.5', label='White in deposit maps (d, e): less than 0.000001 m')],
               loc='lower left', bbox_to_anchor=(.055, .112), frameon=False, fontsize=14)
    fig.text(.055, .093, 'Common floodplain: %.0f km²; average each fine 2 × 2 block; retain dry cells.' %
             (stats['common_floodplain_area_m2'] / 1e6), fontsize=14)
    fig.text(.055, .068, 'Mean absolute differences: depth %.6f m; deposit %.6f m. Symmetric-log linear core: ±0.0001 m.' %
             (stats['mean_absolute_difference_m']['water_depth'], stats['mean_absolute_difference_m']['deposition']), fontsize=13)
    fig.text(.055, .032, 'Independent validation diagnostic — not a manuscript panel or evidence of grid/time convergence.',
             fontsize=14, weight='bold')
    pdf, png = output / 'first_flood_validation.pdf', output / 'first_flood_validation.png'
    fig.savefig(str(pdf), metadata={'Creator': 'scripts/plot_first_flood.py', 'CreationDate': None, 'ModDate': None})
    fig.savefig(str(png), dpi=220, metadata={'Software': 'scripts/plot_first_flood.py'})
    plt.close(fig)
    return conventions, {relative(path): sha(path.read_bytes()) for path in (pdf, png)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'figures')
    args = parser.parse_args()
    relative(args.output)
    cases, reference, inputs, members = load()
    difference, excluded, stats = compare(cases, reference)
    args.output.mkdir(parents=True, exist_ok=True)
    conventions, outputs = plot(cases, difference, excluded, stats, args.output)
    evidence = dict(format=1, scope='archived first-flood validation only; no manuscript-panel assessment',
                    command=[sys.executable] + sys.argv, processor_sha256=sha(Path(__file__).read_bytes()),
                    versions=dict(python=sys.version, numpy=np.__version__, matplotlib=matplotlib.__version__),
                    input_sha256=inputs, member_sha256=members,
                    verified_case_records={name: dict(state='complete', exit_code=0,
                        binary_sha256=cases[name]['process']['binary_sha256'], snapshot=cases[name]['snapshot']) for name in CASES},
                    comparison=stats, plotting_conventions=conventions, outputs_sha256=outputs)
    (args.output / 'first_flood_validation_manifest.json').write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print('Wrote first-flood validation figure; all 24 archived members and comparison metrics verified.')


if __name__ == '__main__':
    main()
