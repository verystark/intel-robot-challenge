"""Webcam capture tool for building the anomaly detection dataset.

Shows the inspection camera with a green box and saves the area inside it.
Exposure, white balance and focus are locked (on Linux) so every photo is taken
the same way. The camera, box and settings are stored in camera_config.json,
which live inspection reuses so it crops exactly like the training photos.

Keys (click the window first):
    g       save box to dataset/normal       (good bricks, used for training)
    t       save box to dataset/test_normal  (extra good bricks, testing only)
    b       save box to dataset/abnormal     (defective bricks, testing only)
    click   move the box to the clicked point
    + / -   make the box bigger / smaller (keep it fixed once you start a dataset!)
    1 / 2   darker / brighter (exposure first, then gain)
    3 / 4   colour cooler (bluer) / warmer (more orange)
    5 / 6   focus down / up by hand
    k       automatic focus: find the sharpest focus for what is inside the box
    c       switch camera (Windows only; on Linux use --camera, see --list-cameras)
    q / ESC quit

Every photo is also saved as a full frame in dataset_full/, so the box can be
changed later and the crops regenerated.
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
from camera import (  # noqa: E402
    CameraConfig,
    box_rect,
    can_lock_controls,
    crop_box,
    list_cameras,
    open_camera,
    set_control,
)

DATASET_DIR = HERE / "dataset"
FULL_DIR = HERE / "dataset_full"
SAVE_KEYS = {
    ord("g"): "normal",
    ord("b"): "abnormal",
    ord("t"): "test_normal",
}
WINDOW = "Anomaly capture"
ROI_STEP = 20
ROI_MIN = 64
DISPLAY_MAX_WIDTH = 1280
# Digit keys, because OpenCV's window on Linux does not report Shift (E arrives as e).
KEY_DARKER, KEY_BRIGHTER = ord("1"), ord("2")
ADJUST_KEYS = {  # key: (control, step, min, max) for the station webcam
    ord("3"): ("white_balance_temperature", -100, 2800, 6500),  # lower K = image looks bluer
    ord("4"): ("white_balance_temperature", 100, 2800, 6500),
    ord("5"): ("focus_absolute", -10, 0, 1023),
    ord("6"): ("focus_absolute", 10, 0, 1023),
}
EXPOSURE_MIN, EXPOSURE_MAX = 3, 330  # units of 100 us; 33 ms is the longest that keeps 30 fps
GAIN_MAX = 16
BRIGHTNESS_FACTOR = 1.25  # each press changes exposure by 25%


def change_brightness(cfg: CameraConfig, brighter: bool) -> str | None:
    """Raise exposure up to one frame time, then gain; lower in reverse. Returns a message or None."""
    c = cfg.controls
    exposure, gain = c["exposure_time_absolute"], c["gain"]
    if brighter:
        if exposure < EXPOSURE_MAX:
            exposure = min(EXPOSURE_MAX, max(exposure + 1, round(exposure * BRIGHTNESS_FACTOR)))
        elif gain < GAIN_MAX:
            gain += 1
        else:
            return "Maximum brightness reached: add light (a desk lamp)"
    elif gain > 0:
        gain -= 1
    elif exposure > EXPOSURE_MIN:
        exposure = max(EXPOSURE_MIN, min(exposure - 1, round(exposure / BRIGHTNESS_FACTOR)))
    else:
        return "Minimum brightness reached"
    for name, value in (("exposure_time_absolute", exposure), ("gain", gain)):
        if value != c[name]:
            c[name] = value
            error = set_control(cfg.device, name, value)
            if error:
                return error
    return None


def count_images(folder: Path) -> int:
    return len(list(folder.glob("*.png"))) if folder.exists() else 0


def sharpness(image: np.ndarray) -> float:
    return float(cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())


def exposure_stats(image: np.ndarray) -> tuple[float, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(gray.mean()), float((gray >= 250).mean() * 100)


def focus_sweep(cap: cv2.VideoCapture, cfg: CameraConfig) -> int:
    """Try focus positions and keep the one that makes the box sharpest."""

    def measure(value: int) -> float:
        set_control(cfg.device, "focus_absolute", value)
        for _ in range(4):  # let the lens move
            cap.read()
        ok, frame = cap.read()
        return sharpness(crop_box(frame, cfg)) if ok else 0.0

    coarse = {v: measure(v) for v in range(0, 1024, 40)}
    best = max(coarse, key=coarse.get)
    fine = {v: measure(v) for v in range(max(0, best - 40), min(1023, best + 40) + 1, 8)}
    best = max(fine, key=fine.get)
    cfg.controls["focus_absolute"] = best
    set_control(cfg.device, "focus_absolute", best)
    return best


def switch_camera(cap: cv2.VideoCapture, cfg: CameraConfig) -> cv2.VideoCapture:
    cameras = list_cameras()
    start = cameras.index(cfg.device) + 1 if cfg.device in cameras else 0
    previous = cfg.device
    cap.release()
    for step in range(len(cameras)):
        cfg.device = cameras[(start + step) % len(cameras)]
        try:
            return open_camera(cfg)
        except RuntimeError:
            continue
    cfg.device = previous
    return open_camera(cfg)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", help="camera index or /dev path (default: the one in camera_config.json)")
    parser.add_argument("--roi", type=int, help="box size in pixels (default: the one in camera_config.json)")
    parser.add_argument("--list-cameras", action="store_true", help="print the cameras --camera accepts and exit")
    args = parser.parse_args()

    if args.list_cameras:
        print("\n".join(list_cameras()))
        return

    cfg = CameraConfig.load()
    if args.camera is not None:
        cfg.device = args.camera
    if args.roi is not None:
        cfg.box_size = args.roi

    for sub in SAVE_KEYS.values():
        (DATASET_DIR / sub).mkdir(parents=True, exist_ok=True)
        (FULL_DIR / sub).mkdir(parents=True, exist_ok=True)
    counts = {sub: count_images(DATASET_DIR / sub) for sub in SAVE_KEYS.values()}

    try:
        cap = open_camera(cfg)
    except RuntimeError as err:
        sys.exit(str(err))
    cfg.save()
    print(f"Using camera {cfg.device}")
    if not can_lock_controls():
        print("Camera settings can't be locked on this system; brightness and colour may drift between photos.")

    scale = 1.0
    status, status_until = "", 0.0

    def on_mouse(event: int, x: int, y: int, *_: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            cfg.box_center = [int(x / scale), int(y / scale)]
            cfg.save()

    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW, on_mouse)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                sys.exit(f"Camera {cfg.device} stopped delivering frames.")

            cfg.box_size = max(ROI_MIN, min(cfg.box_size, *frame.shape[:2]))
            x0, y0, x1, y1 = box_rect(frame.shape, cfg)
            roi = frame[y0:y1, x0:x1].copy()

            scale = min(1.0, DISPLAY_MAX_WIDTH / frame.shape[1])
            display = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            cv2.rectangle(display, (int(x0 * scale), int(y0 * scale)), (int(x1 * scale), int(y1 * scale)), (0, 255, 0), 2)

            brightness, clipped = exposure_stats(roi)
            c = cfg.controls
            lines = [
                f"box {cfg.box_size}px | " + "  ".join(f"{k}:{v}" for k, v in counts.items()),
                f"brightness {brightness:.0f} (aim 110-150)  clipped {clipped:.1f}%  sharpness {sharpness(roi):.0f}",
                f"exposure {c['exposure_time_absolute']}  gain {c['gain']}  wb {c['white_balance_temperature']}K  focus {c['focus_absolute']}",
            ]
            if time.time() < status_until:
                lines.append(status)
            for i, text in enumerate(lines):
                org = (10, 25 + 24 * i)
                cv2.putText(display, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
                cv2.putText(display, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)
            cv2.putText(display, "g/t/b=save  click=move box  +/-=box  1/2=darker/brighter  3/4=cooler/warmer  "
                        "5/6=focus  k=autofocus  q=quit",
                        (10, display.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow(WINDOW, display)

            key = cv2.waitKey(1) & 0xFF
            if ord("A") <= key <= ord("Z"):  # Caps Lock or a backend that reports capitals
                key += ord("a") - ord("A")
            if key in (ord("q"), 27):
                break
            if key in (ord("+"), ord("=")):
                cfg.box_size += ROI_STEP
                cfg.save()
                status, status_until = f"Box size {cfg.box_size}px", time.time() + 1.5
            elif key in (ord("-"), ord("_")):
                cfg.box_size -= ROI_STEP
                cfg.save()
                status, status_until = f"Box size {cfg.box_size}px", time.time() + 1.5
            elif key in (KEY_DARKER, KEY_BRIGHTER):
                message = change_brightness(cfg, brighter=key == KEY_BRIGHTER)
                cfg.save()
                if message:
                    status, status_until = message, time.time() + 3
            elif key in ADJUST_KEYS:
                name, step, lo, hi = ADJUST_KEYS[key]
                cfg.controls[name] = int(np.clip(cfg.controls[name] + step, lo, hi))
                error = set_control(cfg.device, name, cfg.controls[name])
                cfg.save()
                if error:
                    status, status_until = error, time.time() + 3
            elif key == ord("k"):
                cv2.putText(display, "Focusing...", (10, display.shape[0] // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
                cv2.imshow(WINDOW, display)
                cv2.waitKey(1)
                best = focus_sweep(cap, cfg)
                cfg.save()
                status, status_until = f"Focus set to {best}", time.time() + 2
            elif key == ord("c"):
                if can_lock_controls():
                    # Switching would apply this camera's locked settings to the next
                    # camera (e.g. the policy's wrist camera), so pick it with --camera.
                    status, status_until = "Use --camera to choose the camera (see --list-cameras)", time.time() + 3
                    continue
                cap = switch_camera(cap, cfg)
                cfg.save()
                status, status_until = f"Switched to camera {cfg.device}", time.time() + 2
                print(status)
            elif key in SAVE_KEYS:
                sub = SAVE_KEYS[key]
                stem = f"{sub}_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 1000:03d}"
                path = DATASET_DIR / sub / f"{stem}.png"
                cv2.imwrite(str(path), roi)
                cv2.imwrite(str(FULL_DIR / sub / f"{stem}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                counts[sub] += 1
                status, status_until = f"Saved {path.name}", time.time() + 1.5
                print(f"Saved {path}")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        cfg.save()


if __name__ == "__main__":
    main()
