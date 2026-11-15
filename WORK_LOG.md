# Work log: inspection, closed loop and benchmarks

2026-11-14, Claude Code session on the station laptop.

## Summary

Everything around the models is now built and pushed to `main`:

- the closed loop that runs pick → inspect → sort, with its demo screen;
- the show tool;
- a retrained Anomalib pipeline;
- benchmarks with an evidence table;
- a demo-day guide.

All of it was tested in simulation; nothing that moves the arm has been run yet.

The work followed both judging tables. The PDF (page 7) gives 25 points to the closed loop, 20 to
Anomalib, 20 to VLA and Studio, 20 to OpenVINO, 10 to reliability and 5 to the demo.
`JUNCTION2026.md`'s alternative table gives 20 points to system efficiency: latency, temperature
and power.

**One thing needs action before the inspection model is trusted:** the crop box moved at 10:58,
after the model was trained. Run `recrop.py` and retrain (about 3 minutes now).

## Inspection model (Anomalib)

The detector now trains on photos that match the current setup, trains on the Intel GPU, and has
an INT8 copy and calibrated score bands.

**Photos**

- 475 of the 647 good photos showed the old setup: the arm reaching down from above, a different
  backdrop. They moved to `anomaly/old_setup/` and are no longer trained on.
- The 172 current photos were re-cut to one size (720 px). The last 22, a block of different
  bricks, became `test_normal`.
- There are still no defective photos.

**Training (`train_export.py`)**

- Trains without defective photos. The threshold then becomes the highest held-out good score,
  and testing is skipped.
- Trains on the Intel GPU through Anomalib's XPU accelerator. The slowest step took 2.7 min instead
  of 12–17 min on the CPU.
- `--int8` makes a weight-only INT8 copy: 35 MB → 9 MB, scores within about 0.06. Full INT8 moved
  scores by up to 0.28, so it isn't used.

**New tools**

- `detector.py` runs the model with plain OpenVINO. Its scores match Anomalib's own inferencer
  exactly on the CPU.
- `calibrate_bands.py` sets the good / unsure / defective bands per device and writes
  `bands.json`.
- `quantize_int8.py` makes the INT8 copy.

**Trial on the current photos** (150 good to train, 22 held back, 25 fake marker strokes):

| Photos | Good (< 0.4) | Unsure | Defective (> 0.6) |
|---|---|---|---|
| 22 held-back good bricks | 16 | 6 | 0 |
| 25 fake defects | 8 | 7 | 10 |

None of the good bricks was called defective, but 8 of the 25 fake defects passed as good. The
heatmaps put the doubt on the brick itself, at grip angles training hadn't seen. Real defect
photos and more good photos at those angles are the fix.

## Closed loop, demo screen and show tool

`loop/run_cell.py` runs the cell with no one choosing anything. Anomalib's verdict becomes the
sentence the VLA is given.

```text
PICK ─────────▶ SHOW ─────────────▶ INSPECT ─────────────────────▶ verdict?
SmolVLA or ACT  scripted move to    photo, turn 180°, photo           │
picks the brick the saved pose      (Anomalib scores on the GPU      ├─ good / defective ─▶ SORT
     ▲                               while the arm turns)            │
     │                                                               └─ unsure ─▶ RE-CHECK: turn 90°, 3rd photo
     │                                                                             good → good
     │                                                                             still unsure → defective ─▶ SORT
     │
     └──── next brick ◀── SORT: SmolVLA is told the verdict
                            good:      "The brick is good. Put it on the green plate."
                            defective: "The brick is defective. Put it on the orange plate."
```

Either view defective rejects the brick, and both good accepts it. Otherwise a third look decides,
and a brick that is still unsure is rejected.

**How it runs**

- It runs standalone on Studio's own runtime (`RobotRuntime`), because Studio has no API call that
  starts a run.
- It takes Studio's device lock, so the loop and a Studio session can't drive the arm at once.
- Pick and sort can be different models, e.g. ACT for the pick on the NPU and SmolVLA for the sort
  on the GPU.
- It checks the sentences against each model's dataset before starting.
- A stage ends when the arm has gone out, come back near its start and held still for 0.5 s. Run
  over the recorded episodes, that rule fired on 87% of picks and 90% of sorts, and too early on 3
  of 158 picks.

**Safety**

- Each policy step is clamped: 2 units per tick at the start of a stage, ramping to 12 over the
  first second.
- Scripted moves are eased, speed-limited and stop if a joint lags.
- Esc stops the arm (it holds position). Stages time out after 25 s (pick) and 15 s (sort).
- Every command that moves the arm asks you to type `clear` first.

**Demo screen:** live camera, the sentence sent to SmolVLA, inspection photos with heatmaps, a
score bar with the bands, the verdict, timings per stage, latency per model and device, and
temperature and loads.

