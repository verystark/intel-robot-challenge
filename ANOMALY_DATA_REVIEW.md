# Inspection photo review (2026-11-14)

Review of the first Anomalib dataset: 475 photos of good bricks held by the gripper in front of
the inspection webcam, taken around 03:45–04:20 (commit `eb01460`).

## Verdict

The anomaly tools now work end to end (capture → train → OpenVINO export → inference on CPU,
GPU and NPU). **The photos are not ready for the final model.** There are no defective or
test photos yet, so `train_export.py` cannot run on the real set, and a trial run rejected
3 of 15 good bricks (20%) as defective.

## What was fixed

| Problem | Fix |
|---|---|
| The crop box changed size four times during capture (500, 580, 660 and 760 px), so bricks appeared at different scales | All 475 photos re-cut from the full frames at the final box (760 px centred at 1015, 525). `anomaly/recrop.py` does this again whenever the box changes; old crops are backed up in `anomaly/dataset_old_crops/` (git-ignored) |
| `train_export.py` exported a model locked to a batch of two 256×256 images, so it rejected single live crops | Now exports a model that takes one crop at the box size (760×760, RGB). Resize to 256×256 and normalization are inside the model. The script also refuses to train on photos of mixed sizes |

## Trial run

Setup: 100 of the photos for training, 15 other good photos for testing, and 15 photos with fake
marker scribbles drawn on them by code as stand-in defects.

| Result | Value |
|---|---|
| Training + export time | about 3 minutes |
| Fake scribbles flagged | 14 of 15 |
| Good bricks wrongly rejected | 3 of 15 (scores 0.56, 0.51, 0.51; threshold 0.5) |
| Image AUROC / F1 | 0.97 / 0.875 (very noisy with this few test photos: an earlier run on the same data gave AUROC 0.875) |

Real marker defects are smaller than the fake scribbles, and many scribbles landed on the gripper
or background rather than the brick, so real detection will be harder than this.

Inference time per 760×760 crop (FP32, `anomalib.deploy.OpenVINOInferencer`, including pre- and
post-processing):

| Device | Time per crop |
|---|---|
| GPU | 11 ms |
| CPU | 30 ms |
| NPU | 102 ms |

PatchCore belongs on the GPU. Try INT8 and the NPU again later for the optimization score.

## Why good bricks get rejected

1. **Too dark.** Brightness is 24–63 out of 255 even at maximum exposure (33 ms) and gain (16), so
   the images are grainy. The photos were taken at night; the demo will be in daylight, which will
   look different again.
2. **Every photo is in a different arm pose.** The arm, gripper and their shadow on the backdrop
   change in every photo. In the live loop the arm shows the brick in one pose, so the model is
   learning far more variation than it will ever see.
3. **The orange bowl is at the bottom of the crop.** If the bowls are moved around, every photo
   without it in the same place will look defective.

## What to do next (about 30 minutes)

1. **Lamp:** light the inspection area with a lamp so it dominates the room light. This lowers the
   gain (less grain) and makes day and night look the same.
2. **Fixed show pose:** make "show the brick to the camera" a fixed, saved arm pose that the loop
   moves to after picking. Take every inspection photo in exactly that pose, so only the brick and
   the grasp change between photos.
3. **Tighter box:** raise or shrink the box so it covers the brick and gripper only, without the
   bowl.
4. **Retake:** about 150 good (`g`), about 30 extra good for testing (`t`) and about 30 defective
   (`b`) photos. Use several marker defect types and sizes, on faces the camera can see, and keep
   one defect type out of training as a check that unseen defects are caught.
5. **Train:** `cd anomaly && ../.venv/bin/python train_export.py`

If a model is needed sooner: take the `t` and `b` photos in the current setup and train on what
exists. It will run, but expect false alarms.

## Effect on the robot plan

Holding the brick up to the camera, instead of placing it on an inspection spot, simplifies the
policies:

- **ACT (pick):** pick the brick and lift it. Episodes end with the brick in the gripper.
- **Loop:** moves the arm to the fixed show pose, takes the inspection photo and runs Anomalib.
- **SmolVLA (sort):** episodes start from the show pose with the brick already in the gripper,
  then go to the bowl named in the instruction.
