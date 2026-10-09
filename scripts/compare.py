#!/usr/bin/env python3
"""Compare independent output with written/visual manuscript statements.

No published source-data or DR2 result columns are read. Incomplete runs,
changed plot inputs, and altered configurations remain explicitly pending.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
for key, folder in (("TMPDIR", "compare-tmp"), ("XDG_CACHE_HOME", "cache"),
                    ("PYTHONPYCACHEPREFIX", "pycache")):
    path = ROOT / "tmp" / folder
    path.mkdir(parents=True, exist_ok=True)
    os.environ[key] = str(path)

REFERENCE = "Nicholas et al. (2018), main manuscript Results and captions, doi:10.1130/G40104.1"
VISUAL_RANGES = {"2A": (40., 45.), "2B": (25., 30.), "2C": (15., 17.), "2D": (30., 33.)}


def rows(path):
    if not path.exists():
        return []
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def finite(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def label(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values, quantile):
    ordered = sorted(values)
    index = quantile * (len(ordered) - 1)
    lower = int(math.floor(index))
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (index - lower) * (ordered[upper] - ordered[lower])


def directions(values, desired_sign):
    differences = [b - a for a, b in zip(values[:-1], values[1:])]
    tolerance = 1e-12 * max([1.] + [abs(v) for v in values])
    correct = sum(desired_sign * d > tolerance for d in differences)
    opposite = sum(desired_sign * d < -tolerance for d in differences)
    return dict(adjacent_differences=differences, requested_direction=correct,
                opposite_direction=opposite, ties=len(differences) - correct - opposite)


def section_morphology(y, elevation, active, dx, plane):
    """Cellwise section diagnostics; no inferred surface across channel gaps."""
    if not (len(y) == len(elevation) == len(active)) or not y or dx <= 0:
        raise ValueError("invalid section arrays or spacing")
    if not all(math.isfinite(v) for v in list(y) + list(elevation) + [dx, plane]):
        raise ValueError("nonfinite section")
    if any(a not in (0, 1) for a in active) or any(
            not math.isclose(b - a, dx, rel_tol=1e-12, abs_tol=1e-9) for a, b in zip(y[:-1], y[1:])):
        raise ValueError("section must have uniform increasing cells and a binary channel mask")
    fp = [i for i, channel in enumerate(active) if not channel]
    if not fp:
        raise ValueError("section has no floodplain cells")
    relief = [z - plane for z in elevation]
    height = max(relief[i] for i in fp)
    weight = [max(relief[i], 0.) if not active[i] else 0. for i in range(len(y))]
    total = math.fsum(weight)
    centre = math.fsum(w * x for w, x in zip(weight, y)) / total if total > 0 else None
    spread = (math.sqrt(math.fsum(w * ((x - centre) ** 2 + dx ** 2 / 12.)
                                 for w, x in zip(weight, y)) / total) if total > 0 else None)
    half = [i for i in fp if height > 0 and relief[i] >= .5 * height]
    # Maximum adjacent half-ULP of the float32 elevation snapshots, including subnormals.
    error = [max(2. ** (math.frexp(abs(z))[1] - 25), 2. ** -150) if z else 2. ** -150
             for z in elevation]
    peaks = [i for i in fp if relief[i] == height]
    flanks = {}
    for side, first, last in (("lower_y", fp[0], peaks[0]), ("upper_y", peaks[-1], fp[-1])):
        ids = [i for i in fp if first <= i <= last]
        flank = dict(endpoint_transverse_m=[y[first], y[last]], endpoint_relief_m=[relief[first], relief[last]],
                     sampled_floodplain_cells=len(ids),
                     excluded_active_channel_cells=sum(active[first:last + 1]),
                     mean_chord_departure_m=None, mean_chord_departure_over_crest=None)
        if height > 0 and len(ids) >= 3 and last > first:
            slope = (relief[last] - relief[first]) / (y[last] - y[first])
            departure = math.fsum(relief[i] - relief[first] - slope * (y[i] - y[first])
                                   for i in ids) / len(ids)
            flank.update(mean_chord_departure_m=departure,
                         mean_chord_departure_over_crest=departure / height)
        flanks[side] = flank
    return dict(crest_elevation_m=max(elevation[i] for i in fp), crest_relief_m=height,
                profile_p90_relief_m=percentile([relief[i] for i in fp], .9),
                minimum_elevation_m=min(elevation),
                active_channel_width_m=sum(active) * dx,
                minimum_active_channel_elevation_m=min((z for z, a in zip(elevation, active) if a), default=None),
                positive_relief_area_m2=dx * total,
                positive_relief_area_rounding_bounds_m2=[
                    dx * math.fsum(max(relief[i] - error[i], 0.) for i in fp),
                    dx * math.fsum(max(relief[i] + error[i], 0.) for i in fp)],
                positive_relief_resolved=any(relief[i] > error[i] for i in fp),
                positive_relief_centroid_m=centre, positive_relief_std_m=spread,
                equivalent_positive_relief_width_m=dx * total / height if height > 0 else None,
                half_crest_occupied_width_m=len(half) * dx if half else None,
                half_crest_span_width_m=y[half[-1]] - y[half[0]] + dx if half else None,
                half_crest_components=sum(j == 0 or i != half[j - 1] + 1 for j, i in enumerate(half)),
                half_crest_touches_section_edge=bool(half and (half[0] == 0 or half[-1] == len(y) - 1)),
                crest_transverse_extent_m=[y[peaks[0]], y[peaks[-1]]], flanks=flanks)


def saved_section(selected, run, panel, number, flood, inputs):
    """Verify every plotted section cell against its original saved raster."""
    p = run["parameters"]
    source = run["directory"] / ("fields_%04d.bin" % flood)
    if flood not in run["records"]:
        raise ValueError("requested section flood is absent from completed summary")
    if not source.exists() or run["plot_input_hashes"].get(label(source)) != digest(source):
        raise ValueError("section raster is absent from verified plotting inputs")
    inputs.add(source)
    blob = source.read_bytes()
    if len(blob) < 40:
        raise ValueError("truncated section raster")
    nx, ny, nodes, saved_flood, dx, clock, slope = struct.unpack_from("=4i3d", blob)
    if min(nx, ny) < 1 or nodes < 2 or len(blob) != 40 + 16 * nx * ny or saved_flood != flood:
        raise ValueError("invalid section raster dimensions, byte count or flood")
    if not all(math.isfinite(v) for v in (dx, clock, slope)) or dx <= 0 or (
            dx != float(p["dx"]) or nx * dx != float(p["length"]) or ny * dx != float(p["width"])
            or slope != float(p["slope"]) or abs(clock - flood * float(p["duration"])) > 1e-5):
        raise ValueError("section raster does not match parameter geometry or end-flood time")
    selected = sorted(selected, key=lambda row: float(row["transverse_m"]))
    if len(selected) != ny:
        raise ValueError("section must contain every transverse cell exactly once")
    column = nx // 2
    x = (column + .5) * dx
    y, elevation, active = [], [], []
    for j, row in enumerate(selected):
        z, h, deposition, mask = struct.unpack_from("=4f", blob, 40 + 16 * (j * nx + column))
        named_source = Path(row["source"])
        if not named_source.is_absolute():
            named_source = ROOT / named_source
        if (row["panel"] != panel or int(row["run"]) != number or int(row["flood"]) != flood
                or row["completed_flood"] != "1" or float(row["downstream_m"]) != x
                or float(row["transverse_m"]) != (j + .5) * dx or float(row["elevation_m"]) != z
                or float(row["active_channel"]) != mask or mask not in (0., 1.)
                or named_source.resolve() != source.resolve()):
            raise ValueError("section table differs from exact saved column, mask or source")
        if not all(math.isfinite(v) for v in (z, h, deposition)) or min(h, deposition) < 0:
            raise ValueError("invalid saved section state")
        y.append((j + .5) * dx); elevation.append(z); active.append(int(mask))
    plane = slope * (nx * dx - x)
    return dict(flood=flood, downstream_m=x, initial_plane_m=plane, source=label(source),
                source_sha256=hashlib.sha256(blob).hexdigest(),
                **section_morphology(y, elevation, active, dx, plane))


def run_readiness_notes(run, require_full_history=True):
    """Keep canonical-input checks separate from comparison-specific coverage."""
    return run["notes"] + (run["history_notes"] if require_full_history else [])


def configuration_notes(config, parameters, physics):
    expected = dict(physics, run=int(config["run"]), A=float(config["A_m_per_flood"]),
                    C=float(config["C"]), E=float(config["E"]), fine=int(config["load"] == "fine"),
                    dx=250, length=72000, width=48000, duration=1728000, channel_width=500,
                    slope=.0001, rho_s=2650, initial_depth=8, qmin=2500, qmax=15000, migration=1)
    # A stopping count does not change the physics of a completed early flood.
    expected.pop("floods", None)
    return ["{}={} (required {})".format(key, parameters.get(key, "unrecorded"), value)
            for key, value in expected.items()
            if finite(parameters.get(key)) is None or not math.isclose(
                float(parameters[key]), value, rel_tol=1e-10, abs_tol=1e-12)]


def comparison_inputs(data_root, figure_root):
    configs = rows(ROOT / "config" / "runs.csv")
    if len(configs) != 31 or {int(c["run"]) for c in configs} != set(range(1, 32)):
        raise ValueError("Expected all 31 documented configurations")
    physics_path = ROOT / "config" / "physics.txt"
    physics = {}
    for line in physics_path.read_text().splitlines():
        if line.strip():
            key, value = line.split()
            physics[key.replace("-", "_")] = float(value)
    inputs = {ROOT / "config" / "runs.csv", physics_path, Path(__file__).resolve()}
    manifest_path = figure_root / "plot_manifest.json"
    errors, manifest_files = [], {}
    if manifest_path.exists():
        inputs.add(manifest_path)
        try:
            manifest = json.loads(manifest_path.read_text())
            manifest_files = manifest["files"]
            recorded_root = Path(manifest["data_root"])
            if not recorded_root.is_absolute():
                recorded_root = ROOT / recorded_root
            if recorded_root.resolve() != data_root:
                errors.append("plot manifest data_root differs from comparison data_root")
            for name, expected in manifest_files.items():
                source = Path(name)
                if not source.is_absolute():
                    source = ROOT / source
                if not source.exists() or digest(source) != expected:
                    errors.append("changed/missing plotting input: " + name)
        except (ValueError, KeyError, TypeError) as error:
            errors.append("invalid plotting provenance: " + str(error))
    else:
        errors.append("plot_manifest.json missing; run scripts/plot.py first")
    derived = {}
    for filename in ("metrics.csv", "deposit_metrics.csv", "sections.csv", "panel_status.csv"):
        path = figure_root / filename
        derived[filename] = rows(path)
        if path.exists():
            inputs.add(path)
        else:
            errors.append(filename + " missing")
    metric_rows = {int(row["run"]): row for row in derived["metrics.csv"]}
    runs = {}
    for config in configs:
        number = int(config["run"])
        directory = data_root / ("run%02d" % number)
        parameters, records, notes, history_notes = {}, {}, [], []
        path = directory / "parameters.txt"
        if path.exists():
            inputs.add(path)
            for line in path.read_text().splitlines():
                pair = line.split(None, 1)
                if len(pair) == 2:
                    parameters[pair[0]] = pair[1]
        notes.extend(configuration_notes(config, parameters, physics))
        path = directory / "summary.csv"
        if path.exists():
            inputs.add(path)
            for row in rows(path):
                try:
                    flood = int(row["flood"])
                    if flood < 1 or flood in records:
                        raise ValueError("duplicate/invalid flood index")
                    records[flood] = {key: finite(value) for key, value in row.items()}
                except (ValueError, KeyError) as error:
                    notes.append("invalid summary row: " + str(error))
            if label(path) not in manifest_files:
                notes.append("summary is not a recorded plotting input")
        else:
            notes.append("summary.csv missing")
        absent = [f for f in range(1, 581) if f not in records]
        if absent:
            history_notes.append("{} of 580 required flood rows missing".format(len(absent)))
        metric = metric_rows.get(number, {})
        if metric.get("configuration_verified") != "1":
            notes.append("plotter has not verified canonical configuration")
        if metric.get("complete_1_to_580") != "1":
            history_notes.append("plotter has not verified the full 580-flood history")
        runs[number] = dict(config=config, parameters=parameters, records=records,
                            metric=metric, notes=notes, history_notes=history_notes, directory=directory,
                            plot_input_hashes=manifest_files)
    return configs, runs, derived, errors, inputs


def evaluate(data_root, figure_root):
    configs, runs, derived, provenance_errors, inputs = comparison_inputs(data_root, figure_root)
    results = []
    panel_state = {row["panel"]: row for row in derived["panel_status.csv"]}

    def ready(numbers, metric=None, panels=(), require_full_history=True):
        reasons = list(provenance_errors)
        for number in sorted(set(numbers)):
            run = runs[number]
            reasons.extend("run {:02d}: {}".format(number, note)
                           for note in run_readiness_notes(run, require_full_history))
            if metric:
                column, first, count, field = (("beta", 561, 20, "beta_mean_561_580") if metric == "beta"
                                               else ("alpha", 381, 200, "alpha95_381_580"))
                values = [run["records"].get(f, {}).get(column) for f in range(first, 581)]
                reported = finite(run["metric"].get(field))
                if any(value is None for value in values) or len(values) != count or reported is None:
                    reasons.append("run {:02d}: complete finite {} window unavailable".format(number, metric))
                else:
                    calculated = statistics.mean(values) if metric == "beta" else percentile(values, .95)
                    if not math.isclose(calculated, reported, rel_tol=1e-10, abs_tol=1e-12):
                        reasons.append("run {:02d}: derived {} differs from saved summary".format(number, metric))
        for panel in panels:
            if panel_state.get(panel, {}).get("data_status") != "complete requested data":
                reasons.append(panel + " does not have complete requested plotted data")
        return list(dict.fromkeys(reasons))

    def add(name, panel, numbers, target, required_metric=None, required_panels=(), require_full_history=True):
        reasons = ready(numbers, required_metric, required_panels, require_full_history)
        record = dict(comparison=name, panel=panel, runs=list(numbers), target=target,
                      status="pending" if reasons else "computed", calculation={}, assessment="",
                      caveat="", pending_reasons=reasons, reference=REFERENCE)
        results.append(record)
        return record

    def beta(number):
        return float(runs[number]["metric"]["beta_mean_561_580"])

    def alpha95(number):
        return float(runs[number]["metric"]["alpha95_381_580"])

    default = [c for c in configs if c["load"] == "default" and float(c["E"]) == 1]
    for C in sorted({float(c["C"]) for c in default}):
        group = sorted([c for c in default if float(c["C"]) == C], key=lambda c: float(c["A_m_per_flood"]))
        if len(group) < 2:
            continue
        numbers = [int(c["run"]) for c in group]
        r = add("beta_increases_with_A_C{:g}".format(C), "3A", numbers,
                "Higher channel-bed aggradation increases beta at fixed C, E=1, default load.", "beta")
        if r["status"] == "computed":
            values = [beta(n) for n in numbers]
            contrasts = directions(values, 1)
            r["calculation"] = dict(A_m_per_flood=[float(c["A_m_per_flood"]) for c in group], beta=values, **contrasts)
            r["assessment"] = "C={:g}: beta increases across {}/{} adjacent A contrasts, decreases across {}, and ties across {}.".format(
                C, contrasts["requested_direction"], len(numbers) - 1, contrasts["opposite_direction"], contrasts["ties"])

    for A in sorted({float(c["A_m_per_flood"]) for c in default}):
        group = sorted([c for c in default if float(c["A_m_per_flood"]) == A], key=lambda c: float(c["C"]))
        if len(group) < 2:
            continue
        numbers = [int(c["run"]) for c in group]
        r = add("beta_decreases_with_C_A{:g}".format(A), "3A", numbers,
                "At matched A, higher suspended sediment load generally lowers beta.", "beta")
        if r["status"] == "computed":
            values = [beta(n) for n in numbers]
            contrasts = directions(values, -1)
            r["calculation"] = dict(C=[float(c["C"]) for c in group], beta=values, **contrasts)
            r["assessment"] = "A={:g} m/flood: beta decreases across {}/{} adjacent C contrasts and increases across {}.".format(
                A, contrasts["requested_direction"], len(numbers) - 1, contrasts["opposite_direction"])
            r["caveat"] = "The paper states a general load tendency; every reversal is retained rather than excluded."

    for E, pairs, reference in [(.5, [(27, 3), (29, 6)], 15.), (1.5, [(28, 3), (30, 6)], -6.5)]:
        numbers = [n for pair in pairs for n in pair]
        r = add("erodibility_E{:g}".format(E), "3A", numbers,
                "Published prose reports approximately {:+g}% beta change for E={:g}.".format(reference, E), "beta")
        if r["status"] == "computed":
            if any(beta(base) == 0 for _, base in pairs):
                r.update(status="pending", pending_reasons=["zero default beta prevents relative-change comparison"])
                continue
            changes = [100 * (beta(altered) / beta(base) - 1) for altered, base in pairs]
            average = statistics.mean(changes)
            r["calculation"] = dict(A_m_per_flood=[0, .012], relative_changes_percent=changes,
                                     mean_change_percent=average, prose_reference_percent=reference,
                                     difference_percentage_points=average - reference)
            r["assessment"] = "E={:g}: mean beta change is {:+.3g}% across A=0 and 0.012 m/flood; the approximate prose target is {:+g}% (difference {:+.3g} percentage points).".format(E, average, reference, average - reference)
            r["caveat"] = "The manuscript does not specify aggregation weights; this comparison averages the two paired relative changes equally. The approximate prose values do not define a pass tolerance."

    pairs = []
    for fine in [c for c in configs if c["load"] == "fine"]:
        matched = [c for c in default if c["A_m_per_flood"] == fine["A_m_per_flood"] and c["C"] == fine["C"]]
        if len(matched) != 1:
            raise ValueError("fine-load configuration lacks a unique default match")
        pairs.append((int(fine["run"]), int(matched[0]["run"])))
    r = add("fine_load_beta", "3A", [n for pair in pairs for n in pair],
            "Fine sediment lowers beta at matched A,C,E; only one published fine-load case exceeds beta=1.", "beta")
    if r["status"] == "computed":
        values = [beta(fine) for fine, _ in pairs]
        deltas = [beta(fine) - beta(base) for fine, base in pairs]
        r["calculation"] = dict(pairs=pairs, beta_difference_fine_minus_default=deltas,
                                 fine_beta=values, lower_count=sum(d < 0 for d in deltas), above_one_count=sum(b > 1 for b in values))
        r["assessment"] = "Fine load lowers beta in {}/{} matched cases; {} fine-load cases exceed beta=1, compared with one reported in the prose.".format(sum(d < 0 for d in deltas), len(pairs), sum(b > 1 for b in values))
        r["caveat"] = "Beta=1 is an interpreted topographic reference, not an avulsion event in the implementation."

    r = add("maximum_alpha95", "3C", list(range(1, 32)),
            "The largest alpha95 occurs at high suspended load and low bed aggradation.", "alpha")
    if r["status"] == "computed":
        ordered = sorted(range(1, 32), key=alpha95, reverse=True)
        n = ordered[0]
        config = runs[n]["config"]
        # C=0.01 has no A=0 run; run 18 is the lowest A at that highest load.
        r["calculation"] = dict(run_order=ordered, alpha95_m=[alpha95(i) for i in ordered],
                                 maximum_run=n, highest_C_lowest_available_A_run=18,
                                 target_run_rank=ordered.index(18) + 1)
        r["assessment"] = "Maximum alpha95 is {:.4g} m in run {:02d} (A={}, C={}); the highest-C, lowest-available-A case (run 18) ranks {} of 31.".format(alpha95(n), n, config["A_m_per_flood"], config["C"], ordered.index(18) + 1)
        r["caveat"] = "This tests ordering among the documented configurations. It does not infer an unsimulated A=0, C=0.01 point."

    for C in [.0003, .003, .01]:
        group = sorted([c for c in default if float(c["C"]) == C], key=lambda c: float(c["A_m_per_flood"]))
        numbers = [int(c["run"]) for c in group]
        r = add("alpha95_A_tendency_C{:g}".format(C), "3C", numbers,
                "Low aggradation favors greater alpha95, especially at high C; the prose does not claim strict monotonicity.", "alpha")
        if r["status"] == "computed":
            values = [alpha95(n) for n in numbers]
            contrasts = directions(values, -1)
            r["calculation"] = dict(A_m_per_flood=[float(c["A_m_per_flood"]) for c in group], alpha95_m=values, **contrasts)
            r["assessment"] = "C={:g}: alpha95 decreases across {}/{} adjacent A contrasts; {} contrasts increase.".format(C, contrasts["requested_direction"], len(numbers) - 1, contrasts["opposite_direction"])

    r = add("alpha_variability_with_C", "3B", [7, 15, 20],
            "At A=0.018 m/flood, greater suspended load produces stronger alpha variability and higher peaks.",
            "alpha", required_panels=["3B"])
    if r["status"] == "computed":
        summaries = []
        for n in [7, 15, 20]:
            values = [runs[n]["records"][f]["alpha"] for f in range(381, 581)]
            mean = statistics.mean(values)
            deviation = statistics.pstdev(values)
            summaries.append(dict(run=n, C=float(runs[n]["config"]["C"]), mean_m=mean,
                                  population_std_m=deviation, cv=deviation / mean if mean > 0 else None,
                                  maximum_m=max(values), minimum_m=min(values)))
        if any(s["cv"] is None for s in summaries):
            r.update(status="pending", pending_reasons=["nonpositive mean alpha prevents CV comparison"])
        else:
            contrasts = directions([s["cv"] for s in summaries], 1)
            r["calculation"] = dict(window=[381, 580], summaries=summaries, cv_contrasts=contrasts,
                                     standard_deviation_contrasts=directions([s["population_std_m"] for s in summaries], 1),
                                     maximum_contrasts=directions([s["maximum_m"] for s in summaries], 1))
            r["assessment"] = "For C=0.0003, 0.003 and 0.01, final-200-flood alpha CV values are {}; standard deviations are {} m and peak alpha values are {} m. CV rises in {}/2 load contrasts.".format(
                ", ".join("{:.3g}".format(s["cv"]) for s in summaries),
                ", ".join("{:.3g}".format(s["population_std_m"]) for s in summaries),
                ", ".join("{:.3g}".format(s["maximum_m"]) for s in summaries), contrasts["requested_direction"])
            r["caveat"] = "CV is population standard deviation divided by mean over the fixed final 200 floods. The paper describes variability without defining a numerical CV target; changes in relative and absolute variability need not have the same sign."

    deposits = {row["panel"]: row for row in derived["deposit_metrics.csv"]}
    for panel, number in [("1A", 11), ("1B", 11), ("1C", 11), ("1D", 11), ("1E", 17), ("1F", 3)]:
        r = add("deposit_" + panel, panel, [number],
                "Published maps show individual-flood deposition, initially in splays and later along abandoned channels.",
                required_panels=[panel], require_full_history=False)
        if r["status"] == "computed":
            row = deposits.get(panel, {})
            keys = ["deposited_area_km2", "deposited_volume_m3", "deposit_max_m", "deposit_p95_m", "deposit_transverse_std_m", "sinuosity"]
            values = {key: finite(row.get(key)) for key in keys}
            if any(values[key] is None for key in keys[:4]):
                r.update(status="pending", pending_reasons=["required derived deposit quantities missing"])
                continue
            r["calculation"] = values
            r["assessment"] = "{}: deposited area above 1e-6 m is {:.4g} km2, deposited volume is {:.4g} m3, and maximum event thickness is {:.4g} m.".format(panel, values["deposited_area_km2"], values["deposited_volume_m3"], values["deposit_max_m"])
            r["caveat"] = "The publication supplies no exact area/volume targets. These quantities support comparison of computed spatial scales; they cannot establish splay or abandoned-channel morphology by themselves. The 0.5 m color-axis limit is not an observed maximum."
    r = add("deposit_time_contrasts", "1A–D", [11],
            "Conveyance and deposition become localized over time, but substantial late-flood variability persists.",
            required_panels=["1A", "1B", "1C", "1D"], require_full_history=False)
    if r["status"] == "computed":
        areas = [finite(deposits.get(p, {}).get("deposited_area_km2")) for p in ["1A", "1B", "1C", "1D"]]
        if any(a is None for a in areas):
            r.update(status="pending", pending_reasons=["temporal deposit areas missing"])
        else:
            r["calculation"] = dict(floods=[61, 251, 501, 562], deposited_area_km2=areas,
                                     area_change_501_minus_61_km2=areas[2] - areas[0], area_change_562_minus_501_km2=areas[3] - areas[2])
            r["assessment"] = "Deposit areas at floods 61, 251, 501 and 562 are {} km2; flood 562 changes by {:+.4g} km2 from flood 501.".format(
                ", ".join("{:.4g}".format(a) for a in areas), areas[3] - areas[2])
            r["caveat"] = "Deposit footprint differs from inundation extent, especially as load changes. No agreement with an inundation claim is inferred from this proxy alone."

    section_rows = derived["sections.csv"]
    for panel, number in [("2A", 22), ("2B", 10), ("2C", 3), ("2D", 15)]:
        r = add("section_relief_" + panel, panel, [number],
                "Late ridge elevation is approximately {}–{} m in the published image; its initial section is near 9 m (coarse visual ranges, not digitized data).".format(*VISUAL_RANGES[panel]),
                required_panels=[panel], require_full_history=False)
        if r["status"] != "computed":
            continue
        profiles, reasons = [], []
        for flood in [50, 225, 400, 580]:
            try:
                selected = [row for row in section_rows if row["panel"] == panel and int(row["flood"]) == flood]
                profiles.append(saved_section(selected, runs[number], panel, number, flood, inputs))
            except (ValueError, KeyError, OSError, struct.error) as error:
                reasons.append("flood {}: {}".format(flood, error))
                break
        if reasons:
            r.update(status="pending", pending_reasons=reasons)
            continue
        target_low, target_high = (v - 9 for v in VISUAL_RANGES[panel])
        relief = profiles[-1]["crest_relief_m"]
        relation = "below" if relief < target_low else "above" if relief > target_high else "within"
        r["calculation"] = dict(profiles=profiles, approximate_published_relief_interval_m=[target_low, target_high],
                                 visual_interval_relation=relation,
                                 difference_from_interval_midpoint_m=relief - .5 * (target_low + target_high))
        r["assessment"] = "{}: final crest relief above the initial model plane is {:.4g} m, {} the approximate published {}–{} m relief interval. Relief at floods 50, 225, 400 and 580 is {} m.".format(
            panel, relief, relation, target_low, target_high, ", ".join("{:.4g}".format(q["crest_relief_m"]) for q in profiles))
        final = profiles[-1]
        if final["positive_relief_resolved"]:
            r["assessment"] += " Final positive-relief equivalent width is {:.4g} km and transverse standard deviation is {:.4g} km; half-crest occupied width/span are {:.4g}/{:.4g} km.".format(
                final["equivalent_positive_relief_width_m"] / 1000, final["positive_relief_std_m"] / 1000,
                final["half_crest_occupied_width_m"] / 1000, final["half_crest_span_width_m"] / 1000)
            departure = [final["flanks"][side]["mean_chord_departure_m"] for side in ("lower_y", "upper_y")]
            r["assessment"] += " Lower-/upper-y mean flank departures from crest-to-distal chords are {} m (positive means above the chord).".format(
                "/".join("undefined" if value is None else "{:.4g}".format(value) for value in departure))
        else:
            r["assessment"] += " Positive relief is absent or unresolved at float32 snapshot precision; nominal width/shape descriptors are not interpreted."
        r["caveat"] = "The reference interval is a coarse visual estimate minus an approximate 9 m initial datum, not a digitized measurement or acceptance bound. Widths and flank chord departures are defined diagnostics of the saved section; the paper gives no numerical targets or mathematical concavity criterion. Active-channel cells are excluded without filling their gaps, while abandoned depressions remain. Nominal float32/grid measurements, including low-relief rounding limits, require visual assessment before any morphology agreement claim."

    report = dict(reference_scope="main-paper prose and coarse visual ranges only; no DR2 result columns or digitized data",
                  data_root=label(data_root), figure_root=label(figure_root), comparisons=results,
                  computed_count=sum(r["status"] == "computed" for r in results), total_count=len(results),
                  provenance_errors=provenance_errors,
                  section_morphology_definitions=dict(
                      datum="r_i=z_i-slope*(length-x); active channel cells excluded throughout; w_i=max(r_i,0) elsewhere",
                      area="B=dx*sum(w_i), cross-sectional positive-relief area in m2, not accumulated sediment mass",
                      spread="mu=sum(w_i*y_i)/sum(w_i); sigma2=sum(w_i*((y_i-mu)^2+dx^2/12))/sum(w_i); piecewise constant cells",
                      widths="Equivalent width B/max(r_i); half-crest occupied width counts non-active cells r_i>=max(r_i)/2, span includes intervening gaps; undefined when max(r_i)<=0",
                      flanks="Lower/upper flank runs from first non-active cell to first crest cell / last crest cell to last non-active cell; each signed mean is r_i minus that flank's endpoint chord over observed non-active cells, including endpoints; no interpolation across channels",
                      shape_scope="At least three non-active cells and positive crest required per flank. Positive departure means above the chord, negative below; this is not a local-curvature or published-concavity test.",
                      precision="Areas include conservative half-ULP float32 elevation-rounding bounds; widths, crest locations and flank descriptors are nominal, with grid resolution and channel gaps retained."),
                  untested_claims=["Splay versus abandoned-channel morphology needs direct comparison of generated maps.",
                                   "Deposit footprint is not flood inundation extent.",
                                   "Axis limits alone supply no agreement evidence.",
                                   "The implementation does not calculate avulsion occurrence or frequency."],
                  input_sha256={label(path): digest(path) for path in sorted(inputs) if path.exists()})
    return report


def latex(text):
    substitutions = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
                     "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(substitutions.get(c, c) for c in text).replace("–", "--")


def results_tex(report):
    lines = [r"\subsection{Quantitative comparison status}" + "\n"]
    count, total = report["computed_count"], report["total_count"]
    lines.append("{} of {} specified numerical comparisons have complete, documented input records. ".format(count, total))
    if not count:
        lines.append("Quantitative manuscript comparison remains pending. No agreement is inferred from missing windows, altered benchmark configurations, or the published axis limits.\n\n")
    else:
        lines.append("The calculations below compare independent output with the main-paper prose and explicitly approximate visual ranges \\cite{nicholas2018}. They do not establish agreement for untested spatial patterns.\n\n")
        for record in report["comparisons"]:
            if record["status"] != "computed":
                continue
            lines.append(r"\paragraph{" + latex(record["comparison"].replace("_", " ")) + "} " + latex(record["assessment"]) + " ")
            if record["caveat"]:
                lines.append(latex(record["caveat"]))
            lines.append("\n\n")
    if count < total:
        pending = [r["comparison"] for r in report["comparisons"] if r["status"] != "computed"]
        lines.append("The remaining {} comparisons are pending. Exact required runs and reasons are recorded in \\texttt{{comparison.json}}; no pending calculation is assigned a numerical result.\n\n".format(len(pending)))
    if report["provenance_errors"]:
        lines.append("Plot provenance needs regeneration: " + latex("; ".join(report["provenance_errors"][:3])) + ".\n\n")
    lines.append("Published result columns were not read by this comparison. Relative erodibility changes use equally weighted paired cases; alpha variability uses the population coefficient of variation over floods 381--580. Datum comparisons subtract the initial plane and retain the uncertainty of coarse visual estimates.\n")
    return "".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--figures", default="figures", help="directory produced by scripts/plot.py")
    parser.add_argument("--output", default="figures", help="comparison.json/csv output directory")
    parser.add_argument("--tex", default="report/generated/results.tex")
    parser.add_argument("--strict", action="store_true", help="exit 2 if any numerical comparison remains pending")
    args = parser.parse_args()
    output, tex_path = Path(args.output).resolve(), Path(args.tex).resolve()
    if ROOT not in output.parents or ROOT not in tex_path.parents:
        parser.error("all generated comparison files must remain inside the /data project")
    report = evaluate(Path(args.data_root).resolve(), Path(args.figures).resolve())
    output.mkdir(parents=True, exist_ok=True)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    report["command"] = sys.argv
    (output / "comparison.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    with (output / "comparison.csv").open("w", newline="") as stream:
        fields = ["comparison", "panel", "status", "runs", "target", "calculation", "assessment", "caveat", "pending_reasons", "reference"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in report["comparisons"]:
            row = dict(record)
            for key in ["runs", "calculation", "pending_reasons"]:
                row[key] = json.dumps(row[key], sort_keys=True, allow_nan=False)
            writer.writerow(row)
    tex_path.write_text(results_tex(report))
    print("Wrote comparison records and {}; {}/{} checks computed from complete documented records.".format(label(tex_path), report["computed_count"], report["total_count"]))
    return 2 if args.strict and report["computed_count"] != report["total_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