**Show tool (`loop/show_tool.py`):** `where` and `save` read the arm's position without touching
torque. `goto` and `test-turn` move to the show pose and try the wrist turns there. `collect` takes
inspection photos at the show pose, as GUIDE2 describes.

**Tested in simulation** (mock arm, recorded episodes and photos): full cycles with replayed
episodes, and one cycle with both real models (ACT pick on the NPU, SmolVLA-v2 sort on the GPU).
Testing caught one bug: a clear third look couldn't overturn an unsure first view. It's fixed.

## Measurements

SmolVLA belongs on the GPU, ACT runs as fast on the NPU as on the GPU, and Anomalib is fastest on
the GPU. All numbers were taken while the GPU was 80–100% busy with other work, so they are
provisional.

| Model (median per call) | GPU | NPU | CPU |
|---|---|---|---|
| SmolVLA-v2, one 50-action chunk | 214 ms | won't compile | 4,764 ms |
| ACT-pick-v1, one 100-action chunk | 15 ms | 17 ms | 218 ms |
| Anomalib PatchCore, one 720 px crop | 18 ms | 184 ms | 56 ms |

- **SmolVLA keeps up on the GPU.** The loop asks for the next chunk with 25 actions left (833 ms at
  30 fps). SmolVLA's p95 on the GPU is 222 ms, 3.8× inside that budget.
- **Anomalib runs on the GPU (changed after this log was first written).** It is 10× faster there
  than on the NPU (18 vs 184 ms). The GPU is free while the brick is shown, since no policy runs
  then. Its scores are also closer to FP32 on the CPU. The NPU's use is the ACT pick, where it
  matches the GPU.
- **INT8 Anomalib is smaller, not faster.** It is 4× smaller (9 MB), about as fast, with scores
  within about 0.06.
- **Sensors without sudo:** package temperature, CPU, GPU and NPU busy %, and the battery's
  whole-laptop power when unplugged. Package power needs one `sudo chmod` at the laptop.
- **The laptop runs hot:** the package reached 90–97 °C under load today.

The full tables are in `bench/RESULTS.md`, generated by `bench/make_table.py`. Re-run both
benchmarks on a quiet laptop before quoting them to judges.

## Findings the team should know

- **The crop box moved after training.** It moved at 10:58 from (997, 589) to (985, 529), same
  720 px size. The model trained on the old position, so live photos are framed about 60 px
  differently. Run `recrop.py`, then `train_export.py`.
- **An ACT pick model exists.** `ACT-pick-v1`, trained on `main-picks`, runs in 17 ms on the NPU.
  The loop can use it for the pick: `--pick-model latest:act --pick-device NPU`.
- **The sentences are the same in every cleaned dataset:** `Pick up the brick.`,
  `The brick is good. Put it on the green plate.` and
  `The brick is defective. Put it on the orange plate.`
- **Recorded episodes don't end still.** The arm is often still moving when an episode stops, so
  the loop's "done" check tests for return-near-start plus 0.5 s of stillness instead.
- **The gripper can't tell holding from empty.** It reads about 3–4 either way with this
  calibration, so an empty grasp can only show up at inspection.
- **A 180° wrist turn doesn't fit from a wrist angle near 0.** Save the show pose with `wrist_roll`
  at least about 6 units to one side; otherwise the loop turns 90°.
- **Studio's Python can't open OpenCV windows** (headless build), so the demo screen uses a Tk
  window.
- **The other session's Studio edits are local only.** Its Modal training changes inside the Studio
  submodule (`GPU_SCALING.md`) weren't pushed, since the submodule is Intel's upstream repository.
  `uv sync` or a submodule update can erase them.

## Not done yet and next steps

The hardware steps need someone at the station with the follower's 12 V plug in reach;
`loop/README.md` has them in order.

- [ ] Re-cut the photos at the new box (`recrop.py`) and retrain (`train_export.py --int8`).
- [ ] Capture 20–40 defective photos (`b`), plus more good ones at the grip angles that scored
      unsure. Then retrain and run `calibrate_bands.py`.
- [ ] Check the demo window once: `run_cell.py --sim --replay --cycles 2`. It was only checked
      through saved screenshots.
- [ ] Save the show pose (`show_tool.py save`), then `goto` and `test-turn` it.
- [ ] Run `run_cell.py --inspect-only` with one good and one defective brick in the gripper. Also
      try an empty gripper, to see if it scores as defective.
- [ ] Run one full cycle, then 10, counting correct sorts by hand.
- [ ] Choose the pick model: SmolVLA or ACT on the NPU.
- [ ] Re-run both benchmarks on a quiet laptop, with package power readable, then `make_table.py`.

When a training run finishes, `DEMO_DAY.md` section 4 lists what to run, in order.

## Commits and files

Three commits on `main`, pushed as `6720e79..7c06559`:

| Commit | What it holds |
|---|---|
| `7c06559` | The other session's notes: `MODEL_RUN_NOTES.md`, `DATASET_MAIN_CLEAN3.md`, `GPU_SCALING.md` |
| `727b200` | `loop/`, `bench/` (with `RESULTS.md`), `DEMO_DAY.md`, `CLAUDE.md`, the GUIDE.md status update |
| `bf29090` | Photo cleanup and re-cut, `train_export.py` changes, `detector.py`, `calibrate_bands.py`, `quantize_int8.py`, both exported models |

| Where | What |
|---|---|
| `DEMO_DAY.md` | Architecture, how each judging criterion is met, the run sheet, likely questions |
| `loop/README.md` | How to run the loop and show tool; the hardware checklist |
| `bench/RESULTS.md` | Generated evidence table: latency, load, temperature, loop runs |
| `anomaly/README.md` | The inspection tools, including the new ones |
| `CLAUDE.md` | Guidance for Claude Code sessions in this repo |

## Update, 2026-11-14 afternoon

- **Anomalib runs on the GPU by default** (`c239919`): 18 ms vs 184 ms on the NPU, and the GPU is
  free while the brick is shown. The NPU's job is the ACT pick.
- **Inspection at three wrist stops:** 0°, 90° and 180°, all turned the same way. From a wrist
  angle near 0 the 180° stop is capped at about 171°.
  - Each stop takes 3 frames; its score is their median.
  - A clearly defective stop rejects at once and skips the rest.
  - Unsure stops get one second look; still unsure means defective.
  - `show_tool.py collect` photographs the same stops (`..._a<degrees>.png`), so the training
    photos match. Anomalib has to be trained on every stop's view, or that view scores as
    defective.
- **Coded home pose:** the loop moves home before each pick (if away) and after inspection,
  before the sort.
  - Every scripted move keeps the gripper at the policy's last commanded value, so the squeeze
    on the brick doesn't change.
  - The home pose is `show_tool.py save --name home`, else the median start of the sort
    episodes.
- **`--bands FILE`** lets the loop use other score bands (used to test the second look).
- **Tested in simulation:** early reject, all three stops, and the second look.
- **The detector is the open problem.** The model retrained at 14:24 with 25 defect photos scores
  held-out good bricks at a median of 0.59, and defects at 0.84. With calibrated bands, 16 of 22
  good bricks and 15 of 25 defects would fall in the unsure band, so nearly everything would be
  rejected. The fix is more good photos taken by `collect` at the real stops, then retraining.

## Update: live dashboard

`run_cell.py` now serves a dashboard at http://localhost:8080 (`--open` = full screen in Firefox).
It replaces the Tk window as the main screen; `--window` keeps the old one.

**What's on it:**
- the Perceive → Detect → Reason → Act → Optimize bar, with device and latency per stage;
- plain narration of the current step;
- the top, wrist and inspection cameras, with a live Anomalib heatmap while inspecting;
- the verdict and the exact sentence sent to the policy;
- the stop tiles with heatmaps, and the score bar;
- the policy's planned vs measured joints;
- GPU / NPU / CPU load, temperature and the measured placement;
- the last bricks, with ✓ / ✗ marks. A teammate clicks them to count correct sorts, which feed
  `bench/RESULTS.md`.

**Look:** it follows `VIDEO_PLAN.md`: dark grey, one accent colour per stage, the plate colours for
verdicts, fades only. The colours are in `loop/dashboard/palette.json` for the video to reuse.

**Checked in simulation** with headless Firefox at 1440×900 and 1920×1200, with replayed episodes
and with the real SmolVLA. The stop and mark posts work.

`PLAN_AND_SHOW.md` and `VIDEO_PLAN.md` still say "loop window"; it is now this page, and `F` still
means full screen.

**The laptop runs hot:** the package sat at 86–97 °C during these tests, with other training and
evaluation running alongside.

## Update: industrial operator screen

The dashboard at http://localhost:8080 is now a plant operator screen in the ISA-101 style. It
looks like the HMI of a real production cell: grey when normal, colour only for alarms.

**What's on it:**
- the process diagram (pick area → SO-101 → inspection → verdict → bins) with the active path and
  a brick token;
- three camera monitors;
- the program-step sequence;
- inspection, VLA-controller, production and compute-node faceplates;
- a timestamped alarm and event log, with P1 / P2 alarms and acknowledgement;
- tabs for the full alarm log and for trends;
- an F-key bar.

The earlier dark page stays at `/modern`, for the video.

**Bugs fixed on the way:**
- **Frozen camera feeds:** a feed whose camera stopped changing (cell stopped) never showed,
  because an MJPEG frame only displays once the next boundary arrives.
- **Blank first paint:** the page now carries the current state.

**Checked in simulation** with headless Firefox at 1440×900 and 1920×1200: running, an early
reject, a stop (P1), ✓ / ✗ marks, acknowledge, and the Trends and Alarms tabs.
