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
| `run_cell.py` | The loop, the demo screen and the log |
| `show_tool.py` | `where` / `save` the show pose (read-only), `goto`, `test-turn`, `collect` photos |
| `cell_config.json` | Models, devices, sentences, timeouts, show settings, camera ids |
| `poses.json` | Saved poses (`show`, optional `via`), written by `show_tool.py save` |
| `arm.py` | Follower: calibration from Studio's DB, Studio's device lock, smooth scripted moves, mock arm |
| `policy.py` | Finding Studio models, zero-noise SmolVLA, "stage finished" detection, simulation |
| `inspection.py` | Inspection webcam (same crop and settings as `capture.py`), background Anomalib scoring |
| `screen.py` | The demo screen |
| `runs/` | One folder per run: `cycles.jsonl`, photos with heatmaps, `config.json`, `summary.json` (git-ignored) |

## One cycle

1. **PICK.** The pick policy, given `Pick up the brick.`, runs until the arm has moved well away
   (40 units), come back near where it started (45 units) and held still for 0.5 s. That's how
   87% of the recorded picks and 90% of the sorts in `main-clean2` end; the rule fired too early
   on only 3 of 158 picks. Timeout: 25 s, after which the loop stops and waits for `r`.
2. **SHOW.** A scripted, eased move to the saved show pose. The grip the policy last commanded
   is kept, so the brick isn't dropped.
3. **INSPECT.** Photo, wrist turn 180° (90° if 180° doesn't fit the wrist's range), photo, turn
   back. Anomalib scores photo 1 while the wrist turns, and photo 2 while it turns back.
   - Either view defective → **DEFECTIVE**.
   - Both views good → **GOOD**.
   - Otherwise **UNSURE**: turn 90° and take a third photo. Any defective view → **DEFECTIVE**;
     otherwise the third photo decides: good → **GOOD**, still unsure → **DEFECTIVE**.
4. **SORT.** Back to where the pick ended (where the sort episodes start), then the sort policy
   with `The brick is good. Put it on the green plate.` or `The brick is defective. Put it on the
   orange plate.` It ends like a pick; timeout 15 s.
5. **LOG.** Stage times, every inference latency, scores, photos and heatmaps, temperature and loads.

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
| 1 | `$PY loop/run_cell.py --sim --replay --cycles 2` | No | The window opens and shows both stages, photos, heatmaps and timings |
| 2 | `$PY loop/show_tool.py where` | No | Joint values look sane |
| 3 | `$PY loop/show_tool.py save` | No | The show pose is saved; the 180° turn fits |
| 4 | `$PY loop/show_tool.py goto` | **Yes**, slowly | It arrives at the show pose |
| 5 | `$PY loop/show_tool.py test-turn` | **Yes** | The wrist turns 180° and 90° and back; the wrist-camera cable doesn't pull |
| 6 | `$PY loop/run_cell.py --inspect-only` | **Yes** | With a brick put in the gripper, press space: show, two photos, verdict |
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

## Window keys

`Esc` or `s` = stop the arm now (it holds), `r` = resume after a stop, `space` = pause after this
cycle (and `space` again to continue), `f` = full screen, `q` = quit. `Ctrl+C` in the terminal also
stops. In `--inspect-only`, `space` starts each cycle.

## Simulation (no hardware)

- **`--sim --replay`:** replays recorded episodes from the sort model's dataset through the real
  runtime: queue, smoothing, stage detection and the scripted show on a mock arm. Inspection photos
  come from `anomaly/dataset/test_normal` and `abnormal`.
- **`--sim`:** the real policy models run on the recorded camera frames. The frames don't react to
  the mock arm, so stages often end by timeout; this is for latency and plumbing, not behaviour.
- **`--no-window --save-screens DIR`:** for headless tests, the screen is saved as images.

## Known limits

- **Empty grasps can't be detected from the gripper.** With this calibration the gripper reads
  about 3–4 whether it holds a brick or not. An empty pick still goes through inspection. No
  training photo shows an empty gripper, so it should score high and be sent to the defective
  plate, but that hasn't been tested yet: try it once with checklist step 6.
- **Correct sorting is counted by a person.** The log knows the verdict, not where the brick
  landed.
- **The Tk window has only been checked through saved screens** (`--save-screens`). Run checklist
  step 1 at the station once.
