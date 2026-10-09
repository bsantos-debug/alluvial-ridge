#!/usr/bin/env python3
"""Render the current input configuration and panel ledger as LaTeX.

This reads no published model results and does not infer reproduction status.
"""
import csv
from collections import Counter
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


panels = rows(ROOT / "docs" / "panels.csv")
required = {"1" + x for x in "ABCDEF"} | {"2" + x for x in "ABCD"} | {"3" + x for x in "ABC"}
if {row["panel"] for row in panels} != required or len(panels) != 13:
    raise ValueError("The report requires exactly the 13 manuscript panels")

counts = Counter(row["status"] for row in panels)
status = [r"\textbf{Current panel ledger:} " + "; ".join(
    "{} {}".format(count, tex(label)) for label, count in sorted(counts.items())) + ".\n"]
if any(row["status"] not in ("reproduced", "independently reproduced") for row in panels):
    status.append("Panels marked partial or not reproduced have missing outputs or agreement limits described in the ledger. Rebuild execution is recorded separately.\n")
status.append("The ledger records the assessment; the command outputs, saved data, and comparisons provide its evidence.\n")
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
            lines.append(r"\textbf{" + tex(field.replace("_", " ").capitalize()) + ":} " + tex(value) + "\n\n")
(OUT / "panels.tex").write_text("".join(lines))

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
