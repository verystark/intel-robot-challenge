#!/usr/bin/env python3
"""Where the training data grabbed and released bricks, seen from above.

For every pick episode, the gripper tip position at the moment it closes on the brick; for every
sort episode, the position where it opens over a plate. Positions come from forward kinematics
of the SO-101 URDF, with joint values mapped the way Physical AI Studio's 3D view maps them
(normalised -100..100 → the URDF joint limits). That mapping is approximate, so treat positions as
good to a few centimetres.

Frame: origin on the shoulder-pan axis (the centre of the turret), x = forward (the arm's
direction at shoulder_pan = 0), y = to the robot's left, in cm.

The datasets are the ones the models in video/facts.json were trained on (looked up read-only in
Studio's database): grasps from the pick model's data, releases from the sort model's data. It
also counts the sort model's episodes, so the video never quotes a hand-typed number.

Needs pyarrow and numpy: run with Studio's backend Python.

    PY=physical-ai-studio/application/backend/.venv/bin/python
    $PY video/scripts/coverage.py                          → video/public/coverage.json (+ a preview PNG)
"""
import argparse
import glob
import sqlite3
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[2]
VIDEO = REPO / "video"
STUDIO_DB = Path.home() / ".local/share/physicalai/data/physicalai.db"
URDF = next(REPO.glob("physical-ai-studio/application/backend/.venv/lib/python*/site-packages/urdf/so101-follower/so101_follower.urdf"))
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
CHAIN = JOINTS + ["gripper_frame_joint"]
GRIPPER = 5


def rot(axis, angle):
    axis = np.asarray(axis, float)
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def rpy(r, p, y):
    return rot([0, 0, 1], y) @ rot([0, 1, 0], p) @ rot([1, 0, 0], r)


def load_urdf():
    root = ET.parse(URDF).getroot()
    joints = {}
    for j in root.findall("joint"):
        o, a, lim = j.find("origin"), j.find("axis"), j.find("limit")
        T = np.eye(4)
        T[:3, :3] = rpy(*map(float, o.get("rpy").split()))
        T[:3, 3] = list(map(float, o.get("xyz").split()))
        joints[j.get("name")] = {
            "origin": T,
            "axis": list(map(float, a.get("xyz").split())) if a is not None and j.get("type") == "revolute" else None,
            "limits": (float(lim.get("lower")), float(lim.get("upper"))) if lim is not None else None,
        }
    return joints


def tool_position(urdf, state):
    """Gripper tip in base_link coordinates (m) for one row of normalised joint values."""
    T = np.eye(4)
    for name in CHAIN:
        j = urdf[name]
        T = T @ j["origin"]
        if j["axis"] is not None:
            lower, upper = j["limits"]
            fraction = min(max((state[JOINTS.index(name)] + 100) / 200, 0), 1)
            R = np.eye(4)
            R[:3, :3] = rot(j["axis"], lower + (upper - lower) * fraction)
            T = T @ R
    return T[:3, 3]


def episodes(dataset: Path):
    meta = pq.read_table(dataset / "meta/episodes/chunk-000/file-000.parquet",
                         columns=["episode_index", "tasks"]).to_pylist()
    task = {m["episode_index"]: m["tasks"][0] for m in meta}
    tables = [pq.read_table(f, columns=["observation.state", "episode_index", "frame_index"])
              for f in sorted(glob.glob(str(dataset / "data/chunk-000/*.parquet")))]
    states = np.concatenate([np.array(t.column("observation.state").to_pylist(), dtype=float) for t in tables])
    index = np.concatenate([t.column("episode_index").to_numpy() for t in tables])
    for ep in sorted(task):
        yield ep, task[ep], states[index == ep]


def model_dataset(model_name: str) -> tuple[str, Path]:
    """(dataset name, folder) the Studio model was trained on. Read-only."""
    db = sqlite3.connect(f"file:{STUDIO_DB}?mode=ro", uri=True)
    row = db.execute("select d.name, d.path from models m join datasets d on d.id = m.dataset_id "
                     "where m.name = ? order by m.created_at desc limit 1", (model_name,)).fetchone()
    if not row:
        raise SystemExit(f"No Studio model called {model_name!r}")
    return row[0], Path(row[1])


def grasp_frame(gripper):
    """First frame after the widest opening where the gripper is mostly closed again."""
    lo, hi = gripper.min(), gripper.max()
    if hi - lo < 5:
        return None
    widest = int(np.argmax(gripper))
    after = np.nonzero(gripper[widest:] < lo + 0.25 * (hi - lo))[0]
    return widest + int(after[0]) if len(after) else None


