# Junction submission: final text

**Paste from this file.** Every field is final; there are no placeholders. Numbers are frozen at
cycle 105 of the 22:43 arm run (recounted from the logs at 23:40 laptop time), with the model
`Pi0.5-v2-8gpu`. The form closes at about **08:00 Sunday laptop time** (16:00 UTC).

It combines [JUNCTION_SUBMISSION_TEXT_V2.md](JUNCTION_SUBMISSION_TEXT_V2.md) (the measured arm
results) with the team's main point: no positions in the code, bricks anywhere in reach, and
plates that can be moved or swapped. That point rests on the method (the sentence names the plate
by colour) and on the training data (each plate on both sides of the table). No separate on-arm
plate-swap count is claimed. The deck and the video read the same numbers from
`video/facts.json`.

---

## Project name

```text
Jenssenit
```

## Punchline (194 of 200)

```text
A pi0.5 VLA picks and sorts Duplo bricks onto movable plates with no positions in the code. Anomalib's verdict becomes its next task: 48 of 52 verdicts right on the arm, all on one Intel laptop.
```

Alternatives, if you prefer: capability only (196): *A pi0.5 VLA on an SO-101 arm picks Duplo bricks from anywhere in reach and sorts them onto plates that can be moved. Anomalib checks each brick, and its verdict becomes the VLA's next instruction.* · names both plates (199): *An SO-101 arm picks Duplo bricks with a pi0.5 VLA, Anomalib checks each one, and the verdict becomes the VLA's next instruction: good to the green plate, defective to orange. All on one Intel laptop.*

## Description (4759 of 5000, markdown)

Paste everything between the outer fences.

````markdown
An SO-101 arm picks Duplo bricks, shows each one to an inspection camera and sorts it onto a green or an orange plate. A vision-language-action model (pi0.5, fine-tuned in Physical AI Studio) does the picking and placing, so there are no positions in our code: the bricks can lie anywhere in reach, and the plates can be moved or swapped, because the task sentence names the plate by its colour. Anomalib PatchCore checks every brick, and its verdict becomes the VLA's next task sentence. All inference runs on one Intel Core Ultra laptop with OpenVINO.

**Result on the arm (final settings, 2026-11-14):** 52 bricks went through the whole loop. The inspection verdict was right for 48: all 16 defective bricks were rejected and 32 of 36 clean bricks accepted. 52 of 73 pick attempts succeeded (6 more were stopped by the operator). Median 20.4 s per brick.

### One cycle

1. **Pick (learned).** pi0.5 gets the top and wrist cameras, the joint positions and "Pick up the brick." Median 7.5 s.
2. **Inspect (scripted).** The arm holds the brick at one fixed pose in front of a webcam and turns the wrist to +90° and -90°, the two faces no gripper finger covers. Each view is the median score of 3 frames. A defective view rejects the brick; an unsure view gets a second look, and a brick still unsure is rejected. Median 3.9 s.
3. **Sort (learned).** The verdict becomes the task sentence: "The brick is good. Put it on the green plate." or "The brick is defective. Put it on the orange plate." The same pi0.5 model finds that plate. Median 5.7 s.

### Scoring only the brick

Our first live run rejected a clean brick with a score of 1.0. The heatmap was hot on the wrist camera's bracket and a loose brick: the model had scored the whole crop. Now each frame is cut to a 360 px square around the brick, found by colour at the tips of the red gripper fingers, so photos from any arm pose train the same view. It learns from 641 good-brick photos. On 28 held-out photos at the two wrist stops (14 clean, 14 with marker defects) the good and defective scores don't overlap.

### Data

- Recorded by teleoperation in Physical AI Studio. The raw dataset is never edited; we clean copies through Studio's API. All 242 sort labels were checked against the top camera (which plate the brick landed on).
- The model is pi0.5 fine-tuned on 424 episodes (182 picks, 242 sorts, 45.5 min): 8 H100s on Modal, 4 epochs, 5,116 steps. Studio keeps the lowest-validation-loss epoch, which once shipped an undertrained model, so we train without a validation split and keep the final weights.
- Bricks and plates were moved while recording. By forward kinematics, the grasps cover about 34 × 40 cm, and each plate stood on both sides of the table (green 84 left / 45 right, orange 51 / 62).

### On the laptop (Core Ultra, OpenVINO)

- pi0.5: about 240 ms per action chunk on the GPU (median of 125 stages on the arm). Asynchronous execution keeps the arm moving while the next chunk is computed.
- PatchCore on the brick square: 35 ms per photo on the GPU in the loop (95th percentile 61 ms), 36 ms on the CPU, 119 ms on the NPU. It uses the GPU while no policy runs.
- Weight-only INT8 makes the PatchCore model 4x smaller (31 to 7.9 MB), with scores within 0.05 of FP32. Full INT8 moved scores by up to 0.28, so we don't use it.
- PatchCore trains on the laptop's Intel GPU in 5 min.
- The loop logs package temperature and CPU, GPU and NPU load: a 33-minute run averaged 52 °C and peaked at 91 °C.

### Safety and recovery

Every policy step is clamped: 2 joint units per tick at the start of a stage, ramping to 12 within a second. Scripted moves are eased and abort if a joint lags. A stage that times out stops the arm for the operator; one key stops it at any time, and a device lock keeps two programs off it.

### Failures and limits

