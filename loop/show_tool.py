"""Save and test the show pose, and collect inspection photos at it (GUIDE2 sections 4 and 9).

Run with Studio's backend Python from the repo root:

    PY=physical-ai-studio/application/backend/.venv/bin/python

    $PY loop/show_tool.py where              # print the follower's joints      (read-only, safe)
    $PY loop/show_tool.py save               # save them as the show pose        (read-only, safe)
    $PY loop/show_tool.py save --name via    # optional waypoint the loop passes through on the way
    $PY loop/show_tool.py goto               # move to the show pose             (MOVES THE ARM)
    $PY loop/show_tool.py save --name home   # save them as the home pose        (read-only, safe)
    $PY loop/show_tool.py test-turn          # at the show pose: visit each wrist stop      (MOVES)
    $PY loop/show_tool.py collect            # inspection photos at the show pose          (MOVES)

Saving the show pose: in Studio, teleoperate the follower so the brick sits in the middle of
capture.py's green box, close the Studio session (the follower keeps holding its position),
then run `save`. `where` and `save` only read the servo positions, so the arm doesn't move
and torque isn't touched; they refuse to run while Studio holds the port.

Saving the home pose: put the follower where the sort episodes start (home, holding a brick) and
run `save --name home`. Without it, run_cell.py uses the median start of the sort episodes.

Collect mode: the tool moves to the show pose and opens the gripper. Put a brick between the
jaws, gripped the way the robot grips it, then type g (good, training), t (good, test only) or
b (defective) and Enter. The tool closes the gripper and takes one photo at every wrist stop of
cell_config.json (0, 90, 180, then back through 90 to 0 deg, as far as the wrist's range allows,
planned exactly as run_cell.py plans them), then opens the gripper. Anomalib must have seen every
stop in training, or that view scores as defective. Photos go to anomaly/dataset/<folder>
(crop, named ..._a<degrees>.png, ..._a<degrees>b.png on the way back) and anomaly/dataset_full/<folder> (full frame), like
capture.py, so recrop.py works. Close capture.py and inspect_live.py first: one program per camera.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import fields
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from arm import (  # noqa: E402
    FOLLOWER_PORT,
    GRIPPER,
    JOINTS,
    WRIST_ROLL,
    Arm,
    ArmError,
    MoveLimits,
    Stopped,
    connect_follower,
    load_calibration,
    load_poses,
    plan_stops,
    roll_units_per_degree,
    save_pose,
)

GRIP_OPEN = 40.0  # median opening before a grasp in main-clean2
GRIP_CLOSED = 2.5  # commanded value while holding a brick in main-clean2 (the brick stops it ~3.7)
FOLDERS = {"g": "normal", "t": "test_normal", "b": "abnormal"}
CONFIG = HERE / "cell_config.json"


def stops_from_config() -> list[float]:
    import json

    return [float(d) for d in json.loads(CONFIG.read_text())["show"]["stops_deg"]]


def read_joints_readonly(calibration: dict) -> np.ndarray:
    """Present positions in Studio's normalized units, without connecting the driver (no torque change)."""
    import scservo_sdk as scs
    from physicalai_so101_plugin._conversion import ticks_to_normalized
    from physicalai_so101_plugin.calibration import SO101Calibration, SO101JointCalibration

    users = subprocess.run(["fuser", FOLLOWER_PORT], capture_output=True, text=True).stdout.strip()
    if users:
        sys.exit(f"The follower's port is in use (process {users}). Close the Studio session using the arm first.")
    names = {f.name for f in fields(SO101JointCalibration)}
    cal = SO101Calibration(joints={j: SO101JointCalibration(**{k: v for k, v in calibration[j].items() if k in names})
                                   for j in JOINTS})
    port = scs.PortHandler(FOLLOWER_PORT)
    packets = scs.PacketHandler(0)
    if not port.openPort() or not port.setBaudRate(1_000_000):
        sys.exit(f"Cannot open {FOLLOWER_PORT}")
    try:
        ticks = []
        for joint in JOINTS:
            value, comm, _ = packets.read2ByteTxRx(port, calibration[joint]["id"], 56)  # Present_Position
            if comm != scs.COMM_SUCCESS:
                sys.exit(f"{joint} did not answer")
            ticks.append(value)
    finally:
        port.closePort()
    return ticks_to_normalized(np.array(ticks), cal)


def describe(joints: np.ndarray) -> str:
    return "  ".join(f"{name} {value:6.1f}" for name, value in zip(JOINTS, joints))


def check_turn(joints: np.ndarray, per_deg: float) -> None:
    """Print the wrist stops the loop would use from this pose."""
    asked = stops_from_config()
    stops = plan_stops(float(joints[WRIST_ROLL]), asked, per_deg)
    print(f"  Wrist stops from wrist_roll {joints[WRIST_ROLL]:.0f}: " + ", ".join(st.name for st in stops))
    if any(abs(st.deg - st.asked_deg) > 1 for st in stops):
        print(f"  (asked for {', '.join(f'{d:.0f}°' for d in asked)}: the wrist's range caps the largest; "
              "turning the wrist a few units away from 0 before saving gives the full angle)")


def confirm() -> None:
    print("\nThis MOVES the follower. Someone must be at the station with the 12 V plug in reach,")
    if input("and the workspace clear. Type 'clear' to continue: ").strip().lower() != "clear":
        sys.exit("Not confirmed.")


def connect(args) -> tuple[Arm, object]:
    robot, locks = connect_follower()
    arm = Arm(robot, limits=MoveLimits(speed=args.speed))
    arm.hold()
    return arm, locks


