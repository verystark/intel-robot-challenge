"""Policy side of the loop: pick the Studio model, load it, tell when a stage is done, simulate.

- find_model() resolves "latest", a Studio model id/name, or an export folder, using
  Studio's database (read-only), and returns the export dir plus its dataset's tasks.
- load_policy() loads the OpenVINO export with physicalai's InferenceModel. With
  zero_noise, every call gets an all-zero `noise` input instead of fresh random noise:
  the flow-matching policy then gives the same chunk for the same input, which cut p99
  jerk 5-10x in the other session's offline tests (same tracking error).
- StageWatcher is a runtime callback that stops a policy stage once the arm moved away,
  came back near where the stage started and held still (how every pick and sort
  episode in main-clean / main-clean2 ends), with a timeout as backstop.
- SimWorld replays recorded episodes from a Studio dataset for --sim: camera frames
  for the policy, and (with ReplayModel) the recorded actions instead of a model.
"""

from __future__ import annotations

import json
import random
import sqlite3
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

STUDIO = Path.home() / ".local/share/physicalai"
STUDIO_DB = STUDIO / "data" / "physicalai.db"


# --- Model selection -------------------------------------------------------------------


@dataclass
class ModelInfo:
    export_dir: Path
    name: str
    model_id: str
    dataset_name: str | None
    dataset_dir: Path | None
    tasks: list[str]
    created: str
    policy: str = ""

    @property
    def takes_task(self) -> bool:
        """Whether the export reads a task sentence (SmolVLA does, ACT doesn't)."""
        manifest = json.loads((self.export_dir / "manifest.json").read_text())
        return '"task"' in json.dumps(manifest.get("model", {}).get("input_features", []))


def _db() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{STUDIO_DB}?mode=ro", uri=True)


def dataset_tasks(dataset_dir: Path) -> list[str]:
    import pandas as pd

    path = dataset_dir / "meta" / "tasks.parquet"
    return list(pd.read_parquet(path).index) if path.exists() else []


def find_model(spec: str = "latest", backend: str = "openvino") -> ModelInfo:
    """Resolve a Studio model with an export.

    `spec`: "latest", "latest:<policy>" (e.g. latest:smolvla, latest:act), a model name
    (e.g. SmolVLA-v2), a Studio model id or its first characters, or an export folder.
    """
    path = Path(spec).expanduser()
    if path.exists() and (path / "manifest.json").exists():
        manifest = json.loads((path / "manifest.json").read_text())
        return ModelInfo(path, path.name, "", None, None, [], "", manifest.get("policy", {}).get("name", ""))
    want_policy = spec.split(":", 1)[1].lower() if spec.startswith("latest:") else None
    db = _db()
    try:
        rows = db.execute(
            "SELECT m.id, m.name, m.created_at, m.policy, d.name, d.path FROM models m "
            "LEFT JOIN datasets d ON d.id = m.dataset_id ORDER BY m.created_at DESC"
        ).fetchall()
    finally:
        db.close()
    for model_id, name, created, policy, ds_name, ds_path in rows:
        export_dir = STUDIO / "models" / model_id / "exports" / backend
        if not (export_dir / "manifest.json").exists():
            continue
        matches = (
            spec == "latest"
            or (want_policy is not None and (policy or "").lower() == want_policy)
            or model_id.startswith(spec)
            or name == spec
        )
        if matches:
            ds_dir = Path(ds_path) if ds_path else None
            tasks = dataset_tasks(ds_dir) if ds_dir and ds_dir.exists() else []
            return ModelInfo(export_dir, name, model_id, ds_name, ds_dir, tasks, created, policy or "")
    raise LookupError(f"No Studio model matching {spec!r} with an {backend} export")


def sort_start_pose(dataset_dir: Path, pick_sentence: str) -> np.ndarray:
    """Median joint pose at the start of the dataset's sort episodes: where the sort policy expects
    to begin, holding the brick (used as the home pose when none is saved in poses.json)."""
    import glob

    import pandas as pd

    tasks = dataset_tasks(dataset_dir)
    columns = ["episode_index", "task_index", "observation.state"]
    data = pd.concat([pd.read_parquet(f, columns=columns)
                      for f in sorted(glob.glob(f"{dataset_dir}/data/*/*.parquet"))])
    firsts = data.groupby("episode_index").first()
    sort = firsts[[tasks[int(t)] != pick_sentence for t in firsts["task_index"]]]
    if sort.empty:
        raise LookupError(f"No sort episodes in {dataset_dir.name}")
    return np.median(np.stack(sort["observation.state"].to_numpy()), axis=0).astype(np.float32)


