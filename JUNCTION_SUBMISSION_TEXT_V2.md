# Junction submission: the text, version 2 (ready)

The form fields, rewritten around what ran on the arm on the evening of 2026-11-14. **Ready to
paste**, except the four links in the description's last line and the Video / Source code / Other
link fields, which exist only once the video is uploaded and the public repo is published.

Version 1, [JUNCTION_SUBMISSION_TEXT.md](JUNCTION_SUBMISSION_TEXT.md), stays as it was. Its
strategy (section 1) and the fields that don't change (section 2) still apply.

Numbers frozen at cycle 105 of the 22:43 run (23:34 laptop time). The form closes at about
**08:00 Sunday laptop time** (16:00 UTC).

## What changed from version 1

| | Version 1 (16:45) | Version 2 (this file) |
|---|---|---|
| VLA | SmolVLA-v2-long, 315 episodes | **pi0.5 (`Pi0.5-v2-8gpu`)**, 424 episodes of `main-clean4`, the model the loop ran tonight |
| Inspection | whole camera crop, wrist stops then 0° / 90° / 180° | **only a square around the brick**, stops +90° / -90°, bands GOOD < 0.45, DEFECTIVE > 0.56 |
| Result | placeholders for planned random-layout rounds (none were run: `video/layouts/` has no `round_*_eval.json`) | **measured on the arm**: 52 bricks through the full loop, every verdict checked by eye |
| Laptop numbers | benchmarks of the old 720 px inspection model | the brick-square model, measured tonight: in the loop (GPU) and a short CPU / NPU run |
| Failures | placeholder | listed: missed picks (the top camera moved), 4 false rejects, blue marker near the limit |

