#!/usr/bin/env python3
"""Render the current input configuration and panel ledger as LaTeX.

Current plotted-data evidence can lower an assessment or establish partial
coverage. Scientific reproduction requires a documented, fingerprinted assessment.
"""
import csv
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "generated"
OUT.mkdir(parents=True, exist_ok=True)


def tex(value):
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%",
        "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
        "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(c, c) for c in str(value))


def rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spatial_source(name, processor):
    """Verify optional saved diagnostics before rendering or retaining a review."""
    path = ROOT / "figures" / name
    record = dict(file=str(path.relative_to(ROOT)), sha256=None, state="absent", problems=[], data={})
    if not path.exists():
        return record
    record["sha256"] = digest(path)
    try:
        data = json.loads(path.read_text())
        inputs = data["input_sha256"]
        if not isinstance(inputs, dict) or not inputs:
            raise ValueError("input_sha256 must be a nonempty hash mapping")
        for required in (processor, "config/runs.csv", "config/physics.txt"):
            if required not in inputs:
                record["problems"].append("required input hash missing: " + required)
        for name, expected in inputs.items():
            source = (ROOT / name).resolve()
            if ROOT not in source.parents or not source.is_file() or digest(source) != expected:
                record["problems"].append("input missing, changed or outside packaged project: " + name)
        # Hash-valid diagnostics from another retained run history must not be
        # displayed beside the current figure, even if its parameters match.
        ready = [(r.get("panel"), r) for r in data.get("samples", [])
                 if r.get("panel") and r.get("state") == "computed canonical snapshot"]
        ready += [(panel, r) for r in data.get("snapshots", []) if r.get("requested_data_ready")
                  for panel in r.get("panels", [])]
        if ready:
            plot_path = ROOT / "figures/plot_manifest.json"
            panel_path = ROOT / "figures/panel_status.csv"
            plot = json.loads(plot_path.read_text())
            plot_root = (ROOT / plot["data_root"]).resolve()
            plotted = {r["panel"]: {(ROOT / p).resolve() for p in r["source_files"].split(";") if p}
                       for r in rows(panel_path)}
            plot_hashes = {(ROOT / p).resolve(): h for p, h in plot["files"].items()}
            helper_hashes = {(ROOT / p).resolve(): h for p, h in inputs.items()}
            required = dict(zip(("1" + x for x in "ABCDEF"),
                                ((11, 61), (11, 251), (11, 501), (11, 562), (17, 562), (3, 562))))
            if len({p for p, r in ready}) != len(ready):
                raise ValueError("duplicate requested spatial panel")
            for panel, sample in ready:
                if (sample["run"], sample["flood"]) != required[panel]:
                    raise ValueError("wrong run/flood for spatial panel " + panel)
                folder = plot_root / ("run%02d" % sample["run"])
                names = ["fields_%04d.bin" % sample["flood"], "parameters.txt", "summary.csv"]
                if "geometry" in sample:
                    names.append("channel_%04d.csv" % sample["flood"])
                    if any((ROOT / sample[key]).resolve() != folder / filename for key, filename in
                           (("fields_file", names[0]), ("channel_file", names[-1]))):
                        raise ValueError("planform paths differ from plotted panel " + panel)
                else:
                    peak = folder / ("peak_fields_%04d.bin" % sample["flood"])
                    if peak not in helper_hashes:
                        raise ValueError("day-12 input is outside plotted run for " + panel)
                for name in names:
                    source = folder / name
                    if (source not in plotted.get(panel, set()) or source not in helper_hashes
                            or helper_hashes[source] != plot_hashes.get(source)):
                        raise ValueError("spatial input differs from plotted panel " + panel + ": " + name)
            record["plot_manifest_sha256"] = digest(plot_path)
            record["panel_status_sha256"] = digest(panel_path)
        if not record["problems"]:
            record["data"] = data
    except (OSError, ValueError, KeyError, TypeError) as error:
        record["problems"].append("invalid diagnostic provenance: " + str(error))
    record["state"] = "invalid" if record["problems"] else "verified"
    return record