def list_models(backend: str = "openvino") -> list[ModelInfo]:
    db = _db()
    try:
        ids = [r[0] for r in db.execute("SELECT id FROM models ORDER BY created_at DESC")]
    finally:
        db.close()
    out = []
    for model_id in ids:
        try:
            out.append(find_model(model_id, backend))
        except LookupError:
            pass
    return out


class SwitchSource:
    """One action source for RobotRuntime that hands over to the pick or the sort policy.

    RobotRuntime can't swap its action source, so this forwards to whichever
    PolicySource is active; choose it with use() before each run().
    """

    def __init__(self, sources: dict) -> None:
        self.sources = sources
        self.active = next(iter(sources.values()))

    def use(self, name: str) -> None:
        self.active = self.sources[name]

    def connect(self, *, bus, session_id: str) -> None:
        self.active.connect(bus=bus, session_id=session_id)

    def update(self, robot_state, camera_frames, step: int):
        return self.active.update(robot_state, camera_frames, step)

    def disconnect(self) -> None:
        self.active.disconnect()

    def set_task(self, task: str | None) -> None:
        self.active.set_task(task)

    def reset(self, *, reset_model: bool = True) -> None:
        self.active.reset(reset_model=reset_model)

    @property
    def action_queue(self):
        return self.active.action_queue


# --- Loading ---------------------------------------------------------------------------


class ZeroNoiseModel:
    """Wraps InferenceModel and feeds an all-zero `noise` input on every call."""

    def __init__(self, model, noise_shape: tuple[int, ...]) -> None:
        self._model = model
        self._noise = np.zeros((1, *noise_shape), dtype=np.float32)

    def predict_action_chunk(self, observation: dict) -> np.ndarray:
        observation = dict(observation)
        observation.setdefault("noise", self._noise)
        return self._model.predict_action_chunk(observation)

    def reset(self) -> None:
        self._model.reset()

    def close(self) -> None:
        close = getattr(self._model, "close", None)
        if close:
            close()

    def __getattr__(self, name: str):
        return getattr(self._model, name)


def noise_shape(export_dir: Path) -> tuple[int, ...] | None:
    manifest = json.loads((export_dir / "manifest.json").read_text())
    text = json.dumps(manifest)
    if '"noise"' not in text:
        return None
    for pre in manifest.get("model", {}).get("preprocessors", []):
        if pre.get("type") == "noise":
            shape = pre.get("shape") or pre.get("noise_shape")
            if shape:
                return tuple(int(x) for x in shape)
    return (50, 32)  # SmolVLA: chunk 50 x max action dim 32


def load_policy(export_dir: Path, device: str, zero_noise: bool = True):
    from physicalai.inference import InferenceModel

    model = InferenceModel(str(export_dir), backend="openvino", device=device)
    shape = noise_shape(export_dir) if zero_noise else None
    return ZeroNoiseModel(model, shape) if shape else model


# --- Stage end detection ---------------------------------------------------------------


@dataclass
class StageRules:
    timeout_s: float = 25.0
    min_time_s: float = 1.5
    moved_away: float = 40.0  # body joints must get this far from the start pose first
    still_speed: float = 15.0  # units/s, fastest body joint
    hold_s: float = 0.5
    return_tol: float = 45.0  # end must be this close to the start pose (0 = don't check)


