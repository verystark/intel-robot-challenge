# Plan to the demo, and the show

Written 2026-11-14 at 14:30 laptop time, from the repo docs, Studio's database, the inspection
photos and `loop/runs/`. It says where we stand, what to do next, in order, and how the demo
should run.

**Clock:** the laptop is set to US Pacific time. Junction (Finland) is 10 h ahead: 14:30 on the
laptop is 00:30 Sunday local time. All times in this file and in the other repo docs are laptop time.
Studio's database stores UTC.

---

## 1. Where we stand

### Done

| Area | State |
|---|---|
| Data | 501 raw episodes in `main` (never edited) → `main-clean3`: 486 episodes. Every sort label (242) and every pick (244) checked ([DATASET_MAIN_CLEAN3.md](DATASET_MAIN_CLEAN3.md)). `main-clean4`: 424, without the 62 picks that end at home |
| Policies | `SmolVLA-v2` (final checkpoint, half as jerky as v1 offline). `ACT-pick-v1` (17 ms on the NPU) |
| Loop | `loop/run_cell.py`, demo screen, show tool, benchmarks: built, tested in simulation only |
| Inspection | Anomalib retrained at 14:24 on the moved crop box. 25 real marker defects exist |

### Gaps

1. **The loop has never run on the arm.** Every run in `loop/runs/` is a simulation.
   `loop/poses.json` doesn't exist: the show pose was never saved.
2. **No model has run on the arm since v1.** `SmolVLA-v2` was only tested offline.
3. **The inspection photos don't match what the loop will see:**
   - The 189 good photos were taken around 07:00, steered by hand to many different poses.
     None are at the show pose.
   - The 25 defect photos were taken at 14:06 with focus 312; the good ones with focus 360.
   - Several defect photos are motion-blurred.
   - So the model may learn pose, focus or blur instead of the marker. Bands calibrated on
     these photos would look better than the live result.
   - `anomaly/bands.json` is missing; the loop uses the default 0.4 / 0.6.
4. **No SmolVLA has trained on the biggest data.** Only Pi0.5 uses `main-clean3`. Offline, new
   brick positions are the weak spot (8 of 13 unseen picks head the right way). More data fixes that.
5. **Not committed:** the retrained Anomalib model, the re-cut photos, the focus change in
   `anomaly/camera_config.json`.

### Cloud jobs (14:30)

| Job | Data | Status | What to do |
|---|---|---|---|
| `SmolVLA-v2-long` | `main-clean2`, 11 epochs, validation 0 | 91%; on the laptop about 15:00 | Test it when it lands (section 2, step 7) |
| `Pi0.5` | `main-clean3`, 5 epochs, batch 8, **validation 0.1** | 23%; about 5 h to go | Validation 0.1 makes Studio export the "best" epoch, the problem that ruined v1. A 3B model on the laptop GPU likely can't compute a chunk inside the 833 ms budget; not measured. Don't plan the demo on it |
| `Pi0.5-smoke-2gpu-c` | `main-clean4`, 2×H100 | Running after 2 failed tries | Training infrastructure, not the demo. Time-box it |

---

## 2. Critical path

Steps 1–5 need someone at the station with the follower's 12 V plug in reach. **Nothing that moves
the arm runs until that person confirms the workspace is clear.** Step 6 runs in parallel.

```bash
cd ~/intel-robot-challenge
PY=physical-ai-studio/application/backend/.venv/bin/python
```

### Step 1: free the devices

Close `capture.py` (it was open at 14:30), `inspect_live.py`, and every Studio session or robot
page that uses the follower. Studio itself can keep running.

### Step 2: show pose

| # | Command | Moves the arm? | Check |
|---|---|---|---|
| a | `$PY loop/run_cell.py --sim --replay --cycles 2` | No | The window shows both stages, photos, heatmaps, timings |
| b | `$PY loop/show_tool.py where` | No | Joint values look sane |
| c | Teleoperate a held brick into the middle of the inspection box in Studio, `wrist_roll` at least ~6 units from 0, close the session, then `$PY loop/show_tool.py save` | No | Pose saved; it says whether 180° fits |
| d | `$PY loop/show_tool.py goto` | **Yes**, slowly | Arrives at the show pose |
| e | `$PY loop/show_tool.py test-turn` | **Yes** | Wrist turns 180° and 90° and back; the wrist-camera cable doesn't pull |

### Step 3: new inspection photos at the show pose

The old photos must not be trained on any more. Move them aside first (both folders, so `recrop.py`
still matches crops to frames):

