#!/usr/bin/env python3
"""Measure diagnostic-definition sensitivity in archived first-flood rasters."""
import sys
sys.dont_write_bytecode = True
import argparse
import csv
import io
import json
import math
from pathlib import Path
import struct
import tarfile

import numpy as np
from inundation_metrics import roundoff
from plot_first_flood import load, require, sha, relative, ROOT, ARCHIVE, CASES

SCOPE = 'archived first-flood diagnostic sensitivity only; no manuscript-panel assessment'
CENTRAL = (60, 80, 100)
DISTAL = (5, 10, 20)
THRESHOLDS = (.0001, .001, .01)
U = np.finfo(float).eps / 2


def gamma(operations):
    return operations * U / (1 - operations * U)


def ratio_bounds(numerator, denominator):
    """Conservative interval division, including signed relief and shared errors."""
    if denominator[0] <= 0:
        return None
    values = [n / d for n in numerator for d in denominator]
    return [min(values), max(values)]


def quotient_allowance(numerator, denominator, numerator_error, denominator_error):
    """Additional interval width from float64 sums and the final division."""
    nominal = ratio_bounds(numerator, denominator)
    expanded = ratio_bounds([numerator[0] - numerator_error, numerator[1] + numerator_error],
                            [denominator[0] - denominator_error, denominator[1] + denominator_error])
    if nominal is None or expanded is None:
        return None
    return max(abs(a - b) for a, b in zip(nominal, expanded)) + 4 * U * max(map(abs, expanded))


def interface_samples(values):
    """One sample per internal XOR-mask face; repeated bank cells stay repeated."""
    z, h = values[:, :, 0].astype(float), values[:, :, 1].astype(float)
    dz, dh = roundoff(values[:, :, 0]), roundoff(values[:, :, 1])
    mask = values[:, :, 3].astype(bool)
    column = np.indices(mask.shape)[1]
    result = {key: [] for key in ('depth', 'depth_error', 'z_magnitude', 'fp_column', 'fp_h', 'fp_h_error',
                                 'stage_above_bank', 'stage_error')}
    for axis in (0, 1):
        left = (slice(None, -1), slice(None)) if axis == 0 else (slice(None), slice(None, -1))
        right = (slice(1, None), slice(None)) if axis == 0 else (slice(None), slice(1, None))
        boundary = mask[left] != mask[right]
        channel_left = mask[left]
        depth = np.where(channel_left, z[right] - z[left], z[left] - z[right])
        channel_h = np.where(channel_left, h[left], h[right])
        stage_error = np.where(channel_left, dh[left], dh[right]) + dz[left] + dz[right]
        stage_error += 4 * gamma(3) * (abs(channel_h) + abs(z[left]) + abs(z[right]) + stage_error)
        sample = dict(depth=depth, depth_error=dz[left] + dz[right], z_magnitude=abs(z[left]) + abs(z[right]),
                      fp_column=np.where(channel_left, column[right], column[left]),
                      fp_h=np.where(channel_left, h[right], h[left]),
                      fp_h_error=np.where(channel_left, dh[right], dh[left]),
                      stage_above_bank=channel_h - depth, stage_error=stage_error)
        for key in result:
            result[key].extend(sample[key][boundary].tolist())
    return {key: np.asarray(value) for key, value in result.items()}


