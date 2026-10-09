#!/usr/bin/env python3
"""Measure independent Figure 1 centerlines; preserve missing-data/timing limits."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shlex
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
PANELS = {"1A": (11, 61), "1B": (11, 251), "1C": (11, 501),
          "1D": (11, 562), "1E": (17, 562), "1F": (3, 562)}
sys.dont_write_bytecode = True


def label(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read(path, hashes):
    data = path.read_bytes()
    hashes[label(path)] = hashlib.sha256(data).hexdigest()
    return data


def table(data):
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    if any(None in row or None in row.values() for row in rows):
        raise ValueError("malformed CSV row")
    return rows


def finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite value")
    return number


def integer(value):
    number = finite(value)
    if number < 0 or number != int(number):
        raise ValueError("expected nonnegative integer")
    return int(number)


def geometry(points, valley_length):
    if len(points) < 3:
        raise ValueError("fewer than three centerline points")
    segments = [math.hypot(b[0] - a[0], b[1] - a[1])
                for a, b in zip(points, points[1:])]
    if min(segments) <= 0:
        raise ValueError("duplicate adjacent centerline points")
    arc = math.fsum(segments)
    chord = math.hypot(points[-1][0]-points[0][0], points[-1][1]-points[0][1])
    if chord <= 0:
        raise ValueError("coincident endpoints")
    mean_y = math.fsum(ds * (a[1] + b[1]) / 2
                       for ds, a, b in zip(segments, points, points[1:])) / arc
    # Exact integral of squared displacement along each straight segment.
    variance = math.fsum(ds * ((a[1] - mean_y)**2 + (a[1] - mean_y) *
                        (b[1] - mean_y) + (b[1] - mean_y)**2) / 3
                        for ds, a, b in zip(segments, points, points[1:])) / arc
    curvature, weights = [], []
    for i in range(1, len(points) - 1):
        a, b, c = points[i-1:i+2]
        d = math.hypot(c[0]-a[0], c[1]-a[1])
        if d <= 0:
            raise ValueError("backtracking triple has undefined curvature")
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        dot = (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1])
        if cross == 0 and dot < 0:
            raise ValueError("collinear reversal has undefined curvature")
        curvature.append(2 * cross / (segments[i-1] * segments[i] * d))
        weights.append((segments[i-1] + segments[i]) / 2)
    support = math.fsum(weights)
    rms = math.sqrt(math.fsum(w*k*k for w, k in zip(weights, curvature)) / support)
    ys = [p[1] for p in points]
    return dict(nodes=len(points), arc_length_m=arc, endpoint_distance_m=chord,
                valley_sinuosity=arc / valley_length if valley_length else None,
                chord_sinuosity=arc / chord, y_min_m=min(ys), y_max_m=max(ys),
                lateral_extent_m=max(ys)-min(ys), length_mean_y_m=mean_y,
                lateral_rms_m=math.sqrt(variance), segment_min_m=min(segments),
                segment_max_m=max(segments), curvature_support_m=support,
                curvature_rms_per_m=rms,
                curvature_mean_abs_per_m=math.fsum(w*abs(k) for w, k in zip(weights, curvature))/support,
                curvature_max_abs_per_m=max(map(abs, curvature)),
                inverse_rms_curvature_m=1/rms if rms else None)


def cutoff_intervals(records):
    """Summary n precedes remap n: C[b]-C[a] counts remaps a through b-1."""
    ordered = sorted(records)
    intervals = []
    for a, b in zip(ordered, ordered[1:]):
        delta = records[b]["cutoffs"] - records[a]["cutoffs"]
        if delta < 0:
            raise ValueError("cumulative cutoff count decreases")
        if delta:
            intervals.append(dict(after_flood_first=a, after_flood_last=b-1,
                                  cutoff_count=delta, timing="exact remap" if b == a+1 else "interval censored"))
    first, last = (ordered[0], ordered[-1]) if ordered else (None, None)
    prior = records[first]["cutoffs"] if first else None
    if first == 1 and prior != 0:
        raise ValueError("first flood has a nonzero pre-remap cutoff count")
    return dict(status="available" if ordered else "unavailable", events=intervals,
                first_summary_flood=first, last_summary_flood=last,
                cutoffs_before_first_summary=prior,
                prior_events_left_censored=bool(prior),
                last_observed_remap_flood=last-1 if last else None,
                right_censor_note="The remap after the last summary flood is unobserved; zero listed events does not establish a cutoff-free final remap.")


def load_run(number, config, data_root, hashes, physics):
    folder = data_root / ("run%02d" % number)
    parameters, records, notes, errors = {}, {}, [], []
    path = folder / "parameters.txt"
    if path.exists():
        for line in read(path, hashes).decode().splitlines():
            pair = line.split(None, 1)
            if len(pair) == 2:
                parameters[pair[0]] = pair[1]  # Resume appends the same configuration.
    expected = dict(run=number, A=float(config["A_m_per_flood"]), C=float(config["C"]),
                    E=float(config["E"]), fine=int(config["load"] == "fine"), dx=250,
                    length=72000, width=48000, duration=1728000, channel_width=500,
                    slope=.0001, rho_s=2650, initial_depth=8, qmin=2500, qmax=15000, migration=1)
    for key, value in physics.items():
        if key != "floods":
            expected.setdefault(key, value)
    for key, value in expected.items():
        try:
            if not math.isclose(finite(parameters[key]), value, rel_tol=1e-10, abs_tol=1e-12):
                raise ValueError("different value")
        except (KeyError, ValueError):
            notes.append("{}={} (required {})".format(key, parameters.get(key, "unrecorded"), value))
    path = folder / "summary.csv"
    if path.exists():
        try:
            for row in table(read(path, hashes)):
                flood = integer(row["flood"])
                if flood < 1 or flood in records:
                    raise ValueError("duplicate/invalid flood index")
                records[flood] = dict(flood=flood, cutoffs=integer(row["cutoffs"]),
                                      sinuosity=finite(row["sinuosity"]))
        except (ValueError, KeyError) as error:
            errors.append("invalid summary: " + str(error))
    else:
        errors.append("summary.csv missing")
    try:
        timing = cutoff_intervals(records) if not errors else dict(status="unavailable", events=[])
    except ValueError as error:
        errors.append(str(error))
        timing = dict(status="unavailable", events=[])
    return dict(parameters=parameters, configuration_verified=not notes,
                configuration_notes=notes, summary_errors=errors, records=records,
                missing_floods_1_to_580=[f for f in range(1, 581) if f not in records],
                complete_1_to_580=not errors and all(f in records for f in range(1, 581)),
                cutoff_timing=timing)


def snapshot(number, flood, run, data_root, hashes):
    folder = data_root / ("run%02d" % number)
    channel = folder / ("channel_%04d.csv" % flood)
    fields = folder / ("fields_%04d.bin" % flood)
    result = dict(run=number, flood=flood, panels=[p for p, pair in PANELS.items() if pair == (number, flood)],
                  channel_file=label(channel), fields_file=label(fields), geometry=None, notes=[])
    points = []
    try:
        points = [(finite(r["x"]), finite(r["y"])) for r in table(read(channel, hashes))]
        length = float(run["parameters"].get("length", "nan"))
        result["geometry"] = geometry(points, length if math.isfinite(length) and length > 0 else None)
    except (OSError, ValueError, KeyError) as error:
        result["notes"].append("centerline unavailable/invalid: " + str(error))
    try:
        data = read(fields, hashes)
        nx, ny, nchan, saved_flood, dx, clock, slope = struct.unpack_from("=4i3d", data)
        result["clock_seconds"] = clock if math.isfinite(clock) else None
        if min(nx, ny) < 1 or nchan != len(points) or saved_flood != flood or len(data) != 40 + 16*nx*ny:
            raise ValueError("invalid dimensions, node count, flood number, or byte count")
        params = run["parameters"]
        duration, length, width, spacing = (finite(params[k]) for k in ("duration", "length", "width", "dx"))
        if not all(v > 0 for v in (duration, length, width, spacing)) or not math.isfinite(slope):
            raise ValueError("invalid recorded grid/flood parameters")
        if not (math.isclose(dx, spacing, rel_tol=1e-10) and math.isclose(nx*dx, length, rel_tol=1e-10)
                and math.isclose(ny*dx, width, rel_tol=1e-10)):
            raise ValueError("binary grid differs from recorded domain")
        if not math.isclose(clock, flood*duration, rel_tol=1e-9, abs_tol=1e-4):
            raise ValueError("clock does not identify the completed flood")
    except (OSError, ValueError, KeyError, struct.error) as error:
        result["notes"].append("snapshot header unavailable/invalid: " + str(error))
    record = run["records"].get(flood)
    if not record or run["summary_errors"]:
        result["notes"].append("valid completed-flood summary unavailable")
    elif result["geometry"]:
        result["summary_sinuosity"] = record["sinuosity"]
        value = result["geometry"]["valley_sinuosity"]
        result["sinuosity_difference_from_summary"] = value-record["sinuosity"] if value else None
        if value is not None and not math.isclose(value, record["sinuosity"], rel_tol=1e-8, abs_tol=1e-10):
            result["notes"].append("centerline and summary sinuosity disagree beyond CSV precision tolerance")
    result["completed_snapshot"] = not result["notes"]
    result["canonical_configuration"] = run["configuration_verified"]
    result["requested_data_ready"] = result["completed_snapshot"] and run["configuration_verified"]
    result["data_status"] = ("complete canonical snapshot" if result["requested_data_ready"] else
                             "complete noncanonical diagnostic snapshot" if result["completed_snapshot"] else
                             "partial diagnostic snapshot" if result["geometry"] else "missing/invalid centerline")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, default=ROOT / "figures")
    parser.add_argument("--strict", action="store_true", help="exit 2 while any requested canonical Figure 1 snapshot is missing")
    args = parser.parse_args()
    data_root, output = args.data_root.resolve(), args.output.resolve()
    try:
        output.relative_to(ROOT)
    except ValueError:
        parser.error("output must be inside this project")
    hashes = {}
    read(Path(__file__).resolve(), hashes)
    configs = {int(row["run"]): row for row in table(read(ROOT / "config/runs.csv", hashes))}
    physics = {}
    for line in read(ROOT / "config/physics.txt", hashes).decode().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, value = line.split()
            physics[key.replace("-", "_")] = finite(value)
    runs, snapshots = {}, []
    for number in sorted({pair[0] for pair in PANELS.values()}):
        run = load_run(number, configs[number], data_root, hashes, physics)
        floods = {f for r, f in PANELS.values() if r == number}
        for path in (data_root / ("run%02d" % number)).glob("channel_*.csv"):
            match = re.fullmatch(r"channel_(\d{4,})\.csv", path.name)
            if match and int(match[1]) > 0:
                floods.add(int(match[1]))
        snapshots.extend(snapshot(number, flood, run, data_root, hashes) for flood in sorted(floods))
        run["summary_series"] = [run["records"][f] for f in sorted(run["records"])]
        del run["records"]
        runs["%02d" % number] = run
    panel_ready = {panel: next(s["requested_data_ready"] for s in snapshots if panel in s["panels"]) for panel in PANELS}
    ready = all(panel_ready.values())
    result = dict(format_version=1, command=" ".join(map(shlex.quote, sys.argv)), data_root=label(data_root),
                  reference="Nicholas et al. (2018), Results and Figure 1 caption, doi:10.1130/G40104.1",
                  scope="Independent geometry/timing diagnostics; the written manuscript supplies no numerical planform target or cutoff schedule.",
                  configuration_reference="Documented run/domain/flood parameters plus recorded assumptions matching config/physics.txt; not proof of physical adequacy.",
                  snapshot_phase="End of flood n, before migration/cutoff/aggradation after flood n; peak_ snapshots are excluded.",
                  raster_check="Header, byte count, grid, clock and centerline row count only; raster field values are not analyzed here.",
                  assessment_status="canonical panel data available; scientific agreement unevaluated" if ready else "pending requested canonical data",
                  required_data_complete=ready, panel_data_ready=panel_ready,
                  histories_complete_1_to_580=all(run["complete_1_to_580"] for run in runs.values()),
                  runs=runs, snapshots=snapshots, input_sha256=hashes)
    output.mkdir(parents=True, exist_ok=True)
    (output / "planform_metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    metric_names = list(next((s["geometry"] for s in snapshots if s["geometry"]), geometry([(0., 0.), (1., 0.), (2., 0.)], 2.)))
    columns = ["run", "flood", "panels", "data_status", "completed_snapshot", "canonical_configuration"] + metric_names
    with (output / "planform_metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for saved in snapshots:
            row = {key: saved[key] for key in columns[:6]}
            row["panels"] = ";".join(saved["panels"])
            row.update(saved["geometry"] or {})
            writer.writerow(row)
    print(json.dumps(dict(assessment_status=result["assessment_status"], measured_snapshots=sum(s["geometry"] is not None for s in snapshots),
                          requested_panels_ready=sum(panel_ready.values()), output=label(output))))
    return 2 if args.strict and not ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
