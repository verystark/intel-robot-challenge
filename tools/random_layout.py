#!/usr/bin/env python3
"""Draw a random layout for one evaluation round: where the bricks and the two plates go.

Positions are in cm, measured from the centre of the arm's turret (the shoulder-pan axis):
x = forward along the taped centre line, y = sideways, positive to the robot's LEFT.
Bricks are drawn inside the area the training data covered (video/public/coverage.json, made
by video/scripts/coverage.py); `--outside N` puts N of them outside it on purpose.

    python3 tools/random_layout.py                 # next round: 6 bricks, 2 defective
    python3 tools/random_layout.py --bricks 5 --defective 1 --seed 7

Writes video/layouts/round_NN.json and round_NN.svg (open the SVG to see the map).
Standard library only.
"""
import argparse
import json
import math
import random
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COVERAGE = REPO / "video" / "public" / "coverage.json"
LAYOUTS = REPO / "video" / "layouts"
NEAR_CM = 4.0  # "inside the trained area": a training grasp lies within this distance
BRICK_GAP_CM = 8.0  # centre to centre: at least one brick-width apart
PLATE_GAP_CM = 20.0  # plate centre to plate centre
PLATE_CLEAR_CM = 13.0  # plate centre to any brick


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def near(p, pts, r):
    return any(dist(p, q) <= r for q in pts)


class NoRoom(Exception):
    pass


def sample(rng, box, ok, tries=4000):
    for _ in range(tries):
        p = (round(rng.uniform(box[0], box[1]), 1), round(rng.uniform(box[2], box[3]), 1))
        if ok(p):
            return p
    raise NoRoom


def svg(layout, grasps, releases) -> str:
    size, s = 640, 12.0  # px, px per cm

    def px(x, y):
        return size / 2 - y * s, size - 20 - x * s

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" style="background:#18181c">']
    bx, by = px(0, 0)
    for r in (10, 20, 30, 40):
        parts.append(f'<circle cx="{bx}" cy="{by}" r="{r * s}" fill="none" stroke="#3a3a42"/>'
                     f'<text x="{bx + 4}" y="{by - r * s - 4}" fill="#96969b" font-size="12">{r} cm</text>')
    for g in grasps:
        x, y = px(g[0], g[1])
        parts.append(f'<circle cx="{x}" cy="{y}" r="2" fill="#555"/>')
    for colour, (x0, y0) in (("#2ec4a6", layout["plates"]["green"]), ("#ff7a1a", layout["plates"]["orange"])):
        x, y = px(x0, y0)
        parts.append(f'<circle cx="{x}" cy="{y}" r="{7 * s}" fill="{colour}33" stroke="{colour}" stroke-width="3"/>')
    for b in layout["bricks"]:
        x, y = px(b["x"], b["y"])
        colour = "#ff7a1a" if b["defective"] else "#ebebeb"
        parts.append(f'<g transform="translate({x},{y}) rotate({-b["rotation"]})">'
                     f'<rect x="{-3.2 * s}" y="{-1.6 * s}" width="{6.4 * s}" height="{3.2 * s}" fill="none" stroke="{colour}" stroke-width="2"/></g>'
                     f'<text x="{x + 10}" y="{y - 10}" fill="{colour}" font-size="18" font-weight="bold">{b["n"]}</text>')
    parts.append(f'<circle cx="{bx}" cy="{by}" r="8" fill="#3d8bd9"/>')
    parts.append(f'<text x="10" y="22" fill="#ebebeb" font-size="16">Round {layout["round"]} · forward is up · robot at the bottom</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bricks", type=int, default=6)
    parser.add_argument("--defective", type=int, default=2)
    parser.add_argument("--outside", type=int, default=0, help="bricks deliberately outside the trained area")
    parser.add_argument("--seed", type=int, help="default: from the clock (printed, so a round can be redrawn)")
    args = parser.parse_args()

    cov = json.loads(COVERAGE.read_text())
    grasps = [(p[0], p[1]) for p in cov["grasps"]]
    releases = [(p[0], p[1]) for k in ("GOOD", "DEFECTIVE") for p in cov["releases"][k]]
    seed = args.seed if args.seed is not None else int(time.time()) % 100000
    rng = random.Random(seed)
    LAYOUTS.mkdir(parents=True, exist_ok=True)
    round_no = 1 + max([int(p.stem.split("_")[1]) for p in LAYOUTS.glob("round_[0-9][0-9].json")] or [0])

    for _attempt in range(200):  # redraw everything if the bricks leave no room for the plates
        try:
            bricks, plates = draw(rng, args, grasps, releases)
            break
        except NoRoom:
            continue
    else:
        raise SystemExit("Couldn't place everything: try fewer bricks.")
    layout = {
        "round": round_no,
        "seed": seed,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "frame": "cm from the turret centre; x forward along the centre line, y to the robot's left",
        "bricks": bricks,
        "plates": {"green": plates[0], "orange": plates[1]},
    }
    path = LAYOUTS / f"round_{round_no:02d}.json"
    path.write_text(json.dumps(layout, indent=2))
    path.with_suffix(".svg").write_text(svg(layout, grasps, releases))

    print(f"Round {round_no} (seed {seed}). Measure from the turret centre: forward along the centre line, then sideways.\n")
    print(" #  forward  sideways        rotate  brick")
    for b in bricks:
        side = f"{abs(b['y']):4.1f} cm {'left ' if b['y'] >= 0 else 'right'}"
        extra = "  (outside training area)" if b["outside_training"] else ""
        print(f" {b['n']}  {b['x']:4.1f} cm  {side}   {b['rotation']:3d}°   {'DEFECTIVE' if b['defective'] else 'good'}{extra}")
    for colour, (x, y) in layout["plates"].items():
        print(f"\n{colour:6} plate centre: {x:4.1f} cm forward, {abs(y):4.1f} cm {'left' if y >= 0 else 'right'}", end="")
    print(f"\n\nWrote {path} and {path.with_suffix('.svg')}")


def draw(rng, args, grasps, releases):
    box = (min(g[0] for g in grasps), max(g[0] for g in grasps), min(g[1] for g in grasps), max(g[1] for g in grasps))
    bricks = []
    for i in range(args.bricks):
        outside = i < args.outside

        def ok(p, outside=outside):
            reach = math.hypot(*p)
            if not 8 <= reach <= 40 or any(dist(p, (b["x"], b["y"])) < BRICK_GAP_CM for b in bricks):
                return False
            return near(p, grasps, NEAR_CM) != outside

        x, y = sample(rng, box, ok)
        bricks.append({"n": i + 1, "x": x, "y": y, "rotation": rng.randrange(0, 180, 15), "outside_training": outside})
    rng.shuffle(bricks)
    for i, b in enumerate(bricks):  # renumber after shuffling, so "outside" bricks aren't always 1, 2...
        b["n"] = i + 1
        b["defective"] = False
    for b in rng.sample(bricks, args.defective):
        b["defective"] = True
    bricks.sort(key=lambda b: b["n"])

    rbox = (min(r[0] for r in releases), max(r[0] for r in releases), min(r[1] for r in releases), max(r[1] for r in releases))
    plates = []
    for _ in range(2):
        plates.append(sample(rng, rbox, lambda p: near(p, releases, NEAR_CM)
                             and all(dist(p, (b["x"], b["y"])) >= PLATE_CLEAR_CM for b in bricks)
                             and all(dist(p, q) >= PLATE_GAP_CM for q in plates)))
    rng.shuffle(plates)
    return bricks, plates


if __name__ == "__main__":
    main()