The random-layout and plate-swap claims from version 1 are **left out**, because they weren't
measured. Claims follow [the team's tone](JUNCTION_SUBMISSION_TEXT.md#13-positioning): only what
was measured, failures counted, no em dashes.

---

## Project name *(required, ≤30)*

```text
Jenssenit
```

## Punchline *(required, ≤200)*

**Recommended:**

```text
An SO-101 arm picks Duplo bricks with a pi0.5 VLA, Anomalib checks each one, and the verdict becomes the VLA's next instruction: good to the green plate, defective to orange. All on one Intel laptop.
```

**199 of 200 characters.** What is learned, what checks, and how the two connect.

**Alternative 1 (puts the measured result in):**

```text
pi0.5 picks and sorts Duplo bricks on an SO-101 arm. Anomalib scores only the brick, and its verdict becomes the VLA's next task sentence. 48 of 52 verdicts right on the arm, all on one Intel laptop.
```

**199 of 200 characters.**

**Alternative 2 (shorter, names the Intel devices):**

```text
A pi0.5 VLA picks and sorts bricks on an SO-101 arm; Anomalib's verdict on each brick becomes its next task sentence. OpenVINO on one Intel laptop's CPU, GPU and NPU.
```

**166 of 200 characters.**

## Description *(required, ≤5000, markdown)*

Paste everything between the outer fences. No tables inside, on purpose: it reads as plain text
if the form's markdown is limited.

````markdown
An SO-101 arm picks Duplo bricks, shows each one to an inspection camera and sorts it onto a green or an orange plate. A vision-language-action model (pi0.5, fine-tuned in Physical AI Studio) does the picking and placing, with no positions in our code. Anomalib PatchCore checks every brick, and its verdict becomes the VLA's next task sentence. All inference runs on one Intel Core Ultra laptop with OpenVINO.

**Result on the arm (final settings, 2026-11-14):** 52 bricks went through the whole loop. The inspection verdict was right for 48: all 16 defective bricks were rejected and 32 of 36 clean bricks accepted. 52 of 73 pick attempts succeeded (6 more were stopped by the operator). Median 20.4 s per brick. Failures are listed below.

### One cycle

1. **Pick (learned).** pi0.5 gets the top and wrist cameras, the joint positions and "Pick up the brick." Median 7.5 s.
2. **Inspect (scripted).** The arm holds the brick at one fixed pose in front of a webcam and turns the wrist to +90° and -90°, the two faces no gripper finger covers. Each view is the median score of 3 frames. A defective view rejects the brick at once; an unsure view gets a second look, and a brick still unsure is rejected. Median 3.9 s.
3. **Sort (learned).** The verdict becomes the task sentence: "The brick is good. Put it on the green plate." or "The brick is defective. Put it on the orange plate." The same pi0.5 model carries it there. Median 5.7 s.

### Scoring only the brick

Our first live run rejected a clean brick with a score of 1.0. The heatmap was hot on the wrist camera's bracket and a loose brick on the table, not on the brick. The model had scored the whole camera crop. Now each frame is cut to a 360 px square around the brick, found by colour at the tips of the red gripper fingers. The square follows the brick, so photos from any arm pose train the same view: the model learns from 641 photos of good bricks, 72 of them at the scripted pose and the rest from earlier hand-held shots. On 28 held-out photos at the two wrist stops (14 clean, 14 with marker defects) the good and defective scores don't overlap.

### Data

- We recorded by teleoperation in Physical AI Studio. The raw dataset is never edited; we clean copies through Studio's API. In the cleaned set, all 242 sort labels were checked against the top camera (which plate the brick landed on).
- The pick and sort model is pi0.5 fine-tuned on 424 episodes (182 picks, 242 sorts, 45.5 min): 8 H100s on Modal, 4 epochs, 5,116 steps, no validation split. Studio keeps the lowest-validation-loss epoch, which once shipped an undertrained model, so we train without one and keep the final weights.

### On the laptop (Core Ultra, OpenVINO)

- pi0.5: about 240 ms per action chunk on the GPU (median of 125 policy stages on the arm). Asynchronous execution keeps the arm moving while the next chunk is computed.
- PatchCore on the brick square: 35 ms per photo on the GPU in the loop (95th percentile 61 ms), 36 ms on the CPU, 119 ms on the NPU. It runs on the GPU because no policy runs during inspection.
- Weight-only INT8 makes the PatchCore model 4x smaller (31 to 7.9 MB), with scores within 0.05 of FP32 on those 28 photos. Full INT8 moved scores by up to 0.28, so we don't use it.
- PatchCore trains on the laptop's Intel GPU in 5 min (641 photos, 2% coreset).
- The loop logs package temperature and CPU, GPU and NPU load: a 33-minute run averaged 52 °C and peaked at 91 °C.

### Safety and recovery

Every policy step is clamped: 2 joint units per tick at the start of a stage, ramping to 12 within a second. Scripted moves are eased and abort if a joint lags. A stage that doesn't finish in time stops the arm and waits for the operator; one key stops it at any moment, and a device lock keeps two programs from driving it.

### Failures and limits

- 21 of 73 pick attempts missed the brick and timed out. The top camera moved about 20 px after the recordings, and pi0.5 was trained without image augmentation; realigning the camera and training with augmentation are the next steps.
- 4 clean bricks were rejected: a green curved brick (3 times) and a tall yellow brick, shapes our good photos barely contain. Dark marker on blue bricks scored lowest of the defects (0.55 to 0.77); the lowest was rejected only after its second look.
- Only the two ungripped faces are checked.
- The soft gripper reads the same holding a brick or not, so an empty grasp is only caught at inspection.
- The loop logs each verdict and that the sort finished, not where the brick landed.

### Stack

Physical AI Studio (recording, cleaning, training on Modal, OpenVINO export), pi0.5, Anomalib 2.7 (PatchCore), OpenVINO on CPU, GPU and NPU, the OpenVINO Physical AI runtime, SO-101 arm, RealSense D415, wrist camera, webcam.

Video: [PLACEHOLDER: video URL] · Unedited take: [PLACEHOLDER: unedited take URL] · Code: [PLACEHOLDER: repo URL] · Live: [PLACEHOLDER: table]
````

**4928 of 5000 characters** with the link placeholders as written. Real links are usually
a little longer, which leaves about 50 characters. If a link has nowhere to point yet (for example
no table number), delete that item rather than leaving a placeholder. Re-count after filling in:
`python3 -c "import sys; print(len(sys.stdin.read()))" < pasted.txt`

## Challenge picker *(required)*

```text
Stop Simulating, Start Moving: See It. Detect It. Act on It. The Intel Physical AI Challenge (Ignite Next x Intel)
```

It may be shortened to "Intel Physical AI Challenge" in the list.

## Project demo, Source code, Video, Other link, Presentation, Tech challenges

As in version 1 section 2:
- **Project demo / Video:** the unlisted YouTube link of the edited video.
- **Source code:** the clean public copy of the repo (this one is private and its history holds
  the station's IP and an SSH key; see SUBMISSION.md §4).
- **Other link:** the unedited take.
- **Presentation:** `video/out/jenssenit_deck.pdf`, under 20 MB.
- **Tech challenges:** only what we really use: Intel OpenVINO, Physical AI Studio, Anomalib;
  Modal only for training.

The video and the deck were planned around SmolVLA. If they now show the pi0.5 runs, check that the
model name and numbers match this description.

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
| 424 episodes, 182 picks, 242 sorts, 45.5 min | `main-clean4` (`cf96b132…`) `meta/episodes`, 81,867 frames at 30 fps |
| 8 H100s, 4 epochs, 5,116 steps, no validation split | MODEL_RUN_NOTES.md "Pi0.5-v2-8gpu" |
| All 242 sort labels checked | DATASET_MAIN_CLEAN3.md (the cleaned set) |
| 52 °C mean, 91 °C peak over 33 min | `loop/runs/20261114_214941/summary.json` (21:50 to 22:23, same model) |
| Top camera moved about 20 px | table screws in the live top frame vs `main-clean4` episode 0, 22:55; another session measured 19 to 25 px and 2° roll at 22:44 |

## Before pasting

- [ ] Fill in the four links in the description's last line (or delete the ones that don't
  exist), then the Video, Source code and Other link fields. Open each in a private window.
- [ ] Re-count the description after the links are in (≤5000).
- [ ] **Pin the model for the filmed take and the live demo.** `loop/cell_config.json` asks for
  `latest:pi05`, and `Pi0.5-one-8gpu-b` was imported at 23:17, so the next loop start would load
  it. Run with `--model Pi0.5-v2-8gpu` (the model these numbers are for), or re-measure.
- [ ] If the inspection model is retrained before submitting (for the green curved brick), the
  numbers here describe the 21:48 model: re-run the loop and recount, or keep them as they are.
- [ ] Preview in the form, Save Draft, then Submit Final before 08:00.
