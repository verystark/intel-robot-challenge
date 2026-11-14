"""The demo screen: what the cell sees, decides and tells the robot, with live timings.

Drawn with OpenCV from a View snapshot, so it never touches the hardware. Layout (1600x900):

    header: model + devices, cycle, run state
    left:   live camera (top camera while the policy runs, inspection camera while showing)
            stage strip PICK > SHOW > INSPECT > SORT with times
    right:  verdict banner, the sentence sent to SmolVLA, inspection photos with heatmaps,
            score bar with the good / unsure / defective bands
    bottom: last cycle's timings, latency per model and device, temperature and loads, tallies
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

W, H = 1600, 900
BG = (24, 24, 28)
PANEL = (38, 38, 44)
TEXT = (235, 235, 235)
DIM = (150, 150, 155)
COLOURS = {"GOOD": (60, 180, 60), "DEFECTIVE": (40, 40, 220), "UNSURE": (0, 170, 240), "": (90, 90, 90)}
STAGES = ("PICK", "SHOW", "INSPECT", "SORT")
FONT = cv2.FONT_HERSHEY_SIMPLEX


@dataclass
class Photo:
    crop: np.ndarray
    heat_overlay: np.ndarray | None = None
    score: float | None = None
    label: str = ""
    ms: float | None = None


@dataclass
class View:
    """Everything the screen shows. The loop updates it; the screen only reads copies."""

    title: str = ""
    devices: str = ""
    cycle: int = 0
    run_state: str = "STARTING"
    stage: str = ""
    stage_started: float = 0.0
    stage_times: dict[str, float] = field(default_factory=dict)
    sentence: str = ""
    verdict: str = ""
    photos: list[Photo] = field(default_factory=list)
    bands: tuple[float, float] = (0.4, 0.6)
    last_cycle: dict = field(default_factory=dict)
    policy_ms: list[float] = field(default_factory=list)
    anomaly_ms: list[float] = field(default_factory=list)
    tallies: dict[str, int] = field(default_factory=lambda: {"GOOD": 0, "DEFECTIVE": 0, "rechecks": 0, "stops": 0})
    sys: dict = field(default_factory=dict)
    message: str = ""
    live: np.ndarray | None = None
    live_label: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set(self, **changes) -> None:
        with self.lock:
            for key, value in changes.items():
                setattr(self, key, value)


class Window:
    """Shows rendered frames in a Tk window and reports key presses.

    Studio's backend venv has a headless OpenCV (no imshow), so the screen uses Tk,
    which that Python ships with. Keys come back as single characters; Esc is "\\x1b".
    `f` toggles full screen.
    """

    def __init__(self, title: str) -> None:
        import tkinter as tk

        self.tk = tk
        self.root = tk.Tk()
        self.root.title(title)
        self.root.configure(background="#18181c")
        self.label = tk.Label(self.root, background="#18181c", borderwidth=0)
        self.label.pack(fill="both", expand=True)
        self.keys: list[str] = []
        self.closed = False
        self.fullscreen = False
        self.root.bind("<Key>", self._on_key)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.geometry(f"{W}x{H}")
        self._photo = None

    def _on_key(self, event) -> None:
        if event.keysym == "Escape":
            self.keys.append("\x1b")
        elif event.keysym == "space":
            self.keys.append(" ")
        elif event.char == "f":
            self.fullscreen = not self.fullscreen
            self.root.attributes("-fullscreen", self.fullscreen)
        elif event.char:
            self.keys.append(event.char.lower())

    def _on_close(self) -> None:
        self.keys.append("q")
        self.closed = True

    def show(self, img_bgr: np.ndarray) -> None:
        from PIL import Image, ImageTk

        w = max(self.label.winfo_width(), 1)
        h = max(self.label.winfo_height(), 1)
        if w > 50 and h > 50 and (w, h) != (img_bgr.shape[1], img_bgr.shape[0]):
            img_bgr = _fit(img_bgr, w, h)
        image = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        self._photo = ImageTk.PhotoImage(image)
        self.label.configure(image=self._photo)
        self.root.update()

    def poll(self, wait_s: float = 0.04) -> list[str]:
        end = time.monotonic() + wait_s
        while time.monotonic() < end and not self.closed:
            self.root.update()
            time.sleep(0.005)
        keys, self.keys = self.keys, []
        return keys

    def close(self) -> None:
        try:
            self.root.destroy()
        except Exception:  # noqa: BLE001
            pass


def _text(img, text, org, scale=0.6, colour=TEXT, thick=1) -> None:
    cv2.putText(img, text, org, FONT, scale, colour, thick, cv2.LINE_AA)


def _fit(img: np.ndarray, w: int, h: int) -> np.ndarray:
    ih, iw = img.shape[:2]
    s = min(w / iw, h / ih)
    resized = cv2.resize(img, (max(1, int(iw * s)), max(1, int(ih * s))))
    out = np.full((h, w, 3), PANEL, np.uint8)
    y, x = (h - resized.shape[0]) // 2, (w - resized.shape[1]) // 2
    out[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return out


def _pct(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def _ms(value: float | None) -> str:
    return f"{value:.0f} ms" if value is not None else "-"


def render(view: View) -> np.ndarray:
    with view.lock:
        v = View(**{k: getattr(view, k) for k in view.__dataclass_fields__ if k != "lock"})
    img = np.full((H, W, 3), BG, np.uint8)

    # Header
    cv2.rectangle(img, (0, 0), (W, 56), PANEL, -1)
    _text(img, v.title, (16, 24), 0.7, TEXT, 2)
    _text(img, v.devices, (16, 46), 0.5, DIM)
    state_colour = {"RUNNING": (60, 180, 60), "PAUSED": (0, 170, 240), "STOPPED": (40, 40, 220)}.get(v.run_state, DIM)
    _text(img, f"cycle {v.cycle}", (W - 330, 34), 0.8, TEXT, 2)
    _text(img, v.run_state, (W - 180, 34), 0.8, state_colour, 2)

    # Live view
    lx, ly, lw, lh = 16, 72, 768, 576
    if v.live is not None:
        img[ly:ly + lh, lx:lx + lw] = _fit(v.live, lw, lh)
    else:
        cv2.rectangle(img, (lx, ly), (lx + lw, ly + lh), PANEL, -1)
    _text(img, v.live_label, (lx + 10, ly + 26), 0.6, (255, 255, 255), 2)

    # Stage strip
    sy = ly + lh + 14
    bw = (lw - 3 * 10) // 4
    for i, name in enumerate(STAGES):
        x = lx + i * (bw + 10)
        active = v.stage == name
        cv2.rectangle(img, (x, sy), (x + bw, sy + 56), (190, 110, 40) if active else PANEL, -1)
        _text(img, name, (x + 12, sy + 24), 0.65, TEXT, 2)
        if active and v.stage_started:
            t = time.monotonic() - v.stage_started
            _text(img, f"{t:4.1f} s", (x + 12, sy + 47), 0.55, TEXT)
        elif name in v.stage_times:
            _text(img, f"{v.stage_times[name]:4.1f} s", (x + 12, sy + 47), 0.55, DIM)

    # Verdict banner and sentence
    rx, rw = 800, W - 816
    colour = COLOURS.get(v.verdict, COLOURS[""])
    cv2.rectangle(img, (rx, 72), (rx + rw, 152), colour, -1)
    _text(img, v.verdict or "waiting for a brick", (rx + 20, 128), 1.4 if v.verdict else 1.0, (255, 255, 255), 3)
    cv2.rectangle(img, (rx, 162), (rx + rw, 222), PANEL, -1)
    _text(img, "Sent to SmolVLA:", (rx + 12, 184), 0.5, DIM)
    _text(img, f'"{v.sentence}"' if v.sentence else "-", (rx + 12, 210), 0.62, TEXT, 1)

    # Photos with heatmaps
    py, ps = 236, 232
    for i in range(3):
        x = rx + i * (ps + 12)
        if i < len(v.photos):
            photo = v.photos[i]
            tile = photo.heat_overlay if photo.heat_overlay is not None else photo.crop
            img[py:py + ps, x:x + ps] = _fit(tile, ps, ps)
            lab_colour = COLOURS.get(photo.label, DIM)
            cv2.rectangle(img, (x, py + ps), (x + ps, py + ps + 30), lab_colour, -1)
            score = f"{photo.score:.2f}" if photo.score is not None else "scoring..."
            _text(img, f"view {i + 1}: {score} {photo.label}", (x + 6, py + ps + 21), 0.5, (255, 255, 255), 1)
        else:
            cv2.rectangle(img, (x, py), (x + ps, py + ps), PANEL, -1)

    # Score bar
    by, bx0, bx1 = py + ps + 58, rx + 10, rx + rw - 10
    low, high = v.bands
    def xof(s: float) -> int:
        return int(bx0 + (bx1 - bx0) * min(max(s, 0.0), 1.0))
    cv2.rectangle(img, (bx0, by), (xof(low), by + 18), COLOURS["GOOD"], -1)
    cv2.rectangle(img, (xof(low), by), (xof(high), by + 18), COLOURS["UNSURE"], -1)
    cv2.rectangle(img, (xof(high), by), (bx1, by + 18), COLOURS["DEFECTIVE"], -1)
    for i, photo in enumerate(v.photos):
        if photo.score is not None:
            x = xof(photo.score)
            cv2.line(img, (x, by - 8), (x, by + 26), (255, 255, 255), 3)
            _text(img, str(i + 1), (x - 5, by - 12), 0.5, TEXT, 1)
    _text(img, f"good < {low:.2f}", (bx0, by + 42), 0.5, DIM)
    unsure = "unsure: look again"
    uw = cv2.getTextSize(unsure, FONT, 0.5, 1)[0][0]
    _text(img, unsure, ((xof(low) + xof(high) - uw) // 2, by + 42), 0.5, DIM)
    bad = f"defective > {high:.2f}"
    _text(img, bad, (bx1 - cv2.getTextSize(bad, FONT, 0.5, 1)[0][0], by + 42), 0.5, DIM)

    # Timings and system
    ty = by + 74
    cv2.rectangle(img, (rx, ty), (rx + rw, H - 16), PANEL, -1)
    c = v.last_cycle
    lines = [
        ("Last cycle", f"{c.get('total_s', 0):.1f} s" if c else "-"),
        ("  pick / show+inspect / sort",
         " / ".join(f"{c.get(k, 0):.1f}" for k in ("pick_s", "show_s", "sort_s")) + " s" if c else "-"),
        ("Policy inference (median / p95)", f"{_ms(_pct(v.policy_ms, 50))} / {_ms(_pct(v.policy_ms, 95))}"),
        ("Anomalib per photo (median)", _ms(_pct(v.anomaly_ms, 50))),
        ("Sorted good / defective", f"{v.tallies.get('GOOD', 0)} / {v.tallies.get('DEFECTIVE', 0)}"
                                    f"   re-checks {v.tallies.get('rechecks', 0)}"),
    ]
    s = v.sys or {}
    def f(key, unit, digits=0):
        value = s.get(key)
        return f"{value:.{digits}f}{unit}" if value is not None else "-"
    lines.append(("Package temp / CPU / GPU / NPU",
                  f"{f('pkg_temp_c', ' C')} / {f('cpu_pct', '%')} / {f('gpu_pct', '%')} / {f('npu_pct', '%')}"))
    if s.get("pkg_w") is not None or s.get("battery_w") is not None:
        lines.append(("Power package / laptop", f"{f('pkg_w', ' W', 1)} / {f('battery_w', ' W', 1)}"))
    for i, (label, value) in enumerate(lines):
        _text(img, label, (rx + 14, ty + 28 + i * 26), 0.55, DIM)
        _text(img, value, (rx + 400, ty + 28 + i * 26), 0.58, TEXT, 1)

    # Footer
    _text(img, v.message, (16, H - 40), 0.6, (0, 200, 255), 1)
    _text(img, "Esc/s stop arm   space pause after this cycle   q quit", (16, H - 14), 0.5, DIM)
    return img
