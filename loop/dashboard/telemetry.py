"""Everything the dashboard shows that isn't in screen.View: frames, the policy's plan, history.

Writers (the control loop, the camera pump, the live scorer) only store references or small
values under a lock; the web server does the encoding in its own threads, so the dashboard never
slows the robot down.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

JOINT_NAMES = ("pan", "lift", "elbow", "wrist flex", "wrist roll", "gripper")


class Telemetry:
    def __init__(self, run_dir: Path | None = None) -> None:
        self.lock = threading.Lock()
        self.run_dir = run_dir
        self.frames: dict[str, tuple[float, np.ndarray, bool]] = {}  # name -> (time, image, is_rgb)
        self.trace: deque[tuple[float, list[float]]] = deque(maxlen=900)  # measured joints, 30 s at 30 Hz
        self.chunk: tuple[float, list[list[float]], float, str] | None = None  # (time, actions, ms, stage)
        self.chunk_ms: dict[str, deque[float]] = {"pick": deque(maxlen=200), "sort": deque(maxlen=200)}
        self.live: dict | None = None  # live inspection score: {"t", "score", "label", "moving", "heat"}
        self.sys_series: deque[tuple[float, dict]] = deque(maxlen=240)  # 2 min at 0.5 s
        self.history: list[dict] = []
        self.marks: dict[int, bool] = {}
        self.tiles: list[dict] = []  # current cycle's stop tiles: {"v", "image"} served from memory
        self.tile_version = 0
        self._last_trace = 0.0

    # --- writers ---------------------------------------------------------------------

    def put_frame(self, name: str, image: np.ndarray, rgb: bool) -> None:
        with self.lock:
            self.frames[name] = (time.monotonic(), image, rgb)

    def put_state(self, joints: np.ndarray) -> None:
        now = time.monotonic()
        if now - self._last_trace < 1 / 30:
            return
        self._last_trace = now
        with self.lock:
            self.trace.append((now, [round(float(x), 1) for x in joints]))

    def put_chunk(self, chunk: np.ndarray, latency_ms: float, stage: str) -> None:
        actions = np.asarray(chunk, dtype=np.float32).reshape(-1, 6)
        with self.lock:
            self.chunk = (time.monotonic(), actions.round(2).tolist(), latency_ms, stage)
            if stage in self.chunk_ms:
                self.chunk_ms[stage].append(latency_ms)

    def put_live(self, score: float | None, label: str, moving: bool, heat: np.ndarray | None) -> None:
        with self.lock:
            self.live = {"t": time.monotonic(), "score": score, "label": label, "moving": moving, "heat": heat}

    def put_sys(self, reading: dict) -> None:
        with self.lock:
            self.sys_series.append((time.monotonic(), dict(reading)))

    def set_tiles(self, images: list[np.ndarray]) -> None:
        with self.lock:
            self.tile_version += 1
            self.tiles = [{"v": self.tile_version, "image": im} for im in images]

    def add_history(self, entry: dict) -> None:
        with self.lock:
            self.history.append(entry)

    def mark(self, cycle: int, ok: bool | None) -> None:
        with self.lock:
            if ok is None:
                self.marks.pop(cycle, None)
            else:
                self.marks[cycle] = ok
            marks = dict(self.marks)
        if self.run_dir is not None:
            (self.run_dir / "marks.json").write_text(json.dumps({str(k): v for k, v in marks.items()}, indent=1) + "\n")

    # --- readers ---------------------------------------------------------------------

    def frame(self, name: str) -> tuple[float, np.ndarray, bool] | None:
        with self.lock:
            return self.frames.get(name)

    def live_heat(self) -> tuple[np.ndarray | None, str, bool, float]:
        """(heatmap, label, arm moving, age in s) of the newest live score."""
        with self.lock:
            if self.live is None:
                return None, "", False, 1e9
            return self.live["heat"], self.live["label"], self.live["moving"], time.monotonic() - self.live["t"]

    def tile(self, index: int) -> np.ndarray | None:
        with self.lock:
            return self.tiles[index]["image"] if 0 <= index < len(self.tiles) else None

    def snapshot(self) -> dict:
        """The JSON-friendly part, for the event stream."""
        now = time.monotonic()
        with self.lock:
            trace = [(round(t - now, 3), j) for t, j in list(self.trace)[-120:][::3]]  # last 4 s at 10 Hz
            chunk = None
            if self.chunk is not None:
                t, actions, ms, stage = self.chunk
                step = max(1, len(actions) // 25)
                chunk = {"age_s": round(now - t, 2), "actions": actions[::step], "every": step, "n": len(actions),
                         "ms": round(ms, 1), "stage": stage}
            live = None
            if self.live is not None:
                live = {k: v for k, v in self.live.items() if k not in ("heat", "t")}
                live["age_s"] = round(now - self.live["t"], 2)
            series = list(self.sys_series)[-120:]
            sys = {key: [r.get(key) for _, r in series] for key in ("gpu_pct", "npu_pct", "cpu_pct", "pkg_temp_c", "pkg_w", "battery_w")}
            chunk_ms = {k: (float(np.median(v)) if v else None) for k, v in self.chunk_ms.items()}
            history = [dict(h, mark=self.marks.get(h["cycle"])) for h in self.history[-10:]]
            marked = [self.marks[c] for c in self.marks]
            tiles = [t["v"] for t in self.tiles]
        return {"trace": trace, "chunk": chunk, "live": live, "sys": sys, "chunk_ms": chunk_ms,
                "history": history, "tiles": tiles,
                "success": {"ok": sum(1 for m in marked if m), "marked": len(marked)}}
