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
| `train_export.py` | Trains a PatchCore model on the photos, tests it, and exports it to OpenVINO in `exported_model/` |
| `requirements.txt` | Python dependencies |

`dataset/`, `exported_model/`, `results/` and `.venv/` are git-ignored.

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

```powershell
python capture.py                 # default camera, 400 px box
python capture.py --camera 1      # pick another camera
python capture.py --roi 360       # set box size
```

| Key | Action |
|---|---|
| `g` | save to `dataset/normal` (good bricks, used for training) |
| `t` | save to `dataset/test_normal` (extra good bricks, testing only) |
| `b` | save to `dataset/abnormal` (defective bricks, testing only) |
| `+` / `-` | resize the box |
| `c` | switch camera |
| `q` / Esc | quit (click the window first) — or `Ctrl+C` in the terminal |

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

Missing / next:
- [ ] End-to-end test run (nothing has been trained yet — verify the Anomalib 2.x API works)
- [ ] Live inspection script: camera → same box crop → OpenVINO model → good/defective + heatmap
- [ ] Shared config for box size/position so capture and inspection crop identically
- [ ] Interface that hands the result to the robot loop (Step 6)
- [ ] `--xpu` option to train on the Intel iGPU (`accelerator="auto"` falls back to CPU)
- [ ] Benchmark latency on CPU / iGPU / NPU (Step 7, judged)
- [ ] INT8 quantization with NNCF for faster inference
