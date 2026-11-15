# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The team repo for the Junction 2026 Intel Physical AI Challenge. An SO-101 arm picks a Duplo brick,
shows it to an inspection webcam, an Anomalib model judges it, and a SmolVLA policy trained in
Physical AI Studio puts it on the "good" or "defective" plate. Everything runs on the Intel Core
Ultra station laptop with OpenVINO.

The repo is mostly team docs plus small Python tools. There is no build, test suite or linter at
the top level. Check a change by running the tool. Most tools need the camera or the arm attached.

`physical-ai-studio/` is a git submodule (branch `junction2026`) with its own `CLAUDE.md` →
`AGENTS.md` (build/test/lint with `prek`, coding standards). Follow those when editing inside it.

## Which doc is current

- `GUIDE.md` has the overall plan: station, Studio setup, recording rules, training settings,
  OpenVINO measurements, fallbacks and troubleshooting (§14).
- `GUIDE2.md` **overrides GUIDE.md §1, 7, 9 and 10.** Showing the brick is scripted, not learned.
  Nobody types in the Task box while recording; the sentences are set afterwards. Bowl and brick
  alternation rules replace `recording/layout.py`, so `layout.py` and `policy/RECORDING.md` are
  out of date for recording.
- **What actually happened differs from both guides.** The team records into the Studio dataset
  `main`, which is raw and never edited, and trains on a cleaned copy, `main-clean`. Neither guide's
  `cell-v1` was used. The real task sentences are in `MODEL_RUN_NOTES.md`: `Pick up the brick.`,
  `The brick is good. Put it on the green plate.` and
  `The brick is defective. Put it on the orange plate.` Code that sets or sends sentences must use
  these strings exactly, including the full stop. Any other wording becomes a new task.
- `DEMO_DAY.md` is the demo-day guide: architecture, how each judging criterion is met, the run
  sheet and what to run when a training run finishes. `loop/README.md` documents the loop and the
  hardware checklist. `bench/RESULTS.md` is generated: run `bench/make_table.py`, don't edit it
  by hand.
- `ANOMALY_DATA_REVIEW.md` explains why the first inspection photos caused false rejects. The arm
  was in a different pose for every photo, which is why the show pose is now scripted.

## Hardware rules

- **Never run anything that moves the follower arm** unless someone at the station has confirmed
  in the chat that the workspace is clear. Never run it over SSH with nobody watching. Read-only
  scripts like `tools/servo_check.py` are fine.
- **Only one program can use a camera or a serial port at a time.** Close Studio's session on the
  arm before running `servo_check.py`, which refuses to run if the port is busy. Close `capture.py`
  before running `inspect_live.py`. The RealSense D415 (`top`) is opened only by Studio. The
  inspection webcam is used only by the `anomaly/` tools and the loop script.
- **Open devices by their stable paths, never by `/dev/ttyACM*` or `/dev/videoN`**, which change
  between boots and replugs:
  - follower arm: `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B3E090516-if00`
  - leader arm: `...5AA9024537-if00`
  - inspection webcam: `/dev/v4l/by-id/usb-Webcam_Webcam_Audio_01.00.00-video-index0`
- **A script that writes servo RAM registers must restore the defaults afterwards:** Goal_Speed
  (address 46) back to 0, Acceleration (41) back to 254. Studio never rewrites Goal_Speed when it
  connects, so a leftover value silently slows a joint down.
- **The SO-101 plugin installed in Studio's backend `.venv` has been edited by hand.**
  `_configure_servos` in `physicalai_so101_plugin/so101.py` now sets P gain 32 (default 16) and
  Acceleration 127. Studio writes these to the servos on every connect, and a `uv sync` in the
  backend reverts the edit.
- Once the inspection setup is locked, leave `anomaly/camera_config.json` and the Studio
  environment `policy-cell` alone.
- `sudopsword.txt` in the repo root is untracked and not ignored by git. Stage files by path and
  never use `git add -A` or `git add .`.

## Python environments

| Environment | Use it for |
|---|---|
| `.venv/` (Python 3.12: Anomalib 2.7, OpenVINO, OpenCV, Intel XPU) | Everything in `anomaly/`. Run from `anomaly/` as `../.venv/bin/python <script>` |
| `physical-ai-studio/application/backend/.venv` (Python 3.13) | Anything that imports `physicalai` or `scservo_sdk`, or uses `lerobot-edit-dataset`: `loop/`, `bench/policy_bench.py`, `tools/servo_check.py`. Its OpenCV is headless (no `imshow`), so windows there use Tk |
| System `python3` | `recording/layout.py`, `bench/sysmon.py`, `bench/make_table.py` (standard library only) |

## Commands