def goto(arm: Arm, pose: np.ndarray, keep_grip: bool = True) -> None:
    target = pose.copy()
    if keep_grip:  # the gripper stays at its commanded value (the squeeze), not the measured one
        target[GRIPPER] = (arm.last_command if arm.last_command is not None else arm.joints())[GRIPPER]
    arm.move_to(target)


def cmd_where(args) -> None:
    calibration = load_calibration()
    joints = read_joints_readonly(calibration)
    print(describe(joints))
    check_turn(joints, roll_units_per_degree(calibration))
    poses = load_poses()
    for name, pose in poses.items():
        print(f"  distance to saved '{name}': {np.max(np.abs(joints[:5] - pose[:5])):.1f} units")


def cmd_save(args) -> None:
    calibration = load_calibration()
    joints = read_joints_readonly(calibration)
    print(describe(joints))
    if args.name == "show":
        check_turn(joints, roll_units_per_degree(calibration))
    save_pose(args.name, joints, note=args.note or "")
    print(f"Saved as '{args.name}' in {HERE / 'poses.json'}")


def cmd_goto(args) -> None:
    poses = load_poses()
    if args.name not in poses:
        sys.exit(f"No pose '{args.name}' saved. Run: show_tool.py save --name {args.name}")
    confirm()
    arm, locks = connect(args)
    try:
        goto(arm, poses[args.name])
        print("Arrived:", describe(arm.joints()))
    finally:
        arm.robot.disconnect()  # the follower keeps holding with torque on
        locks.release_all()


def cmd_test_turn(args) -> None:
    poses = load_poses()
    if "show" not in poses:
        sys.exit("No show pose saved yet.")
    calibration = load_calibration()
    per_deg = roll_units_per_degree(calibration)
    confirm()
    arm, locks = connect(args)
    try:
        goto(arm, poses["show"])
        show = arm.last_command.copy()  # commanded, not measured: keeps any squeeze on a brick
        for stop in plan_stops(float(show[WRIST_ROLL]), stops_from_config(), per_deg)[1:]:
            target = show.copy()
            target[WRIST_ROLL] = stop.roll
            try:
                print(f"Turning to the {stop.name} stop...")
                arm.move_to(target, speed=45)
                time.sleep(0.5)
            except ArmError as error:
                print(f"  {stop.name} failed: {error}")
        arm.move_to(show, speed=45)
        print("Done. Check the wrist camera's cable didn't pull.")
    finally:
        arm.robot.disconnect()
        locks.release_all()


def cmd_collect(args) -> None:
    sys.path.insert(0, str(REPO / "loop"))
    from inspection import InspectionCamera

    poses = load_poses()
    if "show" not in poses:
        sys.exit("No show pose saved yet.")
    calibration = load_calibration()
    per_deg = roll_units_per_degree(calibration)
    camera = InspectionCamera()  # fails early if capture.py holds the webcam
    confirm()
    arm, locks = connect(args)
    dataset, full = REPO / args.dataset, REPO / f"{args.dataset}_full"
    counts = {folder: len(list((dataset / folder).glob("*.png"))) for folder in FOLDERS.values()}
    try:
        show = poses["show"].copy()
        show[GRIPPER] = GRIP_OPEN
        arm.move_to(show)
        while True:
            print("\nCounts: " + "  ".join(f"{k} {v}" for k, v in counts.items()))
            key = input("Brick in the jaws? g = good, t = good (test only), b = defective, q = quit: ").strip().lower()
            if key == "q":
                break
            if key not in FOLDERS:
                continue
            folder = FOLDERS[key]
            arm.set_gripper(GRIP_CLOSED)
            time.sleep(0.4)
            base = arm.last_command.copy()  # commanded pose: turns keep the squeeze
            base[GRIPPER] = GRIP_CLOSED
            stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
            views = []
            for stop in plan_stops(float(base[WRIST_ROLL]), stops_from_config(), per_deg):
                target = base.copy()
                target[WRIST_ROLL] = stop.roll
                try:
                    arm.move_to(target, speed=90)
                except ArmError as error:
                    print(f"  The {stop.name} stop failed ({error}): skipping it")
                    continue
                frame, crop = camera.photo()
                views.append((stop, frame, crop))
            arm.move_to(base, speed=90)
            for stop, frame, crop in views:
                name = f"{folder}_{stamp}_a{stop.tag}"
                (dataset / folder).mkdir(parents=True, exist_ok=True)
                (full / folder).mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(dataset / folder / f"{name}.png"), crop)
                cv2.imwrite(str(full / folder / f"{name}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                counts[folder] += 1
            print(f"  Saved {len(views)} photos to {folder}")
            arm.set_gripper(GRIP_OPEN)
    except (Stopped, ArmError) as error:
        print(f"Stopped: {error}")
    finally:
        camera.close()
        arm.robot.disconnect()
        locks.release_all()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("where", help="print the follower's joints (read-only)")
    p = sub.add_parser("save", help="save the follower's joints as a pose (read-only)")
    p.add_argument("--name", default="show")
    p.add_argument("--note")
    p = sub.add_parser("goto", help="move to a saved pose")
    p.add_argument("--name", default="show")
    p.add_argument("--speed", type=float, default=30.0, help="units per second (default 30, slow)")
    p = sub.add_parser("test-turn", help="at the show pose, visit each wrist stop and come back")
    p.add_argument("--speed", type=float, default=30.0)
    p = sub.add_parser("collect", help="inspection photos at the show pose")
    p.add_argument("--dataset", default="anomaly/dataset",
                   help="where photos go (crops; full frames in <dataset>_full), e.g. anomaly/dataset_show")
    p.add_argument("--speed", type=float, default=40.0)
    args = parser.parse_args()
    {"where": cmd_where, "save": cmd_save, "goto": cmd_goto, "test-turn": cmd_test_turn,
     "collect": cmd_collect}[args.command](args)


if __name__ == "__main__":
    main()
