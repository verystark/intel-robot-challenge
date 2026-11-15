#!/usr/bin/env python3
"""Build video/public/data.json from the repo's real numbers.

Sources: video/facts.json (hand-kept facts), the newest bench/results/*.json, a loop run's
cycles.jsonl and inspection photos, and the footage files present in video/public/footage/.
Standard library only: run with the system python3.

    python3 video/scripts/build_data.py [--run loop/runs/<run>]
"""
import argparse
import json
import shutil
import statistics
from pathlib import Path

VIDEO = Path(__file__).resolve().parents[1]
REPO = VIDEO.parent
PUBLIC = VIDEO / "public"
FOOTAGE_IDS = ["a1", "a2", "a3", "a4", "b1", "b2", "b3", "rec_top", "rec_wrist"]  # rec_*: a recorded teleop episode (B-roll)


def newest(pattern: str) -> Path | None:
    files = sorted(REPO.glob(pattern))
    return files[-1] if files else None


def bench() -> dict:
    out = {"policy": [], "anomaly": [], "policy_time": None, "anomaly_time": None, "contended": []}
    policy = newest("bench/results/policy_*.json")
    if policy:
        d = json.loads(policy.read_text())
        out["policy_time"] = d.get("time")
        out["policy"] = [
            {"model": r["model"], "device": r["device"], "median_ms": r.get("median_ms"),
             "p95_ms": r.get("p95_ms"), "chunk": (r.get("chunk") or [None])[0]}
            for r in d["rows"] if r.get("median_ms") is not None
        ]
        if d.get("contended"):
            out["contended"].append(f"policy: {d['contended']}")
    anomaly = newest("bench/results/anomaly_*.json")
    if anomaly:
        d = json.loads(anomaly.read_text())
        out["anomaly_time"] = d.get("time")
        out["anomaly"] = [
            {"precision": r["model"], "device": r["device"], "median_ms": r.get("median_ms"),
             "size_mb": r.get("size_mb"), "score_diff_max": r.get("score_diff_max")}
            for r in d["rows"] if r.get("median_ms") is not None
        ]
        if d.get("contended"):
            out["contended"].append(f"anomaly: {d['contended']}")
    return out


def pick_ms(rows: list, model_prefix: str, device: str) -> float | None:
    for r in rows:
        if r["model"].lower().startswith(model_prefix.lower()) and r["device"] == device:
            return r["median_ms"]
    return None


def find_run(explicit: str | None) -> Path | None:
    if explicit:
        return (REPO / explicit).resolve()
    runs = [r for r in sorted((REPO / "loop" / "runs").glob("*")) if list(r.glob("c*_heat.jpg"))]
    return runs[-1] if runs else None


def run_data(run: Path | None) -> dict:
    if not run:
        return {"folder": None, "cycles": [], "images": [], "sim": True}
    cycles = []
    log = run / "cycles.jsonl"
    if log.exists():
        cycles = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    for c in cycles:  # newer logs keep one entry per wrist stop; add the flat lists older code reads
        insp = c.get("inspect")
        if insp and "stops" in insp and "scores" not in insp:
            insp["scores"] = [s["median"] for s in insp["stops"]]
            insp["labels"] = [s["label"] for s in insp["stops"]]
            insp["stops_deg"] = [s["deg"] for s in insp["stops"]]
    config = json.loads((run / "config.json").read_text()) if (run / "config.json").exists() else {}
    sim = bool(config.get("args", {}).get("sim", True))
    dest = PUBLIC / "inspect"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    images = []
    for photo in sorted(run.glob("c*_*.jpg")):
        if photo.stem.endswith("_heat"):
            continue
        heat = photo.with_name(photo.stem + "_heat.jpg")
        shutil.copy(photo, dest / photo.name)
        if heat.exists():
            shutil.copy(heat, dest / heat.name)
        images.append({"photo": f"inspect/{photo.name}",
                       "heat": f"inspect/{heat.name}" if heat.exists() else None})
    return {"folder": str(run.relative_to(REPO)), "cycles": cycles, "images": images, "sim": sim}


