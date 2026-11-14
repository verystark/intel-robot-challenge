"""The closed loop: pick -> show -> inspect -> sort, with the Anomalib verdict steering SmolVLA.

Each cycle:
  1. PICK     SmolVLA, "Pick up the brick.", until the arm has gone out, come back and held still.
  2. SHOW     Scripted: smooth move to the saved show pose (loop/poses.json), keeping the grip.
  3. INSPECT  Photo, wrist turn 180 deg, photo, turn back. Anomalib scores each photo in the
              background (on the GPU by default) while the arm moves. Either view defective ->
              DEFECTIVE; both good -> GOOD; otherwise UNSURE -> turn 90 deg, third photo,
              which decides: good -> GOOD, still unsure -> DEFECTIVE (reject when in doubt).
  4. SORT     Back to where the pick ended (where sort episodes start), then SmolVLA with the
              verdict's sentence, until it has gone out, come back and held still.
  5. LOG      Every stage time, every policy inference latency, every score, the photos and
              heatmaps, temperatures and loads: loop/runs/<time>/cycles.jsonl.

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
    Arm,
    ArmError,
    MockRobot,
    MoveLimits,
    Stopped,
    connect_follower,
    load_calibration,
    load_poses,
    roll_units_per_degree,
)
from detector import DEFECTIVE, GOOD, UNSURE, heatmap_overlay, label, load_bands, verdict  # noqa: E402
from inspection import InspectionCamera, ReplayInspectionCamera, Scorer  # noqa: E402
from policy import (  # noqa: E402
    ReplayCamera,
    ReplayModel,
    SimWorld,
    StageRules,
    StageWatcher,
    SwitchSource,
    find_model,
    load_policy,
)
from screen import Photo, View, Window, render  # noqa: E402
from sysmon import SysMon, SysMonThread  # noqa: E402

WINDOW = "Intel Physical AI cell"


class Quit(Exception):
    pass


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
        self.arm = Arm(robot, stop=self.stop, limits=MoveLimits(speed=cfg["show"]["speed"],
                                                                 settle_s=cfg["show"]["settle_s"]))

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

        # Policy
        self.watcher = StageWatcher()
        self.watcher.stop_flag = self.stop
        self.watcher.max_step = float(cfg["max_step_per_tick"])
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
        self.bands = load_bands()
        bands_info = json.loads((REPO / "anomaly/bands.json").read_text()) if (REPO / "anomaly/bands.json").exists() else {}
        if bands_info.get("device") and bands_info["device"] != args.anomaly_device:
            self.say(f"Note: bands were calibrated on {bands_info['device']}, Anomalib runs on {args.anomaly_device}")

        mode = "SIMULATION" if args.sim else ("INSPECT ONLY" if args.inspect_only else "LIVE")
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
            "show_pose": [float(x) for x in self.show_pose], "anomaly_model": str(model_xml),
        }, indent=2, default=str) + "\n")
        self.sysmon.start()
        self.say(f"Ready. Logging to {self.run_dir.relative_to(REPO)}")

    def _real_cameras(self) -> dict:
        from physicalai.capture import RealSenseCamera, UVCCamera

        c = self.cfg["cameras"]
        size = {"width": c["width"], "height": c["height"], "fps": c["fps"]}
        return {
            "top": RealSenseCamera(serial_number=c["top"]["serial_number"], **size),
            "wrist": UVCCamera(device=c["wrist"]["device"], backend="v4l2", **size),
        }

    # --- Helpers ---------------------------------------------------------------------

    def say(self, message: str) -> None:
        print(message, flush=True)
        self.view.set(message=message)

    def set_stage(self, stage: str) -> None:
        self.view.set(stage=stage, stage_started=time.monotonic() if stage else 0.0)

    def rules(self, name: str) -> StageRules:
        return replace(StageRules(), **self.cfg[name])

    def commanded_grip(self) -> float:
        """The gripper value the policy last commanded (squeezing the brick), not the measured one."""
        last = self.watcher._last_action
        return float(last[GRIPPER]) if last is not None else float(self.arm.joints()[GRIPPER])

    def run_stage(self, name: str, sentence: str, rules: StageRules) -> tuple[str, float, list[float]]:
        if self.args.sim:
            episode = self.world.begin(sentence if sentence in self.world.episodes else next(
                t for t in self.world.episodes if t != self.cfg["sentences"]["pick"]))
            if self.args.replay:  # recorded actions only make sense from the recorded start
                self.arm.robot.teleport(episode["state"][0])
        start = self.arm.joints()
        stage = "pick" if name == "PICK" else "sort"
        self.policy_source.use(stage)
        self.policy_source.set_task(sentence if self.models[stage].takes_task else None)
        self.watcher.begin(name, start, rules)
        self.set_stage(name)
        self.view.set(sentence=sentence)
        t0 = time.monotonic()
        self.runtime.run(duration_s=rules.timeout_s + 10)
        took = time.monotonic() - t0
        result = self.watcher.result or self.runtime.last_run_reason or "ended"
        if self.stop.is_set():
            result = "stopped"
        ms = list(self.watcher.inference_ms)
        self.all_policy_ms.extend(ms)
        self.view.set(policy_ms=self.all_policy_ms[-300:])
        return result, took, ms

    def photo(self, index: int, future_list: list, photos: list[Photo]) -> None:
        frame, crop = self.inspection.photo()
        photos.append(Photo(crop=crop))
        self.view.set(photos=list(photos))
        future_list.append(self.scorer.submit(crop))

    def collect_scores(self, futures: list, photos: list[Photo], start: int = 0) -> list[float]:
        scores = []
        for i, future in enumerate(futures[start:], start=start):
            score, heat, ms = future.result(timeout=30)
            photos[i] = Photo(crop=photos[i].crop, heat_overlay=heatmap_overlay(photos[i].crop, heat),
                              score=score, label=label(score, self.bands), ms=ms)
            scores.append(score)
            self.all_anomaly_ms.append(ms)
        self.view.set(photos=list(photos), anomaly_ms=self.all_anomaly_ms[-300:])
        return scores

    # --- One cycle -------------------------------------------------------------------

    def show_and_inspect(self, grip: float) -> tuple[str, list[Photo], bool]:
        show = self.show_pose.copy()
        show[GRIPPER] = grip
        self.set_stage("SHOW")
        if self.via_pose is not None:
            via = self.via_pose.copy()
            via[GRIPPER] = grip
            self.arm.move_to(via)
        self.arm.move_to(show)
        self.show_move_s = time.monotonic() - self.view.stage_started
        self.set_stage("INSPECT")
        photos: list[Photo] = []
        futures: list = []
        turn = float(self.cfg["show"]["turn_degrees"])
        turn_speed = float(self.cfg["show"]["turn_speed"])
        self.photo(0, futures, photos)
        try:
            self.arm.turn_wrist(turn, self.roll_per_deg, speed=turn_speed)
        except ArmError:
            turn = 90.0
            self.say("180 deg doesn't fit at this wrist angle: turning 90 deg instead")
            self.arm.turn_wrist(turn, self.roll_per_deg, speed=turn_speed)
        self.photo(1, futures, photos)
        self.arm.move_to(show, speed=turn_speed)
        scores = self.collect_scores(futures, photos)
        result = verdict(scores, self.bands)
        rechecked = False
        if result == UNSURE:
            rechecked = True
            self.view.set(verdict=UNSURE)
            self.say("Unsure: turning 90 deg for another look")
            self.arm.turn_wrist(float(self.cfg["show"]["recheck_degrees"]), self.roll_per_deg, speed=turn_speed)
            self.photo(2, futures, photos)
            self.arm.move_to(show, speed=turn_speed)
            scores += self.collect_scores(futures, photos, start=2)
            # GUIDE2: any defective view rejects; otherwise the extra look decides, and a brick
            # that is still unsure is rejected (reject when in doubt).
            recheck = label(scores[-1], self.bands)
            if DEFECTIVE in (label(x, self.bands) for x in scores):
                result = DEFECTIVE
            elif recheck == GOOD:
                result = GOOD
                self.say("Re-check looks good: accepting it")
            else:
                result = DEFECTIVE
                self.say("Still unsure: rejecting it (defective)")
        return result, photos, rechecked

    def cycle(self, n: int) -> None:
        sentences = self.cfg["sentences"]
        record: dict = {"cycle": n, "start": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.cycle_mon.sample()
        t_cycle = time.monotonic()
        self.view.set(cycle=n, verdict="", photos=[], sentence="", stage_times={})
        stage_times: dict[str, float] = {}

        if self.args.inspect_only:
            grip = float(self.arm.joints()[GRIPPER])
            pick_end = self.arm.joints()
        else:
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
            pick_end = self.arm.joints()
            grip = self.commanded_grip()

        t_show = time.monotonic()
        verdict_, photos, rechecked = self.show_and_inspect(grip)
        record["inspect"] = {
            "scores": [round(p.score, 4) for p in photos if p.score is not None],
            "labels": [p.label for p in photos], "verdict": verdict_, "rechecked": rechecked,
            "anomaly_ms": [round(p.ms, 1) for p in photos if p.ms is not None],
            "device": self.args.anomaly_device, "bands": [self.bands.low, self.bands.high],
        }
        sentence = sentences[verdict_]
        self.view.set(verdict=verdict_, sentence=sentence)
        for i, p in enumerate(photos):
            cv2.imwrite(str(self.run_dir / f"c{n:03d}_view{i + 1}.jpg"), p.crop)
            if p.heat_overlay is not None:
                cv2.imwrite(str(self.run_dir / f"c{n:03d}_view{i + 1}_heat.jpg"), p.heat_overlay)

        back = pick_end.copy()
        back[GRIPPER] = grip
        self.arm.move_to(back)
        show_s = time.monotonic() - t_show
        stage_times["SHOW"] = self.show_move_s
        stage_times["INSPECT"] = show_s - self.show_move_s
        record["show_s"] = round(show_s, 2)
        self.view.set(stage_times=dict(stage_times))

        if not self.args.inspect_only:
            result, took, ms = self.run_stage("SORT", sentence, self.rules("sort"))
            record["sort"] = {"result": result, "sentence": sentence, "s": round(took, 2),
                              "inference_ms": _stats(ms), "clamped_ticks": self.watcher.clamped}
            stage_times["SORT"] = took
            if result == "stopped":
                raise Stopped("stopped during sort")
            if result != "done":
                self.say(f"Sort ended by {result}")

        total = time.monotonic() - t_cycle
        record["total_s"] = round(total, 2)
        record["system"] = {k: (round(v, 1) if v is not None else None) for k, v in self.cycle_mon.sample().items()}
        tallies = dict(self.view.tallies)
        tallies[verdict_] = tallies.get(verdict_, 0) + 1
        tallies["rechecks"] = tallies.get("rechecks", 0) + int(rechecked)
        self.set_stage("")
        self.view.set(
            stage_times=dict(stage_times), tallies=tallies,
            last_cycle={"total_s": total, "pick_s": stage_times.get("PICK", 0), "show_s": show_s,
                        "sort_s": stage_times.get("SORT", 0)},
        )
        self._log(record)
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
                    self.view.set(run_state="PAUSED")
                    self.say("Paused: press space to start the next cycle" +
                             (" (put a brick in the gripper first)" if self.args.inspect_only else ""))
                    self._wait_for(self.resume)
                    self.pause_after_cycle.clear() if not self.args.inspect_only else None
                    self.view.set(run_state="RUNNING")
                n += 1
                try:
                    self.cycle(n)
                except (Stopped, ArmError) as error:
                    self._hold_quietly()
                    tallies = dict(self.view.tallies)
                    tallies["stops"] = tallies.get("stops", 0) + 1
                    self.set_stage("")
                    self.view.set(run_state="STOPPED", tallies=tallies)
                    self.say(f"Stopped ({error}). The arm is holding. Clear the cell, then press r to continue.")
                    if self.args.no_window:
                        raise Quit
                    self._wait_for(self.resume)
                    self.stop.clear()
                    self.view.set(run_state="RUNNING")
        except Quit:
            pass
        except BaseException as error:  # noqa: BLE001
            traceback.print_exc()
            self.say(f"Error: {type(error).__name__}: {error}")
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

    def close(self) -> None:
        self.request_stop()
        self.sysmon.stop()
        for closer in (lambda: self.runtime and self.runtime.disconnect(),
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
    parser.add_argument("--cycles", type=int, default=0, help="stop after this many cycles (0 = until stopped)")
    parser.add_argument("--sim", action="store_true", help="no hardware: mock arm, recorded camera frames and photos")
    parser.add_argument("--replay", action="store_true", help="with --sim: replay recorded actions instead of a model")
    parser.add_argument("--sim-dataset", help="with --sim: Studio dataset folder to replay (default: the model's)")
    parser.add_argument("--sim-photos", nargs="*", help="with --sim: folders of inspection crops to replay")
    parser.add_argument("--inspect-only", action="store_true", help="real arm, no policy: show + inspect only")
    parser.add_argument("--no-window", action="store_true", help="no screen (for tests); stops after --cycles")
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
    worker = threading.Thread(target=cell.work, name="cell", daemon=True)
    worker.start()
    window = None
    last_saved = 0.0
    if args.save_screens:
        Path(args.save_screens).mkdir(parents=True, exist_ok=True)
    try:
        if not args.no_window:
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
                    cell.request_stop()
                elif key == "r":
                    cell.resume.set()
                elif key == " ":
                    if cell.view.run_state == "PAUSED":
                        cell.resume.set()
                    else:
                        cell.pause_after_cycle.set()
                        cell.say("Will pause after this cycle")
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
        if window is not None:
            window.close()

if __name__ == "__main__":
    main()
