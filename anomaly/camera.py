"""Inspection camera setup shared by capture.py and live inspection.

Anomalib flags anything that differs from its training photos, so live
inspection must take photos exactly the way capture.py took them: same camera,
resolution, locked exposure / white balance / focus, and the same crop box.
Both load camera_config.json through this module to guarantee that.

Locking the camera settings uses v4l2-ctl, so it only works on Linux (the
station laptop). On other systems the camera runs on its automatic settings.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np

CONFIG_PATH = Path(__file__).resolve().parent / "camera_config.json"

# Stable udev name of the station's 2K inspection webcam. /dev/videoN numbers
# change between boots, this name does not.
DEFAULT_DEVICE = "/dev/v4l/by-id/usb-Webcam_Webcam_Audio_01.00.00-video-index0"

# The automatic modes must be switched off before their manual values apply,
# so controls are always set in this order.
CONTROL_ORDER = (
    "auto_exposure",
    "white_balance_automatic",
    "focus_automatic_continuous",
    "power_line_frequency",
    "exposure_time_absolute",
    "gain",
    "white_balance_temperature",
    "focus_absolute",
)


def _default_controls() -> dict[str, int]:
    return {
        "auto_exposure": 1,  # 1 = manual exposure
        "white_balance_automatic": 0,
        "focus_automatic_continuous": 0,
        "power_line_frequency": 1,  # 1 = 50 Hz mains (Finland); 60 Hz gives flicker bands
        "exposure_time_absolute": 200,  # units of 100 us
        "gain": 0,
        "white_balance_temperature": 4600,
        "focus_absolute": 0,
    }


@dataclass
class CameraConfig:
    device: str = DEFAULT_DEVICE  # a /dev path on Linux, or a camera index such as "1"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    controls: dict[str, int] = field(default_factory=_default_controls)
    box_center: list[int] | None = None  # [x, y] of the crop box centre; None = frame centre
    box_size: int = 400  # side of the square crop box, in full-frame pixels

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> CameraConfig:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        controls = {**_default_controls(), **data.pop("controls", {})}
        return cls(**data, controls=controls)

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")


def box_rect(frame_shape: tuple[int, ...], cfg: CameraConfig) -> tuple[int, int, int, int]:
    """Square crop box (x0, y0, x1, y1), kept inside the frame."""
    h, w = frame_shape[:2]
    size = max(1, min(cfg.box_size, h, w))
    cx, cy = cfg.box_center or (w // 2, h // 2)
    x0 = int(np.clip(cx - size // 2, 0, w - size))
    y0 = int(np.clip(cy - size // 2, 0, h - size))
    return x0, y0, x0 + size, y0 + size


def crop_box(frame: np.ndarray, cfg: CameraConfig) -> np.ndarray:
    x0, y0, x1, y1 = box_rect(frame.shape, cfg)
    return frame[y0:y1, x0:x1]


def _v4l2_path(device: str) -> str:
    return f"/dev/video{device}" if str(device).isdigit() else str(device)


def can_lock_controls() -> bool:
    return sys.platform.startswith("linux") and shutil.which("v4l2-ctl") is not None


def set_control(device: str, name: str, value: int) -> str | None:
    """Set one camera control. Returns an error message, or None on success."""
    if not can_lock_controls():
        return None
    result = subprocess.run(
        ["v4l2-ctl", "-d", _v4l2_path(device), f"--set-ctrl={name}={value}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        error = f"camera refused {name}={value}: {result.stderr.strip()}"
        print(f"warning: {error}")
        return error
    return None


def apply_controls(cfg: CameraConfig) -> None:
    for name in CONTROL_ORDER:
        if name in cfg.controls:
            set_control(cfg.device, name, cfg.controls[name])


def list_cameras() -> list[str]:
    """Cameras to cycle through: stable capture-device names on Linux, indices elsewhere.

    The RealSense is left out: it is Studio's top camera, and opening it as a
    plain webcam while Studio uses it crashes Studio's RealSense stream.
    """
    if sys.platform.startswith("linux"):
        names = sorted(
            str(p) for p in Path("/dev/v4l/by-id").glob("*-video-index0") if "RealSense" not in p.name
        )
        if names:
            return names
    return [str(i) for i in range(5)]


def open_camera(cfg: CameraConfig, warmup_s: float = 1.5) -> cv2.VideoCapture:
    source = int(cfg.device) if str(cfg.device).isdigit() else cfg.device
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_V4L2
    cap = cv2.VideoCapture(source, backend)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(
            f"Cannot open camera {cfg.device}. Is another program (such as a Studio preview) "
            "using it? Pick a different camera with --camera."
        )
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
    cap.set(cv2.CAP_PROP_FPS, cfg.fps)
    ok, _ = cap.read()  # some UVC cameras reset their controls when streaming starts
    if not ok:
        cap.release()
        raise RuntimeError(f"Camera {cfg.device} opened but returned no frame.")
    apply_controls(cfg)
    end = time.monotonic() + warmup_s
    while time.monotonic() < end:  # let exposure and focus settle
        cap.read()
    return cap