def ridge_definition(values, plane, central, distal):
    """Crest of row means minus equal-weight distal row means; fixed channel mask."""
    ny, nx = values.shape[:2]
    trim, band = nx * (100 - central) // 200, ny * distal // 100
    require(0 < central <= 100 and 0 < distal <= 50 and band > 0, 'invalid averaging window')
    selected = ~values[:, trim:nx - trim, 3].astype(bool)
    counts = selected.sum(axis=1)
    valid = counts > 0
    require(valid.any(), 'no floodplain rows in central reach')
    relief = values[:, trim:nx - trim, 0].astype(float) - plane[trim:nx - trim]
    errors = roundoff(values[:, trim:nx - trim, 0])
    scale = abs(values[:, trim:nx - trim, 0]) + abs(plane[trim:nx - trim]) + errors
    arithmetic = 2 * gamma(counts + 3) * np.divide((scale * selected).sum(axis=1), counts,
                                                 out=np.zeros(ny), where=valid)
    means = np.divide((relief * selected).sum(axis=1), counts, out=np.zeros(ny), where=valid)
    errors = np.divide((errors * selected).sum(axis=1), counts, out=np.zeros(ny), where=valid)
    outside = valid & ((np.arange(ny) < band) | (np.arange(ny) >= ny - band))
    require(outside.any(), 'no valid distal rows')
    crest = float(means[valid].max())
    crest_bounds = [float((means - errors)[valid].max()), float((means + errors)[valid].max())]
    distal_mean, distal_error = float(means[outside].mean()), float(errors[outside].mean())
    arithmetic = float(arithmetic[valid].max() + arithmetic[outside].mean())
    arithmetic += 2 * gamma(int(outside.sum()) + 2) * float((abs(means[outside]) + errors[outside]).mean())
    arithmetic += 4 * U * (abs(crest) + abs(distal_mean) + max(errors[valid]) + distal_error)
    return dict(central_percent=central, distal_percent_each_side=distal,
                trim_columns_each_end=trim, selected_columns=nx - 2 * trim,
                distal_rows_each_side=band, valid_transverse_rows=int(valid.sum()),
                valid_distal_rows=int(outside.sum()), crest_relief_m=crest,
                distal_relief_m=distal_mean, ridge_height_m=crest - distal_mean,
                ridge_float64_arithmetic_allowance_m=arithmetic,
                ridge_rounding_bounds_m=[crest_bounds[0] - distal_mean - distal_error,
                                         crest_bounds[1] - distal_mean + distal_error])


def beta_variants(values, p):
    ny, nx = values.shape[:2]
    plane = p['slope'] * (p['length'] - (np.arange(nx) + .5) * p['dx'])
    faces = interface_samples(values)
    require(len(faces['depth']) > 0, 'no bank interface')
    depth, error = float(faces['depth'].mean()), float(faces['depth_error'].mean())
    require(depth > error, 'channel-depth interval includes zero')
    depth_bounds = [depth - error, depth + error]
    depth_scale = faces['z_magnitude'] + 2 * abs(plane[faces['fp_column'].astype(int)]) + faces['depth_error']
    depth_arithmetic = 4 * gamma(len(depth_scale) + 4) * float(depth_scale.mean())
    rows = []
    for central in CENTRAL:
        for distal in DISTAL:
            row = ridge_definition(values, plane, central, distal)
            row.update(actual_central_length_m=row['selected_columns'] * p['dx'],
                       actual_distal_band_width_m=row['distal_rows_each_side'] * p['dx'],
                       beta=row['ridge_height_m'] / depth,
                       beta_rounding_bounds=ratio_bounds(row['ridge_rounding_bounds_m'], depth_bounds),
                       beta_float64_arithmetic_allowance=quotient_allowance(
                           row['ridge_rounding_bounds_m'], depth_bounds,
                           row['ridge_float64_arithmetic_allowance_m'], depth_arithmetic))
            rows.append(row)
    canonical = next(r for r in rows if r['central_percent'] == 80 and r['distal_percent_each_side'] == 10)
    for row in rows:
        row['beta_change_percent_of_reconstructed_default'] = (
            100 * (row['beta'] / canonical['beta'] - 1) if canonical['beta'] else None)
    denominator = []
    for central in CENTRAL:
        trim = nx * (100 - central) // 200
        selected = (faces['fp_column'] >= trim) & (faces['fp_column'] < nx - trim)
        require(selected.any(), 'no bank faces in selected reach')
        d, e = float(faces['depth'][selected].mean()), float(faces['depth_error'][selected].mean())
        a = 4 * gamma(int(selected.sum()) + 4) * float(depth_scale[selected].mean())
        denominator.append(dict(central_percent=central, interface_faces=int(selected.sum()),
                                bankfull_depth_m=d, depth_rounding_bounds_m=[d - e, d + e],
                                depth_float64_arithmetic_allowance_m=a,
                                beta_with_default_ridge=canonical['ridge_height_m'] / d if d > 0 else None,
                                beta_rounding_bounds=ratio_bounds(canonical['ridge_rounding_bounds_m'], [d - e, d + e]),
                                beta_float64_arithmetic_allowance=quotient_allowance(
                                    canonical['ridge_rounding_bounds_m'], [d - e, d + e],
                                    canonical['ridge_float64_arithmetic_allowance_m'], a),
                                beta_change_percent_of_full_interface_depth=100 * (depth / d - 1) if d > 0 else None))
    return rows, denominator, depth, depth_bounds, depth_arithmetic, len(faces['depth'])


