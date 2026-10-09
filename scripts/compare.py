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


def comparison_inputs(data_root, figure_root):
    configs = rows(ROOT / "config" / "runs.csv")
    if len(configs) != 31 or {int(c["run"]) for c in configs} != set(range(1, 32)):
        raise ValueError("Expected all 31 documented configurations")
    inputs = {ROOT / "config" / "runs.csv", Path(__file__).resolve()}
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
        parameters, records, notes = {}, {}, []
        path = directory / "parameters.txt"
        if path.exists():
            inputs.add(path)
            for line in path.read_text().splitlines():
                pair = line.split(None, 1)
                if len(pair) == 2:
                    parameters[pair[0]] = pair[1]
        expected = dict(run=number, A=float(config["A_m_per_flood"]), C=float(config["C"]),
                        E=float(config["E"]), fine=int(config["load"] == "fine"), dx=250,
                        length=72000, width=48000, duration=1728000, channel_width=500,
                        slope=.0001, initial_depth=8, qmin=2500, qmax=15000, migration=1)
        for key, value in expected.items():
            actual = finite(parameters.get(key))
            if actual is None or not math.isclose(actual, value, rel_tol=1e-10, abs_tol=1e-12):
                notes.append("{}={} (required {})".format(key, parameters.get(key, "unrecorded"), value))
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
            notes.append("{} of 580 required flood rows missing".format(len(absent)))
        metric = metric_rows.get(number, {})
        if metric.get("configuration_verified") != "1" or metric.get("complete_1_to_580") != "1":
            notes.append("plotter has not verified canonical configuration and full history")
        runs[number] = dict(config=config, parameters=parameters, records=records,
                            metric=metric, notes=notes, directory=directory)
    return configs, runs, derived, errors, inputs


def evaluate(data_root, figure_root):
    configs, runs, derived, provenance_errors, inputs = comparison_inputs(data_root, figure_root)
    results = []
    panel_state = {row["panel"]: row for row in derived["panel_status.csv"]}

    def ready(numbers, metric=None, panels=()):
        reasons = list(provenance_errors)
        for number in sorted(set(numbers)):
            run = runs[number]
            reasons.extend("run {:02d}: {}".format(number, note) for note in run["notes"])
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

    def add(name, panel, numbers, target, required_metric=None, required_panels=()):
        reasons = ready(numbers, required_metric, required_panels)
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
            "At A=0.018 m/flood, greater suspended load produces stronger alpha variability and higher peaks.", "alpha")
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
                "Published maps show individual-flood deposition, initially in splays and later along abandoned channels.", required_panels=[panel])
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
            "Conveyance and deposition become localized over time, but substantial late-flood variability persists.", required_panels=["1A", "1B", "1C", "1D"])
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
                required_panels=[panel])
        if r["status"] != "computed":
            continue
        profiles, reasons = [], []
        p = runs[number]["parameters"]
        for flood in [50, 225, 400, 580]:
            selected = [row for row in section_rows if row["panel"] == panel and int(row["flood"]) == flood]
            if len(selected) != 192 or len({row["transverse_m"] for row in selected}) != 192:
                reasons.append("section must contain 192 distinct documented-resolution cells")
                break
            floodplain = [row for row in selected if row["active_channel"] == "0"]
            elevations = [finite(row["elevation_m"]) for row in floodplain]
            if not elevations or any(z is None for z in elevations):
                reasons.append("finite floodplain profile unavailable")
                break
            x = float(selected[0]["downstream_m"])
            plane = float(p["slope"]) * (float(p["length"]) - x)
            profiles.append(dict(flood=flood, downstream_m=x, initial_plane_m=plane,
                                 crest_elevation_m=max(elevations), crest_relief_m=max(elevations) - plane,
                                 profile_p90_relief_m=percentile(elevations, .9) - plane,
                                 minimum_elevation_m=min(float(row["elevation_m"]) for row in selected)))
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
        r["caveat"] = "The reference interval is a coarse visual estimate minus an approximate 9 m initial datum. It is not a digitized measurement, error bar, or calibrated acceptance interval. The computed crest is the maximum non-active-channel cell at the central saved column; ridge width, concavity and channel pattern require separate visual assessment."

    report = dict(reference_scope="main-paper prose and coarse visual ranges only; no DR2 result columns or digitized data",
                  data_root=label(data_root), figure_root=label(figure_root), comparisons=results,
                  computed_count=sum(r["status"] == "computed" for r in results), total_count=len(results),
                  provenance_errors=provenance_errors,
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
