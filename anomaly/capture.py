"""Webcam capture tool for building the anomaly detection dataset.

Shows a live feed with a centered green ROI box. Keys:
    g - save ROI crop to dataset/normal
    b - save ROI crop to dataset/abnormal
    t - save ROI crop to dataset/test_normal
    c - cycle to the next camera
    q / ESC - quit
"""

import argparse
import sys
import time
from pathlib import Path

import cv2

DATASET_DIR = Path(__file__).resolve().parent / "dataset"
SAVE_KEYS = {
    ord("g"): "normal",
    ord("b"): "abnormal",
    ord("t"): "test_normal",
}
WINDOW = "Anomaly capture"


def open_camera(index: int) -> cv2.VideoCapture | None:
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return None
    ok, _ = cap.read()
    if not ok:
        cap.release()
        return None
    return cap


def next_camera(current: int, max_index: int) -> tuple[int, cv2.VideoCapture | None]:
    """Try camera indices after `current`, wrapping around, until one opens."""
    for step in range(1, max_index + 1):
        idx = (current + step) % max_index
        cap = open_camera(idx)
        if cap is not None:
            return idx, cap
    return current, None


def roi_rect(frame_shape, roi_size: int) -> tuple[int, int, int, int]:
    h, w = frame_shape[:2]
    size = min(roi_size, h, w)
    x0 = (w - size) // 2
    y0 = (h - size) // 2
    return x0, y0, x0 + size, y0 + size


def count_images(folder: Path) -> int:
    return len(list(folder.glob("*.png"))) if folder.exists() else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", type=int, default=0, help="initial camera index")
    parser.add_argument("--roi", type=int, default=300, help="ROI square size in pixels")
    parser.add_argument("--max-cameras", type=int, default=5, help="number of indices to scan when cycling")
    args = parser.parse_args()

    for sub in SAVE_KEYS.values():
        (DATASET_DIR / sub).mkdir(parents=True, exist_ok=True)
    counts = {sub: count_images(DATASET_DIR / sub) for sub in SAVE_KEYS.values()}

    cam_idx = args.camera
    cap = open_camera(cam_idx)
    if cap is None:
        cam_idx, cap = next_camera(cam_idx, args.max_cameras)
    if cap is None:
        sys.exit("No camera could be opened.")
    print(f"Using camera {cam_idx}")

    status, status_until = "", 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print(f"Camera {cam_idx} stopped delivering frames, switching...")
                cap.release()
                cam_idx, cap = next_camera(cam_idx, args.max_cameras)
                if cap is None:
                    sys.exit("No camera available.")
                continue

            x0, y0, x1, y1 = roi_rect(frame.shape, args.roi)
            roi = frame[y0:y1, x0:x1].copy()

            display = frame.copy()
            cv2.rectangle(display, (x0, y0), (x1, y1), (0, 255, 0), 2)
            info = f"cam {cam_idx} | " + "  ".join(f"{k}:{v}" for k, v in counts.items())
            cv2.putText(display, info, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(display, "g=normal b=abnormal t=test_normal c=camera q=quit",
                        (10, display.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            if time.time() < status_until:
                cv2.putText(display, status, (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow(WINDOW, display)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("c"):
                cap.release()
                new_idx, new_cap = next_camera(cam_idx, args.max_cameras)
                if new_cap is None:  # nothing else available, reopen the current one
                    new_cap = open_camera(cam_idx)
                    if new_cap is None:
                        sys.exit("Lost camera while cycling.")
                cam_idx, cap = new_idx, new_cap
                status, status_until = f"Switched to camera {cam_idx}", time.time() + 1.5
                print(status)
            elif key in SAVE_KEYS:
                sub = SAVE_KEYS[key]
                path = DATASET_DIR / sub / f"{sub}_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 1000:03d}.png"
                cv2.imwrite(str(path), roi)
                counts[sub] += 1
                status, status_until = f"Saved {path.name}", time.time() + 1.5
                print(f"Saved {path}")
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
