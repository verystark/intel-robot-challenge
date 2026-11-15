"""The closed loop: pick -> show -> inspect -> sort, with the Anomalib verdict steering SmolVLA.

Each cycle:
  0. HOME     If the arm isn't at the home pose, a scripted move there (the pick episodes start there).
  1. PICK     The pick policy, "Pick up the brick.", until the arm has gone out, come back and held still.
  2. SHOW     Scripted: smooth move to the saved show pose (loop/poses.json).
  3. INSPECT  Photos at the wrist stops of cell_config.json show.stops_deg (now only 90 deg: at 0 and
              180 deg a gripper finger hides the brick; out-and-back lists such as 0, 90, 180, 90, 0
              also work), 3 frames each; a stop's score is the median of its frames. Each stop is
              scored on the GPU while the wrist turns to the next. Any stop clearly defective -> DEFECTIVE at once; all clearly
              good -> GOOD; otherwise a second look at the unsure stops; still unsure -> DEFECTIVE.
  4. HOME     Scripted move back to the home pose, where the sort episodes start.
  5. SORT     The sort policy with the verdict's sentence, until it has gone out, come back and held still.
  6. LOG      Every stage time, every policy inference latency, every score, the photos and
              heatmaps, temperatures and loads: loop/runs/<time>/cycles.jsonl.

Every scripted move keeps the gripper at the value the policy last commanded, so the squeeze on
the brick never changes. The home pose is the saved `home` in loop/poses.json, or else where the
sort model's dataset episodes start.

Run it with Studio's backend Python (it has physicalai and the SO-101 driver):

    PY=physical-ai-studio/application/backend/.venv/bin/python
    $PY loop/run_cell.py --sim --replay        # no hardware, no model: recorded episodes and photos
    $PY loop/run_cell.py --sim                 # no hardware, the real SmolVLA on recorded frames
    $PY loop/run_cell.py --inspect-only        # real arm: show + inspect a brick placed in the gripper
    $PY loop/run_cell.py                       # the full cell
    $PY loop/run_cell.py --cycles 5 --model SmolVLA-v2 --anomaly-device GPU
    $PY loop/run_cell.py --pick-model latest:act --pick-device NPU   # ACT picks on the NPU, SmolVLA sorts

Before running on the real arm: close every Studio session and robot page that uses the
follower, close capture.py / inspect_live.py (they hold the inspection webcam), save the show
pose with show_tool.py, and have someone at the follower's 12 V plug.

Keys in the window: Esc or s = stop the arm now (it holds position), r = resume after a stop,
space = pause after this cycle / continue, q = quit. Ctrl+C in the terminal also stops.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import traceback
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "bench"))
sys.path.insert(0, str(REPO / "anomaly"))

from arm import (  # noqa: E402
    GRIPPER,
    WRIST_ROLL,
    Arm,
    ArmError,
    MockRobot,
    MoveLimits,
    Stopped,
    connect_follower,
    load_calibration,
    Stop,
    load_poses,
    plan_stops,
    roll_units_per_degree,
)
from detector import DEFECTIVE, GOOD, UNSURE, heatmap_overlay, label, load_bands  # noqa: E402
from inspection import InspectionCamera, LiveScorer, ReplayInspectionCamera, Scorer  # noqa: E402
from policy import (  # noqa: E402
    ReplayCamera,
    ReplayModel,
    SimWorld,
    StageRules,
    StageWatcher,
    SwitchSource,
    find_model,
    load_policy,
    sort_start_pose,
)
from screen import Photo, View, Window, render  # noqa: E402
from sysmon import SysMon, SysMonThread  # noqa: E402
from dashboard.server import DashboardServer  # noqa: E402
from dashboard.telemetry import Telemetry  # noqa: E402

WINDOW = "Intel Physical AI cell"


class Quit(Exception):
    pass


# What the screen says during each stage: plain, specific, and true at that moment.
NARRATION = {
    "PICK": "Picking a brick: {pick} reads the top and wrist cameras and plans the arm's next moves.",
    "SHOW": "Holding the brick in front of the inspection camera (a scripted move to one fixed pose).",
    "HOME_BEFORE": "Moving to the start pose, where every recorded pick began.",
    "HOME_AFTER": "Returning to the start pose, still holding the brick.",
    "SORT": "{sort} follows the sentence and puts the brick on the {colour} plate.",
}


class Cell:
    def __init__(self, args: argparse.Namespace, cfg: dict) -> None:
        self.args, self.cfg = args, cfg
        self.view = View()
        self.stop = threading.Event()  # stop the arm now
        self.quit = threading.Event()
        self.pause_after_cycle = threading.Event()
        self.resume = threading.Event()
        self.runtime = None
        self.inspection = None
        self.scorer = None
        self.locks = None
        self.run_dir = REPO / "loop" / "runs" / time.strftime("%Y%m%d_%H%M%S")
        self.sysmon = SysMonThread(interval_s=0.5)
        self.cycle_mon = SysMon()
        self.all_policy_ms: list[float] = []
        self.all_anomaly_ms: list[float] = []
        self.telemetry = Telemetry(self.run_dir)
        self.cam_lock = threading.Lock()  # the camera pump and the runtime never read a camera at once
        self.policy_running = False
        self.policy_cams: dict = {}
        self.live_scorer = None
        self.mode = "SIMULATION" if args.sim else ("INSPECT ONLY" if args.inspect_only else "LIVE")
        self.cycle_times: list[float] = []
        self.models: dict = {}
        self._frame_cache: dict = {}
        self.view.set(narration="Loading the models…", run_state="STARTING")
        self.t_ready: float | None = None
        self.step_detail = ""
        self._hot = False
        self.telemetry.event(3, "CELL", f"Starting · mode {self.mode}")

    # --- Setup -----------------------------------------------------------------------

    def setup(self) -> None:
        from physicalai.runtime import (
            AsyncExecution,
            ChunkedActionQueue,
            LerpSmoother,
            PolicySource,
            RobotRuntime,
            SyncExecution,
        )

        args, cfg = self.args, self.cfg
        sentences = cfg["sentences"]
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log = (self.run_dir / "cycles.jsonl").open("a")
        self.say("Loading...")

        calibration = load_calibration()
        self.roll_per_deg = roll_units_per_degree(calibration)
        poses = load_poses()

        # The pick and sort policies can be the same SmolVLA or different models (e.g. ACT picks).
        # Even --sim --replay needs the Studio records: the sort model's dataset is replayed.
        self.models = {"pick": find_model(args.pick_model), "sort": find_model(args.sort_model)}
        checks = {"pick": [sentences["pick"]], "sort": [sentences["GOOD"], sentences["DEFECTIVE"]]}
        for stage, info in self.models.items():
            if info.takes_task and info.tasks:
                missing = [x for x in checks[stage] if x not in info.tasks]
                if missing:
                    raise SystemExit(f"The {stage} model {info.name} was trained on {info.dataset_name}, which "
                                     f"has no task {missing}.\nIts tasks: {info.tasks}")
        if not self.models["sort"].takes_task:
            raise SystemExit(f"The sort model {self.models['sort'].name} ({self.models['sort'].policy}) can't read "
                             "the verdict sentence. Use a SmolVLA for the sort.")
        info = self.models["sort"]

        # Robot and policy cameras
        world = None
        if args.sim:
            dataset_dir = Path(args.sim_dataset) if args.sim_dataset else info.dataset_dir
            self.say(f"Simulation: replaying episodes from {dataset_dir.name}")
            world = SimWorld(dataset_dir)
            self.world = world
            robot = MockRobot(world.start_pose(sentences["pick"]))
            cameras = {"top": ReplayCamera(world, "top"), "wrist": ReplayCamera(world, "wrist")}
        elif args.inspect_only:
            robot, self.locks = connect_follower(calibration)
            cameras = {}
        else:
            robot, self.locks = connect_follower(calibration)
            cameras = self._real_cameras()
        self.policy_cams = cameras
        self.arm = Arm(robot, stop=self.stop, limits=MoveLimits(speed=cfg["show"]["speed"],
                                                                 settle_s=cfg["show"]["settle_s"]))
        self.arm.on_joints = self.telemetry.put_state
        self.arm.on_command = self.telemetry.put_command

        # Show pose
        if "show" in poses:
            self.show_pose = poses["show"]
        elif args.sim:
            pose = world.start_pose(sentences["pick"])
            pose[1] += 25
            pose[2] -= 25
            self.show_pose = pose
            self.say("No saved show pose: using a made-up one for the simulation")
        else:
            raise SystemExit("No show pose saved. Run: loop/show_tool.py save   (see loop/README.md)")
        self.via_pose = poses.get("via")
        if "home" in poses:
            self.home_pose = poses["home"]
        else:
            self.home_pose = sort_start_pose(self.models["sort"].dataset_dir, sentences["pick"])
            self.say(f"No saved home pose: using where the sort episodes start in {self.models['sort'].dataset_name}")
        self.grip = float(self.arm.joints()[GRIPPER])

        # Policy
        self.watcher = StageWatcher()
        self.watcher.stop_flag = self.stop
        self.watcher.max_step = float(cfg["max_step_per_tick"])
        self.watcher.telemetry = self.telemetry
        if not args.inspect_only:
            threshold = float(cfg["request_threshold"])
            sources, names, loaded = {}, {}, {}
            for stage in ("pick", "sort"):
                model_info, device = self.models[stage], args.pick_device if stage == "pick" else args.sort_device
                if args.sim and args.replay:
                    names[stage] = "replayed episodes"
                    key = "replay"
                else:
                    names[stage] = f"{model_info.name} on {device}"
                    key = (model_info.model_id or str(model_info.export_dir), device)
                if key in loaded:  # same model and device for both stages: load it once
                    sources[stage] = loaded[key]
                    continue
                if key == "replay":
                    model = ReplayModel(world)
                else:
                    self.say(f"Loading {model_info.name} on {device}...")
                    model = load_policy(model_info.export_dir, device, zero_noise=cfg["zero_noise"])
                execution = AsyncExecution(request_threshold=threshold) if cfg["execution"] == "async" \
                    else SyncExecution(request_threshold=threshold)
                sources[stage] = loaded[key] = PolicySource(
                    model, execution,
                    ChunkedActionQueue(smoother=LerpSmoother(duration_frames=int(cfg["lerp_frames"]))),
                    task=sentences["pick"] if model_info.takes_task else None)
            self.policy_source = SwitchSource(sources)
            self.runtime = RobotRuntime(robot, self.policy_source, fps=float(cfg["fps"]), cameras=cameras,
                                        callbacks=[self.watcher])
            self.watcher.runtime = self.runtime
            self.runtime.connect()
            if not args.sim:
                self._check_cameras(cameras)
            policy_name = (f"Pick: {names['pick']}  |  Sort: {names['sort']}" if names["pick"] != names["sort"]
                           else f"Policy: {names['pick']}")
        else:
            policy_name = "No policy (inspect only)"

        # Inspection
        if args.sim:
            folders = [Path(p) for p in args.sim_photos] if args.sim_photos else \
                [REPO / "anomaly/dataset/test_normal", REPO / "anomaly/dataset/abnormal"]
            self.inspection = ReplayInspectionCamera([f for f in folders if f.exists()])
        else:
            self.inspection = InspectionCamera()
        model_xml = REPO / (args.anomaly_model or cfg["anomaly_model"])
        self.say(f"Loading Anomalib on {args.anomaly_device}...")
        self.scorer = Scorer(model_xml, args.anomaly_device)
        bands_path = Path(args.bands) if args.bands else REPO / "anomaly/bands.json"
        self.bands = load_bands(bands_path)
        bands_info = json.loads(bands_path.read_text()) if bands_path.exists() else {}
        self.live_scorer = LiveScorer(model_xml, args.anomaly_device, self.inspection, self.scorer, self.telemetry,
                                      lambda: self.bands, lambda: self.view.stage in ("SHOW", "INSPECT"),
                                      lambda: self.arm.moving)
        if bands_info.get("device") and bands_info["device"] != args.anomaly_device:
            self.say(f"Note: bands were calibrated on {bands_info['device']}, Anomalib runs on {args.anomaly_device}")

        mode = self.mode
        self.view.set(
            title=f"Intel Physical AI cell  [{mode}]",
            devices=f"{policy_name}   |   Anomalib PatchCore on {args.anomaly_device}   |   "
                    f"{cfg['execution']} execution, zero noise {'on' if cfg['zero_noise'] else 'off'}",
            bands=(self.bands.low, self.bands.high),
        )
        (self.run_dir / "config.json").write_text(json.dumps({
            "args": vars(args), "config": cfg,
            "models": {stage: {"name": m.name, "id": m.model_id, "policy": m.policy, "export": str(m.export_dir),
                               "dataset": m.dataset_name} for stage, m in self.models.items()},
            "bands": {"low": self.bands.low, "high": self.bands.high, "source": self.bands.source},
            "show_pose": [float(x) for x in self.show_pose], "home_pose": [float(x) for x in self.home_pose],
            "anomaly_model": str(model_xml),
        }, indent=2, default=str) + "\n")
        self.sysmon.start()
        threading.Thread(target=self._pump, daemon=True, name="camera-pump").start()
        self.say(f"Ready. Logging to {self.run_dir.relative_to(REPO)}")
        self.t_ready = time.monotonic()
        policies = ("replayed episodes (no model)" if args.sim and args.replay else
                    f"pick {self.models['pick'].name} on {args.pick_device} · sort {self.models['sort'].name} on {args.sort_device}")
        self.ev(3, "CELL", f"Ready · {policies} · Anomalib on {args.anomaly_device}")

    def _real_cameras(self) -> dict:
        from physicalai.capture import RealSenseCamera, UVCCamera

        c = self.cfg["cameras"]
        size = {"width": c["width"], "height": c["height"], "fps": c["fps"]}
        # The wrist camera is found by its USB serial, as Studio does (stable across reboots). The
        # "v4l2" backend opened it but never received a frame, so the default backend is used.
        wrist = c["wrist"]
        wrist_device = {"serial": wrist["serial"]} if "serial" in wrist else wrist["device"]
        return {
            "top": RealSenseCamera(serial_number=c["top"]["serial_number"], **size),
            "wrist": UVCCamera(device=wrist_device, **size),
        }

    def _check_cameras(self, cameras: dict, timeout_s: float = 3.0) -> None:
        """Fail before the arm moves if a policy camera sends no frames."""
        for name, cam in cameras.items():
            deadline = time.monotonic() + timeout_s
            while True:
                try:
                    cam.read_latest()
                    break
                except Exception as error:  # noqa: BLE001
                    if time.monotonic() > deadline:
                        raise RuntimeError(f"The {name} camera sends no frames ({error}). Is another program "
                                           "using it? Replug it or restart Studio's backend.") from error
                    time.sleep(0.05)

    # --- Helpers ---------------------------------------------------------------------

    def ev(self, prio: int, tag: str, msg: str) -> None:
        self.telemetry.event(prio, tag, msg)

    def say(self, message: str) -> None:
        print(message, flush=True)
        self.view.set(message=message)

    def set_stage(self, stage: str, narration: str | None = None) -> None:
        self.view.set(stage=stage, stage_started=time.monotonic() if stage else 0.0)
        if narration is not None:
            self.view.set(narration=narration)

    def rules(self, name: str) -> StageRules:
        return replace(StageRules(), **self.cfg[name])

    def keep_grip(self, pose: np.ndarray) -> np.ndarray:
        """`pose` with the gripper at the value last COMMANDED (self.grip), not the measured one.

        Holding a brick, the jaws stop short of their command (the brick is in the way); that gap is
        the squeeze. Commanding the measured position would relax the grip and could drop the brick.
        """
        target = np.asarray(pose, dtype=np.float32).copy()
        target[GRIPPER] = self.grip
        return target

    def take_grip_from_policy(self) -> None:
        last = self.watcher._last_action
        if last is not None:
            self.grip = float(last[GRIPPER])

    def go_home(self, only_if_away: bool = False) -> float:
        """Scripted move to the home pose, gripper unchanged. Returns the seconds it took."""
        if only_if_away:
            away = float(np.max(np.abs(self.arm.joints()[:5] - self.home_pose[:5])))
            if away <= float(self.cfg["home_tol"]):
                return 0.0
        t0 = time.monotonic()
        self.set_stage("HOME", NARRATION["HOME_BEFORE" if only_if_away else "HOME_AFTER"])
        self.arm.move_to(self.keep_grip(self.home_pose))
        return time.monotonic() - t0

    def run_stage(self, name: str, sentence: str, rules: StageRules) -> tuple[str, float, list[float]]:
        if self.args.sim:
            episode = self.world.begin(sentence if sentence in self.world.episodes else next(
                t for t in self.world.episodes if t != self.cfg["sentences"]["pick"]))
            if self.args.replay:  # recorded actions only make sense from the recorded start
                self.arm.robot.teleport(episode["state"][0])
                self.arm.take_over(episode["state"][0])  # the mock's goal is now that start
        start = self.arm.joints()
        stage = "pick" if name == "PICK" else "sort"
        self.policy_source.use(stage)
        colour = "green" if "green" in sentence else "orange"
        names = {k: m.name for k, m in self.models.items()}
        text = NARRATION["PICK" if name == "PICK" else "SORT"].format(pick=names["pick"], sort=names["sort"], colour=colour)
        self.policy_source.set_task(sentence if self.models[stage].takes_task else None)
        # Clamp the policy's first steps against the servos' current goal (the last scripted command).
        self.watcher.begin(name, start, rules, command_ref=self.arm.last_command)
        self.set_stage(name, text)
        if name == "PICK":
            self.view.set(sentence=sentence)
        t0 = time.monotonic()
        with self.cam_lock:  # the camera pump stops reading the policy cameras
            self.policy_running = True
        try:
            self.runtime.run(duration_s=rules.timeout_s + 10)
        finally:
            self.policy_running = False
        took = time.monotonic() - t0
        # Hand-over: the servos keep the policy's last action as their goal; scripted moves continue from it.
        self.arm.take_over(self.watcher._last_action)
        result = self.watcher.result or self.runtime.last_run_reason or "ended"
        if self.stop.is_set():
            result = "stopped"
        ms = list(self.watcher.inference_ms)
        self.all_policy_ms.extend(ms)
        self.view.set(policy_ms=self.all_policy_ms[-300:])
        if result == "done":
            self.ev(3, f"RBT.{name}", f"{name.title()} done in {took:.1f} s · {len(ms)} plans, median {np.median(ms) if ms else 0:.0f} ms")
        elif result == "timeout":
            self.ev(2, f"RBT.{name}", f"{name.title()} timeout after {took:.0f} s (no return to rest)")
        return result, took, ms

    def publish_photos(self, photos: list[Photo]) -> None:
        """The stop tiles for both screens: the Tk view and the dashboard."""
        self.view.set(photos=list(photos), stops=[
            {"name": p.name, "score": None if p.score is None else round(p.score, 3), "label": p.label,
             "ms": p.ms, "second": p.second} for p in photos])
        self.telemetry.set_tiles([p.heat_overlay if p.heat_overlay is not None else p.crop for p in photos])

    def shoot(self, stop: Stop, photos: list[Photo], index: int | None = None) -> dict:
        """Take frames_per_stop fresh frames at this stop and queue them for scoring."""
        crops, futures = [], []
        for _ in range(int(self.cfg["show"]["frames_per_stop"])):
            _, crop = self.inspection.photo()
            crops.append(crop)
            futures.append(self.scorer.submit(crop))
        tile = Photo(crop=crops[0], name=stop.name, second=index is not None)
        if index is None:
            photos.append(tile)
            index = len(photos) - 1
        else:
            photos[index] = tile
        self.publish_photos(photos)
        return {"stop": stop, "crops": crops, "futures": futures, "index": index}

    def finish(self, entry: dict, photos: list[Photo]) -> str:
        """Wait for a stop's scores: its score is the median of its frames."""
        out = [f.result(timeout=30) for f in entry["futures"]]
        scores = [o[0] for o in out]
        median = float(np.median(scores))
        i = int(np.argmin([abs(x - median) for x in scores]))
        ms = [o[2] for o in out]
        self.all_anomaly_ms.extend(ms)
        entry.update(scores=scores, median=median, label=label(median, self.bands), ms=ms)
        self.ev(3, f"INSP.{entry['stop'].tag.upper()}DEG",
                f"Score {median:.2f} (median of {len(scores)}) → {entry['label']}")
        crop = entry["crops"][i]
        photos[entry["index"]] = Photo(crop=crop, heat_overlay=heatmap_overlay(crop, out[i][1]), score=median,
                                       label=entry["label"], ms=float(np.median(ms)), name=entry["stop"].name,
                                       second=photos[entry["index"]].second)
        self.view.set(anomaly_ms=self.all_anomaly_ms[-300:])
        self.publish_photos(photos)
        return entry["label"]

    def show_and_inspect(self) -> tuple[str, list[Photo], dict]:
        """Show pose, then photos at each stop of show.stops_deg (now [90]; the first stop is turned to
        when it isn't the show pose's own angle).

        Each stop's frames are scored on the anomaly device while the wrist turns to the next
        stop. Any stop clearly defective -> DEFECTIVE at once (the remaining stops are skipped).
        All clearly good -> GOOD. Otherwise one second look at the unsure stops; still unsure ->
        DEFECTIVE (reject when in doubt).
        """
        show_cfg = self.cfg["show"]
        speed = float(show_cfg["turn_speed"])
        show = self.keep_grip(self.show_pose)
        self.set_stage("SHOW", NARRATION["SHOW"])
        t0 = time.monotonic()
        if self.via_pose is not None:
            self.arm.move_to(self.keep_grip(self.via_pose))
        self.arm.move_to(show)
        self.show_move_s = time.monotonic() - t0
        self.set_stage("INSPECT")
        stops = plan_stops(float(show[WRIST_ROLL]), [float(d) for d in show_cfg["stops_deg"]], self.roll_per_deg)
        if any(abs(st.deg - st.asked_deg) > 1 for st in stops):
            self.say("Wrist range: stops at " + ", ".join(st.name for st in stops))
        photos: list[Photo] = []
        entries: list[dict] = []
        early = False
        self.view.set(stops_planned=[st.name for st in stops], early_reject=False, verdict="", verdict_sub="")
        self.publish_photos(photos)
        device = self.args.anomaly_device

        def say_stop(k: int, stop: Stop) -> None:
            ms = f" in about {np.median(self.all_anomaly_ms[-30:]):.0f} ms per photo" if self.all_anomaly_ms else ""
            back = " back" if stop.back else ""
            self.step_detail = f"VIEW {k + 1}/{len(stops)} @ {stop.deg:.0f}°{back}"
            self.view.set(narration=f"Inspecting the brick: view {k + 1} of {len(stops)} "
                                    f"({stop.deg:.0f}°{', rolling back' if stop.back else ''}). "
                                    f"Anomalib scores 3 photos on the {device}{ms}.")

        def at(stop: Stop) -> np.ndarray:
            target = show.copy()
            target[WRIST_ROLL] = stop.roll
            return target

        for k, stop in enumerate(stops):
            if k > 0:
                self.arm.move_to(at(stop), speed=speed)
                if self.finish(entries[k - 1], photos) == DEFECTIVE:
                    early = True
                    self.view.set(early_reject=True)
                    self.say(f"Defective at {entries[k - 1]['stop'].name}: skipping the other stops")
                    self.ev(3, "INSP", f"Defect at {entries[k - 1]['stop'].deg:.0f}° · remaining views skipped")
                    break
            elif abs(stop.roll - float(show[WRIST_ROLL])) > 0.5:
                # The first stop isn't the show pose's own angle (e.g. stops_deg [90]): turn to it
                # first, as show_tool.py collect does, or the photo would be of the 0 deg view.
                self.arm.move_to(at(stop), speed=speed)
            say_stop(k, stop)
            entries.append(self.shoot(stop, photos))
        if not early:
            self.finish(entries[-1], photos)

        labels = [e["label"] for e in entries]
        second_look = False
        if DEFECTIVE in labels:
            result = DEFECTIVE
        elif all(lab == GOOD for lab in labels):
            result = GOOD
        else:
            second_look = True
            unsure = [e for e in entries if e["label"] == UNSURE]
            self.view.set(verdict=UNSURE, verdict_sub="taking a second look",
                          narration="Unsure at " + ", ".join(f"{e['stop'].deg:.0f}°" for e in unsure)
                                    + ": taking a second look before deciding.")
            self.say("Unsure at " + ", ".join(e["stop"].name for e in unsure) + ": second look")
            self.step_detail = "SECOND LOOK"
            self.ev(3, "INSP", "Unsure at " + ", ".join(f"{e['stop'].deg:.0f}°" for e in unsure) + " · second look")
            for e in unsure:
                self.arm.move_to(at(e["stop"]), speed=speed)
                time.sleep(0.3)  # extra settling before the second look
                again = self.shoot(e["stop"], photos, index=e["index"])
                self.finish(again, photos)
                e["first_median"] = e["median"]
                e.update(scores=again["scores"], median=again["median"], label=again["label"], ms=again["ms"])
            labels = [e["label"] for e in entries]
            if DEFECTIVE in labels:
                result = DEFECTIVE
            elif all(lab == GOOD for lab in labels):
                result = GOOD
                self.say("Second look is good: accepting it")
            else:
                result = DEFECTIVE
                self.say("Still unsure: rejecting it (defective)")
        if self.arm.last_command is None or not np.allclose(self.arm.last_command, show, atol=0.5):
            self.arm.move_to(show, speed=speed)  # wrist back before moving on (already there after a 0 back stop)
        info = {
            "stops": [{"deg": round(e["stop"].deg, 1), "back": e["stop"].back, "scores": [round(x, 4) for x in e["scores"]],
                       "median": round(e["median"], 4), "label": e["label"],
                       **({"first_median": round(e["first_median"], 4)} if "first_median" in e else {})}
                      for e in entries],
            "early_reject": early, "second_look": second_look,
            "anomaly_ms": [round(x, 1) for e in entries for x in e["ms"]],
        }
        return result, photos, info

    def cycle(self, n: int) -> None:
        sentences = self.cfg["sentences"]
        record: dict = {"cycle": n, "start": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.step_detail = ""
        self.ev(3, "SEQ", f"Cycle {n} start")
        self.cycle_mon.sample()
        t_cycle = time.monotonic()
        self.view.set(cycle=n, verdict="", photos=[], sentence="", stage_times={}, verdict_sub="", stops=[],
                      stops_planned=[], early_reject=False)
        self.telemetry.set_tiles([])
        stage_times: dict[str, float] = {}

        if self.args.inspect_only:
            # The brick was put in by hand: squeeze it with the closed-grip command before moving.
            self.grip = float(self.cfg["grip_closed"])
            self.arm.set_gripper(self.grip)
        else:
            home_s = self.go_home(only_if_away=True)  # the pick episodes start at home
            if home_s:
                record["home_before_pick_s"] = round(home_s, 2)
            result, took, ms = self.run_stage("PICK", sentences["pick"], self.rules("pick"))
            record["pick"] = {"result": result, "s": round(took, 2), "inference_ms": _stats(ms),
                              "clamped_ticks": self.watcher.clamped}
            stage_times["PICK"] = took
            self.view.set(stage_times=dict(stage_times))
            if result == "stopped":
                raise Stopped("stopped during pick")
            if result != "done" and self.args.sim and result == "timeout":
                self.say("Pick timed out (simulation: carrying on, the replayed video doesn't react to the arm)")
            elif result != "done":
                self.say(f"Pick ended by {result}: check the brick, then press r to continue")
                self._log(record)
                raise Stopped(f"pick {result}")
            self.take_grip_from_policy()
        record["grip"] = round(self.grip, 2)

        t_show = time.monotonic()
        verdict_, photos, info = self.show_and_inspect()
        inspect_s = time.monotonic() - t_show - self.show_move_s
        record["inspect"] = {**info, "verdict": verdict_, "device": self.args.anomaly_device,
                             "bands": [self.bands.low, self.bands.high]}
        sentence = sentences[verdict_]
        scored = [ph for ph in photos if ph.score is not None]
        worst = max(scored, key=lambda ph: ph.score) if scored else None
        where = f" at the {worst.name.replace(' deg', '°')} view" if worst else ""
        if verdict_ == GOOD:
            told = f"No defect found in {len(scored)} views. Telling the robot: “{sentence}”"
        elif info["second_look"] and not any(st["label"] == DEFECTIVE for st in info["stops"]):
            told = f"Still unsure after a second look, so it is rejected. Telling the robot: “{sentence}”"
        else:
            told = f"Defect found{where}. Telling the robot: “{sentence}”"
        sub = (f"worst {worst.score:.2f}{where}" if worst else "") + (" · second look" if info["second_look"] else "") \
            + (" · other views skipped" if info["early_reject"] else "")
        self.view.set(verdict=verdict_, sentence=sentence, narration=told, verdict_sub=sub)
        self.step_detail = ""
        self.ev(3, "INSP.VERDICT", f"{verdict_} → task to VLA: “{sentence}”")
        for p in photos:
            stem = f"c{n:03d}_{p.name.replace(' ', '')}"
            cv2.imwrite(str(self.run_dir / f"{stem}.jpg"), p.crop)
            if p.heat_overlay is not None:
                cv2.imwrite(str(self.run_dir / f"{stem}_heat.jpg"), p.heat_overlay)
        stage_times["SHOW"] = self.show_move_s
        stage_times["INSPECT"] = inspect_s
        self.view.set(stage_times=dict(stage_times))

        # Home, still squeezing: the sort episodes start at home holding the brick.
        stage_times["HOME"] = self.go_home()
        show_s = time.monotonic() - t_show
        record.update(show_s=round(self.show_move_s, 2), inspect_s=round(inspect_s, 2),
                      home_s=round(stage_times["HOME"], 2))
        self.view.set(stage_times=dict(stage_times))

        if not self.args.inspect_only:
            result, took, ms = self.run_stage("SORT", sentence, self.rules("sort"))
            record["sort"] = {"result": result, "sentence": sentence, "s": round(took, 2),
                              "inference_ms": _stats(ms), "clamped_ticks": self.watcher.clamped}
            stage_times["SORT"] = took
            self.take_grip_from_policy()
            if result == "stopped":
                raise Stopped("stopped during sort")
            if result != "done":
                self.say(f"Sort ended by {result}")

        total = time.monotonic() - t_cycle
        record["total_s"] = round(total, 2)
        record["system"] = {k: (round(v, 1) if v is not None else None) for k, v in self.cycle_mon.sample().items()}
        tallies = dict(self.view.tallies)
        tallies[verdict_] = tallies.get(verdict_, 0) + 1
        tallies["rechecks"] = tallies.get("rechecks", 0) + int(info["second_look"])
        self.set_stage("")
        self.view.set(
            stage_times=dict(stage_times), tallies=tallies,
            last_cycle={"total_s": total, "pick_s": stage_times.get("PICK", 0), "show_s": show_s,
                        "sort_s": stage_times.get("SORT", 0)},
        )
        self._log(record)
        self.cycle_times.append(total)
        if worst is not None:
            self.telemetry.add_history({
                "cycle": n, "verdict": verdict_, "worst": round(worst.score, 3),
                "worst_stop": worst.name.replace(" deg", "°"), "cycle_s": round(total, 1),
                "second_look": info["second_look"], "early": info["early_reject"],
                "thumb": f"/api/img/{n}/c{n:03d}_{worst.name.replace(' ', '')}_heat.jpg"})
        self.say(f"Cycle {n}: {verdict_} in {total:.1f} s")

    def _log(self, record: dict) -> None:
        self.log.write(json.dumps(record) + "\n")
        self.log.flush()

    # --- Main loop (worker thread) -----------------------------------------------------

    def work(self) -> None:
        try:
            self.setup()
            self.view.set(run_state="RUNNING")
            n = 0
            while not self.quit.is_set():
                if self.args.cycles and n >= self.args.cycles:
                    self.say(f"Done: {n} cycles")
                    break
                if self.args.inspect_only or self.pause_after_cycle.is_set():
                    self.view.set(run_state="PAUSED", narration="Paused. Press Space to start the next brick."
                                  if not self.args.inspect_only else
                                  "Put a brick in the gripper, then press Space to inspect it.")
                    self.say("Paused: press space to start the next cycle" +
                             (" (put a brick in the gripper first)" if self.args.inspect_only else ""))
                    self._wait_for(self.resume)
                    self.pause_after_cycle.clear() if not self.args.inspect_only else None
                    self.view.set(run_state="RUNNING")
                n += 1
                try:
                    self.cycle(n)
                except (Stopped, ArmError) as error:
                    self.ev(1, "RBT.LAG" if isinstance(error, ArmError) else "CELL.STOP", f"Stopped: {error} · arm holding")
                    self._hold_quietly()
                    tallies = dict(self.view.tallies)
                    tallies["stops"] = tallies.get("stops", 0) + 1
                    self.set_stage("")
                    self.view.set(run_state="STOPPED", tallies=tallies,
                                  narration="Stopped. The arm is holding still. Clear the cell, then press R.")
                    self.say(f"Stopped ({error}). The arm is holding. Clear the cell, then press r to continue.")
                    if self.args.headless:
                        raise Quit
                    self._wait_for(self.resume)
                    self.stop.clear()
                    self.view.set(run_state="RUNNING")
        except Quit:
            pass
        except BaseException as error:  # noqa: BLE001
            traceback.print_exc()
            self.say(f"Error: {type(error).__name__}: {error}")
            self.ev(1, "CELL.ERROR", f"{type(error).__name__}: {error}")
            self.view.set(run_state="STOPPED")
            self._hold_quietly()
        finally:
            self.quit.set()

    def _wait_for(self, event: threading.Event) -> None:
        event.clear()
        while not event.wait(0.1):
            if self.quit.is_set():
                raise Quit

    def _hold_quietly(self) -> None:
        try:
            if getattr(self, "arm", None) is not None:
                self.arm.hold()
        except Exception:  # noqa: BLE001
            pass

    def request_stop(self) -> None:
        self.stop.set()
        if self.runtime is not None:
            self.runtime.stop()

    # --- Dashboard ---------------------------------------------------------------------

    def command(self, name: str) -> None:
        """Stop / resume / pause, from the dashboard, the Tk window or the keys."""
        if name == "stop":
            self.request_stop()
            self.say("Stop pressed: the arm holds where it is")
        elif name == "resume":
            self.resume.set()
            self.ev(3, "CELL", "Resume")
        elif name == "ack":
            self.telemetry.ack_all()
        elif name == "pause":
            if self.view.run_state == "PAUSED":
                self.resume.set()
            else:
                self.pause_after_cycle.set()
                self.say("Will pause after this cycle")

    def _pump(self) -> None:
        """Feed the dashboard between policy runs: policy camera frames and system readings."""
        last_sys = 0.0
        while not self.quit.is_set():
            if not self.policy_running:
                with self.cam_lock:
                    if not self.policy_running:
                        for name, cam in self.policy_cams.items():
                            try:
                                frame = cam.read_latest()
                                if frame is not None:
                                    self.telemetry.put_frame(name, frame.data, rgb=True)
                            except Exception:  # noqa: BLE001
                                pass
            now = time.monotonic()
            if now - last_sys >= 0.5 and self.sysmon.latest:
                last_sys = now
                temp = self.sysmon.latest.get("pkg_temp_c")
                if temp is not None and temp > 90 and not self._hot:
                    self._hot = True
                    self.ev(2, "NODE.TEMP", f"Package {temp:.0f} °C · above 90 °C, GPU may throttle")
                elif temp is not None and temp < 85 and self._hot:
                    self._hot = False
                    self.ev(3, "NODE.TEMP", f"Package {temp:.0f} °C · back below 85 °C")
                self.telemetry.put_sys(self.sysmon.latest)
            time.sleep(0.1)

    def dashboard_frame(self, cam: str) -> np.ndarray | None:
        if cam == "inspection":
            frame = self.inspection.latest() if self.inspection is not None else None
            return None if frame is None else self._inspection_overlay(frame)
        item = self.telemetry.frame(cam)
        if item is None:
            return None
        _, image, rgb = item
        cached = self._frame_cache.get(cam)
        if cached is not None and cached[0] is image:
            return cached[1]
        bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR) if rgb else image
        self._frame_cache[cam] = (image, bgr)
        return bgr

    def _inspection_overlay(self, frame: np.ndarray) -> np.ndarray:
        """The inspection feed with the crop box and, while inspecting, the live heatmap."""
        h, w = frame.shape[:2]
        scale = min(1.0, 960 / w)
        small = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else frame.copy()
        if self.args.sim:
            x0, y0, x1, y1 = 0, 0, small.shape[1], small.shape[0]
        else:
            cx, cy, size = self.inspection.box()
            x0, y0 = int((cx - size / 2) * scale), int((cy - size / 2) * scale)
            x1, y1 = int((cx + size / 2) * scale), int((cy + size / 2) * scale)
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(small.shape[1], x1), min(small.shape[0], y1)
        heat, lab, moving, age = self.telemetry.live_heat()
        colour = (90, 200, 90)
        if heat is not None and age < 1.0 and self.view.stage in ("SHOW", "INSPECT") and x1 > x0 and y1 > y0:
            region = small[y0:y1, x0:x1]
            small[y0:y1, x0:x1] = heatmap_overlay(region, cv2.resize(heat, (x1 - x0, y1 - y0)), 0.25 if moving else 0.45)
            colour = {GOOD: (154, 191, 47), DEFECTIVE: (61, 138, 255), UNSURE: (75, 184, 242)}.get(lab, colour)
            if moving:
                colour = (179, 162, 152)
        cv2.rectangle(small, (x0, y0), (x1 - 1, y1 - 1), colour, 3)
        return small

    def dashboard_state(self) -> dict:
        v = self.view
        with v.lock:
            stage, verdict = v.stage, v.verdict
            state = {
                "mode": self.mode, "run_state": v.run_state, "cycle": v.cycle, "stage": stage,
                "stage_elapsed": round(time.monotonic() - v.stage_started, 1) if v.stage_started else 0,
                "stage_times": {k: round(t, 1) for k, t in v.stage_times.items()},
                "narration": v.narration or v.message, "message": v.message,
                "verdict": verdict, "verdict_sub": v.verdict_sub, "sentence": v.sentence,
                "bands": list(v.bands), "stops": list(v.stops), "stops_planned": list(v.stops_planned),
                "early_reject": v.early_reject,
            }
        state.update(self.telemetry.snapshot())
        models = self.models or {}
        pick = models.get("pick")
        sort = models.get("sort")
        devices = {"anomaly": self.args.anomaly_device,
                   "pick": {"model": pick.name if pick else "–", "device": self.args.pick_device},
                   "sort": {"model": sort.name if sort else "–", "device": self.args.sort_device}}
        if self.args.sim and self.args.replay:
            devices["pick"]["model"] = devices["sort"]["model"] = "replayed episodes"
        chunk_ms = state["chunk_ms"]
        anomaly_ms = float(np.median(self.all_anomaly_ms[-60:])) if self.all_anomaly_ms else None
        sys_now = self.sysmon.latest or {}
        def ms(value):
            return f"{value:.0f} ms" if value else "–"
        active = {"PICK": ["PERCEIVE", "ACT"], "SHOW": ["ACT"], "INSPECT": ["PERCEIVE", "DETECT"],
                  "HOME": ["REASON", "ACT"] if verdict else ["ACT"], "SORT": ["PERCEIVE", "REASON", "ACT"]}.get(stage, [])
        if v.run_state == "RUNNING":
            active = active + ["OPTIMIZE"]
        temp = sys_now.get("pkg_temp_c")
        state["pipeline"] = {
            "active": active,
            "PERCEIVE": {"what": "3 cameras, 30 fps", "meta": "top · wrist · inspection"},
            "DETECT": {"what": "Anomalib PatchCore", "meta": f"{devices['anomaly']} · {ms(anomaly_ms)} / photo"},
            "REASON": {"what": "verdict → sentence", "meta": f"{devices['sort']['model']} · {devices['sort']['device']}"},
            "ACT": {"what": "SO-101 arm, 30 Hz", "meta": f"{devices['pick']['model']} · {ms(chunk_ms.get('pick') or chunk_ms.get('sort'))} / plan"},
            "OPTIMIZE": {"what": "OpenVINO, on-device", "meta": (f"{temp:.0f} °C · " if temp else "") + "placement measured"},
        }
        state["devices"] = devices
        step_no = {"PICK": 20, "SHOW": 30, "INSPECT": 40, "SORT": 60}.get(stage)
        if stage == "HOME":
            step_no = 50 if verdict else 10
        timeouts = {"PICK": self.cfg["pick"]["timeout_s"], "SORT": self.cfg["sort"]["timeout_s"]}
        state["step"] = {"no": step_no, "name": stage, "detail": self.step_detail if stage == "INSPECT" else "",
                         "timeout_s": timeouts.get(stage)}
        total = sum(self.cycle_times)
        state["production"] = {
            "throughput_h": (len(self.cycle_times) / total * 3600) if total else None,
            "runtime_s": (time.monotonic() - self.t_ready) if self.t_ready else 0,
            "second_looks": v.tallies.get("rechecks", 0), "stops": v.tallies.get("stops", 0),
            "good": v.tallies.get("GOOD", 0), "reject": v.tallies.get("DEFECTIVE", 0)}
        state["task_for"] = devices["sort"]["model"] if verdict and stage in ("HOME", "SORT") else devices["pick"]["model"]
        state["cycles_done"] = len(self.cycle_times)
        state["median_cycle_s"] = float(np.median(self.cycle_times)) if self.cycle_times else None
        return state

    def close(self) -> None:
        self.request_stop()
        self.sysmon.stop()
        for closer in (lambda: self.live_scorer and self.live_scorer.close(),
                       lambda: self.runtime and self.runtime.disconnect(),
                       lambda: self.inspection and self.inspection.close(),
                       lambda: self.scorer and self.scorer.close(),
                       lambda: self.locks and self.locks.release_all()):
            try:
                closer()
            except Exception as error:  # noqa: BLE001
                print(f"While closing: {error}")
        if self.args.inspect_only and getattr(self, "arm", None) is not None:
            try:
                self.arm.robot.disconnect()
            except Exception:  # noqa: BLE001
                pass
        if self.all_policy_ms or self.all_anomaly_ms:
            summary = {"policy_inference_ms": _stats(self.all_policy_ms),
                       "anomaly_ms": _stats(self.all_anomaly_ms), "system": self.sysmon.summary()}
            (self.run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(f"Summary: {json.dumps(summary)}")


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    a = np.asarray(values)
    return {"n": len(a), "median": round(float(np.median(a)), 1), "p95": round(float(np.percentile(a, 95)), 1),
            "max": round(float(a.max()), 1)}


def live_frame(cell: Cell) -> tuple[np.ndarray | None, str]:
    stage = cell.view.stage
    if stage in ("SHOW", "INSPECT") and cell.inspection is not None:
        frame = cell.inspection.latest()
        if frame is not None and not cell.args.sim:
            cx, cy, size = cell.inspection.box()
            cv2.rectangle(frame, (cx - size // 2, cy - size // 2), (cx + size // 2, cy + size // 2), (0, 255, 0), 4)
        return frame, "inspection camera"
    frames = cell.watcher.latest_frames if hasattr(cell, "watcher") else {}
    top = frames.get("top")
    if top is not None:
        return cv2.cvtColor(np.asarray(top.data), cv2.COLOR_RGB2BGR), "top camera (policy input)"
    return None, ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=HERE / "cell_config.json")
    parser.add_argument("--model", help="one Studio model for both stages: a name such as SmolVLA-v2, "
                                        "latest:smolvla, an id, or an export folder")
    parser.add_argument("--pick-model", help="model for the pick, e.g. latest:act or ACT-pick-v1 (default from config)")
    parser.add_argument("--sort-model", help="model for the sort; must read sentences (SmolVLA)")
    parser.add_argument("--policy-device", help="OpenVINO device for both policies")
    parser.add_argument("--pick-device", help="OpenVINO device for the pick policy (default from config: GPU)")
    parser.add_argument("--sort-device", help="OpenVINO device for the sort policy (default from config: GPU)")
    parser.add_argument("--anomaly-device", help="OpenVINO device for Anomalib (default from config: GPU)")
    parser.add_argument("--anomaly-model", help="Anomalib model.xml, relative to the repo")
    parser.add_argument("--bands", help="score bands file (default anomaly/bands.json, else 0.4 / 0.6)")
    parser.add_argument("--cycles", type=int, default=0, help="stop after this many cycles (0 = until stopped)")
    parser.add_argument("--sim", action="store_true", help="no hardware: mock arm, recorded camera frames and photos")
    parser.add_argument("--replay", action="store_true", help="with --sim: replay recorded actions instead of a model")
    parser.add_argument("--sim-dataset", help="with --sim: Studio dataset folder to replay (default: the model's)")
    parser.add_argument("--sim-photos", nargs="*", help="with --sim: folders of inspection crops to replay")
    parser.add_argument("--inspect-only", action="store_true", help="real arm, no policy: show + inspect only")
    parser.add_argument("--headless", "--no-window", dest="headless", action="store_true",
                        help="test mode: no Tk window, and the run ends instead of waiting when it stops")
    parser.add_argument("--window", action="store_true", help="also open the Tk screen (fallback to the dashboard)")
    parser.add_argument("--web-port", type=int, default=8080, help="dashboard port on localhost (default 8080)")
    parser.add_argument("--no-web", action="store_true", help="don't start the dashboard")
    parser.add_argument("--open", action="store_true", help="open the dashboard full screen in Firefox (kiosk)")
    parser.add_argument("--save-screens", help="also save the rendered screen to this folder once a second")
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text())
    args.pick_model = args.pick_model or args.model or cfg["pick_model"]
    args.sort_model = args.sort_model or args.model or cfg["sort_model"]
    args.pick_device = args.pick_device or args.policy_device or cfg["pick_device"]
    args.sort_device = args.sort_device or args.policy_device or cfg["sort_device"]
    args.anomaly_device = args.anomaly_device or cfg["anomaly_device"]

    if not args.sim:
        print("\nThis moves the real arm. Someone must be at the station with the follower's 12 V plug in reach,")
        print("and the workspace must be clear of hands and loose objects.")
        if input("Type 'clear' to continue: ").strip().lower() != "clear":
            sys.exit("Not confirmed.")

    cell = Cell(args, cfg)
    server = None
    if not args.no_web:
        try:
            server = DashboardServer(cell, port=args.web_port).start()
            print(f"Dashboard: {server.url}  (keys there: Esc stop, R resume, Space pause, F full screen)", flush=True)
            if args.open:
                import subprocess

                subprocess.Popen(["firefox", "--kiosk", server.url], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as error:
            print(f"Dashboard not started: {error} (another run_cell.py on port {args.web_port}?)")
    worker = threading.Thread(target=cell.work, name="cell", daemon=True)
    worker.start()
    window = None
    last_saved = 0.0
    if args.save_screens:
        Path(args.save_screens).mkdir(parents=True, exist_ok=True)
    try:
        if args.window:
            window = Window(WINDOW)
        while not (cell.quit.is_set() and not worker.is_alive()):
            live, live_label = live_frame(cell)
            cell.view.set(live=live, live_label=live_label, sys=cell.sysmon.latest)
            frame = render(cell.view) if (window or args.save_screens) else None
            if args.save_screens and time.monotonic() - last_saved > 1.0:
                last_saved = time.monotonic()
                cv2.imwrite(str(Path(args.save_screens) / f"screen_{time.strftime('%H%M%S')}.jpg"), frame)
            keys = []
            if window is not None:
                window.show(frame)
                keys = window.poll(0.04)
            else:
                time.sleep(0.25)
            for key in keys:
                if key in ("\x1b", "s"):
                    cell.command("stop")
                elif key == "r":
                    cell.command("resume")
                elif key == " ":
                    cell.command("pause")
                elif key == "q":
                    cell.say("Quitting...")
                    cell.request_stop()
                    cell.quit.set()
    except KeyboardInterrupt:
        print("\nCtrl+C: stopping the arm")
        cell.request_stop()
        cell.quit.set()
    finally:
        cell.quit.set()
        worker.join(timeout=10)
        cell.close()
        if server is not None:
            server.stop()
        if window is not None:
            window.close()

if __name__ == "__main__":
    main()