- 21 of 73 pick attempts missed the brick and timed out. The top camera moved about 20 px after the recordings, and pi0.5 was trained without image augmentation; realigning the camera and training with augmentation are the next steps.
- 4 clean bricks were rejected: a green curved brick (3 times) and a tall yellow brick, shapes our good photos barely contain. Dark marker on blue bricks scored lowest of the defects (0.55 to 0.77); the lowest was rejected only after its second look.
- Only the two ungripped faces are checked, and the soft gripper reads the same holding a brick or not, so an empty grasp is only caught at inspection.
- The loop logs each verdict and that the sort finished, not where the brick landed.

### Stack

Physical AI Studio (recording, cleaning, Modal training, OpenVINO export), pi0.5, Anomalib 2.7, OpenVINO on CPU, GPU and NPU, the OpenVINO Physical AI runtime, SO-101, RealSense D415, two webcams.
````

## Challenge

```text
Stop Simulating, Start Moving: See It. Detect It. Act on It. The Intel Physical AI Challenge
```

It may appear as "Intel Physical AI Challenge" in the list.

## The other fields

| Field | Final entry |
|---|---|
| Project demo | Leave empty. The demo is live at our station; there's no public page for it |
| Source code | Leave empty unless the repo is public. The team repo is private, and its git history holds the station's IP and an SSH key. If you publish a clean copy (SUBMISSION.md §4), paste that URL |
| Video | The unlisted YouTube link of `video/out/jenssenit.mp4` once it's uploaded; leave empty if it isn't |
| Other link | Leave empty |
| Presentation | Upload `video/out/jenssenit_deck.pdf` (about 3 MB, the limit is 20 MB) |
| Tech challenge participation | Tick only challenges for technology we really use: Intel OpenVINO, Physical AI Studio, Anomalib. Modal was only used for training |

---

## Where each number comes from

| Number | Source |
|---|---|
| 52 bricks, 48 verdicts right, 16 of 16 defective rejected, 32 of 36 clean accepted | `loop/runs/20261114_222338/` (all cycles) and `20261114_224325/` (cycles 1 to 105): `cycles.jsonl` plus the `c*_90deg.jpg` / `c*_-90deg.jpg` photos, every inspected brick labelled by eye. Both runs used the 21:48 model and the 0.45 / 0.56 bands (`config.json`) |
| 4 false rejects | cycles 36, 47 and 94 (green curved brick) and 59 (tall yellow brick) of `20261114_224325` |
| Blue marker 0.55 to 0.77 | worst view of cycles 28, 46, 66, 74, 83 of `20261114_224325` and cycle 4 of `20261114_222338`; cycle 66 (0.55) was rejected after its second look |
| 52 of 73 picks (21 timeouts; 6 stopped by the operator, not counted) | `pick.result` in the same cycles |
| Median 20.4 s per brick; pick 7.5 s, inspect 3.9 s, sort 5.7 s | `total_s`, `pick.s`, `inspect_s`, `sort.s` of the 52 inspected cycles |
| About 240 ms per pi0.5 chunk on the GPU | median of the per-stage `inference_ms.median` over 125 pick and sort stages (237 ms) |
| PatchCore 35 ms (p95 61) on the GPU | `inspect.anomaly_ms`, 267 photos |
| 36 ms CPU, 119 ms NPU | short run of `anomaly/detector.py` on the 28 test photos at 23:35, **while the loop was running** (re-run on a quiet laptop with `bench/anomaly_bench.py` if there's time) |
| INT8 31 to 7.9 MB, within 0.05 (max 0.052, mean 0.016) | `anomaly/exported_model*/weights/openvino/model.bin`; FP32 vs INT8 on the 28 photos, CPU, 23:35 |
| Full INT8 up to 0.28 | bench/RESULTS.md, WORK_LOG.md (an older model; the reason we never used it) |
| 641 good photos, 72 at the scripted pose; 28 held-out photos (14 / 14) don't overlap | `anomaly/dataset_brick/`, `anomaly/dataset_show/`; `calibrate_bands.py` on the ±90° photos only (lowest defective 0.588, highest good 0.491); `anomaly/README.md` "Scoring only the brick" |
| First live run rejected a clean brick at 1.0 | `loop/runs/20261114_201611/c001_90deg_heat.jpg` |
| Training 5 min, 2% coreset | `train_export.py --dataset dataset_brick --roi --int8 --coreset 0.02`, 21:44 to 21:49 |
| Grasps over about 34 × 40 cm; each plate on both sides (green 84 left / 45 right, orange 51 / 62) | `video/scripts/coverage.py` on `main-clean4` (forward kinematics, ± a few cm); `video/public/coverage.json` |
| 424 episodes, 182 picks, 242 sorts, 45.5 min | `main-clean4` (`cf96b132…`) `meta/episodes`, 81,867 frames at 30 fps |
| 8 H100s, 4 epochs, 5,116 steps, no validation split | MODEL_RUN_NOTES.md "Pi0.5-v2-8gpu" |
| All 242 sort labels checked | DATASET_MAIN_CLEAN3.md (the cleaned set) |
| 52 °C mean, 91 °C peak over 33 min | `loop/runs/20261114_214941/summary.json` (21:50 to 22:23, same model) |
| Top camera moved about 20 px | table screws in the live top frame vs `main-clean4` episode 0, 22:55; another session measured 19 to 25 px and 2° roll at 22:44 |

## Before you press Submit Final

- [ ] **The live demo and any filmed take use the same model as these numbers:**
  `loop/run_cell.py --model Pi0.5-v2-8gpu`. `latest:pi05` would load `Pi0.5-one-8gpu-b`
  (imported 23:17, not measured).
- [ ] Preview in the form: headings, bullets and bold render, or still read fine as plain text.
- [ ] Save Draft, then Submit Final before 08:00 laptop time.