class StageWatcher:
    """Runtime callback: stops the run when the current stage looks finished."""

    def __init__(self) -> None:
        self.runtime = None
        self.rules = StageRules()
        self.stage = ""
        self.start_pose: np.ndarray | None = None
        self.t0 = 0.0
        self.away = False
        self.still_since: float | None = None
        self.prev: tuple[float, np.ndarray] | None = None
        self.result = ""
        self.latest_frames: dict = {}
        self.latest_state: np.ndarray | None = None
        self.inference_ms: list[float] = []
        self.clamped = 0
        self.max_step = 12.0  # units per tick (360 units/s): larger jumps are clamped
        self.ease_step = 2.0  # units per tick at the very start of a stage (60 units/s)
        self.ease_s = 1.0
        self._last_action: np.ndarray | None = None
        self.stop_flag: threading.Event | None = None
        self.telemetry = None  # dashboard: camera frames, joint trace, the policy's plans
        self._lock = threading.Lock()

    def begin(self, stage: str, start_pose: np.ndarray, rules: StageRules,
              command_ref: np.ndarray | None = None) -> None:
        with self._lock:
            self.stage, self.rules = stage, rules
            self.start_pose = np.asarray(start_pose, dtype=np.float32)
            self.t0 = time.monotonic()
            self.away, self.still_since, self.prev, self.result = False, None, None, ""
            self.inference_ms = []
            self.clamped = 0
            # Start the step limit from the servos' current goal (the last scripted command, else
            # where the arm is), and ramp it up over ease_s, so the first policy action can't yank
            # the arm (Studio uses a 3 s grace).
            ref = command_ref if command_ref is not None else self.start_pose
            self._last_action = np.asarray(ref, dtype=np.float32).copy()

    def on_tick(self, event) -> None:
        now = time.monotonic()
        state = np.asarray(event.robot_state.joint_positions, dtype=np.float32)
        self.latest_state = state
        if event.camera_frames:
            self.latest_frames = dict(event.camera_frames)
        if self.telemetry is not None:
            self.telemetry.put_state(state)
            for name, frame in (event.camera_frames or {}).items():
                self.telemetry.put_frame(name, frame.data, rgb=True)
        if self.runtime is None or self.start_pose is None or self.result:
            return
        if self.stop_flag is not None and self.stop_flag.is_set():
            self.result = "stopped"
            self.runtime.stop()
            return
        rules = self.rules
        elapsed = now - self.t0
        distance = float(np.max(np.abs(state[:5] - self.start_pose[:5])))
        if distance > rules.moved_away:
            self.away = True
        speed = 0.0
        if self.prev is not None:
            dt = now - self.prev[0]
            if dt > 0:
                speed = float(np.max(np.abs(state[:5] - self.prev[1][:5])) / dt)
        self.prev = (now, state)
        near = rules.return_tol <= 0 or distance <= rules.return_tol
        if self.away and near and speed < rules.still_speed and elapsed > rules.min_time_s:
            self.still_since = self.still_since or now
            if now - self.still_since >= rules.hold_s:
                self.result = "done"
                self.runtime.stop()
                return
        else:
            self.still_since = None
        if elapsed > rules.timeout_s:
            self.result = "timeout"
            self.runtime.stop()

    def on_inference(self, event) -> None:
        self.inference_ms.append(event.latency_s * 1000)
        if self.telemetry is not None and getattr(event, "chunk", None) is not None:
            self.telemetry.put_chunk(event.chunk, event.latency_s * 1000, self.stage.lower())

    def on_action_ready(self, *, action: np.ndarray, step: int) -> np.ndarray:  # noqa: ARG002
        """Safety: limit how far any joint may jump in one tick, gently at the start of a stage."""
        action = np.asarray(action, dtype=np.float32)
        if self._last_action is not None:
            ramp = min(1.0, (time.monotonic() - self.t0) / self.ease_s) if self.ease_s > 0 else 1.0
            limit = self.ease_step + (self.max_step - self.ease_step) * ramp
            delta = action - self._last_action
            if np.max(np.abs(delta)) > limit:
                self.clamped += 1
                action = self._last_action + np.clip(delta, -limit, limit)
        self._last_action = action
        if self.telemetry is not None:
            self.telemetry.put_command(action)
        return action


# --- Simulation ------------------------------------------------------------------------


def _decode(video: Path, start_s: float, seconds: float, fps: int, size=(640, 480)) -> list[np.ndarray]:
    w, h = size
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start_s:.3f}", "-t", f"{seconds:.3f}", "-i", str(video),
           "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
    return list(frames)


