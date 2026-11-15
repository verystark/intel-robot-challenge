"""The brick region inside the inspection crop: Anomalib scores only this part.

The whole box crop also shows the gripper, the wrist camera's orange bracket, the table edge
and anything lying on the table. Anything there that the model hasn't seen in training makes
the score jump, even when the brick is fine. Scoring a square around the brick keeps the
model on the brick.

roi.json (next to this file, and copied next to every model trained with train_export.py --roi)
has one of two forms:

    {"mode": "brick", "size": 0.5}
        Find the brick in every crop and cut a square of size x crop width centred on it.
        The square's size never changes, so the model's input size stays fixed.
    {"x0": 0.12, "y0": 0.22, "x1": 0.62, "y1": 0.98}
        A fixed box, as fractions of the crop (the first version: it only fits one wrist angle).

How the brick is found (find_brick): the brick always sits at the tips of the red gripper
fingers. The fingers are found by colour; the brick is the brick-coloured pixels (saturated
and not red, orange or cardboard brown, or bright white) near the finger tips. A red brick
merges with the fingers, and a dark brick may not stand out; then the square is centred just
inside the finger tips, where the brick is held.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROI_PATH = HERE / "roi.json"


def load_roi(path: Path = ROI_PATH) -> dict | None:
    return json.loads(Path(path).read_text()) if Path(path).exists() else None


def describe(roi: dict | None) -> str:
    if not roi:
        return "whole crop"
    if roi.get("mode") == "brick":
        return f"a {roi['size']:.2f} x crop square centred on the brick"
    return "fixed box " + str({k: roi[k] for k in ("x0", "y0", "x1", "y1")})


def _masks(crop_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Red finger pixels, and pixels that could be brick."""
    h_, s_, v_ = cv2.split(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV))
    red = ((h_ < 8) | (h_ > 165)) & (s_ > 120) & (v_ > 50)
    brownish = (h_ >= 6) & (h_ < 20)  # cardboard, the wooden table and the orange camera bracket
    colour = (s_ > 110) & (v_ > 70) & ~red & ~brownish
    white = (v_ > 150) & (s_ < 70)
    return red, colour | white


def find_brick(crop_bgr: np.ndarray) -> tuple[float, float, str]:
    """The brick's centre (x, y) in pixels, and how it was found: colour, tip or none."""
    h, w = crop_bgr.shape[:2]
    red, cand = _masks(crop_bgr)
    kernel = np.ones((5, 5), np.uint8)
    red = cv2.morphologyEx(red.astype(np.uint8), cv2.MORPH_OPEN, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(red)
    # The fingers are chunky blobs. A long thin red strip is the table edge, which shows up
    # reddish along the bottom of the crop; red bricks lying on the table can break it into
    # shorter pieces. So: the biggest chunky blob is a finger, and only blobs close to it count
    # as the other finger.
    def chunky_blob(i: int) -> bool:
        bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        flat = bh < 0.09 * h and bw > 3 * bh  # 121 of 122 such blobs in the photos are the table edge
        return stats[i, cv2.CC_STAT_AREA] > 0.01 * w * h and bw <= 5 * bh and not flat

    chunky = [i for i in range(1, n) if chunky_blob(i)]
    if not chunky:
        return w / 2, h / 2, "none"
    anchor = max(chunky, key=lambda i: stats[i, cv2.CC_STAT_AREA])
    ax, ay, aw, ah = stats[anchor, :4]

    def near_anchor(i: int) -> bool:
        bx, by, bw, bh = stats[i, :4]
        gap_x = max(bx - (ax + aw), ax - (bx + bw), 0)
        gap_y = max(by - (ay + ah), ay - (by + bh), 0)
        return gap_x <= 0.15 * w and gap_y <= 0.15 * h

    fingers = [i for i in chunky if near_anchor(i)]
    ys, xs = np.nonzero(np.isin(labels, fingers))
    tip_x = float(np.percentile(xs, 0.5))  # the fingers point left at the show pose
    tip_y = float(np.median(ys[xs < tip_x + 0.08 * w]))

    # Brick-coloured blobs within reach of the finger tips. A finger in front of the brick can
    # split it in two, so every blob near the tips counts.
    cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_OPEN, kernel)
    window = np.zeros_like(cand)
    x0, x1 = int(max(0, tip_x - 0.30 * w)), int(min(w, tip_x + 0.25 * w))
    y0, y1 = int(max(0, tip_y - 0.35 * h)), int(min(h, tip_y + 0.35 * h))
    window[y0:y1, x0:x1] = cand[y0:y1, x0:x1]
    window = cv2.morphologyEx(window, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(window)
    boxes = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < 0.006 * w * h:
            continue
        bx, by, bw, bh = stats[i, :4]
        dx = max(bx - tip_x, 0, tip_x - (bx + bw))
        dy = max(by - tip_y, 0, tip_y - (by + bh))
        if np.hypot(dx, dy) < 0.08 * w:
            boxes.append((bx, by, bx + bw, by + bh))
    if boxes:
        bx0, by0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        bx1, by1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        return (bx0 + bx1) / 2, (by0 + by1) / 2, "colour"
    return tip_x + 0.08 * w, tip_y, "tip"


def roi_box(crop_bgr: np.ndarray, roi: dict | None) -> tuple[int, int, int, int]:
    """(x0, y0, x1, y1) of the region Anomalib scores, in crop pixels."""
    h, w = crop_bgr.shape[:2]
    if not roi:
        return 0, 0, w, h
    if roi.get("mode") == "brick":
        side = min(int(round(roi["size"] * w)), w, h)
        cx, cy, _ = find_brick(crop_bgr)
        x0 = int(np.clip(round(cx - side / 2), 0, w - side))
        y0 = int(np.clip(round(cy - side / 2), 0, h - side))
        return x0, y0, x0 + side, y0 + side
    return (int(round(roi["x0"] * w)), int(round(roi["y0"] * h)),
            int(round(roi["x1"] * w)), int(round(roi["y1"] * h)))


def apply_roi(crop: np.ndarray, roi: dict | None) -> np.ndarray:
    """Cut the brick region out of a box crop. No roi = the crop unchanged."""
    x0, y0, x1, y1 = roi_box(crop, roi)
    return crop[y0:y1, x0:x1]