def release_frame(gripper):
    """First frame where the gripper opens past half its range."""
    lo, hi = gripper.min(), gripper.max()
    if hi - lo < 5:
        return None
    opened = np.nonzero(gripper > lo + 0.5 * (hi - lo))[0]
    return int(opened[0]) if len(opened) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, help="use this dataset folder for both, instead of the models' datasets")
    args = parser.parse_args()
    urdf = load_urdf()
    facts = json.loads((VIDEO / "facts.json").read_text())
    pick_model, sort_model = facts["models"]["pick"]["name"], facts["models"]["sort"]["name"]
    if args.dataset:
        pick_name = sort_name = args.dataset.name
        pick_path = sort_path = args.dataset
    else:
        pick_name, pick_path = model_dataset(pick_model)
        sort_name, sort_path = model_dataset(sort_model)
    print(f"grasps from {pick_name} ({pick_model}), releases and counts from {sort_name} ({sort_model})")

    # The frame: origin on the pan axis; forward = the arm's direction at shoulder_pan = 0.
    pan_axis = urdf["shoulder_pan"]["origin"][:3, 3]
    ahead = tool_position(urdf, [0, 0, 0, 0, 0, 0]) - pan_axis
    heading = math.atan2(ahead[1], ahead[0])
    c, s = math.cos(-heading), math.sin(-heading)

    def to_table(p):
        d = p - pan_axis
        return [round((c * d[0] - s * d[1]) * 100, 1), round((s * d[0] + c * d[1]) * 100, 1), round(d[2] * 100, 1)]

    grasps, releases = [], {"GOOD": [], "DEFECTIVE": []}
    counts = {"episodes": 0, "picks": 0, "sorts": 0}
    skipped = 0
    for ep, task, st in episodes(pick_path):
        if task.startswith("Pick"):
            f = grasp_frame(st[:, GRIPPER])
            if f is None:
                skipped += 1
            else:
                grasps.append(to_table(tool_position(urdf, st[f])) + [ep])
    for ep, task, st in episodes(sort_path):
        counts["episodes"] += 1
        if task.startswith("Pick"):
            counts["picks"] += 1
            continue
        counts["sorts"] += 1
        f = release_frame(st[:, GRIPPER])
        if f is None:
            skipped += 1
        else:
            releases["GOOD" if "good" in task else "DEFECTIVE"].append(to_table(tool_position(urdf, st[f])) + [ep])

    out = {
        "source": {"grasps": pick_name, "releases": sort_name},
        "dataset": {"name": sort_name, "model": sort_model, **counts},
        "frame": "cm; origin on the shoulder-pan axis; x forward (arm at shoulder_pan 0), y left, z up",
        "approximate": "forward kinematics with Studio's joint mapping; good to a few cm",
        "grasps": grasps,
        "releases": releases,
        "skipped": skipped,
    }
    (VIDEO / "public").mkdir(parents=True, exist_ok=True)
    (VIDEO / "public" / "coverage.json").write_text(json.dumps(out))
    for name, pts in [("grasps", grasps), ("good releases", releases["GOOD"]), ("defective releases", releases["DEFECTIVE"])]:
        a = np.array([p[:3] for p in pts])
        print(f"{name:20} n={len(a):3}  x {a[:,0].min():6.1f}..{a[:,0].max():6.1f}  y {a[:,1].min():6.1f}..{a[:,1].max():6.1f}  "
              f"z median {np.median(a[:,2]):5.1f} (IQR {np.percentile(a[:,2],25):5.1f}..{np.percentile(a[:,2],75):5.1f})")
    print(f"skipped {skipped} episodes (gripper never opened or closed)")
    print(f"{sort_name}: {counts['episodes']} episodes, {counts['picks']} picks, {counts['sorts']} sorts")
    sides = {k: (int(sum(p[1] > 0 for p in v)), int(sum(p[1] <= 0 for p in v))) for k, v in releases.items()}
    print(f"releases left / right of the centre line: green {sides['GOOD']}, orange {sides['DEFECTIVE']}")

    # Preview for checking by eye.
    import cv2
    img = np.full((700, 700, 3), 24, np.uint8)
    scale, ox, oy = 12, 350, 650  # 12 px per cm; base at bottom centre

    def px(p):
        return int(ox - p[1] * scale), int(oy - p[0] * scale)

    for p in grasps:
        cv2.circle(img, px(p), 3, (235, 235, 235), -1)
    for p in releases["GOOD"]:
        cv2.circle(img, px(p), 3, (166, 196, 46), -1)
    for p in releases["DEFECTIVE"]:
        cv2.circle(img, px(p), 3, (26, 122, 255), -1)
    cv2.circle(img, (ox, oy), 8, (61, 139, 217), -1)
    for r in range(10, 60, 10):
        cv2.circle(img, (ox, oy), r * scale, (60, 60, 66), 1)
    cv2.imwrite(str(VIDEO / "out" / "coverage_preview.png"), img)
    print(f"wrote {VIDEO / 'public' / 'coverage.json'} and out/coverage_preview.png")


if __name__ == "__main__":
    main()
