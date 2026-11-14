"""Inspection camera and Anomalib scoring for the loop.

- InspectionCamera opens the webcam exactly like anomaly/capture.py (same device,
  locked settings and crop box from anomaly/camera_config.json) and keeps reading in a
  background thread, so a photo is always a fresh frame, never an old buffered one.
- ReplayInspectionCamera stands in for it in --sim, cycling through saved crops.
- Scorer runs the Anomalib model in its own thread, so photo 1 is scored (on the NPU
  by default) while the wrist turns for photo 2.
"""

from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "anomaly"))
from camera import CameraConfig, crop_box, open_camera  # noqa: E402
from detector import Detector  # noqa: E402


class InspectionCamera:
    def __init__(self) -> None:
        self.cfg = CameraConfig.load()
        self.cap = open_camera(self.cfg)
        self._frame: np.ndarray | None = None
        self._t = 0.0
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._read, daemon=True, name="inspection-camera")
        self._thread.start()

    def _read(self) -> None:
        while self._running:
            ok, frame = self.cap.read()
            if ok:
                with self._lock:
                    self._frame, self._t = frame, time.monotonic()
            else:
                time.sleep(0.01)

    def latest(self) -> np.ndarray | None:
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def photo(self, timeout_s: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
        """A frame captured after this call started: (full frame, crop)."""
        requested = time.monotonic()
        deadline = requested + timeout_s
        while time.monotonic() < deadline:
            with self._lock:
                if self._frame is not None and self._t > requested + 0.03:
                    frame = self._frame.copy()
                    return frame, crop_box(frame, self.cfg)
            time.sleep(0.005)
        raise TimeoutError("The inspection camera sent no new frame")

    def box(self) -> tuple[int, int, int]:
        cx, cy = self.cfg.box_center or (self.cfg.width // 2, self.cfg.height // 2)
        return int(cx), int(cy), int(self.cfg.box_size)

    def close(self) -> None:
        self._running = False
        self._thread.join(timeout=1)
        self.cap.release()


class ReplayInspectionCamera:
    """--sim: returns saved crops in turn, with the crop itself as the 'full frame'."""

    def __init__(self, folders: list[Path]) -> None:
        self.paths = sorted(p for folder in folders for p in Path(folder).glob("*.png"))
        if not self.paths:
            raise FileNotFoundError(f"No .png photos in {', '.join(map(str, folders))}")
        self.i = 0
        self.cfg = CameraConfig.load()

    def latest(self) -> np.ndarray | None:
        return cv2.imread(str(self.paths[self.i % len(self.paths)]))

    def photo(self, timeout_s: float = 2.0) -> tuple[np.ndarray, np.ndarray]:  # noqa: ARG002
        crop = cv2.imread(str(self.paths[self.i % len(self.paths)]))
        self.i += 1
        return crop, crop

    def box(self) -> tuple[int, int, int]:
        h, w = cv2.imread(str(self.paths[0])).shape[:2]
        return w // 2, h // 2, min(w, h)

    def close(self) -> None:
        pass


class Scorer:
    """One Detector on one device, scoring in a background thread."""

    def __init__(self, model_xml: Path, device: str) -> None:
        self.detector = Detector(model_xml, device)
        self.device = device
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="anomalib")
        # Warm up so the first real photo isn't slowed by lazy initialisation.
        h, w = self.detector.input_hw or (256, 256)
        self.detector.score(np.zeros((h, w, 3), np.uint8))

    def submit(self, crop: np.ndarray) -> Future:
        return self.pool.submit(self.detector.score, crop)

    def close(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)
