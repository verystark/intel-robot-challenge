"""Benchmark the Anomalib model on the laptop's CPU, GPU and NPU, in FP32 and INT8.

For each model x device: compile time, latency over real inspection crops (median / p95 /
max), how far scores move from the FP32 CPU reference, and the system readings during
the run (package temperature, GPU / NPU busy %, power when available).

Before measuring it records the background load for a few seconds; numbers taken while
something else keeps the GPU or CPU busy are flagged as contended in the results.

    .venv/bin/python bench/anomaly_bench.py                 # from the repo root
    .venv/bin/python bench/anomaly_bench.py --iters 300 --devices GPU NPU
    .venv/bin/python bench/anomaly_bench.py --extra-model anomaly/exported_model_int8_full/weights/openvino/model.xml

Writes bench/results/anomaly_<time>.json and .md (bench/make_table.py merges them into RESULTS.md).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "anomaly"))
sys.path.insert(0, str(REPO / "bench"))
from detector import DEFAULT_MODEL, INT8_MODEL, Detector  # noqa: E402
from sysmon import SysMonThread  # noqa: E402

RESULTS = REPO / "bench" / "results"


def baseline_load(seconds: float = 3.0) -> dict:
    with SysMonThread(interval_s=0.5) as mon:
        time.sleep(seconds)
    return mon.summary()


def contended(base: dict) -> str:
    notes = []
    if (base.get("gpu_pct_mean") or 0) > 20:
        notes.append(f"GPU {base['gpu_pct_mean']:.0f}% busy before start")
    if (base.get("cpu_pct_mean") or 0) > 25:
        notes.append(f"CPU {base['cpu_pct_mean']:.0f}% busy before start")
    if (base.get("npu_pct_mean") or 0) > 10:
        notes.append(f"NPU {base['npu_pct_mean']:.0f}% busy before start")
    return "; ".join(notes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--devices", nargs="+", default=["CPU", "GPU", "NPU"])
    parser.add_argument("--iters", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--extra-model", action="append", default=[], help="another model.xml to include")
    args = parser.parse_args()

    models = {"FP32": DEFAULT_MODEL}
    if INT8_MODEL.exists():
        models["INT8 weights"] = INT8_MODEL
    for extra in args.extra_model:
        models[Path(extra).parent.parent.parent.name] = REPO / extra

    photos = sorted((REPO / "anomaly/dataset/test_normal").glob("*.png")) + \
        sorted((REPO / "anomaly/dataset/abnormal").glob("*.png"))
    normal = sorted((REPO / "anomaly/dataset/normal").glob("*.png"))
    random.Random(0).shuffle(normal)
    photos = (photos + normal)[:60]
    crops = [cv2.imread(str(p)) for p in photos]
    print(f"{len(crops)} real crops, {args.iters} timed runs per model and device")

    reference = Detector(DEFAULT_MODEL, "CPU")
    ref_scores = np.array([reference.score(c)[0] for c in crops])

    base = baseline_load()
    note = contended(base)
    print("Background load:", note or "quiet")

    rows = []
    for model_name, xml in models.items():
        for device in args.devices:
            print(f"\n{model_name} on {device}...", flush=True)
            try:
                det = Detector(xml, device)
            except Exception as error:  # noqa: BLE001
                print(f"  failed to load: {error}")
                rows.append({"model": model_name, "device": device, "error": str(error)[:200]})
                continue
            scores = np.array([det.score(c)[0] for c in crops])
            for i in range(args.warmup):
                det.score(crops[i % len(crops)])
            times = []
            with SysMonThread(interval_s=0.25) as mon:
                t_end = time.perf_counter() + 3.0  # at least 3 s, so the sensors get readings
                i = 0
                while i < args.iters or time.perf_counter() < t_end:
                    times.append(det.score(crops[i % len(crops)])[2])
                    i += 1
            t = np.array(times)
            diff = np.abs(scores - ref_scores)
            row = {
                "model": model_name, "device": device, "size_mb": round(xml.with_suffix(".bin").stat().st_size / 1e6, 1),
                "compile_s": round(det.compile_s, 2), "median_ms": round(float(np.median(t)), 2),
                "p95_ms": round(float(np.percentile(t, 95)), 2), "max_ms": round(float(t.max()), 2),
                "fps": round(1000 / float(np.median(t)), 1),
                "score_diff_mean": round(float(diff.mean()), 4), "score_diff_max": round(float(diff.max()), 4),
                **{k: (round(v, 1) if v is not None else None) for k, v in mon.summary().items()},
            }
            rows.append(row)
            print(f"  median {row['median_ms']} ms, p95 {row['p95_ms']} ms, score diff max {row['score_diff_max']}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "iters": args.iters, "crops": len(crops),
           "crop_size": list(crops[0].shape[:2]), "background": base, "contended": note, "rows": rows}
    (RESULTS / f"anomaly_{stamp}.json").write_text(json.dumps(out, indent=2) + "\n")
    lines = [f"Anomalib PatchCore, one {crops[0].shape[1]}x{crops[0].shape[0]} crop per call, "
             f"{args.iters} runs ({out['time']}){' - CONTENDED: ' + note if note else ''}", "",
             "| Model | Device | Size | Median | p95 | Max | Score change vs FP32 CPU (mean / max) | GPU / NPU busy | Temp |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['model']} | {r['device']} | | failed: {r['error']} | | | | | |")
            continue
        busy = f"{r.get('gpu_pct_mean') or 0:.0f}% / {r.get('npu_pct_mean') or 0:.0f}%"
        lines.append(f"| {r['model']} | {r['device']} | {r['size_mb']} MB | {r['median_ms']} ms | {r['p95_ms']} ms | "
                     f"{r['max_ms']} ms | {r['score_diff_mean']} / {r['score_diff_max']} | {busy} | "
                     f"{r.get('pkg_temp_c_max') or '-'} °C |")
    (RESULTS / f"anomaly_{stamp}.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