def render_spatial(sources):
    """Report only exact requested snapshots with unchanged diagnostic inputs."""
    lines = [r"\subsection{Spatial measurements from saved snapshots}" + "\n",
             "The following measurements describe independent output; they do not assign scientific agreement. "
             "A dash denotes a missing, noncanonical, inconsistent or unverified requested sample. "
             "Diagnostic provenance and all omitted records are retained in the accompanying JSON files.\\par\n"]

    def number(value, scale=1.):
        if value is None:
            return "---"
        value = float(value) / scale
        return "{:.4g}".format(value) if math.isfinite(value) else "---"

    for source in sources.values():
        if source["state"] != "verified":
            reason = "; ".join(source["problems"][:2]) or "diagnostic has not been generated"
            lines.append(tex(source["file"] + ": " + reason) + ".\\par\n")
    water = sources["inundation"]["data"]
    samples = {row["panel"]: row for row in water.get("samples", [])
               if row.get("panel") and row.get("state") == "computed canonical snapshot"}
    lines.extend([
        "Water is sampled at day 12; deposition is sampled at flood end, before migration. "
        "Wet area excludes channel ghosts and uses $h>1$ mm. Mean depth includes dry floodplain cells. "
        "The wet-bank fraction uses immediate channel--floodplain faces and both depth and stage tests. "
        "Wet patches connect faces sharing a raster vertex; their count is sensitive to threshold rounding. "
        "Patch length does not measure discharge.\\par\n",
        r"\begin{center}\small\begin{tabular}{lrrrrrr}\toprule" + "\n",
        r"Panel & Wet area & Mean $h$ & Wet banks & Patches & Largest patch & Deposit \\" + "\n",
        r" & (km$^2$) & (m) & (fraction) & (count) & (km) & ($10^6$ m$^3$) \\ \midrule" + "\n"])
    for panel in ("1" + x for x in "ABCDEF"):
        row = samples.get(panel, {})
        bank = row.get("interface", {})
        values = [panel, number(row.get("inundated_area_m2"), 1e6), number(row.get("mean_water_depth_m")),
                  number(bank.get("fraction")), number(bank.get("connected_wet_patches")),
                  number(bank.get("largest_wet_patch_length_m"), 1e3),
                  number(row.get("event_deposition_bulk_volume_m3"), 1e6)]
        lines.append(" & ".join(values) + r" \\" + "\n")
    lines.append(r"\bottomrule\end{tabular}\end{center}" + "\n")
    ambiguous = [panel for panel, row in samples.items() if row.get("ambiguous_wet_area_cells", 0)
                 or row["interface"]["definitely_wet_faces"] != row["interface"]["possibly_wet_faces"]]
    if ambiguous:
        lines.append("Float32 rounding makes threshold membership ambiguous for panels " + tex(", ".join(sorted(ambiguous)))
                     + "; the JSON retains definite and possible areas/faces and alpha bounds.\\par\n")
    lines.extend([
        "Deposit volumes include pore space. The next table reports fractions of each event's total "
        "bulk deposit volume on its day-12 wet footprint and in previously sampled channel cells that are now floodplain. "
        "The latter masks omit unsaved channel positions and do not establish complete abandoned-channel infilling.\\par\n",
        r"\begin{center}\small\begin{tabular}{lrrl}\toprule" + "\n",
        r"Panel & On wet footprint & In earlier channels & Earlier saved floods \\ \midrule" + "\n"])
    for panel in ("1" + x for x in "ABCDEF"):
        row = samples.get(panel, {})
        total = row.get("event_deposition_bulk_volume_m3")
        values = [panel]
        for key in ("deposition_on_day12_wet_cells_bulk_volume_m3", "deposition_in_previously_saved_channels_bulk_volume_m3"):
            values.append(number(row[key] / total) if total and total > 0 else "---")
        values.append(tex(", ".join(map(str, row.get("earlier_saved_channel_floods", []))) or "none") if row else "---")
        lines.append(" & ".join(values) + r" \\" + "\n")
    lines.append(r"\bottomrule\end{tabular}\end{center}" + "\n")

    planforms = sources["planforms"]["data"]
    snapshots = {panel: row for row in planforms.get("snapshots", []) if row.get("requested_data_ready")
                 for panel in row.get("panels", [])}
    lines.extend([
        "Planform sinuosity is centerline arc length divided by the 72 km valley length. "
        "Extent and the arc-length-weighted lateral RMS describe the active centerline, not historical channel-belt width. "
        "Inverse RMS curvature uses unsmoothed three-point curvatures and is a curvature scale, not a bend wavelength. "
        "Zero curvature has no finite inverse scale.\\par\n",
        r"\begin{center}\small\begin{tabular}{lrrrr}\toprule" + "\n",
        r"Panel & Sinuosity & Lateral extent (km) & Lateral RMS (km) & Curvature scale (km) \\ \midrule" + "\n"])
    for panel in ("1" + x for x in "ABCDEF"):
        geo = snapshots.get(panel, {}).get("geometry", {})
        values = [panel, number(geo.get("valley_sinuosity")), number(geo.get("lateral_extent_m"), 1e3),
                  number(geo.get("lateral_rms_m"), 1e3), number(geo.get("inverse_rms_curvature_m"), 1e3)]
        lines.append(" & ".join(values) + r" \\" + "\n")
    lines.append(r"\bottomrule\end{tabular}\end{center}" + "\n")
    lines.append("Saved cutoff times and sinuosity series are in "
                 r"\texttt{figures/\allowbreak{}planform\_\allowbreak{}metrics.json}. "
                 "A count increase between summaries $n$ and $n+1$ dates the remap after flood $n$. "
                 "Missing summary intervals remain censored; the last summary cannot date its following remap. "
                 "The spatial tables supply no unreported numerical target from the publication.\n")
    (OUT / "spatial.tex").write_text("".join(lines))
    (OUT / "spatial_evidence.json").write_text(json.dumps({
        key: {k: v for k, v in value.items() if k != "data"} for key, value in sources.items()
    }, indent=2, sort_keys=True) + "\n")


