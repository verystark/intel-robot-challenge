"""Tell the team what to set up and which sentences to use for each recording cycle.

Everything is recorded into ONE Studio dataset (cell-v1, environment policy-cell)
and trains ONE SmolVLA. One cycle = two episodes recorded back to back:

  1. PICK  "Pick up the brick and show it to the inspection camera."
           home -> grab the brick -> hold it still in capture.py's green box ~1 s -> Accept.
           Person B presses g or b in capture.py while the brick is held.
  2. SORT  "The brick is good. Put it in the blue bowl." (or the defective / orange one)
           from where the pick ended -> into the named bowl -> home -> hold still ~1 s -> Accept.

The sort sentence is drawn at random, independently of whether the brick is
really good or defective. That is on purpose: SmolVLA must learn to follow the
sentence (which carries Anomalib's verdict at run time), not to judge the brick
itself.

Follows Studio's recording guide (library/docs/how-to/data/recording-a-dataset.md):
add variety one stage at a time, and train and test after each stage.

    python3 recording/layout.py --stage 1   # ~50 cycles: one brick, bowls fixed
    python3 recording/layout.py --stage 2   # ~30 cycles: plus 1-2 other bricks (clutter)
    python3 recording/layout.py --stage 3   # ~40 cycles: plus bowls in 4 layouts

Before the first cycle, mark with small pieces of tape:
  - the pick area, split into a 3x3 grid. Rows are named by distance from the
    robot's base (near / middle / far); columns as seen in Studio's top camera
    view on screen (left / centre / right)
  - bowl spots 1-4, all reachable by the arm, none on the pick area, none
    touching the arm's base, none under the showing point. Spots 1 and 2 are the
    fixed positions used in stages 1 and 2.

Press Enter when BOTH episodes of a cycle are accepted. If you discard an
episode, don't press Enter: redo it (for a discarded sort, first bring the brick
back to the green box without recording).
Commands: Enter = next cycle, p = previous, a number = jump to that cycle, q = quit.
Progress is saved per stage, so you can quit and continue later.
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
FIXED_BOWLS = [(1, 2)]
MOVED_BOWLS = [(1, 2), (2, 1), (3, 4), (4, 3)]  # swaps make colour, not position, tell the bowls apart
STAGES = {  # stage: (target cycles, description)
    1: (50, "one brick, bowls fixed on spots 1 and 2"),
    2: (30, "one brick to pick plus 1-2 other bricks, bowls fixed"),
    3: (40, "bowls moved between 4 layouts, other bricks sometimes present"),
}
PICK_TASK = "Pick up the brick and show it to the inspection camera."
BOLD, END = "\033[1m", "\033[0m"


def sort_task(verdict: str, colour: str) -> str:
    return f"The brick is {verdict}. Put it in the {colour} bowl."


def deck(items: list, seed: int, length: int) -> list:
    """Repeat a shuffled list (reshuffled each round) up to `length` items, so coverage stays even."""
    rng = random.Random(seed)
    out: list = []
    while len(out) < length:
        round_ = list(items)
        rng.shuffle(round_)
        out.extend(round_)
    return out[:length]


def cycles(stage: int, seed: int, colours: list[str], n: int = 500) -> list[dict]:
    rows = ROWS if stage == 1 else ROWS[:2]  # with clutter, the others must fit further from the robot
    bricks = deck([(r, c, rot) for r in rows for c in COLS for rot in ROTATIONS], seed, n)
    bowls = deck(MOVED_BOWLS if stage == 3 else FIXED_BOWLS, seed + 1, n)
    # Brick type and sentence are drawn independently, so each brick type gets both sentences equally often.
    combos = deck([(kind, verdict) for kind in ("GOOD", "DEFECTIVE") for verdict in ("good", "defective")], seed + 2, n)
    others = deck([1, 2] if stage == 2 else [0, 1, 2] if stage == 3 else [0], seed + 3, n)
    colour_of = {"good": colours[0], "defective": colours[1]}
    out = []
    for i in range(n):
        row, col, rot = bricks[i]
        kind, verdict = combos[i]
        out.append(
            {
                "bowls": bowls[i],
                "brick": f"{BOLD}{kind}{END} brick in the pick area: {row} row, {col} column, turned {rot}°",
                "others": others[i],
                "photo_key": "g" if kind == "GOOD" else "b",
                "sort_task": sort_task(verdict, colour_of[verdict]),
                "sort_colour": colour_of[verdict],
            }
        )
    return out


def show(stage: int, index: int, c: dict, colours: list[str]) -> None:
    target, description = STAGES[stage]
    print("\033[2J\033[H", end="")  # clear the terminal
    print(f"STAGE {stage} ({description})")
    print(f"Cycle {BOLD}{index + 1}{END} of ~{target}")
    if index >= target:
        print(f"{BOLD}Stage target reached: train and test before recording the next stage.{END}")

    a, b = c["bowls"]
    print(f"\n{BOLD}SET UP{END}")
    print(f"  Bowls:   {colours[0]} bowl on spot {BOLD}{a}{END},  {colours[1]} bowl on spot {BOLD}{b}{END}")
    print(f"  Brick:   {c['brick']}")
    if c["others"]:
        n = c["others"]
        print(
            f"  Others:  {n} other brick{'s' if n > 1 else ''} in the pick area, further from the robot than this one, "
            "not touching it. Always pick the brick NEAREST the robot."
        )

    print(f"\n{BOLD}EPISODE 1: PICK{END}   Task box:\n")
    print(PICK_TASK)
    print("\n  Home -> grab the brick -> hold it still in the green box ~1 s -> Accept.")
    print(f"  While it's held, person B presses {BOLD}{c['photo_key']}{END} in capture.py.")

    print(f"\n{BOLD}EPISODE 2: SORT{END}   Task box:\n")
    print(c["sort_task"])
    print(f"\n  Start where the pick ended -> {c['sort_colour']} bowl -> home -> hold still ~1 s -> Accept.")
    print("  (The sentence is random on purpose. It doesn't have to match the brick.)")

    print("\n  Enter = next cycle (after both episodes are accepted)   p = previous   number = jump   q = quit")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", type=int, choices=sorted(STAGES), default=1)
    parser.add_argument("--colours", nargs=2, default=["blue", "orange"], help="colour of the GOOD bowl, then the DEFECTIVE bowl")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    plan = cycles(args.stage, args.seed + 100 * args.stage, args.colours)
    key = f"stage{args.stage}"
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    index = state.get(key, 0)
    while True:
        show(args.stage, index, plan[index], args.colours)
        command = input("> ").strip().lower()
        if command == "q":
            break
        if command == "p":
            index = max(0, index - 1)
        elif command.isdigit():
            index = min(len(plan) - 1, max(0, int(command) - 1))
        elif command == "":
            index = min(len(plan) - 1, index + 1)
        state[key] = index
        STATE.write_text(json.dumps(state) + "\n")


if __name__ == "__main__":
    main()