def evaluation(facts: dict) -> dict:
    """Add up the evaluation rounds (tools/eval_round.py). Numbers typed into facts.json win."""
    layouts_dir = VIDEO / "layouts"
    evals = sorted(layouts_dir.glob("round_[0-9][0-9]_eval.json"))
    cycles, trials, failures = [], [], []
    for path in evals:
        record = json.loads(path.read_text())
        layout = json.loads((layouts_dir / path.name.replace("_eval", "")).read_text())
        bricks = {b["n"]: b for b in layout["bricks"]}
        for c in record["cycles"]:
            cycles.append(c)
            if c.get("brick") in bricks:
                b = bricks[c["brick"]]
                trials.append({"x": b["x"], "y": b["y"], "ok": bool(c.get("correct_plate"))})
            if c["pick"] != "first try" or not c.get("correct_plate"):
                what = c.get("note") or ", ".join(
                    x for x in [f"pick {c['pick']}" if c["pick"] != "first try" else "",
                                "wrong verdict" if c.get("verdict_correct") is False else "",
                                f"plate {c.get('plate')}" if c.get("plate") not in (None, "correct") else ""] if x)
                failures.append(f"R{record['round']} C{c['cycle']}: {what}")
    seconds = [c["seconds"] for c in cycles if c.get("seconds")]
    measured = {
        "rounds": len(evals) or None,
        "cycles": len(cycles) or None,
        "pick_first_try": sum(c["pick"] == "first try" for c in cycles) if cycles else None,
        "verdict_correct": sum(bool(c.get("verdict_correct")) for c in cycles) if cycles else None,
        "placed_as_told": sum(bool(c.get("placed_as_told")) for c in cycles) if cycles else None,
        "correct_plate": sum(bool(c.get("correct_plate")) for c in cycles) if cycles else None,
        "median_cycle_s": round(statistics.median(seconds), 1) if seconds else None,
        "failures": failures,
    }
    typed = facts["evaluation"]
    merged = {k: (typed[k] if typed.get(k) not in (None, []) else v) for k, v in measured.items()}
    layout_path = facts["run_take"].get("layout")
    layouts = sorted(p for p in layouts_dir.glob("round_[0-9][0-9].json"))
    layout = json.loads((REPO / layout_path).read_text()) if layout_path else (json.loads(layouts[-1].read_text()) if layouts else None)
    return {"evaluation": merged, "trials": trials, "layout": layout}


def examples(facts: dict, run: dict) -> list:
    """The inspection examples chosen in facts.json (by cycle), with their photos and scores per stop."""
    out = []
    for kind, ex in (facts.get("inspection", {}).get("examples") or {}).items():
        cycle = next((c for c in run["cycles"] if c.get("cycle") == ex["cycle"]), None)
        if not cycle or not cycle.get("inspect"):
            continue
        stops = []
        for s in cycle["inspect"].get("stops", []):
            stem = f"c{ex['cycle']:03d}_{int(s['deg'])}deg"
            stops.append({"deg": s["deg"], "median": s["median"], "label": s["label"],
                          "photo": f"inspect/{stem}.jpg", "heat": f"inspect/{stem}_heat.jpg"})
        out.append({"kind": kind, "cycle": ex["cycle"], "what": ex.get("what", ""), "verdict": cycle["inspect"]["verdict"],
                    "second_look": cycle["inspect"].get("second_look", False), "stops": stops})
    return out


