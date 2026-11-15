#!/usr/bin/env python3
"""Record what happened in each cycle of an evaluation round, right after it happens.

    python3 tools/eval_round.py video/layouts/round_03.json [--run loop/runs/<run>]

For every cycle it asks which brick was picked, whether the pick worked first time, which
verdict the screen showed and whether the brick landed on the right plate. With --run, the
verdict and the cycle time are read from the loop's own log instead of asked. The truth (good or
defective) comes from the layout, so "verdict correct" is not typed by hand.

Writes video/layouts/round_NN_eval.json, which video/scripts/build_data.py adds up for the
video and the submission. Standard library only.
"""
import argparse
import json
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def ask(prompt: str, allowed: str) -> str:
    while True:
        answer = input(prompt).strip().lower()
        if answer in allowed.split("/"):
            return answer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("layout", type=Path)
    parser.add_argument("--run", type=Path, help="the loop run folder of this round (verdicts and times from its log)")
    args = parser.parse_args()

    layout = json.loads(args.layout.read_text())
    bricks = {b["n"]: b for b in layout["bricks"]}
    log = []
    if args.run:
        lines = (args.run / "cycles.jsonl").read_text().splitlines()
        log = [json.loads(line) for line in lines if line.strip()]
    out_path = args.layout.with_name(args.layout.stem + "_eval.json")
    record = {"round": layout["round"], "layout": str(args.layout), "run": str(args.run) if args.run else None,
              "started": time.strftime("%Y-%m-%d %H:%M:%S"), "cycles": []}

    print(f"Round {layout['round']}: {len(bricks)} bricks. Answer after each cycle; q at the brick question ends.\n")
    while True:
        k = len(record["cycles"]) + 1
        n = ask(f"Cycle {k}: which brick did it pick? (1-{len(bricks)}, 0 = none, q = done) ",
                "/".join(["q", "0"] + [str(i) for i in bricks]))
        if n == "q":
            break
        n = int(n)
        cycle = {"cycle": k, "brick": n or None}
        cycle["pick"] = {"f": "first try", "r": "after a retry", "x": "failed"}[ask("  pick: f = first try, r = after a retry, x = failed ", "f/r/x")]
        if n and cycle["pick"] != "failed":
            truth = "DEFECTIVE" if bricks[n]["defective"] else "GOOD"
            entry = log[k - 1] if len(log) >= k else None
            if entry and entry.get("inspect"):
                verdict = entry["inspect"]["verdict"]
                cycle["seconds"] = entry.get("total_s")
                print(f"  verdict from the log: {verdict}")
            else:
                verdict = {"g": "GOOD", "d": "DEFECTIVE"}[ask("  verdict on screen: g = good, d = defective ", "g/d")]
            cycle.update(truth=truth, verdict=verdict, verdict_correct=verdict == truth)
            cycle["plate"] = {"c": "correct", "w": "wrong", "n": "not placed"}[ask("  plate: c = correct for the verdict, w = wrong, n = not placed ", "c/w/n")]
            cycle["placed_as_told"] = cycle["plate"] == "correct"
            cycle["correct_plate"] = cycle["placed_as_told"] and cycle["verdict_correct"]  # end to end
        note = input("  note (enter to skip): ").strip()
        if note:
            cycle["note"] = note
        record["cycles"].append(cycle)
        out_path.write_text(json.dumps(record, indent=2))  # saved after every cycle

    c = record["cycles"]
    first = sum(x["pick"] == "first try" for x in c)
    verdicts = sum(bool(x.get("verdict_correct")) for x in c)
    told = sum(bool(x.get("placed_as_told")) for x in c)
    plates = sum(bool(x.get("correct_plate")) for x in c)
    print(f"\n{len(c)} cycles: pick first try {first}, verdict correct {verdicts}, placed where told {told}, "
          f"correct end to end {plates}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