```bash
# Studio: backend on :7860 and UI on :3000 (project "intel"), in two long-running terminals
cd physical-ai-studio/application/backend && uv run --extra xpu physicalai-studio serve
cd physical-ai-studio/application/ui && npm run start

# Servo health check, read-only (close any Studio session that uses the arm first)
physical-ai-studio/application/backend/.venv/bin/python tools/servo_check.py          # follower
physical-ai-studio/application/backend/.venv/bin/python tools/servo_check.py leader

# Anomaly tools (run from anomaly/)
../.venv/bin/python capture.py [--camera <index or by-id path>] [--list-cameras] [--roi <px>]
../.venv/bin/python recrop.py                  # re-cut every crop after the box moves or resizes
../.venv/bin/python train_export.py --int8     # PatchCore on the Intel GPU → exported_model/ (+ _int8/)
../.venv/bin/python calibrate_bands.py         # good / unsure / defective bands → bands.json
../.venv/bin/python inspect_live.py [--device GPU|CPU|NPU] [--unsure 0.4 0.6]

# Loop, show tool and benchmarks (repo root; PY = Studio's backend Python)
PY=physical-ai-studio/application/backend/.venv/bin/python
$PY loop/run_cell.py --sim --replay --cycles 2 --no-window   # end-to-end test, no hardware
$PY loop/show_tool.py where                                  # follower joints, read-only
$PY bench/policy_bench.py                                    # SmolVLA / ACT latency per device
.venv/bin/python bench/anomaly_bench.py                      # Anomalib latency per precision and device
python3 bench/make_table.py                                  # → bench/RESULTS.md
```

There are no unit tests. Check changes to the loop with `run_cell.py --sim --replay --no-window
--save-screens <dir>` (it uses a mock arm, recorded episodes and saved photos), and look at the
saved screens.

If Studio shows `CaptureTimeoutError` or "robot is in use by a runtime session" with nothing
running, restart the backend: Ctrl+C, wait about 30 s, then start it again.

## Architecture

### Inspection (`anomaly/`)

- **`camera.py` decides how every inspection photo is taken.** It opens the webcam, locks its
  controls with `v4l2-ctl` (Linux only, applied in `CONTROL_ORDER` because the automatic modes
  must be off before manual values take effect) and cuts the square box (`crop_box`). Its settings
  live in `camera_config.json`, which `capture.py` writes. Any new code that photographs bricks for
  the model, such as the show tool or the loop, must use `CameraConfig.load()`, `open_camera` and
  `crop_box`. Otherwise its crops won't match the training photos, and Anomalib flags the
  difference as a defect.
- `capture.py` saves each photo twice with the same file name: the crop as
  `dataset/<label>/<stem>.png` and the full frame as `dataset_full/<label>/<stem>.jpg`. The labels
  are `normal`, `test_normal` and `abnormal`. `recrop.py` rebuilds the crops from the full frames
  and backs up the old ones in `dataset_old_crops/` (ignored by git).
- `train_export.py` trains PatchCore (resnet18, `layer2` and `layer3`, one epoch) on the Intel GPU
  through Anomalib's XPU accelerator, falling back to the CPU. The slowest step takes 2.7 min there
  vs 12–17 min on the CPU. It needs `normal` and `test_normal` photos, all the same size;
  `abnormal` is optional. Without it the threshold is the highest held-out good score.
  `test_normal` must be a time block of photos, not a random pick, because burst photos are
  near-duplicates.
- It exports OpenVINO IR to `exported_model/weights/openvino/model.xml` with a fixed input of one
  RGB crop at the box size. The resize to 256×256 and the normalisation happen inside the model.
  The export needs `dynamic_axes: {}`; without it the model only accepts batches of two.
- `--int8` calls `quantize_int8.py`, which does weight-only INT8 (4× smaller, scores within about
  0.06). Full INT8 and Anomalib's own `INT8_PTQ` both fail for this model:
  - full INT8 moved scores by up to 0.28;
  - `INT8_PTQ` calibrates with batches, which the single-crop model rejects.
- `detector.py` runs the exported model with plain OpenVINO in either venv; `inspect_live.py`
  still uses Anomalib's own inferencer.
  - Its scores match Anomalib's inferencer exactly on the CPU; the GPU and NPU differ by up to
    0.004 and 0.047 (16-bit).
  - `calibrate_bands.py` writes the bands to `bands.json` per device. The loop and
    `inspect_live.py` read them.
- **Changing `box_size` means running `recrop.py` and retraining.** `inspect_live.py` refuses to
  start if the model's input size doesn't match the box. Scores are normalised so that 0.5 is the
  model's threshold. The `--unsure` band around it separates GOOD, UNSURE and DEFECTIVE.
- OpenCV windows on Linux don't report Shift, so the tools use digit keys for adjustments.
- Per-crop latency for the current 720×720 model is in `bench/RESULTS.md`. The loop runs it on the
  GPU (18 ms vs 184 ms on the NPU). SmolVLA isn't running while the brick is shown, so the GPU is
  free then. Its scores are also closest to FP32 on the CPU. ACT is the model that suits the NPU.

### Policy (Physical AI Studio)

- Environment `policy-cell` has two cameras: `top` (the RealSense) and `wrist`. When training,
  map `top` → Overview and `wrist` → Gripper. Training runs on Modal. Studio exports each model to
  OpenVINO.
- When running a model, set **Execution → Asynchronous**. In the default Synchronous mode the arm
  pauses about once a second while the next action chunk is computed (about 160 ms on the GPU).
