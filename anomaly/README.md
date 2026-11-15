# Anomaly detection (Anomalib)

Detects defective objects (e.g. Duplo bricks) from a camera image. This is the
**DETECT** step of the challenge pipeline (see `documents/junction2026.md`, Step 4):

```
PERCEIVE ──► DETECT ──► REASON ──► EXECUTE ──► OPTIMIZE
cameras      Anomalib    VLA policy  SO-101      OpenVINO
```

## Files

| File | What it does |
|---|---|
| `capture.py` | Shows the webcam with a green box and saves the area inside it as a photo into `dataset/` |
| `camera.py` | Opens the inspection camera, locks its settings and crops the box. Shared by capture and live inspection |
| `camera_config.json` | Written by `capture.py`: camera, box position/size and locked settings. Live inspection reads it |
| `recrop.py` | Re-cuts all photos from `dataset_full/` with the current box (after moving or resizing it). Backs up the old crops in `dataset_old_crops/`. `--dataset dataset_show` re-cuts the photos from `show_tool.py collect` |
| `old_setup/` | The first 475 good photos (03:47–04:16 on 2026-11-14), taken with the arm reaching down from above in front of a different backdrop. They don't match the current showing pose, so they are kept out of `dataset/` and not trained on |
| `train_export.py` | Trains a PatchCore model on the photos, tests it, and exports it to OpenVINO in `exported_model/` |
| `inspect_live.py` | Live test of the trained model: show a brick to the camera, see GOOD / UNSURE / DEFECTIVE, the anomaly score, a heatmap and the time per check |
| `detector.py` | Runs the exported model with plain OpenVINO (works in Studio's venv too); bands and verdict rule. Used by the loop and the benchmarks |
| `calibrate_bands.py` | Sets the good / unsure / defective bands from `test_normal` and `abnormal` scores on the loop's device, writes `bands.json` |
| `roi.py`, `roi.json` | **Only the brick is scored.** Finds the brick at the red finger tips in every crop and cuts a fixed 360 px square around it. `train_export.py --roi` trains on these squares and copies `roi.json` next to the model; `detector.py` then cuts the same square. See "Scoring only the brick" below |
| `dataset_show/` | Photos at the scripted show pose, from loop runs (0°) and `show_tool.py collect` (±90°). `excluded/` holds takes without a brick |
| `dataset_brick/` | Symlinks: `dataset/` + `dataset_show/` in one set, for training the brick-square model on all photos |
| `quantize_int8.py` | Weight-only INT8 copy of the model in `exported_model_int8/` (4x smaller, scores within ~0.06); `--mode full` for full INT8 (moves scores a lot) |
| `requirements.txt` | Python dependencies |

The photos (`dataset/`, `dataset_full/`) and `exported_model/` are committed so the whole team has them. `dataset_old_crops/`, `results/`, caches and `.venv/` are git-ignored.

## Setup on the station laptop (Linux)

Already done: the repo-root venv `intel-robot-challenge/.venv` has Anomalib 2.7.0 with Intel GPU
support. Run the scripts with it from `anomaly/`:

```bash
cd ~/intel-robot-challenge/anomaly
../.venv/bin/python capture.py
```

## Setup (Windows, one time)

Use Python 3.11 (3.14 is too new for Anomalib/PyTorch). Keep it separate from
Physical AI Studio's environment.

```powershell
cd intel-robot-challenge\anomaly
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If `Activate.ps1` is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 1. Capture photos

```bash
python capture.py                 # camera and box from camera_config.json (station webcam by default)
python capture.py --camera 1      # pick another camera: an index, or a /dev/v4l/by-id/... path on Linux
python capture.py --list-cameras  # show the cameras --camera accepts
python capture.py --roi 360       # set box size
```

On Linux the default camera is the station's 2K webcam, opened by its fixed
`/dev/v4l/by-id/...` name because `/dev/videoN` numbers change between boots.
Exposure, white balance and focus are switched to manual and locked, so photos
don't drift in brightness or colour (Anomalib would flag that drift as defects).
Mains flicker is set to 50 Hz. Every setting and the box are saved to
`camera_config.json`.

| Key | Action |
|---|---|
| `g` | save to `dataset/normal` (good bricks, used for training) |
| `t` | save to `dataset/test_normal` (extra good bricks, testing only) |
| `b` | save to `dataset/abnormal` (defective bricks, testing only) |
| click | move the box to the clicked point |
| `+` / `-` | resize the box |
| `1` / `2` | darker / brighter (exposure up to 33 ms, then gain): aim for brightness 110–150 with ~0% clipped |
| `3` / `4` | colour cooler (bluer) / warmer (more orange): make white paper look white |
| `k` | automatic focus on what is inside the box (put a brick there first) |
| `5` / `6` | focus down / up by hand |

Adjustments use number keys because OpenCV's window on Linux ignores Shift
(`E` arrives as `e`).
| `c` | switch camera (Windows only; on Linux use `--camera`, so the locked settings never land on the wrist camera) |
| `q` / Esc | quit (click the window first) — or `Ctrl+C` in the terminal |

Each photo is also saved as a full frame in `dataset_full/`, so the box can be
moved later and the crops regenerated.

Set the camera up once before the first photo: put a brick on the inspection
spot, click it to centre the box, size the box, press `k`, then adjust brightness
(`1`/`2`) and colour (`3`/`4`). Don't change any of it after you start the dataset.

Targets: ~80–100 `normal`, ~20 `test_normal`, ~20 `abnormal`.

Tips:
- Capture with the **real inspection camera at its final mounted position**, not a laptop webcam.
- Size the box so the brick **fills most of it** with a small margin, then **keep that size fixed**
  for the whole dataset and for live inspection.
- Keep background, lighting and camera height constant. Vary brick rotation/position slightly and
  include every colour/size that counts as "good" — anything missing from `normal` will be flagged.
- Close Studio's camera stream while capturing; only one program can use a camera at a time.
- The real objects/defects are announced at kickoff — capture the final dataset after that.

## 2. Train and export

```powershell
python train_export.py
```

Trains PatchCore (`resnet18`, layers `layer2`+`layer3`, 256×256 input), tests on `abnormal` +
`test_normal`, exports OpenVINO IR to `exported_model/weights/openvino/model.xml`, and prints the
image threshold and test metrics (AUROC, F1).

`abnormal` may be empty. PatchCore learns from good photos only; without defective ones the
threshold becomes the highest score among the held-out good photos and testing is skipped, so
retrain once there are defective photos. `test_normal` must be a block of photos taken at another
time (other bricks, other grips), not a random pick from `normal`: burst photos are near-duplicates
and would make the threshold far too low.

All photos must be the same size (run `recrop.py` if the box changed). The exported model takes
one crop at that size, exactly as `camera.crop_box()` cuts it, as RGB; the resize to 256×256 and
normalization are inside the model. With `anomalib.deploy.OpenVINOInferencer` you pass the RGB
crop as a NumPy array.

Trial run on 2026-11-14 (100 normal photos, fake scribbles as defects): training + export took
about 3 minutes; one crop takes about 11 ms on the GPU, 30 ms on the CPU and 100 ms on the NPU.

## 3. Test the model live

```bash
../.venv/bin/python inspect_live.py                 # GPU (default)
../.venv/bin/python inspect_live.py --device NPU    # or CPU
../.venv/bin/python inspect_live.py --unsure 0.4 0.6
```

Uses the same camera, settings and box as `capture.py` (close `capture.py` first: one program per
camera). Shows the verdict, the anomaly score (0–100 %, 50 % = the model's threshold; the
`--unsure` band in between is UNSURE), a heatmap of where it looks defective (`h`), and ms per
check. `space` freezes the result. It refuses to start if the box size no longer matches the model.
The score is a distance from "normal", not a probability: use it to set the unsure band from
real good and defective bricks.

How PatchCore works: a pretrained ResNet18 describes each small patch of every good image; PatchCore
stores a memory of these "normal" patches. A new image is scored by how far its patches are from the
nearest normal patch — high distance = anomaly, which also gives a heatmap. One epoch is enough.

## Scoring only the brick

The whole box crop also shows the gripper, the wrist camera's orange bracket, the table edge and
bricks lying on the table. Before this, anything new there made the score jump. The first live run
(2026-11-14 20:16) rejected a clean yellow brick with a score of 1.0: the heatmap was hot on the
bracket and a loose brick, not on the brick in the gripper.

Now `roi.json` is `{"mode": "brick", "size": 0.5}`:
- `roi.find_brick` finds the red fingers by colour and takes the brick-coloured pixels near their
  tips. A red or dark brick falls back to a point just inside the tips. A long thin red strip is
  ignored: that's the table edge.
- The model scores a 360 px square centred there. Outside it the heatmap is dimmed, and a white
  outline marks the square, in the saved photos, the operator screen and `inspect_live.py`.
- The square is centred on the brick, not fixed in the frame, so photos from any arm pose train
  the same view. The old hand-held `dataset/` photos are usable again.

Train and calibrate:

```bash
../.venv/bin/python train_export.py --dataset dataset_brick --roi --int8 --coreset 0.02
../.venv/bin/python calibrate_bands.py --dataset dataset_show     # the show pose the loop sees
```

Check the squares when adding photos: a take where the brick fell out goes in `dataset_show/excluded/`.

## Status

Done:
- [x] Score only the brick (`roi.py`, brick mode), trained on `dataset_brick` (2026-11-14)
- [x] Capture tool
- [x] Train + OpenVINO export script
- [x] Shared config for box size/position so capture and inspection crop identically (`camera.py` + `camera_config.json`)
- [x] Locked camera settings and stable camera name on the station laptop

Missing / next:
- [x] End-to-end test run: train, test and OpenVINO export work with Anomalib 2.7 (trial with fake defects)
- [ ] Capture real `abnormal` and `test_normal` photos, then train on the real dataset
- [x] Live inspection script (`inspect_live.py`)
- [x] Train on the Intel GPU (`train_export.py`, default; slowest step 2.7 min vs 12–17 min on CPU)
- [x] Benchmark latency on CPU / iGPU / NPU: `bench/anomaly_bench.py` → `bench/RESULTS.md`
- [x] INT8 with NNCF: `quantize_int8.py` / `train_export.py --int8` (weight-only; full INT8 moved scores up to 0.28)
- [x] Interface to the robot loop: `detector.py` + `bands.json`, used by `loop/run_cell.py`
