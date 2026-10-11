#!/usr/bin/env python3
"""Stage a later report from terminal, verified saved data; never run a model."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from run_suite import completion

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {"complete", "incomplete", "failed", "interrupted"}
SENSITIVITY = {"baseline250", "coarse500", "fine125", "time250_cfl02",
               "tau005", "tau020", "concentration_half", "concentration_double"}


def utc():
    return datetime.datetime.utcnow().isoformat() + "Z"


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing file or disallowed symlink: " + str(path))
    before = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("file changed during verification: " + str(path))
    return h.hexdigest()


def child(folder, name):
    path = folder / name
    if Path(name).is_absolute() or ".." in Path(name).parts or folder.resolve() not in path.resolve().parents:
        raise ValueError("manifest path leaves its directory: " + str(name))
    if any(parent.is_symlink() for parent in [path] + list(path.parents) if parent != folder.parent):
        raise ValueError("symlink in evidence path: " + str(path))
    return path


def read(path):
    digest(path)
    return json.loads(path.read_text())


def save(path, record):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def verify(folder, hashes):
    for name, expected in hashes.items():
        if digest(child(folder, name)) != expected:
            raise ValueError("hash mismatch: " + str(folder / name))


def no_live_writers(workspace):
    """Also catch a numerical child surviving a driver with a stale terminal record."""
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            args = cmdline.read_bytes().decode().rstrip("\0").split("\0")
            cwd = (cmdline.parent / "cwd").resolve()
            for option in ("--out", "--data-root", "--output"):
                if option in args:
                    target = (cwd / args[args.index(option) + 1]).resolve()
                    if target == workspace or workspace in target.parents:
                        raise ValueError("live writer references source workspace: PID " + cmdline.parent.name)
        except (OSError, UnicodeError, IndexError):
            continue


def terminal(record, label, end_key="utc_end"):
    if record.get("state") not in TERMINAL or not record.get(end_key) or "current_attempt" in record:
        raise ValueError("not terminal: " + label)


def lock_suite(lock):
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError("suite writer lock is held; refusing mutable source data")


def case_artifacts(folder, record, sensitivity=False):
    terminal(record, str(folder), "utc_finished" if sensitivity else "utc_end")
    if sensitivity:
        hashes = record.get("artifact_sha256", {})
    else:
        attempts = record.get("attempts", [])
        if not attempts:
            raise ValueError("no terminal attempt evidence: " + str(folder))
        terminal(attempts[-1], str(folder) + " latest attempt")
        hashes = attempts[-1].get("artifacts_sha256", {})
    if not hashes:
        raise ValueError("no recorded terminal artifact hashes: " + str(folder))
    verify(folder, hashes)
    ignored = {"process_status.json"} | ({"checkpoint.tmp", "progress.tmp"} if not sensitivity else set())
    actual = {p.name for p in folder.iterdir() if p.name not in ignored}
    if actual != set(hashes):
        raise ValueError("unrecorded or missing case artifacts: " + str(folder))


def verify_case_record(folder, record, floods, historical_workspace, allow_relocation=False):
    """Keep original terminal records; optionally audit the specific cached-root failure."""
    process_path = folder / "process_status.json"
    process = read(process_path)
    number = record["run"]
    if process.get("run") != number or process.get("attempts") != record.get("attempts"):
        raise ValueError("case and suite terminal records disagree: " + str(number))
    terminal(record, "suite case " + str(number))
    case_artifacts(folder, process)
    if process.get("state") == record.get("state"):
        return None

    error = "all project paths must remain inside this /data project: " + str(folder.resolve())
    expected = dict(process, state="incomplete", error=error)
    if not allow_relocation or process.get("state") != "complete" or record != expected:
        raise ValueError("case and suite terminal records disagree: " + str(number))
    attempt = process["attempts"][-1]
    if (attempt.get("state") != "complete" or attempt.get("exit_code") != 0
            or process.get("exit_code") != 0 or attempt.get("requested_floods") != floods):
        raise ValueError("relocation audit requires a completed attempt at the requested flood count")
    command = attempt.get("command", [])
    if command != process.get("command") or command.count("--out") != 1:
        raise ValueError("relocation audit requires identical recorded output commands")
    position = command.index("--out") + 1
    if position == len(command) or not historical_workspace:
        raise ValueError("relocation audit lacks the historical workspace or output path")
    historical = Path(historical_workspace) / "data" / ("run%02d" % number)
    if (not historical.is_absolute() or command[position] != str(historical)
            or historical == folder.resolve() or historical.resolve(strict=True) != folder.resolve()):
        raise ValueError("historical output alias does not resolve to the relocated case")
    checked = completion(folder, floods)
    return dict(run=number, historical_output=str(historical), verified_source_output=str(folder.resolve()),
                packaged_case="data/run%02d" % number, original_suite_state=record["state"],
                original_process_state=process["state"], original_suite_error=record["error"],
                process_record_sha256=digest(process_path), completion=checked,
                scope="separate saved-data recheck of histories and final/peak snapshot metadata; "
                      "checkpoint checked nonempty, not decoded; no scientific acceptance")


def inspect_rebuild(rebuild, allow_relocation=False):
    """Verify the actual clean-wrapper, suite and sensitivity manifest shapes."""
    outer = read(rebuild / "rebuild_manifest.json")
    terminal(outer, "outer rebuild")
    workspace = rebuild / "workspace"
    no_live_writers(workspace)
    stages = {row["name"]: row for row in outer["stages"]}
    for name, stage in stages.items():
        if stage.get("state") not in TERMINAL | {"skipped"}:
            raise ValueError("nonterminal original stage: " + name)
        if "log" in stage:
            verify(rebuild, {stage["log"]: stage["log_sha256"]})
    if stages.get("checks", {}).get("exit_code") != 0 or stages["checks"]["state"] != "complete":
        raise ValueError("the original exact-executable checks did not pass")
    if any(name not in stages for name in ("simulations", "sensitivity")):
        raise ValueError("original numerical stages are missing")
    source = outer["source_sha256"]
    if not {"src/main.cpp", "src/model.hpp", "config/physics.txt", "config/runs.csv", "scripts/run_suite.py"} <= set(source):
        raise ValueError("original numerical source identities are incomplete")
    verify(workspace, source)
    # Later code may change reporting, but must describe this same numerical model.
    numerical = {name: value for name, value in source.items() if name.startswith(("src/", "config/"))}
    verify(ROOT, numerical)
    suite = read(workspace / "data/suite_manifest.json")
    terminal(suite, "numerical suite")
    if suite.get("format") != 2 or suite.get("requested_floods") != 580 or set(suite.get("selected_runs", [])) != set(range(1, 32)):
        raise ValueError("expected the documented 31-case, 580-flood suite")
    provenance = read(workspace / "data/_inputs/provenance.json")
    if suite["provenance"] != provenance or provenance.get("compile_exit_code") != 0:
        raise ValueError("suite and frozen compilation provenance disagree")
    verify(workspace / "data/_inputs", provenance["frozen_sha256"])
    if any(provenance[key] != provenance["frozen_sha256"][name] for key, name in
           (("binary_sha256", "ridge"), ("config_sha256", "physics.txt"), ("runs_table_sha256", "runs.csv"))):
        raise ValueError("frozen input identity fields disagree")
    verify(workspace / "data/_inputs", {"compile.log": provenance["compile_log_sha256"]})
    if provenance["source_sha256"] != {name: value for name, value in source.items() if name.startswith("src/")}:
        raise ValueError("compiled source differs from original staged source")
    if any(provenance["frozen_sha256"][frozen] != source[original] for frozen, original in
           (("physics.txt", "config/physics.txt"), ("runs.csv", "config/runs.csv"), ("run_suite.py", "scripts/run_suite.py"))):
        raise ValueError("frozen numerical inputs differ from original staged inputs")
    verify(workspace, {"validation/kernel.txt": stages["checks"]["log_sha256"],
                       "build/ridge": provenance["binary_sha256"]})
    cases = {row["run"]: row for row in suite["cases"]}
    if len(suite["cases"]) != 31 or set(cases) != set(range(1, 32)):
        raise ValueError("suite does not contain each requested case exactly once")
    reconciliations = []
    for number, record in cases.items():
        folder = workspace / "data" / ("run%02d" % number)
        evidence = verify_case_record(folder, record, suite["requested_floods"],
                                      outer.get("workspace"), allow_relocation)
        if evidence:
            reconciliations.append(evidence)
    sensitivity = workspace / "validation/runs"
    validation = read(sensitivity / "validation_manifest.json")
    if not validation.get("utc_finished"):
        raise ValueError("sensitivity driver is not terminal")
    vp = read(sensitivity / "_inputs/provenance.json")
    if validation["provenance"] != vp or vp["binary_sha256"] != provenance["binary_sha256"] or vp["source_sha256"] != provenance["source_sha256"]:
        raise ValueError("sensitivity and production source/binary identities disagree")
    verify(workspace, {vp["executable"]: vp["binary_sha256"]})
    verify(sensitivity / "_inputs", {name: vp[name + "_sha256"] for name in ("physics.txt", "runs.csv")})
    if any(vp[name + "_sha256"] != provenance["frozen_sha256"][name] for name in ("physics.txt", "runs.csv")):
        raise ValueError("sensitivity base inputs differ from production inputs")
    vcases = {row["name"]: row for row in validation["cases"]}
    if len(validation["cases"]) != 8 or set(vcases) != SENSITIVITY:
        raise ValueError("all eight terminal sensitivity records are required")
    for name, record in vcases.items():
        folder = sensitivity / name
        if read(folder / "process_status.json") != record or record["binary_sha256"] != provenance["binary_sha256"]:
            raise ValueError("sensitivity process provenance disagrees: " + name)
        case_artifacts(folder, record, True)
    if "pdf" in outer:
        verify(rebuild, {outer["pdf"]: outer["pdf_sha256"]})
    return outer, suite, validation, reconciliations


def files(folder):
    if not folder.exists():
        return []
    paths = list(folder.rglob("*"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("symlink in archive tree: " + str(folder))
    return sorted(p for p in paths if p.is_file())


def source_files():
    paths = []
    for name in ("src", "tests", "config", "scripts", "docs"):
        paths.extend(p for p in files(ROOT / name) if "__pycache__" not in p.parts)
    # Validation evidence is selected from version control, excluding local binaries.
    tracked = subprocess.check_output(["git", "ls-files", "-z", "validation/stress", "validation/first-flood-audit-002",
                                       "validation/production-recycling-002",
                                       "validation/production-preview-20261011",
                                       "validation/rejected-rebuild-001", "validation/migration-linear",
                                       "validation/relocation-20261010"], cwd=str(ROOT))
    paths.extend(ROOT / name for name in tracked.decode().split("\0") if name)
    paths.extend(p for p in (ROOT / "report").iterdir() if p.is_file() and p.suffix in (".tex", ".bib", ".py", ".sh"))
    paths.append(ROOT / "report/generated/implementation.tex")
    paths.extend(ROOT / name for name in ("Makefile", "README.md", "AGENTS.md", ".gitignore", "brad-lipovsky-academic-style-guide.md") if (ROOT / name).is_file())
    return sorted(set(paths))


def environment(workspace):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for key, name in (("TMPDIR", "tmp"), ("XDG_CACHE_HOME", "tmp/cache"), ("MPLCONFIGDIR", "tmp/matplotlib"),
                      ("PYTHONPYCACHEPREFIX", "tmp/pycache"), ("CCACHE_DIR", "tmp/ccache")):
        path = workspace / name
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    return env


def stage(output, record, name, command):
    workspace = output / "workspace"
    before = output_hashes(workspace)
    item = dict(name=name, command=command, utc_start=utc(), state="running", log="logs/" + name + ".log")
    record["commands"].append(item)
    save(output / "postprocess_manifest.json", record)
    start = time.monotonic()
    print("saved-data report stage: " + name, flush=True)
    with (output / item["log"]).open("w") as log:
        try:
            code = subprocess.run(command, cwd=str(workspace), env=environment(workspace), stdout=log, stderr=subprocess.STDOUT).returncode
        except OSError as error:
            log.write(str(error) + "\n")
            code = 127
    item.update(exit_code=code, state="complete" if code == 0 else "incomplete", utc_end=utc(),
                wall_seconds=time.monotonic() - start, log_sha256=digest(output / item["log"]))
    after = output_hashes(workspace)
    item["output_sha256"] = {k: v for k, v in after.items() if before.get(k) != v}
    item["removed_outputs"] = sorted(set(before) - set(after))
    save(output / "postprocess_manifest.json", record)
    return code


def output_hashes(workspace):
    paths = files(workspace / "figures") + files(workspace / "report/generated")
    paths.extend(p for p in (workspace / "report/report.pdf", workspace / "validation/report_summary.json") if p.exists())
    return {str(p.relative_to(workspace)): digest(p) for p in paths}


def execution_tex(output, record):
    # Do not claim that these later processors ran in the original clean execution.
    state = record["original_rebuild_state"]
    text = ("This report was generated later from verified saved numerical data. "
            "The original clean rebuild ended with state \\texttt{" + state + "}. "
            "Its unchanged manifest, stage logs and available original PDF are preserved in the "
            "package's \\texttt{original/} directory. The separate "
            "\\texttt{postprocess\\_manifest.json} records the numerical input hashes, later source, "
            "commands, exit codes and output hashes. No model simulation was run by this reporting procedure.\\par\n"
            "Later stages before this PDF compilation:\\par\n\\begin{tabular}{lll}Stage & State & Exit code \\\\ \\hline\n")
    for item in record["commands"]:
        text += "{} & {} & {} \\\\\n".format(item["name"], item["state"], item.get("exit_code", "pending"))
    text += ("\\end{tabular}\\par\nThe external manifest records subsequent report compilation. "
             "A compiled PDF or complete numerical coverage does not establish scientific agreement; "
             "the maintained panel ledger records that assessment.\n")
    reconciliations = record.get("relocation_reconciliations", [])
    if reconciliations:
        text += ("\\par A separate relocation audit rechecked " + str(len(reconciliations)) +
                 " production cases whose original suite records say incomplete while their "
                 "process records say complete. Only the exact failure of the cached project-path "
                 "check was accepted. The historical output aliases resolved to the current cases; "
                 "recorded artifact hashes, complete histories, finite conservation diagnostics, "
                 "and final and day-12 snapshot metadata passed independent checks. "
                 "The checkpoint check establishes only a nonempty file, not a decoded valid state. "
                 "The separate manifest retains both states, paths and errors; all original records "
                 "and the original rebuild outcome remain unchanged. This audit establishes "
                 "neither grid convergence nor manuscript agreement.\n")
    (output / "workspace/report/generated/rebuild.tex").write_text(text)


def finalize(rebuild, output, allow_relocation=False):
    if output.exists():
        raise ValueError("choose a new output directory; existing packages are preserved")
    # Hold the existing suite lock read-only; do not alter frozen files or start jobs.
    with (rebuild / "workspace/data/.suite.lock").open("rb") as lock:
        lock_suite(lock)
        outer, suite, validation, reconciliations = inspect_rebuild(rebuild, allow_relocation)
        original_workspace = rebuild / "workspace"
        inputs = files(original_workspace / "data") + files(original_workspace / "validation/runs")
        inputs = [p for p in inputs if p.name != ".suite.lock" and not (
            p.parent.parent == original_workspace / "data" and p.parent.name.startswith("run")
            and p.name in ("checkpoint.tmp", "progress.tmp"))]
        inputs += [original_workspace / "validation/kernel.txt", original_workspace / validation["provenance"]["executable"]]
        input_hashes = {str(p.relative_to(original_workspace)): digest(p) for p in inputs}
        sources = source_files()
        source_hashes = {str(p.relative_to(ROOT)): digest(p) for p in sources}
        originals = [rebuild / "rebuild_manifest.json"]
        originals += [child(original_workspace, name) for name in outer["source_sha256"]]
        originals += [child(rebuild, stage["log"]) for stage in outer["stages"] if "log" in stage]
        originals += files(original_workspace / "figures") + files(original_workspace / "report/generated")
        originals += [p for p in (original_workspace / "report/report.pdf", rebuild / "interruption_reason.json") if p.exists()]
        original_hashes = {str(p.relative_to(rebuild)): digest(p) for p in sorted(set(originals))}
        record = dict(format=1, scope="later saved-data postprocessing; not a new numerical rebuild",
                      utc_start=utc(), state="copying", original_rebuild=str(rebuild),
                      original_rebuild_state=outer["state"], original_manifest_sha256=digest(rebuild / "rebuild_manifest.json"),
                      original_binary_sha256=suite["provenance"]["binary_sha256"],
                      original_case_states={str(c["run"]): c["state"] for c in suite["cases"]},
                      original_sensitivity_states={c["name"]: c["state"] for c in validation["cases"]},
                      relocation_reconciliations=reconciliations,
                      original_files_sha256=original_hashes, input_sha256=input_hashes,
                      source_sha256=source_hashes, source_revision=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT)).decode().strip(),
                      source_worktree_status=subprocess.check_output(["git", "status", "--porcelain"], cwd=str(ROOT)).decode(),
                      commands=[], scientific_acceptance="not determined automatically; review all 13 panels",
                      artifact_verification_scope="recorded latest terminal case attempts and frozen inputs; other copied evidence hashed at finalization")
        output.mkdir(parents=True)
        (output / "logs").mkdir()
        save(output / "postprocess_manifest.json", record)
        for base, names, destination in ((ROOT, source_hashes, output / "workspace"),
                                         (original_workspace, input_hashes, output / "workspace"),
                                         (rebuild, original_hashes, output / "original")):
            for name, expected in names.items():
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(base / name), str(target))
                if digest(target) != expected:
                    raise ValueError("copy changed: " + name)
            verify(base, names)
        if inspect_rebuild(rebuild, allow_relocation)[3] != reconciliations:
            raise ValueError("relocation evidence changed during copying")
    workspace = output / "workspace"
    (workspace / "report/generated").mkdir(parents=True, exist_ok=True)
    record["state"] = "postprocessing"
    commands = [
        ("versions", [sys.executable, "-c", "import sys,numpy,matplotlib; print(sys.version); print('numpy',numpy.__version__); print('matplotlib',matplotlib.__version__)"]),
        ("tex-version", ["pdflatex", "--version"]),
        ("figures", [sys.executable, "scripts/plot.py", "--data-root", "data", "--output", "figures", "--strict"]),
        ("comparison", [sys.executable, "scripts/compare.py", "--data-root", "data", "--figures", "figures", "--output", "figures", "--strict"]),
        ("inundation", [sys.executable, "scripts/inundation_metrics.py", "--data-root", "data", "--output", "figures/inundation_metrics.json", "--strict"]),
        ("planforms", [sys.executable, "scripts/planform_metrics.py", "--data-root", "data", "--output", "figures", "--strict"]),
        ("first-flood-figure", [sys.executable, "scripts/plot_first_flood.py"]),
        ("diagnostic-sensitivity", [sys.executable, "scripts/diagnostic_sensitivity.py"]),
        ("validation-report", [sys.executable, "report/make_validation.py", "--data-root", "data", "--sensitivity-root", "validation/runs", "--checks-exit-code", "0", "--strict"])]
    for name, command in commands:
        stage(output, record, name, command)
    execution_tex(output, record)
    stage(output, record, "report", ["bash", "report/build.sh"])
    verify(workspace, input_hashes)
    verify(workspace, source_hashes)
    record.update(utc_end=utc(), output_sha256=output_hashes(workspace),
                  state="complete" if all(c["exit_code"] == 0 for c in record["commands"]) else "incomplete")
    save(output / "postprocess_manifest.json", record)
    return 0 if record["state"] == "complete" else 2


def render_only(output):
    record = read(output / "postprocess_manifest.json")
    terminal(record, "saved-data package")
    workspace = output / "workspace"
    no_live_writers(workspace)
    verify(workspace, record["input_sha256"])
    verify(output / "original", record["original_files_sha256"])
    verify(workspace, {k: v for k, v in record["source_sha256"].items() if k != "docs/panels.csv"})
    verify(workspace, record["output_sha256"])
    number = len([c for c in record["commands"] if c["name"].startswith("assessment-render-")]) + 1
    name = "assessment-render-%03d" % number
    archive = output / "renders" / name
    archive.mkdir(parents=True)
    shutil.copy2(str(output / "postprocess_manifest.json"), str(archive / "manifest-before.json"))
    if (workspace / "report/report.pdf").exists():
        shutil.copy2(str(workspace / "report/report.pdf"), str(archive / "report-before.pdf"))
    shutil.copy2(str(workspace / "docs/panels.csv"), str(archive / "panels.csv"))
    shutil.copy2(str(Path(__file__).resolve()), str(archive / "finalize_report.py"))
    previous_state = record["state"]
    record["state"] = "rendering"
    code = stage(output, record, name, ["bash", "report/build.sh"])
    # Assessments may change generated report inputs, never figures or model data.
    verify(workspace, record["input_sha256"])
    verify(workspace, {k: v for k, v in record["output_sha256"].items() if k.startswith("figures/")})
    if (workspace / "report/report.pdf").exists():
        shutil.copy2(str(workspace / "report/report.pdf"), str(archive / "report.pdf"))
    record["commands"][-1]["assessment_ledger_sha256"] = digest(archive / "panels.csv")
    record["commands"][-1]["procedure_sha256"] = digest(archive / "finalize_report.py")
    record["commands"][-1]["outputs_sha256"] = {str(p.relative_to(output)): digest(p) for p in files(archive)}
    record.update(utc_end=utc(), output_sha256=output_hashes(workspace))
    record["state"] = "incomplete" if code else previous_state
    save(output / "postprocess_manifest.json", record)
    return 0 if record["state"] == "complete" and code == 0 else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", default="tmp/full-rebuild-002")
    parser.add_argument("--output", default="deliverables/final")
    parser.add_argument("--reconcile-relocation", action="store_true",
                        help="audit only exact cached-root terminal failures; preserve original states")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true", help="verify terminal saved evidence without copying or generating output")
    mode.add_argument("--render-only", action="store_true", help="rebuild a staged report after editing only its panel ledger; preserve figure bytes")
    args = parser.parse_args()
    if args.render_only and args.reconcile_relocation:
        parser.error("render-only uses the already archived relocation audit")
    rebuild, output = (ROOT / args.rebuild).resolve(), (ROOT / args.output).resolve()
    if not str(ROOT).startswith(tuple("/data/data%d/" % n for n in range(8))):
        parser.error("this procedure requires a /data/data[n] project")
    packaged_render = args.render_only and ROOT == output / "workspace"
    if ROOT not in output.parents and not packaged_render:
        parser.error("output must remain inside the project (or its own packaged parent for render-only)")
    if not args.render_only and (ROOT not in rebuild.parents or rebuild == output or rebuild in output.parents or output in rebuild.parents):
        parser.error("use separate project-local rebuild and package directories")
    existed = output.exists()
    try:
        if args.render_only:
            return render_only(output)
        if args.check_only:
            with (rebuild / "workspace/data/.suite.lock").open("rb") as lock:
                lock_suite(lock)
                evidence = inspect_rebuild(rebuild, args.reconcile_relocation)
            print("Terminal saved evidence verified; scientific assessment remains separate.")
            if evidence[3]:
                print("Relocation discrepancies independently rechecked: " + str(len(evidence[3])))
            return 0
        return finalize(rebuild, output, args.reconcile_relocation)
    except (OSError, ValueError, KeyError, TypeError, struct.error, subprocess.SubprocessError) as error:
        # Leave any partial package available for inspection, never label it complete.
        manifest_path = output / "postprocess_manifest.json"
        if not args.check_only and not args.render_only and not existed and manifest_path.exists():
            record = read(manifest_path)
            record.update(state="failed", utc_end=utc(), error=str(error))
            save(manifest_path, record)
        print("REFUSED: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
