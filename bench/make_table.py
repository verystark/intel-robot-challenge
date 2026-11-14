"""Merge the newest benchmark results and loop runs into bench/RESULTS.md (the judges' evidence table).

    python3 bench/make_table.py                 # newest results of each kind
    python3 bench/make_table.py --run loop/runs/20261114_150000

Sources:
  bench/results/policy_*.json    bench/policy_bench.py   (latency per policy and device)
  bench/results/anomaly_*.json   bench/anomaly_bench.py  (latency per precision and device)
  loop/runs/*/cycles.jsonl       loop/run_cell.py        (real cycles: times, verdicts, loads)
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "bench" / "results"
OUT = REPO / "bench" / "RESULTS.md"


def newest(pattern: str) -> Path | None:
    files = sorted(RESULTS.glob(pattern))
    return files[-1] if files else None


def cpu_name() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def med(values: list[float]) -> str:
    return f"{statistics.median(values):.1f}" if values else "-"


def policy_section(path: Path) -> list[str]:
    data = json.loads(path.read_text())
    lines = [f"## Policies (OpenVINO), {data['time']}", ""]
    if data.get("contended"):
        lines += [f"> Measured while the laptop was busy ({data['contended']}): re-run on a quiet laptop "
                  "for final numbers.", ""]
    lines += ["| Model | Device | Load + compile | Median per chunk | p95 | Max | Headroom* | GPU / NPU busy | Max temp |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in data["rows"]:
        name = f"{r['model']} ({r['policy']})"
        if "error" in r:
            lines.append(f"| {name} | {r['device']} | {r.get('load_s', '')} | not supported: {r['error'][:80]} | | | | | |")
            continue
        chunk = (r.get("chunk") or [50])[0]
        budget = chunk * 0.5 / 30 * 1000
        headroom = budget / r["p95_ms"]
        lines.append(f"| {name} | {r['device']} | {r['load_s']} s | **{r['median_ms']} ms** | {r['p95_ms']} ms | "
                     f"{r['max_ms']} ms | x{headroom:.1f} ({chunk} actions) | {r.get('gpu_pct_mean') or 0:.0f}% / "
                     f"{r.get('npu_pct_mean') or 0:.0f}% | {r.get('pkg_temp_c_max') or '-'} °C |")
    lines += ["", "*Headroom: the loop asks for the next chunk when half the current one is left (at 30 fps: "
              "SmolVLA 25 of 50 actions = 833 ms, ACT 50 of 100 = 1667 ms); headroom = that time / p95 latency. "
              "Above x1 the arm never waits for the model (asynchronous execution).", ""]
    return lines


def anomaly_section(path: Path) -> list[str]:
    data = json.loads(path.read_text())
    size = "x".join(str(x) for x in data.get("crop_size", []))
    lines = [f"## Anomalib PatchCore, one {size} crop per call, {data['time']}", ""]
    if data.get("contended"):
        lines += [f"> Measured while the laptop was busy ({data['contended']}): re-run on a quiet laptop "
                  "for final numbers.", ""]
    lines += ["| Precision | Device | Size | Median | p95 | Score change vs FP32 on CPU (mean / max) | GPU / NPU busy | Max temp |",
              "|---|---|---|---|---|---|---|---|"]
    for r in data["rows"]:
        if "error" in r:
            lines.append(f"| {r['model']} | {r['device']} | | failed: {r['error'][:80]} | | | | |")
            continue
        lines.append(f"| {r['model']} | {r['device']} | {r['size_mb']} MB | **{r['median_ms']} ms** | {r['p95_ms']} ms | "
                     f"{r['score_diff_mean']} / {r['score_diff_max']} | {r.get('gpu_pct_mean') or 0:.0f}% / "
                     f"{r.get('npu_pct_mean') or 0:.0f}% | {r.get('pkg_temp_c_max') or '-'} °C |")
    lines += ["", "Scores are normalised so 0.5 is the model's threshold; the loop's unsure band is 0.4-0.6 "
              "unless anomaly/bands.json says otherwise.", ""]
    return lines


def newest_live_run() -> Path | None:
    for run in sorted((REPO / "loop" / "runs").glob("*/"), reverse=True):
        config = run / "config.json"
        if (run / "cycles.jsonl").exists() and config.exists():
            args = json.loads(config.read_text()).get("args", {})
            if not args.get("sim") and not args.get("inspect_only"):
                return run
    return None


def loop_section(run: Path) -> list[str]:
    config = json.loads((run / "config.json").read_text())
    cycles = [json.loads(line) for line in (run / "cycles.jsonl").read_text().splitlines() if line.strip()]
    done = [c for c in cycles if "total_s" in c]
    sim = config.get("args", {}).get("sim")
    lines = [f"## Closed loop: {run.name}{' (SIMULATION)' if sim else ''}", ""]
    models = config.get("models", {})
    if models:
        lines.append("Pick: {}  ·  Sort: {}  ·  Anomalib on {}".format(
            f"{models['pick']['name']} on {config['args'].get('pick_device')}",
            f"{models['sort']['name']} on {config['args'].get('sort_device')}", config["args"].get("anomaly_device")))
        lines.append("")
    verdicts = [c["inspect"]["verdict"] for c in done]
    stops = len(cycles) - len(done)
    pick = [c["pick"]["s"] for c in done if "pick" in c]
    show = [c["show_s"] for c in done if "show_s" in c]
    sort = [c["sort"]["s"] for c in done if "sort" in c]
    total = [c["total_s"] for c in done]
    pick_ms = [c["pick"]["inference_ms"].get("median") for c in done if c.get("pick", {}).get("inference_ms", {}).get("n")]
    sort_ms = [c["sort"]["inference_ms"].get("median") for c in done if c.get("sort", {}).get("inference_ms", {}).get("n")]
    anomaly_ms = [m for c in done for m in c["inspect"].get("anomaly_ms", [])]
    temps = [c["system"]["pkg_temp_c"] for c in done if c.get("system", {}).get("pkg_temp_c") is not None]
    watts = [c["system"]["pkg_w"] for c in done if c.get("system", {}).get("pkg_w") is not None]
    lines += [
        "| | |", "|---|---|",
        f"| Cycles completed / stopped | {len(done)} / {stops} |",
        f"| Verdicts good / defective (re-checked) | {verdicts.count('GOOD')} / {verdicts.count('DEFECTIVE')} "
        f"({sum(1 for c in done if c['inspect'].get('rechecked'))}) |",
        f"| Cycle time, median | {med(total)} s |",
        f"| Pick / show + inspect / sort, median | {med(pick)} / {med(show)} / {med(sort)} s |",
        f"| Pick policy inference, median of cycle medians | {med(pick_ms)} ms |",
        f"| Sort policy inference, median of cycle medians | {med(sort_ms)} ms |",
        f"| Anomalib per photo, median | {med(anomaly_ms)} ms |",
        f"| Package temperature during cycles, max | {max(temps) if temps else '-'} °C |",
        f"| Package power during cycles, mean | {f'{statistics.mean(watts):.1f} W' if watts else 'not measured (needs RAPL access)'} |",
        "",
        "Correct sorting must be counted by a person (the log knows the verdict, not where the brick landed): "
        "write it next to this table as 'sorted correctly N of M'.", "",
    ]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, help="loop run folder (default: newest run on the real arm)")
    args = parser.parse_args()

    lines = ["# Measured results", "",
             f"Machine: {cpu_name()}, {round(int(Path('/proc/meminfo').read_text().split()[1]) / 1e6)} GB RAM. "
             "All models run with OpenVINO on this laptop. Generated by `bench/make_table.py`; the raw numbers "
             "are in `bench/results/` and `loop/runs/`.", ""]
    policy = newest("policy_*.json")
    anomaly = newest("anomaly_*.json")
    run = args.run or newest_live_run()
    if policy:
        lines += policy_section(policy)
    if anomaly:
        lines += anomaly_section(anomaly)
    if run:
        lines += loop_section(run)
    else:
        lines += ["## Closed loop", "", "No run on the real arm yet: `loop/run_cell.py` logs one to `loop/runs/`.", ""]
    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