def loop_settings() -> dict:
    """What the loop does at inspection, from loop/cell_config.json (so slides never hard-code it)."""
    cfg = json.loads((REPO / "loop" / "cell_config.json").read_text())
    show = cfg.get("show", {})
    return {"stops_deg": show.get("stops_deg", [0]), "frames_per_stop": show.get("frames_per_stop", 1),
            "pick_timeout_s": cfg.get("pick", {}).get("timeout_s"), "sort_timeout_s": cfg.get("sort", {}).get("timeout_s"),
            "fps": cfg.get("fps", 30)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", help="loop run folder for the overlays and photos (default: newest with heatmaps)")
    args = parser.parse_args()

    facts = json.loads((VIDEO / "facts.json").read_text())
    b = bench()
    run = run_data(find_run(args.run or facts["run_take"]["loop_run"]))
    footage = {fid: (PUBLIC / "footage" / f"{fid}.mp4").exists() for fid in FOOTAGE_IDS}

    pick = facts["models"]["pick"]
    sort = facts["models"]["sort"]
    pick_prefix = "ACT" if pick["name"].upper().startswith("ACT") else "SmolVLA"
    anomaly_gpu = next((r["median_ms"] for r in b["anomaly"]
                        if r["precision"] == "FP32" and r["device"] == facts["models"]["anomaly"]["device"]), None)

    scores = [s for c in run["cycles"][:1] for s in c.get("inspect", {}).get("scores", [])]
    cycle_s = [c["total_s"] for c in run["cycles"] if c.get("total_s")]
    e = evaluation(facts)
    ev = e["evaluation"]
    draft_reasons = []
    if run["sim"]:
        draft_reasons.append("run overlays come from a simulation run")
    results = facts.get("results") or {}
    if ev["cycles"] is None and not results.get("bricks_through_loop"):
        draft_reasons.append("no evaluation yet")
    if not footage["a1"]:
        draft_reasons.append("no footage of the run yet")
    inspection = facts.get("inspection") or {}
    if inspection.get("ms_cpu_npu_note"):
        draft_reasons.append("inspection CPU / NPU latency measured while the loop ran")
    elif b["contended"]:
        draft_reasons.append("benchmarks measured on a busy laptop")

    # Episode counts come from the sort model's own dataset (scripts/coverage.py); facts.json is the fallback.
    coverage_path = PUBLIC / "coverage.json"
    counted = json.loads(coverage_path.read_text()).get("dataset") if coverage_path.exists() else None
    dataset = counted or facts["dataset"]
    if counted and counted.get("model") != sort["name"]:
        draft_reasons.append(f"coverage.json was made for {counted.get('model')}, not {sort['name']}: rerun scripts/coverage.py")
    # INT8 size and score difference of the current inspection model (scripts/int8_check.py).
    int8_path = PUBLIC / "int8.json"
    model_bin = REPO / "anomaly/exported_model/weights/openvino/model.bin"
    if inspection.get("int8_mb"):  # measured on the current brick-square model (facts.json)
        for r in b["anomaly"]:
            r["size_mb"] = inspection["int8_mb"] if r["precision"].startswith("INT8") else inspection["fp32_mb"]
            if r["precision"].startswith("INT8"):
                r["score_diff_max"] = inspection["int8_diff_max"]
    elif int8_path.exists():
        int8 = json.loads(int8_path.read_text())
        for r in b["anomaly"]:
            r["size_mb"] = int8["int8_mb"] if r["precision"].startswith("INT8") else int8["fp32_mb"]
            if r["precision"].startswith("INT8"):
                r["score_diff_max"] = int8["score_diff_max"]
        if model_bin.exists() and model_bin.stat().st_mtime > int8_path.stat().st_mtime:
            draft_reasons.append("inspection model retrained after the INT8 check: rerun scripts/int8_check.py")
    data = {
        "facts": {**facts, "dataset": {**facts["dataset"], **dataset}},
        "numbers": {
            "EPISODES": dataset["episodes"],
            "PICKS": dataset["picks"],
            "SORTS": dataset["sorts"],
            "PICK_MS": pick_ms(b["policy"], pick_prefix, pick["device"]),
            "SORT_MS": pick_ms(b["policy"], "SmolVLA", sort["device"]),
            "INSPECT_MS": anomaly_gpu,
            "R": ev["rounds"], "M": ev["cycles"], "P": ev["pick_first_try"],
            "I": ev["verdict_correct"], "S": ev.get("placed_as_told"), "E": ev["correct_plate"],
            "X": ev["median_cycle_s"] or results.get("median_cycle_s") or (round(statistics.median(cycle_s), 1) if cycle_s and not run["sim"] else None),
            # Measured on the arm (facts.json "results"); the narration and the results scene use these.
            "BRICKS": results.get("bricks_through_loop"),
            "VERDICTS_OK": results.get("verdicts_correct"),
            "DEF_REJ": (results.get("defective_rejected") or [None, None])[0],
            "DEF_TOTAL": (results.get("defective_rejected") or [None, None])[1],
            "CLEAN_OK": (results.get("clean_accepted") or [None, None])[0],
            "CLEAN_TOTAL": (results.get("clean_accepted") or [None, None])[1],
            "FALSE_REJ": (lambda c: c[1] - c[0] if None not in c else None)(results.get("clean_accepted") or [None, None]),
            "PICKS_OK": results.get("picks_ok"),
            "PICK_ATTEMPTS": results.get("pick_attempts"),
            "CYCLE_S": results.get("median_cycle_s"),
            "PICK_S": results.get("median_pick_s"),
            "INSPECT_S": results.get("median_inspect_s"),
            "SORT_S": results.get("median_sort_s"),
            "VLA_MS": (facts.get("policy") or {}).get("chunk_ms_gpu"),
            "INSPECT_MS_LOOP": inspection.get("ms_gpu_loop"),
            "INSPECT_MS_CPU": inspection.get("ms_cpu"),
            "INSPECT_MS_NPU": inspection.get("ms_npu"),
        },
        "bench": b,
        "run": {**run, "scores": scores, "examples": examples(facts, run)},
        "footage": footage,
        "evaluation": ev,
        "loop": loop_settings(),
        "trials": e["trials"],
        "layout": e["layout"],
        "draft": draft_reasons,
    }
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "data.json").write_text(json.dumps(data, indent=2))
    print(f"wrote {PUBLIC / 'data.json'}")
    for key, value in data["numbers"].items():
        print(f"  {key:10} {value}")
    print("  footage:", ", ".join(k for k, v in footage.items() if v) or "none")
    print("  draft because:", "; ".join(draft_reasons) or "-")


if __name__ == "__main__":
    main()