- **Datasets are edited through the backend API on :7860, and only while no recording session has
  the dataset open:**
  - `PATCH /api/dataset/{id}/episodes/{index}` with `{"task": ...}` relabels an episode.
  - `DELETE /api/dataset/{id}/episodes` takes a JSON list of indices. Delete them all in one call,
    because the indices renumber afterwards.
  - The UI shows episode `index` as `E{index+1}`.
  - Episode videos are AV1, so decode them with ffmpeg, not OpenCV.
  - An open recording session keeps its working copy in `~/.local/share/physicalai/cache/<uuid>/`.
- Studio datasets: `main` is raw; `main-clean`, `main-clean2` and `main-clean3` are cleaned copies.
  `main-picks` is pick-only, for ACT. Models: `SmolVLA`, `SmolVLA-v2` and `ACT-pick-v1`. Model
  and dataset rows are in `~/.local/share/physicalai/data/physicalai.db`; read it only with
  `?mode=ro`.

### Closed loop (`loop/`, see `loop/README.md`)

- **How it drives the hardware.** `run_cell.py` runs standalone on physicalai's `RobotRuntime`.
  Studio has no REST call that starts a run.
  - It takes Studio's device lock (`physicalai.robot.transport._lock.acquire_locks`), so the loop
    and a Studio session can't drive the arm together.
  - It reads the follower calibration from Studio's DB.
  - `SwitchSource` hands one runtime to the pick or the sort `PolicySource`. They can be different
    models, e.g. ACT for the pick on the NPU. ACT gets no task, since its manifest has no `task`
    input.
- **Show and inspect are scripted** with `Arm.move_to`: eased, speed-limited, lag-checked moves
  to `poses.json`. `send_action` jumps straight to the target, so never send far targets
  directly.
  - Inspection stops at the wrist angles in `show.stops_deg`, now only `[90]`: at 0° and 180°
    a gripper finger hides the brick. `run_cell.py` turns to the first stop when it isn't 0°.
    `arm.plan_stops` caps the stops at the joint range; `show_tool.py collect` uses the same plan, so training
    photos match.
  - Each stop's score is the median of 3 frames. A defective stop rejects at once; unsure
    stops get one second look.
  - Scripted moves set the gripper to `Cell.grip`, the policy's last commanded value (the
    squeeze), never the measured one.
  - The home pose is `poses.json` `home`, else the median sort-episode start
    (`policy.sort_start_pose`).
- **Stage-end detection** (`StageWatcher`): moved more than 40 units away, back within 45 of the
  start pose, still for 0.5 s. The gripper value can't tell holding from empty with this
  calibration.
- **Safety:**
  - `on_action_ready` clamps every policy step. The clamp starts at 2 units per tick and ramps to
    12 over the first second of each stage.
  - Esc/s sets one stop flag that every move checks.
- **Zero noise:** with `zero_noise`, SmolVLA gets an all-zero `noise` input. Its noise
  preprocessor keeps a supplied input.
- **Simulation:** `--sim` uses a mock arm and replays the sort model's dataset (`SimWorld`,
  frames decoded with ffmpeg).
- `loop/show_tool.py where/save` read servo positions read-only with `scservo_sdk` and the
  driver's `ticks_to_normalized`. Connecting the driver toggles torque, so the arm can sag.
- **Operator screen (`loop/dashboard/`):** `run_cell.py` serves it at http://localhost:8080. It
  binds to 127.0.0.1 and uses only the standard `http.server`.
  - `/` is the ISA-101-style operator screen (`static/hmi/`): grey when normal, colour only for
    alarms. `/modern` is the earlier dark page (`static/index.html`).
  - Alarms and events come from `Cell.ev(prio, tag, msg)`: 1 = red, 2 = amber, 3 = info.
    `/api/ack` acknowledges them.
  - The served page embeds the current state (`<!--STATE-->`), so it is complete from its first
    paint.
  - MJPEG parts are closed by the next boundary right away, and unchanged frames are resent once
    a second. Otherwise a frozen camera never shows.
  - Endpoints: MJPEG camera streams, server-sent events at 5 Hz, and stop / resume / pause /
    mark posts.
  - `telemetry.py` holds what it shows: frames, the joint trace, policy chunks from
    `on_inference`, the live score, history and marks.
  - Between policy runs a camera pump reads the cameras under `cam_lock`, so it and the runtime
    never read one camera at once.
  - `LiveScorer` scores the inspection feed only during SHOW / INSPECT and only when the stop
    scorer is idle.
  - Colours live in `palette.json`, which the video reuses.
  - Check the page with
    `firefox --headless --no-remote --profile ~/snap/firefox/common/<dir> --screenshot <png>`.
    Snap Firefox can't write to /tmp.
- `bench/sysmon.py` reads temperature, NPU busy, GPU busy and battery power without root. RAPL
  needs `sudo chmod o+r .../intel-rapl:0/energy_uj`.

## Team docs

The docs are for teammates working at the station: short sentences, tables and exact commands.
When you finish something, update the status checklist in GUIDE.md §3, or in `anomaly/README.md`
for the inspection tools.
