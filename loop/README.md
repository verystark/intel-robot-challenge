# The closed loop

`run_cell.py` runs the whole cell: **pick → show → inspect → sort**, with Anomalib's verdict
choosing the sentence SmolVLA gets. `show_tool.py` saves and tests the show pose and collects
inspection photos at it. Both run with **Studio's backend Python**, from the repo root:

```bash
cd ~/intel-robot-challenge
PY=physical-ai-studio/application/backend/.venv/bin/python
```

| File | What it does |
|---|---|
| `run_cell.py` | The loop, the dashboard and the log |
| `dashboard/` | The live web dashboard: `server.py` (local web server), `telemetry.py` (what it shows), `static/` (page), `palette.json` (colours, shared with the video) |
| `show_tool.py` | `where` / `save` the show pose (read-only), `goto`, `test-turn`, `collect` photos |
| `cell_config.json` | Models, devices, sentences, timeouts, show settings, camera ids |
| `poses.json` | Saved poses (`show`, `home`, optional `via`), written by `show_tool.py save` |
| `arm.py` | Follower: calibration from Studio's DB, Studio's device lock, smooth scripted moves, mock arm |
| `policy.py` | Finding Studio models, zero-noise SmolVLA, "stage finished" detection, simulation |
| `inspection.py` | Inspection webcam (same crop and settings as `capture.py`), background Anomalib scoring |
| `screen.py` | The demo screen |
| `runs/` | One folder per run: `cycles.jsonl`, photos with heatmaps, `config.json`, `summary.json` (git-ignored) |

## The operator screen

`run_cell.py` serves the cell's operator screen at **http://localhost:8080**. It is reachable from
this laptop only (it binds to 127.0.0.1). Add `--open` to open it full screen in Firefox, or press
`F11` in the page.

**Style:** it follows ISA-101, the guideline for plant operator screens, the way real production
cells look:
- **Grey when normal:** running equipment is filled dark grey, idle equipment is an outline.
- **Colour only for alarms:** red = priority 1, amber = priority 2. Unacknowledged alarms blink
  until `F5`.
- **Plate swatches:** the GOOD and REJECT bins carry small swatches matching the real plates.

