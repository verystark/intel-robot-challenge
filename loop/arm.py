"""Follower arm helpers shared by run_cell.py and show_tool.py.

Runs in Studio's backend venv (physical-ai-studio/application/backend/.venv), which
has physicalai and the SO-101 driver.

- The follower is found by its fixed USB serial path, never /dev/ttyACM*.
- Its calibration is read (read-only) from Studio's database, so it always matches Studio.
- connect_follower() takes the same device lock as Studio, so Studio refuses to load the
  arm while a script holds it, and the script refuses while Studio holds it.
- Joint units are Studio's "normalized" units: body joints -100..100, gripper 0..100.
- send_action() jumps straight to the target, so every scripted move goes through
  move_to(), which interpolates at 30 Hz, watches for lagging joints and honours
  the stop flag.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
POSES_PATH = HERE / "poses.json"
STUDIO_DB = Path.home() / ".local/share/physicalai/data/physicalai.db"
FOLLOWER_SERIAL = "5B3E090516"
FOLLOWER_PORT = f"/dev/serial/by-id/usb-1a86_USB_Single_Serial_{FOLLOWER_SERIAL}-if00"
LOCK_NAME = "intel-cell-loop"
JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")
WRIST_ROLL, GRIPPER = 4, 5
BODY = slice(0, 5)
FPS = 30


class Stopped(Exception):
    """The stop flag was set during a scripted move; the arm is holding where it was."""


class ArmError(Exception):
    """A scripted move could not finish safely; the arm is holding where it was."""


def load_calibration(serial: str = FOLLOWER_SERIAL) -> dict:
    """The follower's calibration from Studio's database (opened read-only)."""
    if not STUDIO_DB.exists():
        raise FileNotFoundError(f"Studio database not found at {STUDIO_DB}")
    db = sqlite3.connect(f"file:{STUDIO_DB}?mode=ro", uri=True)
    try:
        for (payload,) in db.execute("SELECT payload FROM project_robots"):
            data = json.loads(payload) if isinstance(payload, str) else payload
            if data.get("serial_number") == serial:
                if data.get("unit") != "normalized":
                    raise ValueError(f"Follower unit is {data.get('unit')!r}; the policies were trained on 'normalized'.")
                return data["calibration"]
    finally:
        db.close()
    raise LookupError(f"No robot with serial {serial} in Studio's database")


def roll_units_per_degree(calibration: dict) -> float:
    """Normalized units per degree of wrist roll (200 units span the calibrated range)."""
    roll = calibration["wrist_roll"]
    span_deg = (roll["range_max"] - roll["range_min"]) * 360 / 4096
    return 200 / span_deg


def load_poses(path: Path = POSES_PATH) -> dict[str, np.ndarray]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {name: np.array(value["joints"], dtype=np.float32) for name, value in data.items()}


def save_pose(name: str, joints: np.ndarray, note: str = "", path: Path = POSES_PATH) -> None:
    data = json.loads(path.read_text()) if path.exists() else {}
    data[name] = {
        "joints": [round(float(v), 2) for v in joints],
        "joint_names": list(JOINTS),
        "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
    }
    path.write_text(json.dumps(data, indent=2) + "\n")


def roll_target(current_roll: float, degrees: float, units_per_deg: float) -> float | None:
    """Wrist roll after turning by `degrees`, trying the other direction if out of range."""
    for sign in (1, -1):
        target = current_roll + sign * degrees * units_per_deg
        if -100 <= target <= 100:
            return target
    return None


@dataclass
class Stop:
    """One inspection stop: the angle asked for, the angle the wrist can really reach, its roll target."""

    asked_deg: float
    deg: float
    roll: float

    @property
    def name(self) -> str:
        return f"{self.deg:.0f} deg"  # plain ASCII: OpenCV's screen font has no degree sign


def plan_stops(show_roll: float, stops_deg: list[float], units_per_deg: float, margin: float = 2.0) -> list[Stop]:
    """Wrist-roll targets for the inspection stops, all turned the same way from the show pose.

    The direction is the one with room for the largest stop; if neither has room (a show pose
    with wrist_roll near 0 can't turn a full 180 deg either way), the largest stops are capped
    at the joint's range, e.g. about 173 deg from a roll of -2. run_cell.py and show_tool.py's
    collect mode both use this, so training photos and live photos come from the same angles.
    """
    lo, hi = -100 + margin, 100 - margin
    need = max(abs(d) for d in stops_deg) * units_per_deg
    room_up, room_down = hi - show_roll, show_roll - lo
    if room_up >= need:
        sign = 1
    elif room_down >= need:
        sign = -1
    else:
        sign = 1 if room_up >= room_down else -1
    stops = []
    for asked in stops_deg:
        roll = float(np.clip(show_roll + sign * abs(asked) * units_per_deg, lo, hi))
        stops.append(Stop(asked, abs(roll - show_roll) / units_per_deg, roll))
    return stops


@dataclass
class MoveLimits:
    speed: float = 60.0  # normalized units per second, fastest joint
    min_time_s: float = 0.5
    settle_s: float = 0.35  # wait after the move before a photo
    lag_limit: float = 20.0  # abort if a body joint trails its command by more than this
    arrive_tol: float = 4.0


@dataclass
class Arm:
    """The robot (real SO101 or MockRobot) plus a stop flag every scripted move checks."""

    robot: object
    stop: threading.Event = field(default_factory=threading.Event)
    limits: MoveLimits = field(default_factory=MoveLimits)
    last_command: np.ndarray | None = None

    def joints(self) -> np.ndarray:
        return np.asarray(self.robot.get_observation().joint_positions, dtype=np.float32)

    def take_over(self, command: np.ndarray | None) -> None:
        """Hand-over from the policy: remember the last action it sent, which the servos still hold.

        Scripted moves then continue from that goal instead of the measured position. With a
        brick held the two differ at the gripper (the brick stops the jaws short of their
        command: that gap is the squeeze), and a move starting from the measured gripper would
        relax the grip for its first part.
        """
        if command is not None:
            self.last_command = np.asarray(command, dtype=np.float32).copy()

    def _start(self) -> np.ndarray:
        """Where a scripted move starts: the servos' current goal (last command) when it is known
        and the body is close to it, else the measured position (the arm was moved or is blocked);
        the gripper always keeps its last command when known."""
        here = self.joints()
        if self.last_command is None:
            return here
        if np.max(np.abs(here[BODY] - self.last_command[BODY])) <= self.limits.lag_limit:
            return self.last_command.copy()
        start = here.copy()
        start[GRIPPER] = self.last_command[GRIPPER]
        return start

    def hold(self) -> None:
        """Stop where the arm is: body at its measured position, gripper still at its commanded
        value (commanding the measured gripper would release the squeeze on a held brick)."""
        here = self.joints()
        if self.last_command is not None:
            here[GRIPPER] = self.last_command[GRIPPER]
        self.robot.send_action(here)
        self.last_command = here

    def move_to(self, target: np.ndarray, speed: float | None = None, check_lag: bool = True) -> np.ndarray:
        """Smoothly move all joints to `target` (cosine easing), then wait until it arrives.

        Starts from the last command (see _start), so the hand-over from the policy and from one
        scripted move to the next has no step in the servos' goal. Returns the measured joints at
        the end. Raises Stopped or ArmError after commanding a hold.
        """
        limits = self.limits
        start = self._start()
        target = np.asarray(target, dtype=np.float32)
        distance = float(np.max(np.abs(target - start)))
        duration = max(limits.min_time_s, distance / (speed or limits.speed))
        steps = max(1, math.ceil(duration * FPS))
        t0 = time.perf_counter()
        for i in range(1, steps + 1):
            if self.stop.is_set():
                self.hold()
                raise Stopped("Stop pressed during a scripted move")
            s = 0.5 - 0.5 * math.cos(math.pi * i / steps)
            command = start + (target - start) * s
            self.robot.send_action(command)
            self.last_command = command
            if check_lag and i % 5 == 0:
                lag = np.abs(self.joints()[BODY] - command[BODY])
                if lag.max() > limits.lag_limit:
                    self.hold()
                    worst = JOINTS[int(np.argmax(lag))]
                    raise ArmError(f"{worst} is {lag.max():.0f} units behind its command: blocked or too fast")
            sleep = t0 + i / FPS - time.perf_counter()
            if sleep > 0:
                time.sleep(sleep)
        # Arrive: within tolerance, or stopped moving (a joint under load can rest a few units off
        # its command). The gripper is ignored: a held brick stops it short of its target.
        deadline = time.perf_counter() + 1.5
        prev, still_since = None, None
        while time.perf_counter() < deadline:
            if self.stop.is_set():
                self.hold()
                raise Stopped("Stop pressed during a scripted move")
            here = self.joints()
            if np.max(np.abs(here[BODY] - target[BODY])) <= limits.arrive_tol:
                break
            if prev is not None and np.max(np.abs(here[BODY] - prev[BODY])) * FPS < 2.0:
                still_since = still_since or time.perf_counter()
                if time.perf_counter() - still_since >= 0.15:
                    break
            else:
                still_since = None
            prev = here
            time.sleep(1 / FPS)
        time.sleep(limits.settle_s)
        return self.joints()

    def set_gripper(self, value: float, speed: float = 80.0) -> np.ndarray:
        target = self._start()
        target[GRIPPER] = value
        return self.move_to(target, speed=speed, check_lag=False)

    def turn_wrist(self, degrees: float, units_per_deg: float, speed: float = 90.0) -> np.ndarray:
        """Turn wrist_roll by `degrees` (other direction if out of range). Raises ArmError if neither fits."""
        here = self.joints()
        base = self.last_command if self.last_command is not None else here
        roll = roll_target(float(base[WRIST_ROLL]), degrees, units_per_deg)
        if roll is None:
            raise ArmError(f"A {degrees:.0f}° wrist turn doesn't fit from wrist_roll {base[WRIST_ROLL]:.0f}")
        target = base.copy()
        target[WRIST_ROLL] = roll  # the gripper keeps base's (commanded) value: no change in squeeze
        return self.move_to(target, speed=speed)


def connect_follower(calibration: dict | None = None):
    """Connect the real follower under Studio's device lock. Returns (robot, locks).

    Connecting runs the driver's servo setup, which switches torque off and on
    once, so the arm can sag briefly: someone must be at the station.
    """
    from physicalai.robot.transport._lock import LockContention, acquire_locks
    from physicalai_so101_plugin import SO101

    calibration = calibration or load_calibration()
    robot = SO101(port=FOLLOWER_PORT, calibration=calibration, role="follower", unit="normalized")
    try:
        locks = acquire_locks(LOCK_NAME, robot.device_ids)
    except LockContention as error:
        raise RuntimeError(
            "The follower is in use (Studio session, robot page, calibration wizard or another script). "
            f"Close it first. ({error})"
        ) from error
    try:
        robot.connect()
    except BaseException:
        locks.release_all()
        raise
    return robot, locks


# --- Simulation -------------------------------------------------------------------------


@dataclass
class MockObservation:
    joint_positions: np.ndarray
    timestamp: float
    sensor_data: dict | None = None
    images: dict | None = None

    @property
    def state(self) -> np.ndarray:
        return self.joint_positions


class MockRobot:
    """Stands in for the follower in --sim: follows each command with a short first-order lag."""

    joint_names = list(JOINTS)
    device_ids: tuple[str, ...] = ()

    def __init__(self, start: np.ndarray, time_constant_s: float = 0.06) -> None:
        self._pos = np.asarray(start, dtype=np.float32).copy()
        self._goal = self._pos.copy()
        self._tau = time_constant_s
        self._t = time.monotonic()
        self._lock = threading.Lock()
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def _advance(self) -> None:
        now = time.monotonic()
        alpha = 1 - math.exp(-(now - self._t) / self._tau)
        self._pos = self._pos + (self._goal - self._pos) * alpha
        self._t = now

    def get_observation(self) -> MockObservation:
        with self._lock:
            self._advance()
            return MockObservation(self._pos.copy(), time.monotonic())

    def send_action(self, action: np.ndarray, goal_time: float | None = None) -> None:  # noqa: ARG002
        with self._lock:
            self._advance()
            self._goal = np.clip(np.asarray(action, dtype=np.float32), -100, 100)

    def set_torque(self, enabled: bool) -> None:  # noqa: ARG002
        pass

    def teleport(self, joints: np.ndarray) -> None:
        """Simulation only: put the arm at the start of a replayed episode."""
        with self._lock:
            self._pos = np.asarray(joints, dtype=np.float32).copy()
            self._goal = self._pos.copy()
            self._t = time.monotonic()