```bash
cd ~/intel-robot-challenge/anomaly
mkdir -p old_teleop_pose
mv dataset old_teleop_pose/dataset && mv dataset_full old_teleop_pose/dataset_full
```

Then collect. Put a brick in the open jaws and press a key. The arm grips it and takes one photo
at each wrist stop in `loop/cell_config.json` (`show.stops_deg`, now 0°, 90° and 180°), the
same stops the loop uses:

```bash
cd ~/intel-robot-challenge
$PY loop/show_tool.py collect
```

| Key | Folder | How many | Which bricks |
|---|---|---|---|
| `g` | `normal` | ~60 photos (~20 grips) | 10+ good bricks, every colour, 2×2 and 2×4, each gripped twice |
| `t` | `test_normal` | ~15 photos (~5 grips) | Good bricks **not** used for `g`, taken last as one block |
| `b` | `abnormal` | ~30 photos (~10 grips) | Marker defects; mostly white, yellow, light blue (marker on red is hard to see) |

Don't change the camera focus during or after this. Then train, calibrate and check:

```bash
cd ~/intel-robot-challenge/anomaly
../.venv/bin/python train_export.py --int8     # about 3 min on the Intel GPU
../.venv/bin/python calibrate_bands.py         # writes bands.json; read the printed table
```

### Step 4: inspection on the arm

`$PY loop/run_cell.py --inspect-only` (**moves the arm**). Press space for each cycle. Try:

- a good brick → GOOD;
- a defective brick → DEFECTIVE;
- an empty gripper → should be DEFECTIVE; write down what it scores.

### Step 5: full cycles

Name the model. `latest:smolvla` changes silently when `SmolVLA-v2-long` lands.

```bash
$PY loop/run_cell.py --model SmolVLA-v2 --cycles 1                                     # hand near Esc
$PY loop/run_cell.py --pick-model ACT-pick-v1 --pick-device NPU --sort-model SmolVLA-v2 --cycles 1
$PY loop/run_cell.py --model SmolVLA-v2 --cycles 10                                    # count correct sorts
```

Write each 10-cycle result as "sorted correctly N of M" in the table in section 4.

Once single cycles work, switch to the **random-position rounds** in
[VIDEO_PLAN.md](VIDEO_PLAN.md) §3: 6 bricks and the plates placed by a random draw
(`python3 tools/random_layout.py`), one plate swap, every round filmed, and each cycle recorded
with `python3 tools/eval_round.py`. Those numbers go in the video, the form and the demo.

### Step 6 (parallel, cloud): SmolVLA-v3 on `main-clean4`

Not started yet; **needs the team's OK** (about $10). Same request as
[GPU_SCALING.md](GPU_SCALING.md) §6, on one H100 (the proven path). 8 epochs ≈ 20.5k steps at
batch 32. Expected on the laptop about 2 h after submitting (1 h 40 min training, upload, export,
12 min download).

```bash
curl -s -X POST http://localhost:7860/api/jobs:train -H 'Content-Type: application/json' -d '{
  "project_id": "4b65ec52-5559-4023-8a69-bf7e5ae36b8a",
  "dataset_id": "cf96b132-2e62-42e3-8885-9cf5b756a1c0",
  "model_name": "SmolVLA-v3",
  "policy": "smolvla",
  "max_epochs": 8,
  "batch_size": 32,
  "num_workers": "auto",
  "auto_scale_batch_size": false,
  "precision": "bf16-mixed",
  "compile_model": false,
  "image_key_reorder_map": {"top": 0, "wrist": 1},
  "num_cameras": 3,
  "export_backends": ["openvino"],
  "augment_images": true,
  "val_split": 0.0,
  "training_target": "remote",
  "remote_trainer_id": "d9d99f90-6122-4e12-8259-2db895ffc5c0",
  "modal_gpu": "H100"
}'
```

### Step 7: each new model as it lands

Follow [DEMO_DAY.md](DEMO_DAY.md) §4: wait for the export, `bench/policy_bench.py`, a `--sim`
cycle, then 1 and 10 cycles on the arm. **Choose by the 10-cycle count on the arm**, not by
offline numbers.

### Step 8: freeze

- [ ] Commit the working state (stage files by path, never `git add -A`) and tag it, e.g. `demo-v1`.
- [ ] Record a backup video of 5 clean cycles: phone on the arm, plus a screen capture.
- [ ] Re-run both benchmarks on a quiet laptop, then `python3 bench/make_table.py`.
- [ ] Put the chosen models and devices in `loop/cell_config.json` by name, not `latest:`.

---

## 3. The show

Judges will remember one moment, one screen and one number.

### The main point: nothing is in a fixed place

