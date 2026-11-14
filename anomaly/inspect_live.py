"""Live test of the trained inspection model: show a brick to the camera, see the verdict.

Uses the same camera, locked settings and crop box as capture.py (camera_config.json),
so the live crop matches the training photos exactly. Nothing is saved and the
camera settings are never changed.

    ../.venv/bin/python inspect_live.py                 # GPU
    ../.venv/bin/python inspect_live.py --device CPU    # or NPU
    ../.venv/bin/python inspect_live.py --unsure 0.4 0.6

Keys (click the window first):
    space   freeze / unfreeze the current result
    h       heatmap on / off (where the model thinks the defect is)
    q / ESC quit

The anomaly score is normalised so 0.5 is the model's threshold:
    below the unsure band  -> GOOD
    inside the unsure band -> UNSURE (the loop would turn the brick and look again)
    above the unsure band  -> DEFECTIVE
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
from camera import CameraConfig, box_rect, crop_box, open_camera  # noqa: E402

DEFAULT_MODEL = HERE / "exported_model" / "weights" / "openvino" / "model.xml"
WINDOW = "Live inspection"
DISPLAY_MAX_WIDTH = 1280
COLOURS = {"GOOD": (0, 200, 0), "UNSURE": (0, 200, 255), "DEFECTIVE": (0, 0, 255)}  # BGR


def first(value) -> float:
    """First element of a scalar / array / tensor as a float."""
    return float(np.asarray(value).reshape(-1)[0])


def model_input_size(model_path: Path) -> tuple[int, int] | None:
    """(height, width) the exported model expects, if it has a fixed shape."""
    try:
        import openvino as ov

        shape = ov.Core().read_model(str(model_path)).input(0).partial_shape
        if shape.is_static:
            dims = shape.to_shape()
            return int(dims[2]), int(dims[3])  # N, C, H, W
    except Exception:
        pass
    return None


def verdict_for(score: float, unsure: tuple[float, float]) -> str:
    if score < unsure[0]:
        return "GOOD"
    if score > unsure[1]:
        return "DEFECTIVE"
    return "UNSURE"


def heatmap_overlay(crop_bgr: np.ndarray, anomaly_map: np.ndarray) -> np.ndarray:
    amap = np.asarray(anomaly_map, dtype=np.float32).squeeze()
    amap = cv2.resize(amap, (crop_bgr.shape[1], crop_bgr.shape[0]))
    amap = np.clip(amap, 0.0, 1.0) if amap.max() <= 1.0 else (amap - amap.min()) / (np.ptp(amap) + 1e-6)
    colour = cv2.applyColorMap((amap * 255).astype(np.uint8), cv2.COLORMAP_JET)
    return cv2.addWeighted(crop_bgr, 0.55, colour, 0.45, 0)


def draw_text(img: np.ndarray, text: str, org: tuple[int, int], scale: float, colour, thick: int = 2) -> None:
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, colour, thick, cv2.LINE_AA)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="exported OpenVINO model.xml")
    parser.add_argument("--device", default="GPU", help="OpenVINO device: GPU, CPU or NPU")
    parser.add_argument("--unsure", nargs=2, type=float, default=(0.4, 0.6), metavar=("LOW", "HIGH"),
                        help="score band treated as unsure (default 0.4 0.6)")
    args = parser.parse_args()

    if not args.model.exists():
        sys.exit(f"No model at {args.model}\nTrain one first: ../.venv/bin/python train_export.py")

    cfg = CameraConfig.load()
    expected = model_input_size(args.model)
    if expected and expected != (cfg.box_size, cfg.box_size):
        sys.exit(
            f"The model expects {expected[1]}x{expected[0]} crops but the box is {cfg.box_size}px.\n"
            "The box changed after training: retrain (after recrop.py) or put the box back."
        )

    from anomalib.deploy import OpenVINOInferencer  # slow import, so after the quick checks

    print(f"Loading {args.model} on {args.device}...")
    inferencer = OpenVINOInferencer(path=args.model, device=args.device)

    try:
        cap = open_camera(cfg)
    except RuntimeError as err:
        sys.exit(str(err))

    show_heatmap, frozen = True, False
    display = None
    times: list[float] = []
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    try:
        while True:
            if not frozen:
                ok, frame = cap.read()
                if not ok:
                    sys.exit(f"Camera {cfg.device} stopped delivering frames.")

                crop = crop_box(frame, cfg)
                rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0  # as read_image() gives

                start = time.perf_counter()
                result = inferencer.predict(rgb)
                times = (times + [(time.perf_counter() - start) * 1000])[-30:]

                score = first(result.pred_score)
                verdict = verdict_for(score, tuple(args.unsure))
                colour = COLOURS[verdict]

                x0, y0, x1, y1 = box_rect(frame.shape, cfg)
                shown = frame.copy()
                anomaly_map = getattr(result, "anomaly_map", None)
                if show_heatmap and anomaly_map is not None:
                    shown[y0:y1, x0:x1] = heatmap_overlay(crop, anomaly_map)

                scale = min(1.0, DISPLAY_MAX_WIDTH / frame.shape[1])
                display = cv2.resize(shown, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                p0, p1 = (int(x0 * scale), int(y0 * scale)), (int(x1 * scale), int(y1 * scale))
                cv2.rectangle(display, p0, p1, colour, 4)

                draw_text(display, f"{verdict}", (10, 50), 1.6, colour, 3)
                draw_text(display, f"anomaly score {score * 100:.0f}%   (threshold 50%, unsure "
                                   f"{args.unsure[0] * 100:.0f}-{args.unsure[1] * 100:.0f}%)", (10, 90), 0.7, colour)
                draw_text(display, f"{args.device}: {np.median(times):.0f} ms per check", (10, 120), 0.6, (255, 255, 255), 1)

            if display is not None:
                hint = "FROZEN  " if frozen else ""
                shown_now = display.copy()
                draw_text(shown_now, f"{hint}space=freeze  h=heatmap  q=quit", (10, shown_now.shape[0] - 12), 0.55,
                          (255, 255, 255), 1)
                cv2.imshow(WINDOW, shown_now)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                frozen = not frozen
            elif key == ord("h"):
                show_heatmap = not show_heatmap
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
