"""Re-cut the dataset crops from the saved full frames, using the current box.

Run after moving or resizing the box in capture.py so every photo is cut the
same way as live inspection will cut it. Only photos that still have a crop
are re-cut, so crops you deleted stay deleted. The old crops are copied to
dataset_old_crops/<date_time>/ first (dataset_old_crops/<folder>_<date_time>/
for another photo folder).

    python recrop.py                         # dataset/ from dataset_full/
    python recrop.py --dataset dataset_show  # dataset_show/ from dataset_show_full/
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from camera import CameraConfig, crop_box  # noqa: E402

BACKUP_DIR = HERE / "dataset_old_crops"
SUBDIRS = ("normal", "test_normal", "abnormal")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="dataset",
                        help="photo folder under anomaly/ (default dataset; dataset_show = photos from show_tool "
                             "collect). Full frames are read from <folder>_full")
    args = parser.parse_args()
    dataset_dir, full_dir = HERE / args.dataset, HERE / f"{args.dataset}_full"
    if not dataset_dir.is_dir() or not full_dir.is_dir():
        sys.exit(f"Need both {dataset_dir} and {full_dir}.")

    cfg = CameraConfig.load()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / (stamp if args.dataset == "dataset" else f"{args.dataset}_{stamp}")
    for sub in SUBDIRS:
        crops = sorted((dataset_dir / sub).glob("*.png"))
        if not crops:
            continue
        (backup / sub).mkdir(parents=True, exist_ok=True)
        recut, no_full = 0, 0
        for crop_path in crops:
            frame = cv2.imread(str(full_dir / sub / f"{crop_path.stem}.jpg"))
            if frame is None:
                no_full += 1
                continue
            shutil.copy2(crop_path, backup / sub / crop_path.name)
            cv2.imwrite(str(crop_path), crop_box(frame, cfg))
            recut += 1
        note = f" ({no_full} have no full frame and were left as they are)" if no_full else ""
        print(f"{dataset_dir.name}/{sub}: re-cut {recut} of {len(crops)} photos{note}")
    print(f"Box: {cfg.box_size}px centred at {cfg.box_center}. Old crops copied to {backup}")


if __name__ == "__main__":
    main()
