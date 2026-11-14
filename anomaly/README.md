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
| `train_export.py` | Trains a PatchCore model on the photos, tests it, and exports it to OpenVINO in `exported_model/` |
| `requirements.txt` | Python dependencies |

`dataset/`, `dataset_full/`, `exported_model/`, `results/` and `.venv/` are git-ignored.

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

How PatchCore works: a pretrained ResNet18 describes each small patch of every good image; PatchCore
stores a memory of these "normal" patches. A new image is scored by how far its patches are from the
nearest normal patch — high distance = anomaly, which also gives a heatmap. One epoch is enough.

## Status

Done:
- [x] Capture tool
- [x] Train + OpenVINO export script
- [x] Shared config for box size/position so capture and inspection crop identically (`camera.py` + `camera_config.json`)
- [x] Locked camera settings and stable camera name on the station laptop

Missing / next:
- [ ] End-to-end test run (nothing has been trained yet — verify the Anomalib 2.x API works)
- [ ] Live inspection script: camera → same box crop → OpenVINO model → good/defective + heatmap (use `camera.open_camera` + `camera.crop_box`)
- [ ] Interface that hands the result to the robot loop (Step 6)
- [ ] `--xpu` option to train on the Intel iGPU (`accelerator="auto"` falls back to CPU)
- [ ] Benchmark latency on CPU / iGPU / NPU (Step 7, judged)
- [ ] INT8 quantization with NNCF for faster inference
