"""Re-cut the dataset crops from the saved full frames, using the current box.

Run after moving or resizing the box in capture.py so every photo is cut the
same way as live inspection will cut it. Only photos that still have a crop
are re-cut, so crops you deleted stay deleted. The old crops are copied to
dataset_old_crops/<date_time>/ first.

    python recrop.py
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from camera import CameraConfig, crop_box  # noqa: E402

DATASET_DIR = HERE / "dataset"
FULL_DIR = HERE / "dataset_full"
BACKUP_DIR = HERE / "dataset_old_crops"
SUBDIRS = ("normal", "test_normal", "abnormal")


def main() -> None:
    cfg = CameraConfig.load()
    backup = BACKUP_DIR / time.strftime("%Y%m%d_%H%M%S")
    for sub in SUBDIRS:
        crops = sorted((DATASET_DIR / sub).glob("*.png"))
        if not crops:
            continue
        (backup / sub).mkdir(parents=True, exist_ok=True)
        recut, no_full = 0, 0
        for crop_path in crops:
            frame = cv2.imread(str(FULL_DIR / sub / f"{crop_path.stem}.jpg"))
            if frame is None:
                no_full += 1
                continue
            shutil.copy2(crop_path, backup / sub / crop_path.name)
            cv2.imwrite(str(crop_path), crop_box(frame, cfg))
            recut += 1
        note = f" ({no_full} have no full frame and were left as they are)" if no_full else ""
        print(f"{sub}: re-cut {recut} of {len(crops)} photos{note}")
    print(f"Box: {cfg.box_size}px centred at {cfg.box_center}. Old crops copied to {backup}")


if __name__ == "__main__":
    main()