spatial = dict(inundation=spatial_source("inundation_metrics.json", "scripts/inundation_metrics.py"),
               planforms=spatial_source("planform_metrics.json", "scripts/planform_metrics.py"))
render_spatial(spatial)


def merge_evidence(panels):
    """Keep source prose/commands intact while deriving the current report status."""
    ledger = ROOT / "figures" / "panel_status.csv"
    plotted = rows(ledger) if ledger.exists() else []
    if len({row["panel"] for row in plotted}) != len(plotted):
        raise ValueError("Duplicate panel in figures/panel_status.csv")
    if any(row["panel"] not in {p["panel"] for p in panels} for row in plotted):
        raise ValueError("Unknown panel in figures/panel_status.csv")
    plotted = {row["panel"]: row for row in plotted}
    manifest_path = ROOT / "figures" / "plot_manifest.json"
    manifest, manifest_error = {}, "plot input hashes unavailable"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())["files"]
            if not isinstance(manifest, dict):
                raise ValueError("files must be a hash mapping")
            manifest_error = ""
        except (ValueError, KeyError, TypeError):
            manifest_error = "plot_manifest.json is invalid"
    checked, hashes = {}, {}

    def current_hash(name):
        if name not in hashes:
            path = Path(name)
            if not path.is_absolute():
                path = ROOT / path
            hashes[name] = digest(path) if path.is_file() else None
        return hashes[name]

    processor_names = ("scripts/plot.py", "scripts/compare.py")
    processor_hashes = {name: current_hash(name) for name in processor_names}
    review_problems = []
    for name in ("scripts/plot.py", "config/runs.csv"):
        if current_hash(name) is None or current_hash(name) != manifest.get(name):
            review_problems.append("plot processor/configuration hash missing or changed: " + name)
    if not processor_hashes["scripts/compare.py"]:
        review_problems.append("comparison processor missing")
    if current_hash("config/physics.txt") is None:
        review_problems.append("physics reference missing")
    comparison_path = ROOT / "figures" / "comparison.json"
    if comparison_path.exists():
        try:
            comparison_inputs = json.loads(comparison_path.read_text())["input_sha256"]
            if not isinstance(comparison_inputs, dict):
                raise ValueError("input_sha256 must be a hash mapping")
            if comparison_inputs.get("scripts/compare.py") != processor_hashes["scripts/compare.py"]:
                review_problems.append("comparison processor hash missing or changed")
            for name, expected in comparison_inputs.items():
                if current_hash(name) is None or current_hash(name) != expected:
                    review_problems.append("comparison input missing or changed: " + name)
        except (ValueError, KeyError, TypeError):
            review_problems.append("comparison.json provenance is invalid")
    evidence_records, merged = {}, []
    assessed = {"reproduced", "independently reproduced", "partially reproduced"}
    for source in panels:
        row = dict(source)
        prior = source.get("status", "not reproduced").strip().lower()
        original_notes = row.pop("notes", "")
        assessment = source.get("scientific_assessment") or source.get("assessment") or (
            original_notes if prior in assessed else "")
        for name in ("scientific_assessment", "assessment", "assessment_fingerprint"):
            row.pop(name, None)
        text = assessment.strip().lower()
        documented = bool(text) and text not in {"pending", "not assessed", "not recorded"}
        if "required production outputs pending" in text or "agreement assessment pending" in text:
            documented = False
        if prior in {"reproduced", "independently reproduced"} and "pending" in text:
            documented = False
        evidence = plotted.get(row["panel"], {})
        availability = evidence.get("data_status", "current plotted-data verification unavailable")
        files = [name.strip() for name in evidence.get("source_files", "").split(";") if name.strip()]
        problems = [manifest_error] if manifest_error else []
        if not files:
            problems.append("no numerical source files recorded")
        for name in files:
            if name not in checked:
                if current_hash(name) is None:
                    checked[name] = "missing source: " + name
                elif name not in manifest:
                    checked[name] = "source hash unrecorded: " + name
                elif current_hash(name) != manifest[name]:
                    checked[name] = "source changed since plotting: " + name
                else:
                    checked[name] = ""
            if checked[name]:
                problems.append(checked[name])
        verified = bool(files) and not problems
        figure_name = "figures/figure{}.pdf".format(row["panel"][0])
        fingerprint_problems = problems + review_problems
        spatial_identity = {}
        if row["panel"].startswith("1"):
            for key, value in spatial.items():
                spatial_identity[key] = dict(file=value["file"], sha256=value["sha256"], state=value["state"])
                fingerprint_problems.extend(value["problems"])
        if current_hash(figure_name) is None:
            fingerprint_problems.append("generated figure missing: " + figure_name)
        payload = dict(format="panel-assessment-v2", panel=row["panel"], panel_status=evidence,
                       numerical_source_sha256={name: current_hash(name) for name in sorted(files)},
                       plot_manifest_sha256=current_hash("figures/plot_manifest.json"),
                       figure=figure_name, figure_sha256=current_hash(figure_name),
                       processor_sha256=processor_hashes,
                       physics_reference_sha256=current_hash("config/physics.txt"),
                       comparison_json_sha256=current_hash("figures/comparison.json"),
                       spatial_diagnostics=spatial_identity)
        fingerprint = None if fingerprint_problems else hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        recorded_fingerprint = source.get("assessment_fingerprint", "").strip()
        matching_review = bool(fingerprint) and recorded_fingerprint == fingerprint
        evidence_records[row["panel"]] = dict(current_fingerprint=fingerprint, evidence=payload,
                                              problems=list(dict.fromkeys(fingerprint_problems)),
                                              recorded_fingerprint=recorded_fingerprint,
                                              assessment_fingerprint_matches=matching_review)
        if availability == "complete requested data":
            row["status"] = "partially reproduced"
            reason = "All requested numerical data independently generated; agreement assessment pending."
            if verified and documented and matching_review and prior in assessed:
                row["status"] = prior
                reason = "Documented scientific assessment retained with complete data and matching input, processor and figure fingerprint: " + assessment
            elif not verified:
                reason = "Plotter reports all requested numerical data; current input provenance is unverified, and the scientific assessment is pending."
        elif availability == "partial requested data":
            row["status"] = "partially reproduced"
            reason = "Requested numerical data are incomplete or use altered/unverified settings."
            if verified and documented and matching_review and prior == "partially reproduced":
                reason += " Documented partial assessment: " + assessment
            elif prior in {"reproduced", "independently reproduced"}:
                reason += " The prior complete assessment is withheld because current coverage is partial."
        else:
            row["status"] = "not reproduced"
            reason = "No requested numerical data are verified for this panel."
        if documented and prior in assessed and not matching_review:
            reason += " Prior scientific assessment withheld: its input, processor and figure fingerprint is missing, changed or currently unverifiable."
        row["assessment"] = reason
        row["data_coverage"] = availability + ". " + evidence.get("notes", "No current plotter coverage record is available.")
        if verified:
            row["data_provenance"] = "{} source-file hashes verified against figures/plot_manifest.json; coverage from figures/panel_status.csv.".format(len(files))
        else:
            row["data_provenance"] = "; ".join(dict.fromkeys(problems)) + ". Coverage claims have not been verified against unchanged numerical inputs."
        if files:
            row["data_source_files"] = "; ".join(files)
        row["current_assessment_fingerprint"] = fingerprint or "unavailable; see report/generated/panel_evidence.json"
        if fingerprint_problems:
            row["assessment_provenance"] = "; ".join(dict.fromkeys(fingerprint_problems))
        row["source_ledger_status"] = source.get("status", "not recorded")
        if original_notes:
            row["source_ledger_notes"] = original_notes
        if assessment:
            row["source_ledger_assessment"] = assessment
        if recorded_fingerprint:
            row["source_ledger_assessment_fingerprint"] = recorded_fingerprint
        merged.append(row)
    (OUT / "panel_evidence.json").write_text(json.dumps(evidence_records, indent=2, sort_keys=True) + "\n")
    return merged