def alpha_variants(values, dx):
    """Change only the diagnostic wetness threshold; retain dry cells in the mean."""
    fp = ~values[:, :, 3].astype(bool)
    require(fp.any(), 'no floodplain cells')
    h, dh = values[:, :, 1].astype(float), roundoff(values[:, :, 1])
    mean, error = float(h[fp].mean()), float(dh[fp].mean())
    mean_arithmetic = 2 * gamma(int(fp.sum()) + 2) * float((abs(h[fp]) + dh[fp]).mean())
    faces = interface_samples(values)
    count = len(faces['depth'])
    require(count > 0, 'no bank interface')
    rows = []
    for threshold in THRESHOLDS:
        wet = int(((faces['fp_h'] > threshold) & (faces['stage_above_bank'] > threshold)).sum())
        certain = int(((faces['fp_h'] - faces['fp_h_error'] > threshold) &
                       (faces['stage_above_bank'] - faces['stage_error'] > threshold)).sum())
        possible = int(((faces['fp_h'] + faces['fp_h_error'] > threshold) &
                        (faces['stage_above_bank'] + faces['stage_error'] > threshold)).sum())
        wet_area = fp & (h > threshold)
        certain_area, possible_area = fp & (h - dh > threshold), fp & (h + dh > threshold)
        rows.append(dict(threshold_m=threshold, mean_water_m=mean,
                         mean_water_rounding_bounds_m=[mean - error, mean + error],
                         mean_water_float64_arithmetic_allowance_m=mean_arithmetic,
                         interface=dict(interface_faces=count, wet_faces=wet, definitely_wet_faces=certain,
                                        possibly_wet_faces=possible, ambiguous_faces=possible - certain,
                                        fraction=wet / count, fraction_rounding_bounds=[certain / count, possible / count]),
                         alpha_m=mean * count / wet if wet else None,
                         alpha_rounding_bounds_m=ratio_bounds([mean - error, mean + error], [certain / count, possible / count]),
                         alpha_float64_arithmetic_allowance_m=(mean_arithmetic * count / certain +
                                                              4 * U * mean * count / certain) if certain else None,
                         wet_area_m2=int(wet_area.sum()) * dx ** 2,
                         wet_area_rounding_bounds_m2=[int(certain_area.sum()) * dx ** 2, int(possible_area.sum()) * dx ** 2],
                         ambiguous_wet_area_cells=int(possible_area.sum() - certain_area.sum())))
    return rows


def summary_check(value, bounds, recorded, arithmetic):
    # The source writes 12 significant digits, not 12 decimal places.
    decimal = .5 * 10. ** (math.floor(math.log10(abs(recorded))) - 11) if recorded else 0.
    margin = arithmetic + 2 * U * abs(recorded)
    valid = bounds is not None and bounds[0] - decimal - margin <= recorded <= bounds[1] + decimal + margin
    require(valid, 'default reconstruction differs from the double summary beyond rounding bounds')
    return dict(recorded_summary=recorded, reconstructed=value,
                reconstructed_minus_summary=value - recorded, rounding_bounds=bounds,
                summary_rounding_half_width=decimal, float64_arithmetic_allowance=margin,
                summary_within_rounding_bounds=bool(valid))


