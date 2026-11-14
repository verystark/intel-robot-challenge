"""Tell the person resetting the table where to put things for each episode.

Follows Studio's recording guide (library/docs/how-to/data/recording-a-dataset.md):
add variety one stage at a time, and train and test after each stage before
recording the next. Within a stage it walks through every position and rotation
in a shuffled but even order, because people placing things "randomly" cluster
them in comfortable spots.

    python3 recording/layout.py pick --stage 1   # ~50: one brick, bowls fixed
    python3 recording/layout.py pick --stage 2   # ~30: plus 1-2 other bricks (clutter)
    python3 recording/layout.py pick --stage 3   # ~40: plus bowls in 4 layouts
    python3 recording/layout.py sort --stage 1   # ~50: bowls fixed, good/defective pairs
    python3 recording/layout.py sort --stage 2   # ~40: bowls in 4 layouts, pairs

Record all stages of one task into the same Studio dataset (pick-v1 or sort-v1).

Before the first episode, mark with small pieces of tape:
  - the pick area, split into a 3x3 grid. Rows are named by distance from the
    robot's base (near / middle / far); columns as seen in Studio's top camera
    view on screen (left / centre / right)
  - bowl spots 1-4, all reachable by the arm, none on the pick area or the
    inspection spot, none touching the arm's base. Spots 1 and 2 are the
    fixed positions used in the early stages.

Every episode starts at home and ends back at home, held still for ~1 second
before you press Accept.

After each ACCEPTED episode press Enter for the next layout. If you DISCARD an
episode, don't press Enter: redo the same layout.
Commands: Enter = next, p = previous, a number = jump to that episode, q = quit.
Progress is saved per task and stage, so you can quit and continue later.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

STATE = Path(__file__).with_name("state.json")
ROWS = ("near", "middle", "far")  # distance from the robot's base
COLS = ("left", "centre", "right")  # as seen in the top camera view
ROTATIONS = (0, 45, 90, 135)
SHIFTS = ("centred", "~1 cm left", "~1 cm right", "~1 cm nearer the robot", "~1 cm further from the robot")
FIXED_BOWLS = [(1, 2)]
MOVED_BOWLS = [(1, 2), (2, 1), (3, 4), (4, 3)]  # swaps make colour, not position, tell the bowls apart
STAGES = {
    # (task, stage): (target episode count, description)
    ("pick", 1): (50, "one brick, bowls fixed on spots 1 and 2"),
    ("pick", 2): (30, "one brick to pick plus 1-2 other bricks, bowls fixed"),
    ("pick", 3): (40, "bowls moved between 4 layouts, other bricks sometimes present"),
    ("sort", 1): (50, "bowls fixed on spots 1 and 2, each layout recorded as a good/defective pair"),
    ("sort", 2): (40, "bowls moved between 4 layouts, each layout recorded as a good/defective pair"),
}
PICK_TASK = "Pick up the brick and place it on the inspection spot."
BOLD, END = "\033[1m", "\033[0m"


def deck(items: list, seed: int, length: int) -> list:
    """Repeat a shuffled list (reshuffled each round) up to `length` items, so coverage stays even."""
    rng = random.Random(seed)
    out: list = []
    while len(out) < length:
        round_ = list(items)
        rng.shuffle(round_)
        out.extend(round_)
    return out[:length]


def pick_episodes(stage: int, seed: int, n: int = 500) -> list[dict]:
    rows = ROWS if stage == 1 else ROWS[:2]  # with clutter, others must fit further from the robot
    bricks = deck([(r, c, rot) for r in rows for c in COLS for rot in ROTATIONS], seed, n)
    bowls = deck(MOVED_BOWLS if stage == 3 else FIXED_BOWLS, seed + 1, n)
    kinds = deck(["GOOD", "DEFECTIVE"], seed + 2, n)
    others = deck([1, 2] if stage == 2 else [0, 1, 2] if stage == 3 else [0], seed + 3, n)
    episodes = []
    for i in range(n):
        row, col, rot = bricks[i]
        extra = ""
        if others[i]:
            extra = (
                f"Also put {others[i]} other brick{'s' if others[i] > 1 else ''} in the pick area, further from "
                "the robot than this one and not touching it. Always pick the brick NEAREST the robot."
            )
        episodes.append(
            {
                "bowls": bowls[i],
                "brick": f"{BOLD}{kinds[i]}{END} brick in the pick area: {row} row, {col} column, turned {rot}°",
                "extra": extra,
                "photo_key": "g" if kinds[i] == "GOOD" else "b",
                "task": PICK_TASK,
            }
        )
    return episodes


def sort_episodes(stage: int, seed: int, colours: list[str], n: int = 500) -> list[dict]:
    placements = deck([(s, rot) for s in SHIFTS for rot in ROTATIONS], seed, n // 2)
    bowls = deck(MOVED_BOWLS if stage == 2 else FIXED_BOWLS, seed + 1, n // 2)
    verdicts = [("good", colours[0]), ("defective", colours[1])]
    episodes = []
    for i in range(n // 2):
        # Each layout is recorded once per verdict with the same brick, so only the
        # sentence (which carries Anomalib's verdict) tells the policy which bowl.
        shift, rot = placements[i]
        for verdict, colour in verdicts if i % 2 == 0 else verdicts[::-1]:
            episodes.append(
                {
                    "bowls": bowls[i],
                    "brick": f"any brick on the inspection spot: {shift}, turned {rot}°",
                    "extra": "",
                    "photo_key": None,
                    "task": f"The brick is {verdict}. Put it in the {colour} bowl.",
                }
            )
    return episodes


def show(task: str, stage: int, index: int, ep: dict, prev: dict | None, colours: list[str]) -> None:
    target, description = STAGES[(task, stage)]
    print("\033[2J\033[H", end="")  # clear the terminal
    print(f"{task.upper()} stage {stage} ({description})")
    print(f"Episode {BOLD}{index + 1}{END} of ~{target}")
    if index >= target:
        print(f"{BOLD}Stage target reached: train and test before recording the next stage.{END}")
    a, b = ep["bowls"]
    print(f"\n  Bowls:   {colours[0]} bowl on spot {BOLD}{a}{END},  {colours[1]} bowl on spot {BOLD}{b}{END}")
    print(f"  Brick:   {ep['brick']}")
    if ep["extra"]:
        print(f"  Others:  {ep['extra']}")
    task_changed = prev is not None and prev["task"] != ep["task"]
    print(f"\n  Task:    {BOLD}{ep['task']}{END}" + ("   <-- CHANGE the Task box in Studio" if task_changed else ""))
    print("\n  Start at home. Finish back at home, hold still ~1 s, then Accept.")
    if ep["photo_key"]:
        print(f"  Then press {BOLD}{ep['photo_key']}{END} in capture.py for the inspection photo.")
    print("\n  Enter = next   p = previous   number = jump   q = quit")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task", choices=("pick", "sort"))
    parser.add_argument("--stage", type=int, default=1, help="pick: 1-3, sort: 1-2")
    parser.add_argument("--colours", nargs=2, default=["blue", "orange"], help="colour of the GOOD bowl, then the DEFECTIVE bowl")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    if (args.task, args.stage) not in STAGES:
        parser.error(f"{args.task} has stages {sorted(s for t, s in STAGES if t == args.task)}")

    seed = args.seed + 100 * args.stage
    episodes = (
        pick_episodes(args.stage, seed) if args.task == "pick" else sort_episodes(args.stage, seed, args.colours)
    )
    key = f"{args.task}{args.stage}"
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    index = state.get(key, 0)
    while True:
        show(args.task, args.stage, index, episodes[index], episodes[index - 1] if index else None, args.colours)
        command = input("> ").strip().lower()
        if command == "q":
            break
        if command == "p":
            index = max(0, index - 1)
        elif command.isdigit():
            index = min(len(episodes) - 1, max(0, int(command) - 1))
        elif command == "":
            index = min(len(episodes) - 1, index + 1)
        state[key] = index
        STATE.write_text(json.dumps(state) + "\n")


if __name__ == "__main__":
    main()
