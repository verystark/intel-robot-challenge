# Team guide: Intel Physical AI Challenge

How we build the autonomous brick-sorting cell, step by step. Start here; the
detailed tool docs are linked from each section.

Last updated: 2026-11-14, morning. The status in section 3 changes quickly, so update it when you
finish something.

> **Updated plan for recording and running the arm: [GUIDE2.md](GUIDE2.md).** The policy only picks
> and lifts; showing the brick to the camera is scripted; the Task box is never touched while
> recording; bowls follow simple alternation rules. Where GUIDE2.md disagrees with sections 1, 7, 9
> or 10 below, GUIDE2.md wins.

---

## 1. What we're building

```text
HOME ──SmolVLA──▶ SHOWING POSE ──script──▶ photo ──Anomalib──▶ verdict ──script──▶ sentence ──SmolVLA──▶ BOWL ──▶ HOME
     "Pick up the   brick held in          waits until          good /              "The brick is
      brick and     front of the           the arm is still     defective /         defective. Put it
      show it..."   inspection webcam                           unsure              in the orange bowl."
```

1. **Pick and show:** SmolVLA, given "Pick up the brick and show it to the inspection camera.", grabs a
   brick from the pick area and holds it still in front of the inspection webcam.
2. **Inspect:** the loop script waits until the arm stops moving, moves it the last few millimetres to
   the **saved show pose** (exact joint angles, so every photo is taken from the same arm position),
   takes a photo and runs Anomalib: score, heatmap, verdict.
3. **Unsure score (round 2):** the script turns the wrist about 90° by itself and looks again. Still
   unsure → treat as defective (reject when in doubt).
4. **Decide:** the verdict picks the sentence: "The brick is good. Put it in the blue bowl." or
   "The brick is defective. Put it in the orange bowl."
5. **Sort:** the same SmolVLA, now given that sentence, puts the brick in the named bowl and returns
   home. Repeat.

Nobody chooses anything during a run. Everything runs on the laptop with OpenVINO.

**One dataset, one policy.** Everything is recorded into one Studio dataset (`cell-v1`) and trains
one SmolVLA, steered by three sentences.

**Why this design:**

- **The arm holds the brick up instead of putting it down:** one grasp instead of two (no second
  pick-up from a table), a faster cycle, and the wrist can turn to show another side for a re-check.
- **One dataset:** the sort episode starts exactly where the pick episode ended, so recording is one
  continuous flow with no unrecorded setup, and the sort data starts from real grasps. One model to
  train, export, optimise and run.
- **The verdict is in the sentence:** the PDF asks for the defect result to reach the robot policy
  "as a structured signal, label, score", and for the VLA to interpret "the task instruction and
  perception results". Anomalib's verdict visibly changes what the VLA is told.
- **SmolVLA for the grasp too:** the SmolVLA paper reports it beating ACT on SO-100 pick-and-place
  tasks. ACT is much faster to run, so it stays the fallback for the pick (section 12).
- The challenge PDF's "End Goal" slide uses ACT for the pick and SmolVLA for the sort. That's an
  example, not a rule: "How you build the pipeline is up to you" (`JUNCTION2026.md`).

---

## 2. How we're judged