Our edge over a hard-coded setup: **any number of bricks at random positions, and plates that can
be anywhere within reach.** The VLA learned picking and placing; there are no coordinates in the
code. The live demo should let the judges test that themselves:

1. **The judges set the table.** Give them the bricks: "Put them anywhere in the taped area." Ask
   them to move the plates too.
2. **The loop clears the table**, one brick at a time, inspecting each.
3. **Mid-run, a judge swaps the plates.** The next brick still goes to the right colour. Only if
   the swap worked in testing.

How we measure it beforehand, and the fallback if positions or swaps fail:
[VIDEO_PLAN.md](VIDEO_PLAN.md) §3 and §10.

### Second moment: a judge makes the defect

Hand a judge a white brick and a black marker: "Draw a defect, anywhere." The robot picks it up,
the heatmap lights up where they drew, and the screen shows *"The brick is defective. Put it on the
orange plate."* Then the arm sorts it.

That one moment proves three things:

- Anomalib catches a defect it has never seen.
- The verdict reaches the VLA as language.
- The loop runs with nobody choosing anything.

**Only include it if 5 fresh scribbles out of 5 work tonight.** Use white or yellow bricks and a
thick black marker.

### Run of show (about 5 min)

| Time | Beat | What to say | Criterion |
|---|---|---|---|
| 0:00 | Press start. Good brick | "Nobody touches the robot from here." SmolVLA sees the top and wrist cameras, runs on the GPU in N ms per chunk. A script holds the brick at one fixed pose, two views, heatmap, the sentence | End-to-end, VLA |
| 0:45 | The judges set the table and move the plates; the loop clears it | "No coordinates in the code; picking and placing are learned." | Robustness, VLA |
| 1:30 | The judge's defect; a plate swap mid-run (if tested) | Heatmap where they drew → orange plate; the next brick follows the colour | Anomalib, creativity |
| 2:00 | Re-check, if an unsure brick comes up | Second look at the unsure side; "reject when in doubt" | Reliability |
| 2:30 | Hardware on screen | NPU picks (ACT), GPU inspects while the arm is still turning, CPU runs the loop. Device per model chosen by measurement. INT8 Anomalib a quarter of the size. Temperature and power | OpenVINO, efficiency |
| 3:30 | Data story | Raw data never edited, all 242 sort labels checked by script and by eye. The first inspection photos failed because every arm pose differed, so the show pose is scripted | Dataset quality |
| 4:15 | The number | "Sorted correctly N of M, X s per brick." | Task success |
| 4:30 | Questions | Likely questions: [DEMO_DAY.md](DEMO_DAY.md) §5 | |

### Staging

- [ ] A monitor facing the judges, the loop screen full size (`f`).
- [ ] Tape marks for the pick zone and the plates. Big GOOD and DEFECTIVE labels on the plates.
- [ ] **Shield the inspection point.** People crowding the station cast shadows on the backdrop,
      which changes the photos and causes false rejects. Use a cardboard hood, and test with
      people standing where the judges will.
- [ ] Defect bricks and good bricks lined up beside the pick zone, in the order they'll be used.
- [ ] Backup video open in a tab.
- [ ] Laptop on mains, rested before the demo (it reached 97 °C today), other programs closed.
- [ ] Rehearse the full run of show 3 times with a stopwatch.

### Roles

| Role | Job |
|---|---|
| Operator | At the laptop: start, `Esc` to stop, `r` to resume |
| Safety | Hand on the follower's 12 V plug |
| Presenter | Talks, points at the screen, hands the judge the marker |
| Brick handler | Places bricks, clears plates between cycles |

---

## 4. Results so far

| Model(s) | Pick device | Cycles | Sorted correctly | Cycle time | Notes |
|---|---|---|---|---|---|
| | | | | | |

---

## 5. Extra, only after 10 good cycles: re-pick on an empty grab

The gripper can't tell holding from empty, so an empty pick currently "sorts" nothing onto the
orange plate. Train a second PatchCore on ~20 empty-gripper photos at the show pose. If a photo
looks like "empty", send the arm back to pick again instead of sorting. The brief asks for exactly
this: "using the anomaly score to trigger a re-grasp".

---

## 6. Open questions

- [ ] When is the live judging at the station, in laptop time? The Junction form closes at about
      08:00 Sunday laptop time ([JUNCTION_SUBMISSION_FORM.md](JUNCTION_SUBMISSION_FORM.md)); the
      submission and the video are planned in [SUBMISSION.md](SUBMISSION.md).
- [ ] Who is at the station for steps 1–5?
- [ ] Start SmolVLA-v3 on `main-clean4` (about $10)? Keep the Pi0.5 job running?
