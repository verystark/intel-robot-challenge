# Junction submission: the text

> **Superseded by [JUNCTION_SUBMISSION_TEXT_V2.md](JUNCTION_SUBMISSION_TEXT_V2.md)** (pi0.5, measured on the arm).
> Paste from V2. This file's strategy (section 1) and checklists still apply.

Every field of the Junction form, filled out and ready to paste, with the strategy behind it.
The form itself is in [JUNCTION_SUBMISSION_FORM.md](JUNCTION_SUBMISSION_FORM.md); the wider
submission plan (repo cleanup, video, deck) is in [SUBMISSION.md](SUBMISSION.md).

Written 2026-11-14, about 16:30 laptop time. The form closes at about **08:00 Sunday laptop
time** (16:00 UTC). **Status: draft with defaults filled in** (16:45): model SmolVLA-v2-long on the GPU for both stages
(the loop's default), its training data, the grasp area, INT8 numbers measured on the current
inspection model, one plate-swap round. Still `[PLACEHOLDER: …]`: the evaluation results and the
URLs. Section 5 says who fills each one, and from which file.

---

## 1. Strategy

### 1.1 Who reads it, and what they need in the first 3 lines

| Reader | When and how | Needs in the first 3 lines |
|---|---|---|
| **Intel judges**: robotics and edge-AI engineers who know Studio, Anomalib and OpenVINO | Before or after the live demo at our station; they score it | What is learned and what is scripted; that the loop closes on the real arm; that their stack is used on purpose; one measured result |
| **Peer reviewers**: other hackers, in the dashboard's Peer Review | Skimming many entries; probably no live demo; the video maybe with the sound off | In one sentence, what is different about ours; a reason to open the video |
| **Finals audience**, if we get there | The stage; the text is background | One idea: nothing on the table is in a fixed place, and the inspection's verdict is the robot's instruction |

### 1.2 What the text has to achieve

| After reading | The reader should believe |
|---|---|
| The punchline | It's a learned pick-inspect-sort cell that copes with random brick and plate positions, running on one laptop |
| The first paragraph | Nothing is hard-coded: a VLA does picking and placing, Anomalib checks every brick, and the two are connected through language. All inference is local, with OpenVINO |
| The whole description | They measured it honestly (failures counted, limits named), the data work is careful, and each Intel device was chosen by measurement |

**Text, video and live demo do different jobs.** The video proves it works (one uncut take). The
live demo lets judges set the table themselves. The text carries what neither can show for long:
the method, the data checks, the per-stage evaluation and the device measurements. It points to
the video instead of retelling it.

### 1.3 Positioning

What we lead with, in this order:

1. **Generalised, learned pick and place.** A variable number of bricks at random positions and
   rotations, plates that can stand anywhere within reach, and no coordinates in our code. A
   setup that replays a recorded motion only works for one object in one place.
2. **The defect check is in the loop, through language.** Anomalib's verdict becomes the VLA's next
   task sentence, so the same policy sorts by what inspection found.
3. **Evidence instead of adjectives:** a coverage map of the training data, random layouts drawn by
   a script, results per stage with failures listed, latency per model and device.
4. **The Intel stack used deliberately:** SmolVLA on the GPU, ACT on the NPU (if used), PatchCore
   on the GPU while no policy runs, weight-only INT8, Anomalib trained on the Intel GPU.

We state what ours does and never compare by name or put other teams down.

### 1.4 How each judging criterion is covered

Two rubrics exist (GUIDE.md §2, DEMO_DAY.md §3); the text covers both.

| PDF rubric | Pts | Where in the description |
|---|---|---|
| End-to-end physical AI solution | 25 | Opening paragraph; "One cycle"; "Evaluation" |
| Defect detection with Anomalib, and how its result reaches the robot | 20 | "One cycle" steps 2–3 (the verdict becomes the task sentence); "Why inspection is scripted" |
| VLA and Physical AI Studio | 20 | "One cycle"; "Data" (recorded, cleaned and trained in Studio) |
| OpenVINO and Core Ultra (CPU / GPU / NPU) | 20 | "On the laptop" |
| Robot execution and reliability, recovery from uncertain detections | 10 | "Safety and recovery"; the second look on unsure views |
| Innovation and clarity | 5 | Opening; the video link |

| JUNCTION2026.md rubric | Pts | Where in the description |
|---|---|---|
| Task success rate (accuracy, cycle time, robustness to shifted objects and clutter) | 25 | "Evaluation" (random layouts, per-stage numbers, cycle time) |
| Intel tech integration | 25 | "On the laptop"; "Stack" |
| Dataset and pipeline quality | 20 | "Data" |
| System efficiency (latency, thermal headroom, power) | 20 | "On the laptop" |
| Creativity | 10 | The verdict as the task sentence; the coverage map; random layouts |

### 1.5 Risky claims and their fallbacks

These claims aren't measured on the arm yet. The paste text uses the strongest wording (level A).
Before pasting, choose the level that matches the evaluation (VIDEO_PLAN.md §10), and swap in the
fallback sentences from section 3.

| Claim | Measured by | Level A (paste text now) | If it doesn't hold |
|---|---|---|---|
| Picks at random positions | Evaluation rounds (`tools/random_layout.py`, `tools/eval_round.py`) | "a variable number of bricks at random positions" + rates | B: "random positions inside the area our training data covers" + the rates. D: "stage by stage" |
| Plates anywhere, swapped mid-run | The swap round | "plates that can stand anywhere within reach; swapping them mid-run works" | C: plates moved between rounds only, or kept as during recording |
| Results per stage, cycle time | `round_*_eval.json`, loop logs | Real numbers | Never invented; if too few rounds, say how many |
| ACT pick on the NPU | Which model the filmed take used | "ACT picks on the NPU" | Leave it out; the NPU line becomes a measured option |
| Power and temperature per cycle | `loop/runs/*/cycles.jsonl` (`system`) | Measured values | Leave the sentence out |
| Training size and coverage of the model used | Which model is in the take (SmolVLA-v2 / v2-long on `main-clean2`: 315 episodes; a SmolVLA-v3 on `main-clean4` would be 424) | The placeholders' current values | Update from `video/public/data.json` and a coverage re-run for that dataset |

---

## 2. The fields

### Project name *(required, ≤30)*

```text
Jenssenit
```

**9 of 30 characters**. Already in the draft.

### Punchline *(required, ≤200)*

**Recommended:**

```text
An SO-101 arm clears a table of randomly placed bricks: SmolVLA picks each one, Anomalib checks it, and SmolVLA puts it on the right plate, wherever the plates are. All on one Intel laptop.
```

**189 of 200 characters**. It opens with what is different ("clears a table of randomly placed bricks" says both a
variable count and random positions; "wherever the plates are" says movable plates), names
Anomalib and the VLA for the judges, and ends on local inference.

**Alternative 1 (shorter, leads with "no coordinates"):**

```text
Pick, inspect, sort with no coordinates in the code: SmolVLA handles random brick and plate positions, and Anomalib's verdict becomes its next task sentence. All inference on one Intel laptop.
```

**192 of 200 characters**.

**Alternative 2 (leads with the link through language):**

```text
Anomalib inspects every brick and its verdict becomes the task sentence for SmolVLA, which picks and sorts bricks at random positions onto movable plates. OpenVINO on the laptop's CPU, GPU and NPU.
```

**197 of 200 characters**.

### Description *(required, ≤5000, markdown)*

Paste everything between the outer fences. Use the form's **Preview** once: if it doesn't render
some markdown, the text still reads well as plain text (no tables, on purpose).

````markdown
An SO-101 arm picks, inspects and sorts Duplo bricks with no positions in its code. The number of bricks, where they lie and where the two plates stand change from run to run. A vision-language-action model (SmolVLA) does the picking and placing; Anomalib checks every brick, and its verdict becomes the VLA's next task sentence. All inference runs on one Intel Core Ultra laptop with OpenVINO.

**Result:** [PLACEHOLDER: E] of [PLACEHOLDER: M] bricks correct end to end over [PLACEHOLDER: R] random layouts, median [PLACEHOLDER: X] s per brick. Failures are listed below.

### One cycle

1. **Pick (learned).** SmolVLA gets the top and wrist cameras, the joint positions and the sentence "Pick up the brick." It picks one of the bricks on the table, wherever it lies.
2. **Inspect (scripted).** The arm holds the brick at one fixed pose in front of a webcam and turns it to 90° and −90°, the two faces no gripper finger covers. Anomalib PatchCore scores each view (median of 3 frames) and draws a heatmap. A defective view rejects the brick; an unsure view gets a second look, and a brick that stays unsure is rejected.
3. **Sort (learned).** The verdict becomes the task sentence: "The brick is good. Put it on the green plate." or "The brick is defective. Put it on the orange plate." The same SmolVLA finds the plate of that colour, wherever it stands.
4. Repeat until the table is empty. Nobody chooses anything during a run.

**Why inspection is scripted:** an anomaly model flags anything unlike its training photos. When our photos were taken at varying arm poses, it rejected good bricks. A fixed pose shows it every brick the same way.

### Data

- We recorded 501 episodes by teleoperation in Physical AI Studio and never edit the raw set. The cleaned set has 486 episodes; all 242 sort labels were checked against the top camera (which plate the brick landed on) and were correct.
- The model used here, SmolVLA-v2-long, was fine-tuned on 315 episodes: 158 picks and 157 sorts (20,757 steps, final weights). An episode is one pick or one sort.
- Bricks and plates were moved while recording. By forward kinematics, the grasps in that training data cover about 32 × 40 cm in front of the arm, and both plates appear on both sides of the table.
- Studio keeps the lowest-validation-loss epoch, which once shipped an undertrained epoch-3 model. We train with no validation split and keep the final weights; SmolVLA-v2, trained so on 3× the data, was under half as jerky offline.

### Evaluation

[PLACEHOLDER: R] rounds of 6 bricks, 4 good and 2 with marker defects. A script drew brick positions, rotations and plate positions at random inside the area the training data covers; in one round a person swapped the plates mid-run.

- Pick, first try: [PLACEHOLDER: P] / [PLACEHOLDER: M]
- Inspection verdict correct: [PLACEHOLDER: I] / [PLACEHOLDER: M]
- Placed on the plate it was told: [PLACEHOLDER: S] / [PLACEHOLDER: M]
- Correct end to end: [PLACEHOLDER: E] / [PLACEHOLDER: M]
- Failures: [PLACEHOLDER: one line per failure]

### On the laptop (Core Ultra X9 388H, OpenVINO)

- SmolVLA: 214 ms per 50-action chunk on the GPU, against 833 ms before the next chunk is due (asynchronous execution). It doesn't compile for the NPU; on the CPU it takes 4.8 s.
- ACT, a pick-only alternative: 17 ms per 100-action chunk on the NPU, 15 ms on the GPU, 218 ms on the CPU.
- Anomalib PatchCore: 18 ms per view on the GPU, 56 ms on the CPU, 184 ms on the NPU. It runs on the GPU because no policy runs during inspection.
- Weight-only INT8 makes the PatchCore model 4× smaller (29 to 7.4 MB), with scores within 0.05 of FP32 on 47 held-out and defect photos. Full INT8 moved scores by up to 0.28, so we don't use it.
- PatchCore trains on the laptop's Intel GPU: 2.7 min for the slowest step, 12 to 17 min on the CPU.
- The loop logs package temperature and CPU, GPU and NPU load every cycle. Under sustained load the package reached 90 to 97 °C.

### Safety and recovery

Every policy step is clamped, from 2 joint units per tick at a stage's start up to 12 after one second. Stages time out, one key stops the arm, and a device lock keeps two programs from driving it.

### Limits

- Picks far from the training data fail more often: offline, 8 of 13 picks at unseen positions headed the right way. [PLACEHOLDER: what the evaluation showed]
- The soft gripper reads the same holding a brick or not, so an empty grasp is only caught at inspection.

### Stack

Physical AI Studio (recording, training on Modal, OpenVINO export), SmolVLA, ACT, Anomalib 2.7 (PatchCore), OpenVINO on CPU, GPU and NPU, the OpenVINO Physical AI runtime, SO-101 arm, RealSense D415, wrist camera, webcam.

Video: [PLACEHOLDER: video URL] · Unedited take: [PLACEHOLDER: unedited take URL] · Code: [PLACEHOLDER: repo URL] · Live: [PLACEHOLDER: table from the dashboard's Tables page]
````

**4861 of 5000 characters** with the placeholders as written; about 4246 once they hold short numbers, so there is room for the failure lines and links. Notes on the choices:
- The claim is in the first 3 lines; a skimmer can stop there.
- Lists instead of tables, so it reads well even if the form's markdown is limited.
- Every number is from the repo (section 4 lists the source of each); unmeasured ones are placeholders.
- No em dashes, no slogans, failures and limits included.

### Challenge picker *(required)*

```text
Stop Simulating, Start Moving: See It. Detect It. Act on It. The Intel Physical AI Challenge (Ignite Next x Intel)
```

Pick the entry with that name (it may be shortened to "Intel Physical AI Challenge" in the list).

### Project demo

```text
[PLACEHOLDER: video URL]
```

For a hardware project, "experienced" means the video. Use the same YouTube link as **Video** (or
the public repo's README, if that page plays the video). Mention the live demo table in the
description's last line instead.

### Source code

```text
[PLACEHOLDER: public repo URL]
```

The current repo is private (anonymous requests get 404) and its history holds the station's IP,
an SSH key and Intel's slides. Publish a clean copy first ([SUBMISSION.md](SUBMISSION.md) §4).

### Video

```text
[PLACEHOLDER: YouTube URL, unlisted]
```

The edited video (about 2 min, [VIDEO_PLAN.md](VIDEO_PLAN.md)). Check that it plays in a private
browser window.

### Other link

```text
[PLACEHOLDER: unedited take URL]
```

The full unedited evaluation round, uploaded as a second unlisted video (VIDEO_PLAN.md §5.4). It
lets a doubting judge watch every second. This replaces the earlier idea of linking
`bench/RESULTS.md` (SUBMISSION.md §1): the measurements are already in the description and the repo.

### Presentation *(PDF, ≤20 MB)*

```text
video/out/jenssenit_deck.pdf
```

Built from the video project (the deck plan is in SUBMISSION.md §6). Re-render it after the
evaluation numbers are in, and check its size: `ls -la video/out/jenssenit_deck.pdf`.

### Tech challenge participation

The list isn't known yet: open the dropdown. Tick a tech challenge only if:
- we really use that technology in the project (candidates: Intel OpenVINO, Physical AI Studio,
  Anomalib, Modal for training, Hugging Face for SmolVLA's base weights);
- and we meet that challenge's own rules (read them in the dashboard's Challenges page).

Don't tick anything we only touched in passing.

---

## 3. Fallback sentences (not for pasting as they are)

Swap these in when a level A claim doesn't hold (section 1.5).

| Where | Level A text | Fallback |
|---|---|---|
| Punchline (recommended) | "picks a variable number of randomly placed bricks" | B: "picks bricks at random positions inside its training area" |
| Punchline | "wherever the plates are" | C: "on the right plate" |
| Description, opening | "where the two plates stand change from run to run" | C: "and where the plates stand change between rounds" (if swaps failed), or drop the plate clause (if plates stayed as during recording) |
| Description, step 3 | "finds the plate of that colour, wherever it stands" | C: "finds the plate of that colour" |
| Description, Evaluation | "in [n] rounds a person swapped the plates mid-run" | C: "A mid-run plate swap worked [n] of [m] times." or drop the sentence |
| Description, Evaluation | the random-layout sentence | B: add "Positions outside that area fail more often: [numbers from `--outside` rounds]." |
| Description, whole | — | D (no full loop on the arm): replace "Result" with "Status: pick, inspection and sort each run on the arm; the full loop ran in simulation." and say what's missing |
| Description, step 1 | the ACT placeholder | Drop it if ACT isn't used in the filmed take |

---

## 4. Where each number comes from

| Number in the text | Source |
|---|---|
| 501 raw / 486 cleaned episodes, 53.6 min, 242 of 242 sort labels correct | DATASET_MAIN_CLEAN3.md (the full cleaned set, `main-clean3`; a data-pipeline fact, not the model's training size) |
| Model used, now SmolVLA-v2 (or v2-long), both on `main-clean2`: 315 episodes, 158 picks, 157 sorts (82 green, 75 orange) | Studio's DB, MODEL_RUN_NOTES.md; `video/public/data.json` `numbers.EPISODES` / `PICKS` / `SORTS` |
| Grasp area about 32 × 40 cm (x 6.6 to 38.5 cm, y −14.9 to 24.7 cm, 155 grasps); releases left/right of the centre line: green 54/28, orange 39/36 | `video/scripts/coverage.py` on `main-clean2`, as re-run by the main thread. Re-run it for the dataset of the model actually used |
| Epoch-3 model; jerk more than halved (19.6 → 8.5, shoulder_lift, 99th percentile) | MODEL_RUN_NOTES.md |
| 8 of 13 unseen picks | MODEL_RUN_NOTES.md (ACT-pick-v1 offline test table, SmolVLA-v2 column) |
| 214 ms, 3.8× headroom, 4.8 s CPU, NPU won't compile; ACT 17 / 15 / 218 ms; PatchCore 18 / 56 / 184 ms | bench/RESULTS.md (13:23 and 13:29, measured on a busy laptop) |
| INT8 about 4× smaller, within 0.06 (**to re-measure**: measured at 13:29, before the inspection model was retrained at 14:24); full INT8 up to 0.28 | bench/RESULTS.md, WORK_LOG.md |
| 2.7 min vs 12–17 min training | CLAUDE.md, WORK_LOG.md |
| Wrist stops 0° / 90° / 180°, median of 3 frames, second look | loop/cell_config.json (`show`), CLAUDE.md |
| Clamp 2 → 12 units per tick | loop/cell_config.json, CLAUDE.md |

---

## 5. Checklists

### Before pasting

- [ ] Every `[PLACEHOLDER: …]` replaced, or its sentence removed. Search the pasted text for `PLACEHOLDER`.
- [ ] The claims match the level chosen in VIDEO_PLAN.md §10 (A–D); fallbacks from section 3 swapped in where needed.
- [ ] The pick model and device in "One cycle" match the filmed take (`loop/cell_config.json`).
- [ ] "The model used here" names the model that ran in the evaluation, and its dataset.
- [ ] Benchmarks re-run on a quiet laptop (`bench/policy_bench.py`, `bench/anomaly_bench.py`, `python3 bench/make_table.py`); if a number changed, update it in "On the laptop".
- [ ] Character counts re-checked after filling in: `python3 -c "import sys; print(len(sys.stdin.read()))" < pasted.txt` (description ≤5000, punchline ≤200).
- [ ] Preview in the form: headings, bullets and bold render, or still read fine as plain text.
- [ ] Every link opened in a private browser window: video, unedited take, repo.
- [ ] The deck PDF is under 20 MB.
- [ ] No em dashes, no slogans, nothing claimed that we didn't measure.
- [ ] Save as draft first; Submit Final before 08:00 laptop time.

### Who fills which placeholder

| Placeholder | From | Who |
|---|---|---|
| R, M, P, I, S, E, failures (swap rounds: filled as "one", per the protocol) | `video/layouts/round_*_eval.json` (written by `tools/eval_round.py`), added up by `python3 video/scripts/build_data.py`, numbers in `video/public/data.json` | Station runs the rounds; Claude reads the totals |
| X (median s per brick) | Loop logs (`loop/runs/*/cycles.jsonl`, `total_s`), via `build_data.py` | Claude |
| Temperature, load | **Filled** with the logged range (90 to 97 °C); add per-cycle numbers from `loop/runs/*/summary.json` if wanted | Claude |
| Model; EPISODES, PICKS, SORTS | **Filled: SmolVLA-v2-long, 315 / 158 / 157.** If the model changes: set it in `video/facts.json` `models`, run `video/scripts/coverage.py`, read `video/public/data.json` `numbers` | Whoever changes the model |
| Grasp area | **Filled: 32 × 40 cm** (`video/scripts/coverage.py`, from the model in `video/facts.json`) | Claude, if the model changes |
| INT8 size ratio and score change | **Filled: 4× (29 to 7.4 MB), within 0.05** on the 16:02 model (`video/scripts/int8_check.py`). Rerun after any retrain | Claude |
| Pick model and device | `loop/cell_config.json` in the filmed take; `video/facts.json` `models` | Station |
| Video and unedited take URLs | YouTube, uploaded as unlisted | Camera / director |
| Repo URL | The new public repo | Whoever publishes it |
| Table | The dashboard's Tables page | Anyone |
| What the evaluation showed (Limits) | The failures list and the coverage map in scene 7 | Claude, after the rounds |
