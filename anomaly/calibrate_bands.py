"""Set the good / unsure / defective score bands from real photos, and save them for the loop.

Scores every photo in dataset/test_normal (good bricks never trained on) and
dataset/abnormal (defective bricks) with the exported model, then picks:

    high = just above the highest good score, so no known good brick is called defective outright
    low  = just below the lowest defective score, so no known defect is called good outright

Scores between low and high are UNSURE: the loop turns the brick and looks again,
and treats a brick that is still unsure as defective. If the two sets don't
overlap, the unsure band sits in the middle of the gap between them.

Scores differ slightly between devices (the GPU and NPU compute in 16-bit), so
calibrate on the device the loop uses; the device is saved with the bands.

    ../.venv/bin/python calibrate_bands.py                  # GPU, writes bands.json
    ../.venv/bin/python calibrate_bands.py --device NPU
    ../.venv/bin/python calibrate_bands.py --dry-run        # print only
    ../.venv/bin/python calibrate_bands.py --low 0.35 --high 0.7   # set by hand
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from detector import (  # noqa: E402
    BANDS_PATH,
    DEFAULT_MODEL,
    DEFECTIVE,
    GOOD,
    UNSURE,
    Bands,
    Detector,
    label,
    save_bands,
)

DATASET_DIR = HERE / "dataset"
MARGIN = 0.02


def score_folder(det: Detector, folder: Path) -> dict[str, float]:
    return {p.name: det.score(cv2.imread(str(p)))[0] for p in sorted(folder.glob("*.png"))}


def summary(name: str, scores: dict[str, float], bands: Bands) -> str:
    labels = [label(s, bands) for s in scores.values()]
    counts = {lab: labels.count(lab) for lab in (GOOD, UNSURE, DEFECTIVE)}
    values = np.array(list(scores.values()))
    return (
        f"  {name:<12} n={len(values):3}  min {values.min():.3f}  median {np.median(values):.3f}  "
        f"max {values.max():.3f}   good {counts[GOOD]:3}  unsure {counts[UNSURE]:3}  defective {counts[DEFECTIVE]:3}"
    )


def pick_bands(good: np.ndarray, bad: np.ndarray) -> Bands:
    top_good, low_bad = float(good.max()), float(bad.min())
    if low_bad > top_good:  # clean separation: unsure band = middle half of the gap
        gap = low_bad - top_good
        low, high = top_good + gap / 4, low_bad - gap / 4
    else:  # overlap: everything that could be either is unsure
        low, high = low_bad - MARGIN, top_good + MARGIN
    low, high = max(0.0, low), min(1.0, high)
    return Bands(low=round(low, 4), high=round(max(low, high), 4))


def main() -> None:
    global DATASET_DIR
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--device", default="GPU", help="CPU, GPU or NPU: the device the loop runs Anomalib on")
    parser.add_argument("--low", type=float, help="set the band by hand instead")
    parser.add_argument("--high", type=float)
    parser.add_argument("--dry-run", action="store_true", help="print, don't write bands.json")
    parser.add_argument("--dataset", default="dataset", help="photo folder under anomaly/ (e.g. dataset_show)")
    args = parser.parse_args()
    DATASET_DIR = HERE / args.dataset

    det = Detector(args.model, args.device)
    good = score_folder(det, DATASET_DIR / "test_normal")
    bad = score_folder(det, DATASET_DIR / "abnormal")
    if not good:
        sys.exit("No photos in dataset/test_normal: move ~20 good photos there (taken at another time).")

    default = Bands()
    if args.low is not None and args.high is not None:
        bands = Bands(low=args.low, high=args.high, source="set by hand")
    elif bad:
        bands = pick_bands(np.array(list(good.values())), np.array(list(bad.values())))
        bands.source = f"calibrated from {len(good)} test_normal and {len(bad)} abnormal photos"
    else:
        bands = Bands(source="default: no defective photos yet")

    print(f"Model {args.model.relative_to(HERE) if args.model.is_relative_to(HERE) else args.model} on {args.device}")
    print(f"\nDefault bands  low {default.low}  high {default.high}")
    print(summary("test_normal", good, default))
    if bad:
        print(summary("abnormal", bad, default))
    print(f"\nChosen bands   low {bands.low}  high {bands.high}   ({bands.source})")
    print(summary("test_normal", good, bands))
    if bad:
        print(summary("abnormal", bad, bands))
        overlap = min(bad.values()) <= max(good.values())
        if overlap:
            print("\n  The good and defective scores overlap: bricks in the unsure band get a second look,")
            print("  and are rejected if still unsure. More varied good photos narrow the overlap.")
    else:
        print("\n  No defective photos yet: capture some with 'b' and run this again.")

    worst_good = sorted(good.items(), key=lambda kv: -kv[1])[:3]
    print("\nHighest-scoring good photos: " + ", ".join(f"{n} {s:.3f}" for n, s in worst_good))
    if bad:
        best_bad = sorted(bad.items(), key=lambda kv: kv[1])[:3]
        print("Lowest-scoring defective photos: " + ", ".join(f"{n} {s:.3f}" for n, s in best_bad))

    if args.dry_run:
        print("\nDry run: bands.json not written.")
        return
    model_stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(args.model.stat().st_mtime))
    save_bands(bands, {"device": args.device, "model": str(args.model), "model_time": model_stamp,
                       "written": time.strftime("%Y-%m-%d %H:%M:%S")})
    print(f"\nWrote {BANDS_PATH}")


if __name__ == "__main__":
    main()
