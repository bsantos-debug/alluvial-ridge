#!/usr/bin/env python3
"""Measure day-12 water extent and end-flood deposition from independent rasters."""
import argparse
import csv
import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = [('1A', 11, 61), ('1B', 11, 251), ('1C', 11, 501),
           ('1D', 11, 562), ('1E', 17, 562), ('1F', 3, 562)]
WET = .001  # Same diagnostic-only depth threshold as the C++ alpha calculation.


def read(path, inputs):
    blob = path.read_bytes()
    inputs[str(path.relative_to(ROOT))] = hashlib.sha256(blob).hexdigest()
    return blob


def finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def field(path, flood, duration, phase, inputs):
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('invalid recorded flood duration')
    blob = read(path, inputs)
    if len(blob) < 40:
        raise ValueError('truncated raster header')
    nx, ny, nodes, number, dx, clock, slope = struct.unpack('=4i3d', blob[:40])
    if min(nx, ny) < 1 or nodes < 2 or number != flood or len(blob) != 40 + 16 * nx * ny:
        raise ValueError('invalid raster dimensions, flood index, or byte count')
    if not all(math.isfinite(v) for v in (dx, clock, slope)) or dx <= 0:
        raise ValueError('invalid raster metadata')
    if abs(clock - (flood - 1 + phase) * duration) > 1e-5:
        raise ValueError('raster clock does not match requested sampling phase')
    values = np.frombuffer(blob, dtype=np.float32, offset=40).reshape(ny, nx, 4)
    if not np.isfinite(values).all() or (values[:, :, 1:3] < 0).any():
        raise ValueError('negative/nonfinite raster state')
    if not np.isin(values[:, :, 3], (0, 1)).all():
        raise ValueError('nonbinary channel mask')
    return values, dict(nx=nx, ny=ny, nodes=nodes, dx_m=dx, elapsed_seconds=clock, slope=slope)


def roundoff(values):
    """Conservative half-ULP bounds on double-to-float32 snapshot rounding."""
    values = np.asarray(values, dtype=np.float32)
    above = np.nextafter(values, np.float32(np.inf)).astype(np.float64) - values
    below = values.astype(np.float64) - np.nextafter(values, np.float32(-np.inf))
    return .5 * np.maximum(above, below)


def wet_interface(values, dx):
    z, h, mask = values[:, :, 0].astype(float), values[:, :, 1].astype(float), values[:, :, 3].astype(bool)
    dz, dh = roundoff(values[:, :, 0]), roundoff(values[:, :, 1])
    total = wet = certain = possible = 0
    edges = []
    # An edge is stored by its two integer grid vertices; components share a vertex.
    for axis in (0, 1):
        left = (slice(None, -1), slice(None)) if axis == 0 else (slice(None), slice(None, -1))
        right = (slice(1, None), slice(None)) if axis == 0 else (slice(None), slice(1, None))
        boundary = mask[left] != mask[right]
        channel_left = mask[left]
        fp_h = np.where(channel_left, h[right], h[left])
        fp_dh = np.where(channel_left, dh[right], dh[left])
        stage = np.where(channel_left, h[left] + z[left] - z[right], h[right] + z[right] - z[left])
        error = np.where(channel_left, dh[left], dh[right]) + dz[left] + dz[right]
        active = boundary & (fp_h > WET) & (stage > WET)
        total += int(boundary.sum()); wet += int(active.sum())
        certain += int((boundary & (fp_h - fp_dh > WET) & (stage - error > WET)).sum())
        possible += int((boundary & (fp_h + fp_dh > WET) & (stage + error > WET)).sum())
        for j, i in np.argwhere(active):
            edges.append(((int(i), int(j + 1)), (int(i + 1), int(j + 1))) if axis == 0
                         else ((int(i + 1), int(j)), (int(i + 1), int(j + 1))))
    adjacency = {}
    for index, pair in enumerate(edges):
        for vertex in pair:
            adjacency.setdefault(vertex, []).append(index)
    unseen = set(range(len(edges))); counts = []
    while unseen:
        todo = [unseen.pop()]; count = 0
        while todo:
            edge = todo.pop(); count += 1
            for vertex in edges[edge]:
                for neighbor in adjacency[vertex]:
                    if neighbor in unseen:
                        unseen.remove(neighbor); todo.append(neighbor)
        counts.append(count)
    return dict(interface_faces=total, wet_faces=wet, definitely_wet_faces=certain,
                possibly_wet_faces=possible, fraction=wet / total if total else None,
                length_m=total * dx, wet_length_m=wet * dx,
                connected_wet_patches=len(counts), largest_wet_patch_length_m=max(counts, default=0) * dx)