def analyze(cases, members):
    result = {}
    for name in CASES:
        case = cases[name]
        p, end = case['parameters'], case['values']
        prefix = 'validation/runs/' + name + '/'
        summary = list(csv.DictReader(io.StringIO(members[prefix + 'summary.csv'].decode())))[0]
        blob = members[prefix + 'peak_fields_0001.bin']
        nx, ny, nodes, flood, dx, clock, slope = struct.unpack('=4i3d', blob[:40])
        require((nx, ny, nodes, flood, dx, clock, slope) ==
                (end.shape[1], end.shape[0], case['snapshot']['channel_nodes'], 1, p['dx'], .6 * p['duration'], p['slope']),
                'invalid day-12 snapshot metadata: ' + name)
        require(len(blob) == 40 + 16 * nx * ny, 'invalid day-12 snapshot length: ' + name)
        peak = np.frombuffer(blob, dtype='=f4', offset=40).reshape(ny, nx, 4).astype(float)
        require(np.isfinite(peak).all() and (peak[:, :, 1:3] >= 0).all(), 'invalid day-12 fields: ' + name)
        require(np.array_equal(peak[:, :, 3], end[:, :, 3]), 'channel mask changed during flood: ' + name)
        beta, denominator, depth, depth_bounds, depth_arithmetic, count = beta_variants(end, p)
        alpha = alpha_variants(peak, dx)
        b = next(r for r in beta if r['central_percent'] == 80 and r['distal_percent_each_side'] == 10)
        a = next(r for r in alpha if r['threshold_m'] == .001)
        checks = {key: summary_check(value, bounds, float(summary[key]), arithmetic)
                  for key, value, bounds, arithmetic in (
                      ('ridge_height', b['ridge_height_m'], b['ridge_rounding_bounds_m'], b['ridge_float64_arithmetic_allowance_m']),
                      ('channel_depth', depth, depth_bounds, depth_arithmetic),
                      ('beta', b['beta'], b['beta_rounding_bounds'], b['beta_float64_arithmetic_allowance']),
                      ('alpha', a['alpha_m'], a['alpha_rounding_bounds_m'], a['alpha_float64_arithmetic_allowance_m']))}
        result[name] = dict(dx_m=dx, full_interface_faces=count, full_interface_channel_depth_m=depth,
                            summary_reconstruction=checks, beta_definition_variants=beta,
                            denominator_only_variants=denominator, alpha_threshold_variants=alpha,
                            binary_sha256=case['process']['binary_sha256'], flood=1,
                            beta_elapsed_seconds=p['duration'], alpha_elapsed_seconds=.6 * p['duration'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('figures/first_flood_diagnostic_sensitivity.json'))
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT)
    cases, reference, inputs, member_hashes = load()
    # load() verifies the full existing archive and completed-case identities.
    # Read only the four additional members needed here, checking their same hashes.
    archive = ARCHIVE / 'resolution-inputs.tar.xz'
    blob = archive.read_bytes()
    require(sha(blob) == inputs[relative(archive)], 'archive changed during analysis')
    members = {}
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:*') as stream:
        for name in CASES:
            for filename in ('peak_fields_0001.bin', 'summary.csv'):
                key = 'validation/runs/' + name + '/' + filename
                members[key] = stream.extractfile(key).read()
                require(sha(members[key]) == member_hashes[key], 'member changed: ' + key)
    result = dict(format=1, status='verified', scope=SCOPE,
                  processor_sha256=sha(Path(__file__).read_bytes()),
                  dependency_sha256={name: sha((ROOT / name).read_bytes()) for name in
                                     ('scripts/plot_first_flood.py', 'scripts/inundation_metrics.py', 'src/model.hpp')},
                  command=[sys.executable, 'scripts/diagnostic_sensitivity.py'] + sys.argv[1:],
                  versions=dict(python=sys.version, numpy=np.__version__),
                  input_sha256=inputs, member_sha256=member_hashes,
                  method=dict(default_central_percent=80, default_distal_percent_each_side=10,
                              central_percent=list(CENTRAL), distal_percent_each_side=list(DISTAL),
                              alpha_thresholds_m=list(THRESHOLDS),
                              integer_windows='trim=floor(nx*(100-central)/200); distal rows=floor(ny*percent/100) per side',
                              numerator='crest of equal-column floodplain row means minus equal-weight valid distal row means; fixed mask',
                              numerator_denominator='full-domain mean bank-face bed-to-bank depth held fixed',
                              denominator_only='select bank faces by adjacent floodplain cell column in the central reach; default ridge held fixed',
                              alpha_mean='full-domain mean including dry floodplain cells; fixed channel mask',
                              rounding='float32 half-ULP interval propagation; correlated errors may widen bounds; no probabilistic interpretation',
                              summary_allowance='12-significant-digit decimal rounding plus float64 sequential-sum gamma_n bounds and final-arithmetic allowances; gamma_n=n*2^-53/(1-n*2^-53)',
                              interpretation='diagnostic-definition contrasts on two saved first floods; not uncertainty intervals or alternatives fitted to the publication'),
                  cases=analyze(cases, members))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temporary.replace(output)
    print(relative(output))


if __name__ == '__main__':
    main()