| Area | What it shows |
|---|---|
| Header, alarm banner | Cell, screen, mode (`SIM` / `AUTO` / `INSP ONLY`), state, unacknowledged alarm count, clock; the newest unacknowledged alarm |
| Process | A flow diagram: pick area → SO-101 → inspection station → verdict → GOOD / REJECT bins. The active path is drawn heavy, a token marks the brick, the bins show their counts, and each block carries live tags |
| CAM 01 / 02 / 03 | Top and wrist cameras (the policy's inputs) and the inspection camera with the crop box and the live Anomalib heatmap. Each has a timestamp overlay |
| Sequence | Program steps `10 HOME · 20 PICK · 30 SHOW · 40 INSPECT · 50 HOME · 60 SORT`, the current view, elapsed time against the stage timeout |
| Inspection station | Verdict, score gauge with the GOOD / REJECT limits, each view's heatmap, median, frames and result (skipped views marked), and the exact `TASK → VLA` sentence |
| VLA controller | Model, device, plan length, latency, async; J1–J6 actual, commanded and deviation, with the last 4 s and the policy's planned motion (dashed) |
| Production | Inspected / good / reject, reject rate, second looks, throughput, median cycle, run time, sorted OK |
| Last bricks | ✓ / ✗ buttons: a teammate marks where each brick really landed, saved to `runs/<time>/marks.json` and counted in `bench/RESULTS.md` |
| Events | Timestamped log: priority, tag, message |
| Compute node | GPU / NPU / CPU load and who runs there, package temperature against the 90 °C alarm, power, and the measured per-device latencies from the newest benchmark |

**Tabs:**
- `F6` **Overview**.
- `F7` **Alarms / events:** the full log, with the acknowledgement state.
- `F8` **Trends:**
  - the score of every brick against the shaded limits;
  - cycle time per brick;
  - node load and package temperature over 10 minutes.

`http://localhost:8080/#trends` or `#alarms` opens straight on that tab, for a second monitor.

**Alarms the loop raises:**

| Priority | Alarms |
|---|---|
| P1 | Stop (E-STOP key or button), arm lag abort, loop error |
| P2 | Pick or sort timeout, package above 90 °C, a brick marked ✗ |

Verdicts, views, second looks and mode changes are logged as INFO.

**Keys:**
- `F1` start / resume (or `R`).
- `F2` pause after this cycle (or `Space`); in `--inspect-only` it starts each cycle.
- `F3` or `Esc` or `S`: stop, and the arm holds.
- `F5` acknowledge alarms.
- `F11` full screen.

The buttons along the bottom do the same, and `Ctrl+C` in the terminal always stops.

**Options:**
- `/modern` is the earlier dark presentation page, kept for the video.
- `--window` also opens the old Tk screen.
- `--no-web` skips the screen.
- `--web-port N` changes the port.
- `--headless` (also `--no-window`) is test mode: a stop ends the run instead of waiting for `F1`.

## One cycle

0. **HOME.** If the arm isn't at the home pose (more than 8 units away), a scripted move there.
   The pick episodes start at home.
1. **PICK.** The pick policy, given `Pick up the brick.`, runs until the arm has moved well away
   (40 units), come back near where it started (45 units) and held still for 0.5 s. That's how
   87% of the recorded picks and 90% of the sorts in `main-clean2` end; the rule fired too early
   on only 3 of 158 picks. Timeout: 25 s, after which the loop stops and waits for `r`.
2. **SHOW.** A scripted, eased move to the saved show pose.
3. **INSPECT.** The wrist turns to each stop in `show.stops_deg` in `cell_config.json`, in order.
   It is now **`[90, -90]`**: out to +90°, across to −90°, then back to the show pose. At the
   show pose the camera looks along the jaws, so at 0° and 180° a gripper finger hides the middle
   of the brick. At ±90° the fingers are above and below it, so the two ungripped faces are in
   full view, one at each stop. The two gripped faces aren't checked.
   - **Turn direction:** positive angles turn the way with room for the largest of them, and
     negative angles the other way. From the show pose's wrist angle (7), +90° turns to +60 and
     −90° to −46. If a list doesn't fit either way, the stops are capped by the joint's range
     (e.g. 180° becomes about 178°).
   - Lists such as `[0, 90, 180, 90, 0]` (out and back through the same angles) also work.
   - **Training photos:** Anomalib must have seen both views. Collect with
     `show_tool.py collect --dataset anomaly/dataset_show`, which photographs every stop of the
     same plan, then train on `dataset_show`.
   - **Score per stop:** 3 fresh frames, scored on the GPU while the wrist turns to the next
     stop. The stop's score is their median, so one glitchy frame can't decide.
   - **Decision:**
     - Any stop clearly defective → **DEFECTIVE** at once; the remaining stops are skipped.
     - All stops clearly good → **GOOD**.
     - Otherwise a **second look**: back to each unsure stop, settle, 3 new frames.
       - Any defective → **DEFECTIVE**; all good → **GOOD**; still unsure → **DEFECTIVE**
         (reject when in doubt).
       - A full second look adds about 6 s, so it only pays when unsure is rare.
   - **Training must cover every stop.** Anomalib has to have seen each stop's view in its good
     photos, or that view scores as defective. `show_tool.py collect` photographs exactly
     these stops.
4. **HOME.** A scripted move back to the home pose, where the sort episodes start holding the
   brick.
5. **SORT.** The sort policy with `The brick is good. Put it on the green plate.` or `The brick
   is defective. Put it on the orange plate.` It ends like a pick; timeout 15 s.
6. **LOG.** Stage times, every inference latency, each stop's frame scores and median, photos and
   heatmaps, temperature and loads.

**The grip never changes during scripted moves.** Every scripted move (home, show, the stops) sets
the gripper to the value the policy last commanded, not the value measured. Holding a brick, the
jaws stop short of their command, and that gap is the squeeze; commanding the measured position
would relax it. In `--inspect-only` the brick is put in by hand, so the gripper is commanded to
`grip_closed` (2.5, the commanded value while holding a brick in `main-clean2`).

**Home pose:** the saved `home` in `poses.json` (`show_tool.py save --name home`, with the arm
where the sort episodes start). If none is saved, the loop uses the median start of the sort
episodes in the sort model's dataset and says so.

**Safety built in:**
- Every policy action is limited to 12 units per tick. The limit starts at 2 units per tick and
  ramps up over the first second of each stage, measured from where the arm really is.
- Scripted moves are eased and speed-limited, and abort if a joint lags 20 units behind.
- `Esc` or `s` stops the arm at once; it holds where it is.
- Studio's device lock means the loop and Studio can't drive the arm at the same time.

## Before the first run on the arm

1. **Close everything that uses the follower or the cameras:** Studio sessions and robot pages
   (Studio itself can stay running), `capture.py` and `inspect_live.py`.
2. **Save the show pose:**
   1. In Studio, teleoperate a held brick into the middle of `capture.py`'s green box.
   2. Turn the wrist a little away from straight: a 180° turn only fits if `wrist_roll` is at
      least about 6 units from 0. `where` tells you.
   3. Close the Studio session. The follower keeps holding.
   4. Run `$PY loop/show_tool.py save`. It only reads the servos.
3. **Calibrate the score bands** on the device the loop uses (GPU by default), once there are
   defective photos: `cd anomaly && ../.venv/bin/python calibrate_bands.py`.
4. **Someone at the station** with the follower's 12 V plug in reach. Every command that moves
   the arm asks you to type `clear` first.

## Hardware checklist (in this order)

| # | Command | Moves the arm? | Check |
|---|---|---|---|
| 1 | `$PY loop/run_cell.py --sim --replay --cycles 2 --open` | No | The dashboard opens full screen and fills in: cameras, stops, heatmaps, verdict, history |
| 2 | `$PY loop/show_tool.py where` | No | Joint values look sane |
| 3 | `$PY loop/show_tool.py save` | No | The show pose is saved; it prints the wrist stops it allows |
| 3b | `$PY loop/show_tool.py save --name home` | No | With the arm at home holding a brick (optional: else the dataset's sort start is used) |
| 4 | `$PY loop/show_tool.py goto` | **Yes**, slowly | It arrives at the show pose |
| 5 | `$PY loop/show_tool.py test-turn` | **Yes** | The wrist visits every stop and comes back; the brick doesn't slip; the wrist-camera cable doesn't pull |
| 5b | `$PY loop/show_tool.py collect` | **Yes** | Good and defective photos at every stop; then `train_export.py --int8` and `calibrate_bands.py` |
| 6 | `$PY loop/run_cell.py --inspect-only` | **Yes** | With a brick put in the gripper, press space: show, the stops, verdict |
| 7 | `$PY loop/run_cell.py --cycles 1` | **Yes** | One full cycle; keep a hand near Esc |
| 8 | `$PY loop/run_cell.py` | **Yes** | The demo |

## Choosing models and devices

`cell_config.json` sets the defaults: the newest SmolVLA for both stages, and Anomalib, all on the
GPU. Override them on the command line:

```bash
$PY loop/run_cell.py --model SmolVLA-v2                              # one model for both stages
$PY loop/run_cell.py --pick-model latest:act --pick-device NPU       # ACT picks on the NPU, SmolVLA sorts on the GPU
$PY loop/run_cell.py --anomaly-device NPU --anomaly-model anomaly/exported_model_int8/weights/openvino/model.xml
```

- **Model names:** a name (`SmolVLA-v2`), `latest:smolvla`, `latest:act`, a Studio model id or its
  first characters, or an export folder.
- **Sentences:** the loop checks them against each model's dataset before it starts.
- **ACT:** it gets no sentence. The sort model must read sentences, so it must be a SmolVLA.
- **Same model for both stages:** it is loaded once.

`execution: async` keeps the arm moving while the next chunk is computed. `zero_noise: true` feeds
SmolVLA all-zero start noise, which gave 5–10× less jerk in offline tests. Set it to `false` to
compare.

## Keys

The same in the dashboard and in the Tk window (`--window`):
- `Esc` or `s`: stop the arm now (it holds).
- `r`: resume after a stop.
- `space`: pause after this cycle; `space` again to continue. In `--inspect-only`, `space`
  starts each cycle.
- `f`: full screen.
- `q`: quit (Tk window only).
- `Ctrl+C` in the terminal also stops.

## Simulation (no hardware)

- **`--sim --replay`:** replays recorded episodes from the sort model's dataset through the real
  runtime: queue, smoothing, stage detection and the scripted show on a mock arm. Inspection photos
  come from `anomaly/dataset/test_normal` and `abnormal`.
- **`--sim`:** the real policy models run on the recorded camera frames. The frames don't react to
  the mock arm, so stages often end by timeout; this is for latency and plumbing, not behaviour.
- **`--no-window --save-screens DIR`:** for headless tests, the screen is saved as images.
- **`--bands FILE`:** use other score bands, e.g. a wide unsure band to exercise the second look.

## Known limits

- **Empty grasps can't be detected from the gripper.** With this calibration the gripper reads
  about 3–4 whether it holds a brick or not. An empty pick still goes through inspection. No
  training photo shows an empty gripper, so it should score high and be sent to the defective
  plate, but that hasn't been tested yet: try it once with checklist step 6.
- **Correct sorting is counted by a person**, with the dashboard's ✓ / ✗. The log knows the
  verdict, not where the brick landed.
- **The dashboard was checked in simulation with headless Firefox** at 1440×900 and 1920×1200.
  - It hasn't run with the real cameras yet.
  - The top and wrist feeds come from the runtime while a policy runs, and are read directly
    between runs.
  - The Tk window (`--window`) has only been checked through saved screens.
