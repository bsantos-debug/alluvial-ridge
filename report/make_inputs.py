#!/usr/bin/env python3
"""Render the current input configuration and panel ledger as LaTeX.

Current plotted-data evidence can lower an assessment or establish partial
coverage. Scientific reproduction requires a documented, fingerprinted assessment.
"""
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path

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
        if current_hash(figure_name) is None:
            fingerprint_problems.append("generated figure missing: " + figure_name)
        payload = dict(format="panel-assessment-v1", panel=row["panel"], panel_status=evidence,
                       numerical_source_sha256={name: current_hash(name) for name in sorted(files)},
                       plot_manifest_sha256=current_hash("figures/plot_manifest.json"),
                       figure=figure_name, figure_sha256=current_hash(figure_name),
                       processor_sha256=processor_hashes,
                       physics_reference_sha256=current_hash("config/physics.txt"),
                       comparison_json_sha256=current_hash("figures/comparison.json"))
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
    (OUT / "kernel.tex").write_text(
        "Existing kernel verification log (scope limited to the named checks):\n"
        + r"\begingroup\scriptsize\begin{verbatim}" + "\n" + content + "\n"
        + r"\end{verbatim}\endgroup" + "\n")
else:
    previous = OUT / "kernel.tex"
    if previous.exists():
        previous.unlink()