From the challenge PDF (Intel's slides, page 7):

| Criterion | Points | Our answer |
|---|---|---|
| End-to-end physical AI solution: one closed loop, not separate demos | 25 | One script runs pick → inspect → sort in a loop (section 10) |
| Defect detection with Anomalib, including how its result reaches the robot | 20 | PatchCore on the held brick; the verdict goes into SmolVLA's sentence |
| VLA and Physical AI Studio integration | 20 | One SmolVLA trained in Studio does the whole task, steered by sentences that carry the verdict |
| OpenVINO and Core Ultra optimisation (CPU / GPU / NPU) | 20 | Every model in OpenVINO, device chosen by measurement, numbers in a table (section 11) |
| Robot execution and reliability, including recovery from uncertain detections | 10 | Staged data, tested success rates, wrist-turn re-check on unsure scores |
| Innovation and clarity of the demo | 5 | Live screen showing photo, heatmap, score, sentence and timings |

`physical-ai-studio/JUNCTION2026.md` has a different table (task success 25, Intel tech 25, dataset
and pipeline quality 20, system efficiency 20, creativity 10). **Ask a mentor which one the judges
use.** This plan scores under both.

Kickoff rules override this guide. If they say something different, update this file.

---

## 3. Status

**Done**

- [x] Studio runs natively on the laptop with the Intel GPU; the NPU is enabled for OpenVINO.
- [x] Leader and follower arms calibrated.
- [x] Studio environment `policy-cell`: follower controlled by the leader, cameras `top` and `wrist`.
- [x] Anomalib: capture tool, re-crop tool, and the train + OpenVINO export pipeline work
      (trial run: about 3 minutes; one crop takes about 11 ms on the GPU, 30 ms on the CPU, 100 ms on the NPU).
- [x] `recording/layout.py` tells the team what to set up and which sentences to use for each cycle.
- [x] The closed loop `loop/run_cell.py`, its demo screen, and the show tool `loop/show_tool.py` (save / goto /
      test-turn / collect), tested in simulation; the hardware checklist is in [loop/README.md](loop/README.md).
- [x] Benchmarks (`bench/`) and the evidence table `bench/RESULTS.md`; the demo-day guide [DEMO_DAY.md](DEMO_DAY.md).
- [x] Anomalib trains on the Intel GPU, INT8 copy, score bands for the loop (`anomaly/README.md`).

**Blocking: do these first**

- [ ] Connect Modal (section 5). No cloud training is possible until this is done.
- [ ] Set the Hugging Face token in Studio (section 5). SmolVLA needs it.
- [ ] Set up the table and the showing point: tape, backdrop, lamp (section 5).
- [ ] Create the dataset `cell-v1` in `policy-cell` (section 7). Delete the empty `pick-v1` and the old `gtesr`.
- [ ] Set up the inspection camera for the showing pose, then retake the good-brick photos (section 9).
      The current 475 photos show the brick at very different positions and sizes, with the arm's
      shadow moving on the cardboard, so they won't match.

**Then**

- [ ] Stage 1 recording → train SmolVLA → test (sections 7–8).
- [ ] Test the fallback early: export a few episodes, split, re-import (section 12).
- [ ] Anomalib on the photos from the pick episodes (section 9).
- [ ] Save the show pose (section 5) and write the loop script (section 10).
- [ ] Stages 2 and 3, OpenVINO device choice and measurements (section 11).
- [ ] Round 2: wrist-turn re-check, SnapFlow, "collect" mode photos.

---

## 4. The station

| Part | Identity | Used by |
|---|---|---|
| Leader arm | USB serial `5AA9024537` (5 V supply) | Studio, teleoperation |
| Follower arm | USB serial `5B3E090516` (12 V supply) | Studio and the loop script |
| `top` camera | RealSense D415, serial `243722061698`, added in Studio as "RealSense D415" | The policy |
| `wrist` camera | Autodarts DIY Cam on the gripper | The policy |
| Inspection camera | 2K webcam, `/dev/v4l/by-id/usb-Webcam_Webcam_Audio_01.00.00-video-index0` | Anomalib tools and the loop script only |
| Built-in laptop camera | HP 5MP | Ignore |

Leader and follower look identical over USB. Always pick them by serial number; the `ttyACM`
numbers can swap when replugged.

**Studio** (project `intel`, http://localhost:3000). Start it in two terminals:

```bash
# Terminal 1: backend on port 7860
cd ~/intel-robot-challenge/physical-ai-studio/application/backend
uv run --extra xpu physicalai-studio serve

# Terminal 2: UI on port 3000
cd ~/intel-robot-challenge/physical-ai-studio/application/ui
npm run start
```

| Studio item | What it is |
|---|---|
| Environment `policy-cell` | Use this for all recordings. Two cameras only: the policy doesn't need the inspection camera, and fewer cameras run faster. |
| Environment `sorting-cell` | Old, no cameras. Don't use. |
| Dataset `cell-v1` | **The** dataset: all stages, all three sentences (section 7). To create. |
| Datasets `pick-v1`, `gtesr` | Old and empty. Delete. |

**Camera rules**

- Only one program can use a camera at a time.
- The RealSense is opened only by Studio. Never add it as the plain webcam "Intel(R) RealSense(TM) Depth Ca".
- The inspection webcam is used only by `anomaly/capture.py` and the loop script.

Remote access over SSH: see [STATION_SSH.md](STATION_SSH.md). Nothing that moves the arm runs
without someone at the station.

---

## 5. One-time setup still needed

**Modal (cloud GPUs for training)**

1. In a terminal on the laptop, run this. It opens a browser to log in to Modal:
   ```bash
   uvx --python 3.13 --from 'modal[api-proxy-support]>=1.6.3,<2' modal setup
   ```
2. In Studio: **Settings → Training Targets → Modal → Deploy and connect**. The first build takes
   several minutes, so record while it runs.

Each person has $100 of Modal credit. Jobs keep billing even when Studio is closed, and stop after 24 hours.

**Hugging Face token:** create a read-only token at huggingface.co → Settings → Access Tokens, and
paste it into Studio under **Settings → General → Hugging Face**. Never commit it.

**The table**

- **Pick area:** about 15×15 cm in front of the arm, taped as a 3×3 grid. Rows are named by distance
  from the robot's base (near / middle / far); columns as seen in Studio's top camera view
  (left / centre / right).
- **Bowl spots 1–4:** small numbered tape marks, all reachable by the arm, none on the pick area,
  none touching the arm's base, none under the showing point. Spots 1 and 2 are the fixed positions
  for stages 1 and 2.
- **Top camera view:** no cables, bags, phones or people. The leader arm and the person using it
  stay out of view.
- **Lock it down:** if a camera moves after recording, earlier episodes no longer match.

**The showing point** (where the arm holds the brick for the photo)

- **One fixed point in front of the inspection webcam,** reachable comfortably by the arm.
- **A plain, evenly lit backdrop close behind it:** white or grey matte card. No moving shadows
  (the arm's shadow on the cardboard is a problem now), no bowls or other objects inside the box.
- **A diffuse lamp** (bounced off white paper). Duplo is shiny, and hard light makes highlights that
  look like defects. The venue lighting changes between day and night.
- **`capture.py`'s green box is the target:** set the box once (section 9), then keep `capture.py`
  open where person A can see it. The arm puts the brick in the middle of the box, at the same size,
  every time.
- **Save the show pose:** once the box is set, put the arm in the ideal showing position and save the
  follower's joint angles. The loop moves to exactly this pose before every photo, which removes the
  "every photo in a different arm pose" problem from [ANOMALY_DATA_REVIEW.md](ANOMALY_DATA_REVIEW.md).
- **Check the wrist cable:** turn the wrist ±90° at the showing point and make sure the wrist camera's
  cable doesn't pull. The round-2 re-check turns the wrist there.

---

## 6. Recording rules

From Studio's recording guide, [`recording-a-dataset.md`](physical-ai-studio/library/docs/how-to/data/recording-a-dataset.md):

1. **Every cycle starts and ends at home, and every episode ends with the arm held still for about
   1 second before Accept.** The guide calls ending where you started "the single most important rule":
   the policy learns to hold still at the end of a task. We split each cycle into two episodes on
   purpose: the pick episode ends holding still at the camera (exactly where we want SmolVLA to wait
   for the photo), and the sort episode ends at home. Together they form the full cycle.
2. **Add variety one stage at a time,** and train and test after each stage. Varying everything at
   once leaves too few examples of each thing.
3. **Same technique every time:** same approach (straight down from above), same grip (across the
   brick's narrow side, centred), same lift, same path to the camera, same speed.
4. **One selection rule** when several bricks are out: always pick the one nearest the robot.
5. **Practise 5–10 cycles before recording.** Hesitant demos teach hesitation.
6. **Discard freely** (left arrow). A discarded episode costs seconds; a bad one costs a training run.
7. **Every ~10 cycles, check the dataset view:** replay a few episodes (spikes in the joint graph,
   stalls, black or frozen camera frames) and **check the task list has exactly three sentences.**
   Fix typos with the episode's edit icon; a typo becomes a fourth instruction.
8. **Rest the follower every 30–40 minutes.** Hot motors get weak and imprecise.
9. **A design change means a new dataset** (for example a different home pose, showing pose or
   sentence wording). Don't mix incompatible episodes into an existing dataset.

---

## 7. Recording `cell-v1`

**Create the dataset:** Datasets → new dataset → name `cell-v1`, environment `policy-cell`, default
task "Pick up the brick and show it to the inspection camera."

**Two people:**

| Person | Job |
|---|---|
| A | Uses the leader arm and presses the arrow keys in Studio |
| B | Runs `recording/layout.py` and `anomaly/capture.py`, resets the table, changes the Task box, takes the photo |

**Open the recording view:** `cell-v1` → **Add episode**. Wait until both camera feeds and the 3D arm
appear. Teleoperate stays on between episodes, so A can move the arm without recording.

**One cycle = two episodes:**

| | Task box | Motion | Then |
|---|---|---|---|
| Set up | | B arranges bowls and bricks as `layout.py` says; arm at home | |
| Episode 1 | "Pick up the brick and show it to the inspection camera." | **Right arrow** → home → grab the brick → into the green box → hold still ~1 s → **right arrow** (accept) | While it's held, B presses `g` or `b` in `capture.py` (the script says which) |
| Episode 2 | The sort sentence from `layout.py` | B pastes the sentence → **right arrow** → named bowl → home → hold still ~1 s → **right arrow** | B pastes the pick sentence back; press Enter in `layout.py` |

- **The sort sentence is random on purpose** (50/50, independent of the brick). SmolVLA must learn to
  follow the sentence, not judge the brick, because at run time Anomalib's verdict is what's in it.
- **Changing the Task box:** copy the sentence from the `layout.py` terminal (select, Ctrl+C), then in
  Studio click the Task box, Ctrl+A, Ctrl+V. If the cursor lands on an empty line below the text,
  press Backspace.
- **The arrow keys do nothing while the cursor is in the Task box** (Studio ignores shortcuts while
  you type). After pasting, click an empty part of the Studio page, then press **→**.
- **Discards:** a discarded pick → bring the arm home and redo it. A discarded sort → bring the brick
  back to the green box without recording, then redo it. Only press Enter in `layout.py` when both
  episodes are accepted.

| Stage | Cycles (episodes) | What changes | Command for person B |
|---|---|---|---|
| 1 | ~50 (~100) | One brick anywhere in the pick area, bowls fixed on spots 1 and 2 | `python3 recording/layout.py --stage 1` |
| 2 | ~30 (~60) | Plus 1–2 other bricks further from the robot (clutter) | `python3 recording/layout.py --stage 2` |
| 3 | ~40 (~80) | Bowls moved between 4 layouts, including swapped colours | `python3 recording/layout.py --stage 3` |

`layout.py` covers every position and rotation in a shuffled, even order, uses good and defective
bricks half and half, and says when a stage's target is reached. Stage 1 is about 40,000 frames,
close to the recording guide's 45,000 for a first task. If your bowls aren't blue and orange, add
`--colours <good colour> <defective colour>`.

---

## 8. Training and testing SmolVLA

After each stage: Models → **Train**

| Setting | Value |
|---|---|
| Dataset | `cell-v1` (always the whole dataset) |
| Policy | SmolVLA (needs the Hugging Face token) |
| Camera mapping | `top` → **Overview**, `wrist` → **Gripper**. SmolVLA was pretrained with the scene camera in its first slot. |
| Target | Modal, A100 |
| Batch size | Auto |
| Max epochs | 5–10 |
| Augment images | On |
| SnapFlow | Off for the first run. Round 2: on, which makes SmolVLA much faster at run time. It only works on top of a well-trained first run. |

Watch the loss chart. Studio holds back 10% of episodes to test on: stop when that test
(validation) loss stops falling. Stopping keeps the model and exports it.

**Test on the arm:** Models → the model → **Run model** → OpenVINO, GPU. Type a sentence in the Task
box → **Play**.

- The arm moves on its own. Keep hands clear; someone stands by the follower's 12 V plug, which is
  the emergency stop.
- **Pick:** 10 tries across the grid and rotations with the pick sentence. Does it end holding the
  brick still in the green box? Note which placements fail.
- **Sort:** from the showing pose, 5 tries with each sort sentence. Does it pick the bowl the
  sentence names, every time?
- 7/10 or better: go to the next stage. Below that: record 10–20 more cycles where it fails,
  retrain, retest.

---

## 9. The inspection (Anomalib)

Full details: [anomaly/README.md](anomaly/README.md). Run the tools from `anomaly/` with the repo
venv: `../.venv/bin/python <script>`.

1. **Set up the camera once,** with the showing point ready (section 5): A holds a brick at the
   showing point by teleoperation. In `capture.py`, click the brick to centre the box, size it with
   `+`/`-` so the whole brick fits with margin wherever the grip puts it, `k` to focus, `1`/`2` for
   brightness 110–150, `3`/`4` until the backdrop looks neutral. After that, don't change it. If you
   do move the box, run `recrop.py`.
2. **Photos come from the arm,** because the gripper is part of every picture:

   | Folder | Source | Count |
   |---|---|---|
   | `normal` | Good bricks at the end of pick episodes (`g`) | 100+ |
   | `test_normal` | Move ~20 of the good photos here, never trained on. Measures false rejects. | ~20 |
   | `abnormal` | Defective bricks at the end of pick episodes (`b`) | 20–40+ |

   Defects: several marker types and sizes, on faces the camera can see. Keep one type back to test
   unseen defects. Keep defective bricks in a separate box; marker defects are permanent.
3. **Train and export:** `../.venv/bin/python train_export.py` (PatchCore, about 3 minutes, exports to
   OpenVINO in `exported_model/`).
4. **Three score bands** for the loop: clearly good, clearly defective, and **unsure** in between.
   Set the band edges from the `test_normal` and `abnormal` scores.
5. **Round 2, "collect" mode:** once the policy picks reliably, the loop script picks bricks, moves to
   the saved show pose and photographs them by itself; you just label them. Those photos match the
   demo exactly (including the wrist-turned view for the re-check). Retrain on them. The round-1
   photos from teleoperated picks are taken at roughly, not exactly, the show pose.

Background on the first photo set and why good bricks were rejected:
[ANOMALY_DATA_REVIEW.md](ANOMALY_DATA_REVIEW.md).

---

## 10. The closed loop

A single script (to write: `loop/run_cell.py`) runs the whole cell with the one SmolVLA. Each cycle:

1. **Pick:** run SmolVLA with the pick sentence until the arm is still near the showing point for
   about 1 second, or a timeout passes.
2. **Inspect:** move the arm to the saved show pose (a small, direct joint move), then take a photo
   from the inspection webcam, cropped exactly as in training (`anomaly/camera.py`), and run the
   Anomalib OpenVINO model: score, heatmap, verdict.
3. **Re-check (round 2):** if unsure, turn the wrist about 90° with a direct joint command, wait
   until still, photograph and score again. Still unsure → defective.
4. **Sort:** reset the policy's action queue, switch to the verdict's sentence, run SmolVLA until the
   arm is still at home, or a timeout passes.
5. **Log** the time of every stage and inference step, then start the next cycle.

**Built on** OpenVINO Physical AI from Studio's backend environment:

- `physicalai.inference.InferenceModel(export_dir, backend="openvino", device="GPU")` loads the
  exported policy. `reset()` clears the action queue between sentences.
- `physicalai.runtime.RobotRuntime` runs the read-robot → ask-policy → send-action loop with cameras
  and timing callbacks.
- Studio exports every trained model to OpenVINO; download it from the Models page.

**Safety:** a key that stops the arm at once; someone at the station with the 12 V plug in reach; a
clear workspace; no runs from SSH without someone watching.

**Demo screen:** the inspection photo with its heatmap, the score and verdict, the sentence sent to
SmolVLA, and live timings. Judges score the clarity of the demo too.

---

## 11. OpenVINO and measurements

**Which model runs where.** Measure; don't assume. The trial Anomalib model was faster on the GPU
(11 ms) than on the NPU (100 ms).

| Model | Try | Ideas |
|---|---|---|
| Anomalib | GPU, NPU, CPU | INT8 with NNCF; a lighter model (PaDiM, EfficientAd) may suit the NPU better |
| SmolVLA | GPU, CPU | SnapFlow (one denoising step instead of ten), then OpenVINO |
| ACT (if used for the pick) | GPU, CPU | Much smaller than SmolVLA, so much faster per step |

Studio's Run model offers OpenVINO on CPU or GPU. NPU runs go through our own scripts.

**Measure for each setup:**

- **Latency** per inference step for each model (median and worst), and per full sorting cycle.
  `physicalai.benchmark` has an `InferenceLatencyBenchmark` helper for the policy.
- **Power:** for example `sudo turbostat --quiet --interval 1 --show PkgWatt,CorWatt,GFXWatt,PkgTmp`
  during a run. The RAPL energy counters need root.
- **GPU load:** `sudo intel_gpu_top`.
- **Temperature:** the `x86_pkg_temp` thermal zone, or `PkgTmp` in turbostat.
- **Success:** sorted correctly out of N bricks, with N stated.

Keep a before/after table for every change (FP16 → INT8, CPU → GPU → NPU, SnapFlow off → on).
Judges want numbers, not claims.

---

## 12. Fallbacks

| If this fails by demo time | Do this |
|---|---|
| SmolVLA's grasp is weak or slow | **Split the dataset** and train ACT on the pick episodes only (below). Keep SmolVLA for the sort. No new recording needed. |
| SmolVLA ignores the sort sentence | Check the task list for typos and the camera mapping. Last resort: split the sort episodes by bowl and train one small ACT per bowl; the script picks one by the verdict. Costs some VLA points. |
| Moving bowls are unreliable | Demo with bowls on spots 1 and 2. The same model handles it. |
| Unsure re-check isn't ready | Send unsure bricks to the defective bowl. |
| Anything breaks late | Demo the last version that worked. Keep a copy of every working model. |

**Splitting the dataset** (test this early with a few episodes; the round trip hasn't been tried yet):

1. Studio: export `cell-v1` (LeRobot v3 format).
2. List the episode numbers whose task is the pick sentence (the dataset's `meta/` files record each
   episode's task).
3. Split with LeRobot's tool, installed in Studio's backend environment:
   ```bash
   cd ~/intel-robot-challenge/physical-ai-studio/application/backend
   .venv/bin/lerobot-edit-dataset --repo_id cell-v1 --root <exported folder> \
       --new_root <output folder> --operation.type split \
       --operation.splits '{"pick": [0, 2, 4], "sort": [1, 3, 5]}'
   ```
4. Studio: import the `pick` part as a new dataset and train ACT on it.

---

## 13. Rough timeline

| When | What |
|---|---|
| Now | Modal + Hugging Face token, table, showing point, backdrop, lamp, create `cell-v1` |
| Saturday morning | Stage 1 (~50 cycles) → train SmolVLA; meanwhile Anomalib on the pick photos |
| Saturday 12:00 | Intel hands-on session: ask which judging table applies, and about anything stuck |
| Saturday afternoon | Test SmolVLA; test the dataset split; stage 2 → retrain |
| Saturday evening | Write and test the loop; stage 3 → retrain |
| Night / Sunday morning | Round 2 (re-check, SnapFlow, collect-mode photos), OpenVINO device choice, measurements, demo screen |
| Before the demo | Freeze the last working version; rehearse the explanation of the design and the numbers |

---

## 14. Troubleshooting

| Problem | Fix |
|---|---|
| Studio: `CaptureTimeoutError: no publisher responded within timeout` | Check nothing else uses the camera (`capture.py`, a browser preview). If nothing does, restart the Studio backend: Ctrl+C in its terminal, wait ~30 s, start it again. |
| Studio: `No camera found matching ...` | Reload the Studio browser tab, so only one preview or session uses the camera. |
| Studio: "Robot ... is in use by a runtime session" with nothing running | Restart the Studio backend. |
| Camera numbers changed after a reboot | Harmless: Studio and `capture.py` find cameras by name. Don't edit the numbers. |
| Policy completes a task, then freezes in a strange place | Episodes didn't end held still where they should (camera for pick, home for sort). |
| Policy only works at the positions it saw | Record more cycles at the other positions. |
| Policy picks a random brick when several are out | The demos had no consistent selection rule. Always pick the nearest. |
| Policy ignores the brick | Camera framing, contrast or lighting, not the model. |
| Policy wobbles or hesitates | Inconsistent demos, or it needs more training. |
| SmolVLA goes to the same bowl whatever the sentence | Typos in the task list, too few cycles, or the camera mapping is wrong (top must be Overview). |
| `capture.py` can't open the camera | Close any Studio preview of the inspection camera, or the other copy of `capture.py`. |
| Anomalib rejects good bricks | "Good" doesn't cover enough: add those colours, grips and angles to `normal`; check the backdrop for shadows. |

---

## 15. Repository map

| Path | What |
|---|---|
| `GUIDE.md` | This guide |
| `CHALLENGE_INFO.md`, `Intel_Physical AI Hackathon.pdf` | The challenge brief and Intel's slides (judging on page 7, end goal on page 9) |
| `STATION_SSH.md` | Reaching the station laptop over SSH |
| `ANOMALY_DATA_REVIEW.md` | Review of the first 475 inspection photos and the trial Anomalib model |
| `recording/layout.py` | Per cycle: where to put the bricks and bowls, and which sentences to use |
| `anomaly/` | Inspection photos, Anomalib training and export ([README](anomaly/README.md)) |
| `loop/` | The closed loop, demo screen and show tool ([README](loop/README.md)) |
| `bench/` | Latency, load and temperature measurements; `RESULTS.md` is generated by `make_table.py` |
| `DEMO_DAY.md` | Architecture, judging criteria, demo run sheet, what to run when training finishes |
| `physical-ai-studio/` | Studio, on the `junction2026` branch |
| `physical-ai-studio/JUNCTION2026.md` | The organisers' Studio walkthrough |
| `.venv/` | Python 3.12 with Anomalib 2.7, OpenVINO and OpenCV, for the anomaly tools |

## 16. Sources

- Challenge PDF, pages 3–9: overview, required stack, workflow, implementation expectations, judging, hardware, end goal.
- [`physical-ai-studio/JUNCTION2026.md`](physical-ai-studio/JUNCTION2026.md): station setup, Modal, Anomalib, policies, rubric.
- [`recording-a-dataset.md`](physical-ai-studio/library/docs/how-to/data/recording-a-dataset.md): recording rules, stages, sizing, training length, troubleshooting.
- Studio docs: [recording](physical-ai-studio/application/docs/05-recording-datasets.md), [training](physical-ai-studio/application/docs/06-training-policies.md), [deploying](physical-ai-studio/application/docs/08-deploying-model-policies.md).
- Library docs: [first deployment](physical-ai-studio/library/docs/getting-started/first-deployment.md), [image augmentations](physical-ai-studio/library/docs/how-to/training/image_augmentations.md), [SnapFlow](physical-ai-studio/library/docs/how-to/training/snapflow_distillation.md).
- LeRobot's `lerobot-edit-dataset` (in Studio's backend environment): splitting a dataset by episode.
