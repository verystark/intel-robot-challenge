"""Offline test of the inspection exactly as the loop runs it: no camera, no robot.

Feeds the real show-pose photos (dataset_show: full camera-box crops, as the loop takes them)
through detector.Detector with the exported model, which cuts the brick region itself when the
model carries roi.json. The loop's bands (bands.json) and verdict rule turn each score into
GOOD / UNSURE / DEFECTIVE.

Checks, then reports:
    - the model accepts a full box crop and returns a full-size heatmap (for the dashboard);
    - per set (normal = trained on, test_normal = never seen, abnormal = defective):
      how many photos land GOOD / UNSURE / DEFECTIVE, and each score;
    - latency per photo on the chosen device.

    ../.venv/bin/python test_show_model.py                 # GPU, bands.json
    ../.venv/bin/python test_show_model.py --device NPU --bands 0.4 0.6
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from detector import DEFAULT_MODEL, Bands, Detector, label, load_bands  # noqa: E402
from roi import describe  # noqa: E402

DATASET = HERE / "dataset_show"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--device", default="GPU")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--bands", nargs=2, type=float, metavar=("LOW", "HIGH"), help="instead of bands.json")
    args = parser.parse_args()

    det = Detector(args.model, args.device)
    bands = Bands(args.bands[0], args.bands[1], "command line") if args.bands else load_bands()
    print(f"Model {args.model.relative_to(HERE) if args.model.is_relative_to(HERE) else args.model} on {args.device}"
          f" | scores: {describe(det.roi)}"
          f" | bands {bands.low}/{bands.high} ({bands.source})")

    # Plumbing: a full box crop goes in, a full-size heatmap comes out.
    sample = next(iter(sorted((args.dataset / "test_normal").glob("*.png"))), None)
    if sample is not None:
        crop = cv2.imread(str(sample))
        score, heat, _ = det.score(crop)
        assert heat.shape[:2] == crop.shape[:2], f"heatmap {heat.shape} vs crop {crop.shape}"
        print(f"Plumbing OK: {crop.shape[1]}x{crop.shape[0]} crop in, score {score:.3f}, heatmap {heat.shape[1]}x{heat.shape[0]}")
    for _ in range(3):  # warm-up
        det.score(crop)

    times = []
    summary = {}
    for sub, expect in (("normal", "GOOD"), ("test_normal", "GOOD"), ("abnormal", "DEFECTIVE")):
        paths = sorted((args.dataset / sub).glob("*.png"))
        if not paths:
            continue
        rows = []
        for p in paths:
            score, _, ms = det.score(cv2.imread(str(p)))
            times.append(ms)
            rows.append((p.name, score, label(score, bands)))
        counts = {lab: sum(r[2] == lab for r in rows) for lab in ("GOOD", "UNSURE", "DEFECTIVE")}
        right = counts[expect]
        summary[sub] = (right, len(rows))
        print(f"\n{sub:<12} ({'trained on' if sub == 'normal' else 'never seen' if sub == 'test_normal' else 'defective'}): "
              f"{counts['GOOD']} good, {counts['UNSURE']} unsure, {counts['DEFECTIVE']} defective "
              f"-> {right}/{len(rows)} as expected ({expect})")
        print("  " + "  ".join(f"{name[-14:-4]}={s:.2f}{'' if lab == expect else '!'}" for name, s, lab in rows))
    print(f"\nLatency on {args.device}: median {np.median(times):.1f} ms, worst {max(times):.1f} ms per photo")
    print("(! = not the expected verdict; UNSURE gets a second look in the loop, and is rejected if it stays unsure)")


if __name__ == "__main__":
    main()