panels = rows(ROOT / "docs" / "panels.csv")
required = {"1" + x for x in "ABCDEF"} | {"2" + x for x in "ABCD"} | {"3" + x for x in "ABC"}
if {row["panel"] for row in panels} != required or len(panels) != 13:
    raise ValueError("The report requires exactly the 13 manuscript panels")
panels = merge_evidence(panels)

counts = Counter(row["status"] for row in panels)
status = [r"\textbf{Current panel ledger:} " + "; ".join(
    "{} {}".format(count, tex(label)) for label, count in sorted(counts.items())) + ".\n"]
if any(row["status"] not in ("reproduced", "independently reproduced") for row in panels):
    status.append("Panels marked partial or not reproduced have missing outputs or agreement limits described in the ledger. Rebuild execution is recorded separately.\n")
status.append("This report merges the maintained scientific ledger with current plotted-data coverage. Complete numerical coverage alone is classified as partial until a scientific assessment is documented and bound to the current numerical inputs, processors and figure. Source-ledger notes are retained as prior documentation, and current coverage and provenance are listed separately for every panel.\n")
(OUT / "status.tex").write_text("".join(status))

lines = []
for row in panels:
    lines.append(r"\subsection*{Panel " + tex(row["panel"]) + "}\n")
    for field, label in (("quantity", "Quantity"), ("configuration", "Configuration"),
                         ("sampling", "Sampling"), ("status", "Status"),
                         ("data_command", "Data command"), ("plot_command", "Plot command")):
        value = row.get(field, "not recorded")
        if field.endswith("_command"):
            # \detokenize in \texttt handles literal command punctuation; spaces
            # remain line-break opportunities for longer shell commands.
            if "{" in value or "}" in value:
                formatted = tex(value)
            else:
                formatted = r"\texttt{\detokenize{" + value + "}}"
        else:
            formatted = tex(value)
        if field.endswith("_command"):
            lines.append(r"\textbf{" + label + r":}\par {\small " + formatted + "}\\par\n\n")
        else:
            lines.append(r"\textbf{" + label + ":} " + formatted + "\n\n")
    for field, value in row.items():
        if field not in ("panel", "quantity", "configuration", "sampling", "status", "data_command", "plot_command") and value:
            formatted = tex(value).replace("/", r"/\allowbreak{}").replace(r"\_", r"\_\allowbreak{}")
            if field.endswith("fingerprint") and len(value) == 64:
                lines.append(r"\textbf{" + tex(field.replace("_", " ").capitalize())
                             + r":}\par {\small\texttt{" + value + "}}\\par\n\n")
                continue
            if field == "data_source_files":
                lines.append(r"\textbf{Data source files:}\par {\small\raggedright "
                             + formatted + "\\par}\n\n")
                continue
            lines.append(r"\textbf{" + tex(field.replace("_", " ").capitalize()) + ":} " + formatted + "\n\n")
