#!/usr/bin/env python3
"""Size and score difference of the INT8 inspection model against FP32, for the current model files.

Runs both models on the CPU over the held-out good photos and the defect photos, and writes
video/public/int8.json, which build_data.py puts into the video and the deck. Run it after every
retrain of the inspection model (from the repo root, with the anomaly environment):

    .venv/bin/python video/scripts/int8_check.py
"""
import glob
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ANOMALY = REPO / "anomaly"
os.environ.setdefault("OMP_NUM_THREADS", "2")  # the laptop also runs the robot
sys.path.insert(0, str(ANOMALY))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from detector import Detector  # noqa: E402

FP32 = ANOMALY / "exported_model/weights/openvino/model.xml"
INT8 = ANOMALY / "exported_model_int8/weights/openvino/model.xml"


def main() -> None:
    fp, q = Detector(FP32, device="CPU"), Detector(INT8, device="CPU")
    paths = sorted(glob.glob(str(ANOMALY / "dataset/test_normal/*.png"))) + sorted(glob.glob(str(ANOMALY / "dataset/abnormal/*.png")))
    diffs = np.array([abs(fp.score(cv2.imread(p))[0] - q.score(cv2.imread(p))[0]) for p in paths])
    out = {
        "measured": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(FP32.with_suffix(".bin").stat().st_mtime)),
        "crops": len(paths),
        "fp32_mb": round(FP32.with_suffix(".bin").stat().st_size / 1e6, 1),
        "int8_mb": round(INT8.with_suffix(".bin").stat().st_size / 1e6, 1),
        "score_diff_mean": round(float(diffs.mean()), 4),
        "score_diff_max": round(float(diffs.max()), 4),
    }
    (REPO / "video/public/int8.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