def measure(folder, run, flood, panel, config, physics, inputs):
    record = dict(panel=panel, run=run, flood=flood, state='pending', notes=[])
    try:
        p = {}
        for line in read(folder / 'parameters.txt', inputs).decode().splitlines():
            key, value = line.split(None, 1)
            if key != 'command':
                p[key] = float(value)
        expected = dict(physics, run=run, dx=250, length=72000, width=48000, duration=1728000,
                        channel_width=500, slope=.0001, initial_depth=8, qmin=2500, qmax=15000,
                        migration=1, rho_s=2650, A=float(config['A_m_per_flood']), C=float(config['C']),
                        E=float(config['E']), fine=int(config['load'] == 'fine'))
        mismatches = [key for key, value in expected.items()
                      if key not in p or not math.isclose(p[key], value, rel_tol=1e-10, abs_tol=1e-12)]
        record['canonical_configuration'] = not mismatches
        if mismatches:
            record['notes'].append('Noncanonical configuration: ' + ', '.join(mismatches))
        summary = {}
        for row in csv.DictReader(io.StringIO(read(folder / 'summary.csv', inputs).decode())):
            n = int(row['flood'])
            if n in summary or n < 1:
                raise ValueError('duplicate/invalid flood in summary')
            summary[n] = row
        if flood not in summary:
            raise FileNotFoundError('requested completed flood is absent from summary')
        peak, pm = field(folder / ('peak_fields_%04d.bin' % flood), flood, p['duration'], .6, inputs)
        end, em = field(folder / ('fields_%04d.bin' % flood), flood, p['duration'], 1., inputs)
        for key in ('nx', 'ny', 'nodes', 'dx_m', 'slope'):
            if pm[key] != em[key]:
                raise ValueError('day-12/end raster metadata differ')
        if not np.array_equal(peak[:, :, 3], end[:, :, 3]):
            raise ValueError('channel mask changed within a flood')
        if pm['nx'] * pm['dx_m'] != p['length'] or pm['ny'] * pm['dx_m'] != p['width'] or pm['dx_m'] != p['dx']:
            raise ValueError('raster geometry differs from recorded parameters')
        fp = ~peak[:, :, 3].astype(bool); area = pm['dx_m'] ** 2
        if not fp.any():
            raise ValueError('no floodplain cells in raster')
        depth = peak[:, :, 1].astype(float); depth_error = roundoff(peak[:, :, 1])
        wet = fp & (depth > WET)
        wet_certain = fp & (depth - depth_error > WET)
        wet_possible = fp & (depth + depth_error > WET)
        interface = wet_interface(peak, pm['dx_m'])
        mean = float(depth[fp].mean()); mean_error = float(depth_error[fp].mean())
        fraction = interface['fraction']; count = interface['interface_faces']
        alpha = mean / fraction if fraction else None
        lower_fraction = interface['definitely_wet_faces'] / count if count else 0
        upper_fraction = interface['possibly_wet_faces'] / count if count else 0
        bounds = dict(mean_water=(max(0., mean - mean_error), mean + mean_error),
                      interface_fraction=(lower_fraction, upper_fraction),
                      alpha=(max(0., mean - mean_error) / upper_fraction if upper_fraction else None,
                             (mean + mean_error) / lower_fraction if lower_fraction else None))
        consistency = {}
        for key, (lo, hi) in bounds.items():
            value = finite(summary[flood].get(key)); tolerance = 1e-11 * max(1., abs(value or 0.))
            if lo is not None and hi is not None:
                consistency[key] = value is not None and lo - tolerance <= value <= hi + tolerance
            elif key == 'alpha' and upper_fraction == 0:
                consistency[key] = value is None
            else:
                consistency[key] = None
        deposit = end[:, :, 2].astype(float); deposit_error = roundoff(end[:, :, 2])
        volume = float(deposit[fp].sum() * area)
        historical = np.zeros(fp.shape, dtype=bool); past = []
        for n in sorted(n for n in summary if n < flood):
            path = folder / ('fields_%04d.bin' % n)
            if path.exists():
                previous, metadata = field(path, n, p['duration'], 1., inputs)
                if previous.shape != peak.shape or metadata['dx_m'] != pm['dx_m']:
                    raise ValueError('earlier saved raster has different geometry')
                historical |= previous[:, :, 3].astype(bool); past.append(n)
        record.update(state='computed canonical snapshot' if not mismatches else 'computed noncanonical diagnostic',
                      metadata=pm, floodplain_area_m2=int(fp.sum()) * area,
                      inundated_area_m2=int(wet.sum()) * area, inundated_fraction=float(wet.sum() / fp.sum()),
                      inundated_area_bounds_m2=[int(wet_certain.sum()) * area, int(wet_possible.sum()) * area],
                      ambiguous_wet_area_cells=int(wet_possible.sum() - wet_certain.sum()),
                      floodplain_water_volume_m3=float(depth[fp].sum() * area), mean_water_depth_m=mean,
                      interface=interface, reconstructed_alpha_m=alpha, rounding_bounds=bounds,
                      summary_consistency=consistency,
                      summary_diagnostics={key: finite(summary[flood].get(key)) for key in bounds},
                      event_deposition_bulk_volume_m3=volume,
                      deposition_on_day12_wet_cells_bulk_volume_m3=float(deposit[wet].sum() * area),
                      deposition_on_day12_wet_cells_bulk_volume_bounds_m3=[
                          float(np.maximum(0., deposit - deposit_error)[wet_certain].sum() * area),
                          float((deposit + deposit_error)[wet_possible].sum() * area)],
                      earlier_saved_channel_floods=past,
                      previously_saved_channel_area_now_floodplain_m2=int((historical & fp).sum()) * area,
                      deposition_in_previously_saved_channels_bulk_volume_m3=float(deposit[historical & fp].sum() * area))
        if any(value is False for value in consistency.values()):
            record['state'] = 'diagnostic mismatch'
            record['notes'].append('Raster-derived diagnostics disagree with summary beyond float32 and CSV rounding bounds.')
        record['notes'].extend([
            'Wet patches use nominal float32 wetness and shared-vertex face connectivity; threshold rounding can change their topology. They are not measurements of water flux or breach discharge.',
            'Deposit volumes are bulk bed volumes including pore space, not solid-grain volumes.',
            'Earlier saved channel masks form a sparse occupancy history; they do not identify all abandoned channels or prove cutoff-channel infilling.',
            'Metrics alone do not establish agreement with a published panel.'])
    except FileNotFoundError as error:
        record['notes'].append(str(error))
    except (ValueError, KeyError, OSError, struct.error) as error:
        record['state'] = 'invalid inputs'; record['notes'].append(str(error))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', default='data')
    parser.add_argument('--output', default='figures/inundation_metrics.json')
    parser.add_argument('--sample', action='append', help='additional run:flood diagnostic; no manuscript panel label')
    parser.add_argument('--strict', action='store_true', help='exit 2 while requested canonical Figure 1 snapshots are missing or inconsistent')
    args = parser.parse_args()
    data = (ROOT / args.data_root).resolve(); output = (ROOT / args.output).resolve()
    if ROOT not in data.parents or ROOT not in output.parents or not str(ROOT).startswith(tuple('/data/data%d/' % n for n in range(8))):
        parser.error('data and outputs must remain inside this /data project')
    inputs = {}; read(Path(__file__).resolve(), inputs)
    configs = {int(r['run']): r for r in csv.DictReader(io.StringIO(read(ROOT / 'config/runs.csv', inputs).decode()))}
    physics = {line.split()[0].replace('-', '_'): float(line.split()[1])
               for line in read(ROOT / 'config/physics.txt', inputs).decode().splitlines() if line.strip()}
    physics.pop('floods', None)  # Requested duration of a history does not change an earlier completed flood.
    samples = list(SAMPLES)
    for value in args.sample or []:
        run, flood = map(int, value.split(':'))
        if run not in configs or flood < 1:
            parser.error('invalid additional run:flood sample')
        samples.append((None, run, flood))
    records = [measure(data / ('run%02d' % run), run, flood, panel, configs[run], physics, inputs)
               for panel, run, flood in samples]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(utc=datetime.datetime.utcnow().isoformat() + 'Z', command=sys.argv,
                                      scope='independent raster diagnostics; no automatic scientific panel assessment',
                                      wet_depth_threshold_m=WET, input_sha256=inputs, samples=records),
                                 indent=2, allow_nan=False) + '\n')
    print('Measured %d of %d requested snapshots; see %s' %
          (sum(r['state'].startswith('computed') for r in records), len(records), output))
    ready = all(r['state'] == 'computed canonical snapshot' for r in records if r['panel'])
    return 2 if args.strict and not ready else 0


if __name__ == '__main__':
    raise SystemExit(main())
