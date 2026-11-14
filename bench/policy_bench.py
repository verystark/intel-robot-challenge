"""Benchmark the exported SmolVLA (or any Studio OpenVINO export) on the laptop's CPU, GPU and NPU.

Inputs are real: camera frames, joint states and task sentences from the model's own
dataset. For each device: load + compile time, latency per action chunk (median / p95 /
max) and the system readings during the run. The control loop asks for the next chunk when
half the current one is left (SmolVLA: 25 of 50 actions = 0.83 s at 30 fps; ACT: 50 of 100 =
1.67 s), so the "headroom" column says how many times a chunk's inference fits into that
budget; below 1 the arm would wait for the model.

Run with Studio's backend Python, from the repo root:

    PY=physical-ai-studio/application/backend/.venv/bin/python
    $PY bench/policy_bench.py                              # newest SmolVLA and newest ACT
    $PY bench/policy_bench.py --models SmolVLA-v2 ACT-pick-v1 --devices GPU NPU --iters 50

Writes bench/results/policy_<time>.json and .md (bench/make_table.py merges them into RESULTS.md).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "loop"))
sys.path.insert(0, str(REPO / "bench"))
from anomaly_bench import baseline_load, contended  # noqa: E402
from policy import SimWorld, find_model, load_policy  # noqa: E402
from sysmon import SysMonThread  # noqa: E402

RESULTS = REPO / "bench" / "results"


def budget_ms(chunk_len: int, threshold: float = 0.5, fps: float = 30.0) -> float:
    """Time the remaining actions take to play when the next chunk is requested."""
    return chunk_len * threshold / fps * 1000


def sample_inputs(dataset_dir: Path, n: int, seed: int = 0) -> list[dict]:
    """n observations (state, top, wrist, task) from random frames of random episodes."""
    world = SimWorld(dataset_dir, frame_fps=10, seed=seed)
    rng = random.Random(seed)
    observations = []
    tasks = list(world.episodes)
    while len(observations) < n:
        task = tasks[len(observations) % len(tasks)]
        episode = world.begin(task)
        frames = len(world.frames["top"])
        k = rng.randrange(max(1, frames))
        t = int(k / world.frame_fps * 30)
        state = episode["state"][min(t, len(episode["state"]) - 1)]
        observations.append({
            "state": state[np.newaxis].astype(np.float32),
            "images.top": world.frames["top"][k][np.newaxis],
            "images.wrist": world.frames["wrist"][min(k, len(world.frames["wrist"]) - 1)][np.newaxis],
            "task": [task],
        })
    return observations


def _inputs(observation: dict, info) -> dict:
    """Policies that don't read a sentence (ACT) get no task input."""
    return observation if info.takes_task else {k: v for k, v in observation.items() if k != "task"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=["latest:smolvla", "latest:act"],
                        help="Studio models: names, ids or latest:<policy> (missing ones are skipped)")
    parser.add_argument("--min-seconds", type=float, default=3.0, help="measure for at least this long")
    parser.add_argument("--devices", nargs="+", default=["GPU", "CPU", "NPU"])
    parser.add_argument("--iters", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--samples", type=int, default=12, help="distinct real observations to cycle through")
    args = parser.parse_args()

    infos = []
    for spec in args.models:
        try:
            infos.append(find_model(spec))
        except LookupError as error:
            print(f"Skipping {spec}: {error}")
    sort_info = next((i for i in infos if i.takes_task), infos[0])
    observations = sample_inputs(sort_info.dataset_dir, args.samples)  # real frames of this station
    base = baseline_load()
    note = contended(base)
    print("Background load:", note or "quiet")

    rows = []
    for info in infos:
        print(f"\n{info.name} ({info.policy}, {info.dataset_name})")
        for device in args.devices:
            print(f"  {device}: loading...", flush=True)
            start = time.perf_counter()
            row = {"model": info.name, "policy": info.policy, "dataset": info.dataset_name, "device": device}
            try:
                model = load_policy(info.export_dir, device, zero_noise=True)
                row["load_s"] = round(time.perf_counter() - start, 1)
                for i in range(args.warmup):
                    model.predict_action_chunk(_inputs(observations[i % len(observations)], info))
                times = []
                with SysMonThread(interval_s=0.25) as mon:
                    t_end = time.perf_counter() + args.min_seconds
                    i = 0
                    while i < args.iters or time.perf_counter() < t_end:
                        t0 = time.perf_counter()
                        chunk = model.predict_action_chunk(_inputs(observations[i % len(observations)], info))
                        times.append((time.perf_counter() - t0) * 1000)
                        i += 1
            except Exception as error:  # noqa: BLE001
                print(f"    failed: {str(error).splitlines()[0][:200]}")
                rows.append({**row, "error": str(error).splitlines()[0][:200]})
                continue
            t = np.array(times)
            row.update({
                "runs": len(t), "median_ms": round(float(np.median(t)), 1),
                "p95_ms": round(float(np.percentile(t, 95)), 1), "max_ms": round(float(t.max()), 1),
                "chunk": list(np.asarray(chunk).shape),
                "budget_ms": round(budget_ms(len(np.asarray(chunk))), 0),
                "headroom": round(budget_ms(len(np.asarray(chunk))) / float(np.percentile(t, 95)), 1),
                **{k: (round(v, 1) if v is not None else None) for k, v in mon.summary().items()},
            })
            rows.append(row)
            print(f"    median {row['median_ms']} ms, p95 {row['p95_ms']} ms, headroom x{row['headroom']}")
            del model

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "background": base, "contended": note, "rows": rows}
    (RESULTS / f"policy_{stamp}.json").write_text(json.dumps(out, indent=2) + "\n")
    lines = [f"Policies (OpenVINO), one action chunk per call on real frames of this station, at least "
             f"{args.iters} runs / {args.min_seconds:.0f} s each ({out['time']})"
             f"{' - CONTENDED: ' + note if note else ''}", "",
             "| Model | Device | Load + compile | Median | p95 | Max | Headroom (budget / p95) | GPU / NPU busy | Temp |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        name = f"{r['model']} ({r['policy']})"
        if "error" in r:
            lines.append(f"| {name} | {r['device']} | {r.get('load_s', '')} | failed: {r['error']} | | | | | |")
            continue
        busy = f"{r.get('gpu_pct_mean') or 0:.0f}% / {r.get('npu_pct_mean') or 0:.0f}%"
        lines.append(f"| {name} | {r['device']} | {r['load_s']} s | {r['median_ms']} ms | {r['p95_ms']} ms | "
                     f"{r['max_ms']} ms | x{r['headroom']} | {busy} | {r.get('pkg_temp_c_max') or '-'} °C |")
    (RESULTS / f"policy_{stamp}.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
