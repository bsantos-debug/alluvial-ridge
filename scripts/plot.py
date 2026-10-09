#!/usr/bin/env python3
"""Plot the 13 manuscript panels from saved independent-model output only."""
import argparse
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
# Set before importing numerical/plotting packages, including during import tests.
for key, name in (("MPLCONFIGDIR", "matplotlib"), ("XDG_CACHE_HOME", "cache"),
                  ("TMPDIR", "plot-tmp"), ("PYTHONPYCACHEPREFIX", "pycache")):
    directory = ROOT / "tmp" / name
    directory.mkdir(parents=True, exist_ok=True)
    os.environ[key] = str(directory)
sys.dont_write_bytecode = True

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection


DEPOSITS = [("1A", 11, 61), ("1B", 11, 251), ("1C", 11, 501),
            ("1D", 11, 562), ("1E", 17, 562), ("1F", 3, 562)]
SECTIONS = [("2A", 22), ("2B", 10), ("2C", 3), ("2D", 15)]
TIMES = [50, 225, 400, 580]
COLORS = {0.00003: "#7b3294", 0.0003: "#0072b2", 0.003: "#d55e00", 0.01: "#222222"}


def csv_rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def relative(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_run(data_root, config):
    run = int(config["run"])
    folder = data_root / ("run%02d" % run)
    result = dict(run=run, folder=folder, config=config, records={}, notes=[], sources=[])
    parameters = {}
    path = folder / "parameters.txt"
    if path.exists():
        result["sources"].append(path)
        for line in path.read_text().splitlines():
            pair = line.split(None, 1)
            if len(pair) == 2:
                parameters[pair[0]] = pair[1]
    expected = {"run": run, "A": float(config["A_m_per_flood"]), "C": float(config["C"]),
                "E": float(config["E"]), "fine": int(config["load"] == "fine"),
                "dx": 250, "length": 72000, "width": 48000, "duration": 20 * 86400}
    for key, value in expected.items():
        try:
            actual = float(parameters[key])
            if not math.isclose(actual, value, rel_tol=1e-10, abs_tol=1e-12):
                result["notes"].append("{}={} (requested {})".format(key, actual, value))
        except (KeyError, ValueError):
            result["notes"].append("{} unrecorded".format(key))
    result["parameters"] = parameters
    path = folder / "summary.csv"
    if path.exists():
        result["sources"].append(path)
        for row in csv_rows(path):
            try:
                required = ("flood", "alpha", "interface_fraction", "mean_water", "beta", "ridge_height", "channel_depth", "sinuosity")
                if not all(key in row for key in required):
                    raise ValueError("required diagnostic column missing")
                flood = int(row["flood"])
                if flood < 1 or flood in result["records"]:
                    raise ValueError("duplicate or invalid flood number")
                parsed = {key: float(value) for key, value in row.items()}
                result["records"][flood] = parsed
            except (TypeError, ValueError) as error:
                result["notes"].append("invalid summary row: {}".format(error))
    else:
        result["notes"].append("summary.csv missing")
    result["series_complete"] = all(f in result["records"] for f in range(1, 581))
    return result


def snapshot(run, flood):
    path = run["folder"] / ("fields_%04d.bin" % flood)
    channel_path = run["folder"] / ("channel_%04d.csv" % flood)
    info = dict(data=None, sources=[], notes=[], completed=flood in run["records"])
    if not path.exists():
        info["notes"].append("requested flood {} snapshot missing".format(flood))
        return info
    info["sources"].append(path)
    try:
        with path.open("rb") as stream:
            header = np.fromfile(stream, dtype=np.int32, count=4)
            scalars = np.fromfile(stream, dtype=np.float64, count=3)
            if len(header) != 4 or len(scalars) != 3:
                raise ValueError("truncated header")
            nx, ny, nchan, recorded_flood = (int(value) for value in header)
            dx, clock, slope = scalars
            if min(nx, ny) < 1 or nx * ny > 100000000 or recorded_flood != flood or dx <= 0:
                raise ValueError("invalid dimensions or flood number")
            values = np.fromfile(stream, dtype=np.float32)
        if values.size != nx * ny * 4:
            raise ValueError("snapshot byte length does not match its dimensions")
        values = values.reshape(ny, nx, 4)
        if not np.isfinite(values).all() or not np.isfinite(scalars).all():
            raise ValueError("nonfinite snapshot values")
        if np.min(values[:, :, 1:3]) < -1e-8:
            raise ValueError("negative water depth or deposit thickness")
        if not np.all((values[:, :, 3] == 0) | (values[:, :, 3] == 1)):
            raise ValueError("channel mask is not binary")
        if not channel_path.exists():
            info["notes"].append("channel coordinate file missing")
        else:
            info["sources"].append(channel_path)
            channel = csv_rows(channel_path)
            if len(channel) != nchan:
                raise ValueError("channel node count disagrees with snapshot")
        if not info["completed"]:
            info["notes"].append("flood not complete: absent from summary.csv")
        else:
            try:
                expected_clock = flood * float(run["parameters"]["duration"])
                if not math.isclose(clock, expected_clock, rel_tol=1e-9, abs_tol=1e-4):
                    info["notes"].append("snapshot clock does not reach the requested complete flood")
            except (KeyError, ValueError):
                info["notes"].append("snapshot time cannot be checked without duration metadata")
        for key, actual in (("dx", dx), ("length", nx * dx), ("width", ny * dx)):
            expected = {"dx": 250, "length": 72000, "width": 48000}[key]
            if not math.isclose(actual, expected):
                info["notes"].append("snapshot {}={} (requested {})".format(key, actual, expected))
        info.update(data=values, dx=dx, clock=clock, slope=slope, nx=nx, ny=ny)
    except (OSError, ValueError) as error:
        info["notes"].append("invalid snapshot: {}".format(error))
    return info


def window_stat(run, column, first, last, operation):
    values = [run["records"].get(flood, {}).get(column, float("nan"))
              for flood in range(first, last + 1)]
    valid = int(np.isfinite(values).sum())
    if valid != last - first + 1:
        return None, valid
    if operation == "mean":
        return float(np.mean(values)), valid
    # NumPy 1.19 uses the interpolation keyword; linear is recorded explicitly.
    return float(np.percentile(values, 95, interpolation="linear")), valid


def interface_segments(mask, dx):
    """Exactly the internal Cartesian faces used by the model's interface metric."""
    j, i = np.nonzero(mask[:, 1:] != mask[:, :-1])
    segments = [[((a + 1) * dx, b * dx), ((a + 1) * dx, (b + 1) * dx)]
                for b, a in zip(j, i)]
    j, i = np.nonzero(mask[1:, :] != mask[:-1, :])
    segments.extend([[(a * dx, (b + 1) * dx), ((a + 1) * dx, (b + 1) * dx)]
                     for b, a in zip(j, i)])
    return np.asarray(segments, dtype=float).reshape(-1, 2, 2) / 1000


def panel_record(panel, runs, infos, notes=()):
    available = sum(info["data"] is not None for info in infos)
    problems = list(notes)
    sources = []
    for run in runs:
        problems.extend(run["notes"])
        sources.extend(run["sources"])
    for info in infos:
        problems.extend(info["notes"])
        sources.extend(info["sources"])
    status = "complete requested data" if available == len(infos) and not problems else "partial requested data"
    if not available:
        status = "no requested numerical data"
    return dict(panel=panel, data_status=status, source_files=";".join(sorted({relative(p) for p in sources})),
                notes="; ".join(dict.fromkeys(problems)))


def save_figure(fig, output, number):
    fig.savefig(str(output / ("figure%d.pdf" % number)), bbox_inches="tight")
    fig.savefig(str(output / ("figure%d.png" % number)), dpi=150, bbox_inches="tight")
    plt.close(fig)


def missing(ax, text):
    ax.set_facecolor("#f2f2f2")
    ax.text(.5, .5, text, ha="center", va="center", transform=ax.transAxes,
            fontsize=9, wrap=True, color="#444444")


def plots(data_root, output, configs):
    runs = {int(c["run"]): read_run(data_root, c) for c in configs}
    panels, deposit_rows, section_rows, metric_rows = [], [], [], []
    used_sources = {ROOT / "config" / "runs.csv", Path(__file__).resolve()}
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
                         "pdf.fonttype": 42, "savefig.facecolor": "white"})

    fig, axes = plt.subplots(2, 3, figsize=(13, 7.6), constrained_layout=True)
    cmap = copy.copy(plt.get_cmap("viridis"))
    cmap.set_under("#145b25")
    cmap.set_bad("black")
    image = None
    for ax, (panel, number, flood) in zip(axes.flat, DEPOSITS):
        run = runs[number]
        info = snapshot(run, flood)
        used_sources.update(info["sources"] + run["sources"])
        record = panel_record(panel, [run], [info])
        panels.append(record)
        cfg = run["config"]
        ax.set_title("{}  Run {:02d}, flood {}\nA={}, C={}".format(panel, number, flood, cfg["A_m_per_flood"], cfg["C"]))
        ax.set(xlabel="Downstream distance (km)", ylabel="Transverse distance (km)", xlim=(0, 72), ylim=(0, 48))
        if info["data"] is None:
            missing(ax, "No saved result for the requested flood.\n{}".format(relative(run["folder"] / ("fields_%04d.bin" % flood))))
            continue
        field, dx = info["data"], info["dx"]
        mask = field[:, :, 3].astype(bool)
        deposit = np.ma.array(field[:, :, 2], mask=mask)
        image = ax.imshow(deposit, origin="lower", extent=(0, info["nx"] * dx / 1000, 0, info["ny"] * dx / 1000),
                          vmin=1e-6, vmax=.5, cmap=cmap, interpolation="nearest", aspect="equal")
        ax.set_xlim(0, info["nx"] * dx / 1000)
        ax.set_ylim(0, info["ny"] * dx / 1000)
        if panel == "1E":
            ax.add_collection(LineCollection(interface_segments(mask, dx), colors="#d936d9", linewidths=.35))
        if record["data_status"] != "complete requested data":
            ax.text(.02, .02, "PARTIAL: see panel_status.csv", transform=ax.transAxes, color="#b22222",
                    bbox=dict(facecolor="white", alpha=.9, edgecolor="none"), fontsize=8)
        fp = ~mask
        d = field[:, :, 2][fp].astype(float)
        deposited = (field[:, :, 2] >= 1e-6) & fp
        row = dict(panel=panel, run=number, flood=flood, completed_flood=int(info["completed"]),
                   dx_m=dx, deposited_area_km2=float(deposited.sum() * dx * dx / 1e6),
                   deposited_volume_m3=float(d.sum() * dx * dx),
                   deposit_max_m=float(d.max()) if d.size else "",
                   deposit_p95_m=float(np.percentile(d, 95)) if d.size else "",
                   above_color_scale_cells=int((d > .5).sum()), source=relative(info["sources"][0]))
        weights = np.where(fp, field[:, :, 2], 0).sum(axis=1).astype(float)
        y = (np.arange(info["ny"]) + .5) * dx
        mean = float(np.dot(weights, y) / weights.sum()) if weights.sum() else float("nan")
        row["deposit_transverse_std_m"] = float(np.sqrt(np.dot(weights, (y - mean) ** 2) / weights.sum())) if weights.sum() else ""
        row["sinuosity"] = run["records"].get(flood, {}).get("sinuosity", "")
        deposit_rows.append(row)
    if image is not None:
        fig.colorbar(image, ax=list(axes.flat), shrink=.8, pad=.02, label="Individual-flood deposit thickness (m)", extend="max")
    fig.suptitle("Independent numerical output: manuscript Figure 1\nGreen: deposit <10$^{-6}$ m; black: active channel; magenta in 1E: diagnostic interface", fontsize=12)
    save_figure(fig, output, 1)

    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    colors = ["#222222", "#777777", "#e69f00", "#b22222"]
    styles = ["-", ":", "--", "-"]
    for ax, (panel, number) in zip(axes.flat, SECTIONS):
        run = runs[number]
        infos = [snapshot(run, flood) for flood in TIMES]
        for info in infos:
            used_sources.update(info["sources"])
        used_sources.update(run["sources"])
        record = panel_record(panel, [run], infos)
        panels.append(record)
        absent = []
        xpos = []
        for flood, info, color, style in zip(TIMES, infos, colors, styles):
            if info["data"] is None:
                absent.append(flood)
                continue
            field, dx = info["data"], info["dx"]
            column = info["nx"] // 2
            x = (column + .5) * dx
            ypos = (np.arange(info["ny"]) + .5) * dx
            z, mask = field[:, column, 0], field[:, column, 3].astype(bool)
            xpos.append(x / 1000)
            suffix = " (partial flood)" if not info["completed"] else ""
            ax.plot(ypos / 1000, z, color=color, linestyle=style, linewidth=1, label="Flood {}{}".format(flood, suffix))
            if flood == 580:
                segments = [[((y - .5 * dx) / 1000, height), ((y + .5 * dx) / 1000, height)]
                            for y, height, active in zip(ypos, z, mask) if active]
                ax.add_collection(LineCollection(segments, colors="#00a7c4", linewidths=2.2, label="Active bed at flood 580"))
            for y, height, active in zip(ypos, z, mask):
                section_rows.append(dict(panel=panel, run=number, flood=flood, completed_flood=int(info["completed"]),
                                         downstream_m=x, transverse_m=y, elevation_m=float(height),
                                         active_channel=int(active), source=relative(info["sources"][0])))
        cfg = run["config"]
        location = "x={} km".format(",".join("{:g}".format(x) for x in sorted(set(xpos)))) if xpos else "central grid column"
        ax.set_title("{}  Run {:02d}; A={}, C={}\n{}".format(panel, number, cfg["A_m_per_flood"], cfg["C"], location))
        widths = [i["ny"] * i["dx"] / 1000 for i in infos if i["data"] is not None]
        ax.set(xlabel="Transverse distance (km)", ylabel="Elevation (m, model datum)", xlim=(0, max(widths) if widths else 48))
        if len(absent) == 4:
            missing(ax, "No saved sections for floods 50, 225, 400, 580.")
        else:
            ax.legend(loc="best", fontsize=7)
            if absent:
                ax.text(.02, .98, "Missing floods: " + ", ".join(map(str, absent)), transform=ax.transAxes, va="top", color="#b22222", fontsize=8)
            if record["data_status"] != "complete requested data":
                ax.text(.98, .02, "PARTIAL DATA", ha="right", transform=ax.transAxes, color="#b22222", fontsize=8,
                        bbox=dict(facecolor="white", alpha=.9, edgecolor="none"))
        ax.grid(alpha=.2)
    fig.suptitle("Independent numerical output: manuscript Figure 2\nRaw saved elevations; no published datum shift or synthetic late sections", fontsize=12)
    save_figure(fig, output, 2)

    for number, run in sorted(runs.items()):
        used_sources.update(run["sources"])
        beta, nbeta = window_stat(run, "beta", 561, 580, "mean")
        alpha, nalpha = window_stat(run, "alpha", 381, 580, "percentile")
        run["beta_mean"], run["alpha95"] = beta, alpha
        cfg = run["config"]
        metric_rows.append(dict(run=number, A_m_per_flood=cfg["A_m_per_flood"], C=cfg["C"], E=cfg["E"], load=cfg["load"],
                                completed_floods=len(run["records"]), last_completed_flood=max(run["records"], default=0),
                                complete_1_to_580=int(run["series_complete"]), beta_mean_561_580=beta if beta is not None else "",
                                beta_finite_count=nbeta, alpha95_381_580=alpha if alpha is not None else "",
                                alpha_finite_count=nalpha, configuration_verified=int(not run["notes"]),
                                notes="; ".join(run["notes"])))
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), constrained_layout=True)
    groups = sorted({(float(c["C"]), float(c["E"]), c["load"]) for c in configs})
    for ax, column in ((axes[0], "beta_mean"), (axes[2], "alpha95")):
        for C, E, load in groups:
            selected = [r for r in runs.values() if float(r["config"]["C"]) == C
                        and float(r["config"]["E"]) == E and r["config"]["load"] == load and r[column] is not None]
            label = "C={:g}{}{}".format(C, "; fine" if load == "fine" else "", "; E={:g}".format(E) if E != 1 else "")
            marker = "+" if E < 1 else "x" if E > 1 else "D" if load == "fine" else "s"
            ax.scatter([float(r["config"]["A_m_per_flood"]) for r in selected], [r[column] for r in selected],
                       c=COLORS[C], marker=marker, s=35, label=label)
            partial = [r for r in selected if r["notes"] or not r["series_complete"]]
            if partial:
                ax.scatter([float(r["config"]["A_m_per_flood"]) for r in partial], [r[column] for r in partial],
                           facecolors="none", edgecolors="#b22222", s=95, linewidths=.8)
        count = sum(r[column] is not None for r in runs.values())
        ax.text(.02, .98, "{}/31 required windows available".format(count), transform=ax.transAxes, va="top", fontsize=8)
        ax.set(xlabel="Bed aggradation A (m/flood)", xlim=(-.001, .04))
        ax.grid(alpha=.2)
    axes[0].axhline(1, color="#888888", linestyle="--", linewidth=.8)
    axes[0].set(title="3A  Final-20-flood mean", ylabel=r"Super-elevation ratio $\beta$")
    axes[0].legend(fontsize=6, loc="best")
    if not any(r["beta_mean"] is not None for r in runs.values()):
        axes[0].set_ylim(0, 3.5)
        missing(axes[0], "No complete finite beta window\nfor floods 561–580.")
    axes[2].set(title="3C  Final-200-flood 95th percentile", ylabel=r"$\alpha_{95}$ (m)")
    if not any(r["alpha95"] is not None for r in runs.values()):
        axes[2].set_ylim(1, 10)
        missing(axes[2], "No complete finite alpha window\nfor floods 381–580.")
    elif all(r["alpha95"] is None or r["alpha95"] > 0 for r in runs.values()):
        axes[2].set_yscale("log")
    alpha_available, alpha_positive = 0, True
    for number in [20, 15, 7]:
        run = runs[number]
        floods = np.arange(1, 581)
        values = np.array([run["records"].get(int(f), {}).get("alpha", float("nan")) for f in floods])
        alpha_available += int(np.isfinite(values).sum())
        alpha_positive = alpha_positive and bool(np.all(values[np.isfinite(values)] > 0))
        C = float(run["config"]["C"])
        axes[1].plot(floods, values, color=COLORS[C], linewidth=.6, label="C={:g}".format(C))
    axes[1].set(title="3B  Connectivity at 0.6 flood duration", xlabel="Flood number", ylabel=r"$\alpha$ (m)", xlim=(0, 580))
    axes[1].legend(fontsize=8, loc="best")
    axes[1].grid(alpha=.2)
    if alpha_positive:
        axes[1].set_yscale("log")
    if not alpha_available:
        axes[1].set_ylim(.1, 10)
        missing(axes[1], "No completed-flood alpha values\nfor runs 07, 15, 20.")
    axes[1].text(.02, .98, "{}/1740 finite flood values".format(alpha_available), transform=axes[1].transAxes, va="top", fontsize=8)
    fig.suptitle("Independent numerical output: manuscript Figure 3\nMissing windows remain absent; red rings mark altered or unverified run settings/history", fontsize=12)
    save_figure(fig, output, 3)

    for panel, column, numbers, expected in [("3A", "beta_mean", range(1, 32), 31),
                                              ("3C", "alpha95", range(1, 32), 31)]:
        selected = [runs[n] for n in numbers]
        available = sum(r[column] is not None for r in selected)
        complete = available == expected and all(not r["notes"] and r["series_complete"] for r in selected)
        panels.append(dict(panel=panel, data_status="complete requested data" if complete else "partial requested data" if available else "no requested numerical data",
                           source_files=";".join(sorted({relative(p) for r in selected for p in r["sources"]})),
                           notes="{}/{} complete finite required windows; missing floods and nonfinite values are not filled. See metrics.csv.".format(available, expected)))
    complete = alpha_available == 1740 and all(not runs[n]["notes"] and runs[n]["series_complete"] for n in [7, 15, 20])
    panels.append(dict(panel="3B", data_status="complete requested data" if complete else "partial requested data" if alpha_available else "no requested numerical data",
                       source_files=";".join(sorted({relative(p) for n in [7, 15, 20] for p in runs[n]["sources"]})),
                       notes="{}/1740 finite alpha values. Missing/undefined values create gaps; {} vertical axis.".format(alpha_available, "logarithmic" if alpha_positive else "linear because nonpositive values occur")))

    write_csv(output / "panel_status.csv", sorted(panels, key=lambda p: p["panel"]), ["panel", "data_status", "source_files", "notes"])
    write_csv(output / "metrics.csv", metric_rows, list(metric_rows[0]))
    write_csv(output / "deposit_metrics.csv", deposit_rows,
              ["panel", "run", "flood", "completed_flood", "dx_m", "deposited_area_km2", "deposited_volume_m3",
               "deposit_max_m", "deposit_p95_m", "above_color_scale_cells", "source", "deposit_transverse_std_m", "sinuosity"])
    write_csv(output / "sections.csv", section_rows,
              ["panel", "run", "flood", "completed_flood", "downstream_m", "transverse_m", "elevation_m", "active_channel", "source"])
    manifest = {"command": sys.argv, "python": sys.version, "numpy": np.__version__, "matplotlib": matplotlib.__version__,
                "data_root": relative(data_root), "status_scope": "data availability only; no scientific reproduction claim",
                "alpha_percentile": "NumPy linear interpolation, exactly floods 381–580, all 200 finite",
                "beta_average": "arithmetic mean of per-flood ratios, exactly floods 561–580, all 20 finite",
                "files": {relative(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(used_sources) if p.exists()}}
    (output / "plot_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return panels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data", help="directory containing run01 through run31")
    parser.add_argument("--output", default="figures", help="output directory inside this project")
    parser.add_argument("--strict", action="store_true", help="exit 2 after plotting if any panel lacks its complete requested data")
    args = parser.parse_args()
    data_root, output = Path(args.data_root).resolve(), Path(args.output).resolve()
    if ROOT not in output.parents:
        parser.error("output must remain inside the /data project directory")
    output.mkdir(parents=True, exist_ok=True)
    configs = csv_rows(ROOT / "config" / "runs.csv")
    if len(configs) != 31 or {int(c["run"]) for c in configs} != set(range(1, 32)):
        raise ValueError("expected all 31 documented configuration IDs")
    panels = plots(data_root, output, configs)
    available = sum(p["data_status"] == "complete requested data" for p in panels)
    print("Wrote Figure 1–3 attempts and provenance to {}; {}/13 panels have complete requested data.".format(relative(output), available))
    print("Data availability does not establish agreement with the publication.")
    return 2 if args.strict and available != 13 else 0


if __name__ == "__main__":
    sys.exit(main())