class SimWorld:
    """Recorded episodes from a Studio dataset, picked per stage and replayed in real time."""

    def __init__(self, dataset_dir: Path, frame_fps: int = 15, seed: int = 0) -> None:
        import glob

        import pandas as pd

        self.dir = dataset_dir
        self.fps = 30
        self.frame_fps = frame_fps
        self.rng = random.Random(seed)
        self.tasks = dataset_tasks(dataset_dir)
        eps = pd.concat([pd.read_parquet(f) for f in glob.glob(f"{dataset_dir}/meta/episodes/*/*.parquet")])
        data = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{dataset_dir}/data/*/*.parquet"))])
        self.episodes: dict[str, list[dict]] = {}
        for _, row in eps.iterrows():
            ep = int(row["episode_index"])
            rows = data[data["episode_index"] == ep]
            task = self.tasks[int(rows["task_index"].iloc[0])]
            self.episodes.setdefault(task, []).append({
                "index": ep,
                "state": np.stack(rows["observation.state"].to_numpy()).astype(np.float32),
                "action": np.stack(rows["action"].to_numpy()).astype(np.float32),
                "video": {cam: (int(row[f"videos/observation.images.{cam}/chunk_index"]),
                                int(row[f"videos/observation.images.{cam}/file_index"]),
                                float(row[f"videos/observation.images.{cam}/from_timestamp"]))
                          for cam in ("top", "wrist")},
            })
        self.current: dict | None = None
        self.frames: dict[str, list[np.ndarray]] = {}
        self.t0 = time.monotonic()
        self._cache: dict[tuple[int, str], list[np.ndarray]] = {}

    def start_pose(self, task: str) -> np.ndarray:
        return self.episodes[task][0]["state"][0].copy()

    def begin(self, task: str) -> dict:
        self.current = self.rng.choice(self.episodes[task])
        for cam in ("top", "wrist"):
            key = (self.current["index"], cam)
            if key not in self._cache:
                chunk, file, start = self.current["video"][cam]
                video = self.dir / "videos" / f"observation.images.{cam}" / f"chunk-{chunk:03d}" / f"file-{file:03d}.mp4"
                seconds = len(self.current["action"]) / self.fps
                self._cache[key] = _decode(video, start, seconds, self.frame_fps)
            self.frames[cam] = self._cache[key]
        self.t0 = time.monotonic()
        return self.current

    def frame(self, cam: str) -> np.ndarray:
        frames = self.frames.get(cam)
        if not frames:
            return np.zeros((480, 640, 3), np.uint8)
        i = min(int((time.monotonic() - self.t0) * self.frame_fps), len(frames) - 1)
        return frames[i]

    def actions_from(self, elapsed_s: float, n: int) -> np.ndarray:
        actions = self.current["action"]
        i = min(int(elapsed_s * self.fps), len(actions) - 1)
        chunk = actions[i:i + n]
        if len(chunk) < n:
            chunk = np.concatenate([chunk, np.repeat(actions[-1:], n - len(chunk), axis=0)])
        return chunk


class ReplayCamera:
    """physicalai Camera stand-in that serves SimWorld frames."""

    def __init__(self, world: SimWorld, name: str) -> None:
        self.world, self.name, self._seq = world, name, 0

    def connect(self, timeout: float = 5.0) -> None:  # noqa: ARG002
        pass

    def disconnect(self) -> None:
        pass

    def _frame(self):
        from physicalai.capture.frame import Frame

        self._seq += 1
        return Frame(data=self.world.frame(self.name), timestamp=time.monotonic(), sequence=self._seq)

    def read(self, timeout: float = 2.0):  # noqa: ARG002
        return self._frame()

    def read_latest(self):
        return self._frame()


class ReplayModel:
    """Model stand-in for --sim without a policy: returns the recorded episode's actions."""

    def __init__(self, world: SimWorld, chunk: int = 50, latency_s: float = 0.0) -> None:
        self.world, self.chunk, self.latency_s = world, chunk, latency_s

    def predict_action_chunk(self, observation: dict) -> np.ndarray:  # noqa: ARG002
        if self.latency_s:
            time.sleep(self.latency_s)
        return self.world.actions_from(time.monotonic() - self.world.t0, self.chunk)

    def reset(self) -> None:
        pass

    def close(self) -> None:
        pass