(OUT / "panels.tex").write_text("".join(lines).rstrip() + "\n")

runs = rows(ROOT / "config" / "runs.csv")
if len(runs) != 31:
    raise ValueError("Expected the 31 documented input configurations")
lines = [r"\begin{longtable}{rrrrl}" + "\n",
         r"\toprule Run & $A$ & $C$ & $E$ & Load \\ \midrule\endhead" + "\n"]
for row in runs:
    lines.append(" & ".join(tex(row[key]) for key in ("run", "A_m_per_flood", "C", "E", "load")) + r" \\" + "\n")
lines.append(r"\bottomrule\end{longtable}" + "\n")
(OUT / "runs.tex").write_text("".join(lines))

kernel = ROOT / "validation" / "kernel.txt"
if kernel.exists():
    content = kernel.read_text()
    if r"\end{verbatim}" in content:
        raise ValueError("Unexpected TeX control in validation log")
    wrapped = "\n".join(textwrap.fill(line, width=96, subsequent_indent="  ",
                                    replace_whitespace=False, drop_whitespace=False,
                                    break_on_hyphens=False) for line in content.splitlines())
    wrapped = "\n".join(line.rstrip() for line in wrapped.split("\n"))
    (OUT / "kernel.tex").write_text(
        "Existing kernel verification log (scope limited to the named checks). "
        r"Display lines are wrapped; the original bytes remain in \texttt{validation/kernel.txt}." + "\n"
        + r"\begingroup\scriptsize\begin{verbatim}" + "\n" + wrapped + "\n"
        + r"\end{verbatim}\endgroup" + "\n")
else:
    previous = OUT / "kernel.tex"
    if previous.exists():
        previous.unlink()
