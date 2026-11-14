# Team guide: Intel Physical AI Challenge

How we build the autonomous brick-sorting cell, step by step. Start here; the
detailed tool docs are linked from each section.

Last updated: 2026-11-14, about 04:45. The status in section 3 changes quickly, so update it when you
finish something.

---

## 1. What we're building

```text
 brick anywhere           inspection spot          Anomalib verdict             sentence to SmolVLA            bowl
 in the pick area ──ACT──▶ (fixed, taped)  ──photo──▶ good / defective / unsure ──▶ "The brick is defective. ──SmolVLA──▶ blue (good)
                                                                                    Put it in the orange bowl."           orange (defective)
```

1. **ACT picks the brick** from anywhere in the pick area and puts it on the fixed inspection spot,
   then returns home.
2. **Anomalib checks the brick** in a photo from the inspection webcam and gives a verdict and a score.
3. **The verdict goes into the sentence** that SmolVLA receives, for example
   "The brick is defective. Put it in the orange bowl."
4. **SmolVLA puts the brick in the named bowl** and returns home. Repeat.
5. **Unsure scores trigger a re-check** (round 2): "The brick is unclear. Turn it and put it back on the
   inspection spot.", then inspect again.

Nobody chooses anything during a run. Everything runs on the laptop with OpenVINO.

**Why this design:**

- The challenge PDF's "End Goal" slide uses exactly this split: ACT to the inspection camera, Anomalib,
  then SmolVLA into the "defective" or "perfect" plate.
- The PDF asks for the defect result to reach the robot policy "as a structured signal, label, score",
  and for the VLA to interpret "the task instruction and perception results". The verdict in the
  sentence does that visibly.
- ACT is precise with few demonstrations and fast on the laptop, which is what the grasp needs.
  Dropping into a bowl needs little precision, so the slower, language-driven SmolVLA fits there.

---

## 2. How we're judged

From the challenge PDF (Intel's slides, page 7):

| Criterion | Points | Our answer |
|---|---|---|
| End-to-end physical AI solution: one closed loop, not separate demos | 25 | One script runs pick → inspect → sort in a loop (section 10) |
| Defect detection with Anomalib, including how its result reaches the robot | 20 | PatchCore on the inspection crop; the verdict goes into SmolVLA's sentence |
| VLA and Physical AI Studio integration | 20 | Both policies trained in Studio; SmolVLA acts on the verdict sentence |
| OpenVINO and Core Ultra optimisation (CPU / GPU / NPU) | 20 | Every model in OpenVINO, device chosen by measurement, numbers in a table (section 11) |
| Robot execution and reliability, including recovery from uncertain detections | 10 | Staged data, tested success rates, re-check on unsure scores |
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
- [x] Studio dataset `pick-v1` created, with the task text set (0 episodes so far).
- [x] Anomalib: capture tool, re-crop tool, and the train + OpenVINO export pipeline work
      (trial run: about 3 minutes; one crop takes about 11 ms on the GPU, 30 ms on the CPU, 100 ms on the NPU).
- [x] 475 good-brick photos captured.
- [x] `recording/layout.py` tells the person resetting the table where to put everything.

**Blocking: do these first**

- [ ] Connect Modal (section 5). No cloud training is possible until this is done.
- [ ] Set the Hugging Face token in Studio (section 5). Needed for SmolVLA.
- [ ] Tape the table and set up the lamp (section 5).
- [ ] Anomalib photos: run `anomaly/recrop.py` (the 475 photos were cut with four different box
      sizes), and check that the photos taken before the 04:19 camera retune still match.
      Recrop fixes the box, not colour or focus. Then capture the real `abnormal` and `test_normal` sets.

**Then**

- [ ] Pick stages 1–3 with ACT (section 7).
- [ ] Sort stages 1–2 with SmolVLA (section 9).
- [ ] Loop script (section 10).
- [ ] OpenVINO device choice and measurements (section 11).
- [ ] Round 2: the "unsure" re-check, SnapFlow.

---

## 4. The station

| Part | Identity | Used by |
|---|---|---|
| Leader arm | USB serial `5AA9024537` (5 V supply) | Studio, teleoperation |
| Follower arm | USB serial `5B3E090516` (12 V supply) | Studio and the loop script |
| `top` camera | RealSense D415, serial `243722061698`, added in Studio as "RealSense D415" | Both policies |
| `wrist` camera | Autodarts DIY Cam on the gripper | Both policies |
| Inspection camera | 2K webcam, `/dev/v4l/by-id/usb-Webcam_Webcam_Audio_01.00.00-video-index0` | Anomalib tools only |
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
| Environment `policy-cell` | Use this for **all** recordings. Two cameras only: the policies don't need the inspection camera, and fewer cameras run faster. |
| Environment `sorting-cell` | Old, no cameras. Don't use. |
| Dataset `pick-v1` | All pick stages (section 7). |
| Dataset `sort-v1` | All sort stages (section 9). Create it in `policy-cell`. |
| Dataset `gtesr` | Old test. Can be deleted. |

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
- **Inspection spot:** taped, fixed, under the inspection webcam.
- **Bowl spots 1–4:** small numbered tape marks, all reachable by the arm, none on the pick area or
  the inspection spot, none touching the arm's base. Spots 1 and 2 are the fixed positions for the
  early stages.
- **Lamp:** diffuse light (bounced off white paper). Duplo is shiny, and hard light makes highlights
  that look like defects. The venue lighting changes between day and night.
- **Top camera view:** no cables, bags, phones or people. The leader arm and the person using it
  stay out of view.
- **Lock it down:** if a camera moves after recording, earlier episodes no longer match.

---

## 6. Recording rules (every dataset)

From Studio's recording guide, [`recording-a-dataset.md`](physical-ai-studio/library/docs/how-to/data/recording-a-dataset.md):

1. **Every episode starts at home and ends back at home, held still for about 1 second, then Accept.**
   The guide calls this the most important rule. It teaches the policy to wait at home after a task,
   which lets the loop chain tasks. Episodes that stop at the target teach the policy to freeze there.
2. **Add variety one stage at a time,** and train and test after each stage. Varying everything at
   once leaves too few examples of each thing.
3. **Same technique every time:** same approach (straight down from above), same grip, same lift
   height, same speed. ACT averages between styles.
4. **One selection rule** when several bricks are out: always pick the one nearest the robot.
5. **Practise 5–10 runs before recording.** Hesitant demos teach hesitation.
6. **Discard freely** (left arrow). A discarded episode costs seconds; a bad one costs a training run.
7. **Every ~10 episodes, replay a few** in the dataset view: look for spikes in the joint graph,
   stalls, and black or frozen camera frames. Delete bad episodes.
8. **Rest the follower every 30–40 minutes.** Hot motors get weak and imprecise.
9. **A design change means a new dataset** (for example a different home pose or task sentence).
   Don't mix incompatible episodes into an existing dataset.

**Two people work best:**

| Person | Job |
|---|---|
| A | Uses the leader arm and presses the arrow keys in Studio |
| B | Runs `recording/layout.py`, resets the table as it says, and takes the inspection photo |

**Recording in Studio:** Datasets → the dataset → **Add episode**. Wait until both camera feeds and
the 3D arm appear. Then for each episode: reset the table → **right arrow** (start) → demonstrate →
back home, hold 1 s → **right arrow** (accept), or **left arrow** (discard).

---

## 7. Part A: the pick (ACT, dataset `pick-v1`)

**Task text** (already set on the dataset): "Pick up the brick and place it on the inspection spot."

| Stage | Episodes | What changes | Command for person B |
|---|---|---|---|
| 1 | ~50 | One brick anywhere in the pick area, bowls fixed on spots 1 and 2 | `python3 recording/layout.py pick --stage 1` |
| 2 | ~30 | Plus 1–2 other bricks further from the robot (clutter) | `python3 recording/layout.py pick --stage 2` |
| 3 | ~40 | Bowls moved between 4 layouts | `python3 recording/layout.py pick --stage 3` |

- **Brick mix:** good and defective bricks, half and half (the script says which). The pick motion
  is the same for both.
- **Inspection photo:** after each episode, with the arm home, person B presses `g` (good) or `b`
  (defective) in `anomaly/capture.py`. That gives real robot-placed photos for Anomalib.
- **Using the layout script:** Enter after an accepted episode; after a discarded one, redo the same
  layout. It tells you when the stage target is reached.

**Train after each stage:** Models → **Train**

| Setting | Value |
|---|---|
| Dataset | `pick-v1` (always the whole dataset) |
| Policy | ACT |
| Target | Modal, A10G |
| Batch size | 8 |
| Max epochs | 10 |
| Augment images | On |

Watch the loss chart. Studio holds back 10% of episodes to test on. ACT has no fixed epoch count:
stop when the test (validation) loss stops falling. Stopping keeps the model and exports it.

**Test on the arm:** Models → the model → **Run model** → OpenVINO, GPU → **Play**.

- The arm moves on its own. Keep hands clear; someone stands by the follower's 12 V plug, which is
  the emergency stop.
- Place the brick 10 times across the grid and rotations. Write down which placements fail.
- 7/10 or better: go to the next stage. Below that: record 10–20 more episodes at the failing
  placements, retrain, retest.

---

## 8. Part B: the inspection (Anomalib)

Full details: [anomaly/README.md](anomaly/README.md). Run the tools from `anomaly/` with the repo
venv: `../.venv/bin/python <script>`.

1. **Set up the camera once** in `capture.py`: brick on the spot, click it to centre the box, size the
   box with `+`/`-`, `k` to focus, `1`/`2` for brightness 110–150, `3`/`4` until white paper looks white.
   After that, don't change it. If you do move the box, run `recrop.py`.
2. **Photos:**

   | Folder | Count | What |
   |---|---|---|
   | `normal` | 100–150 | Every good colour and size, 4 rotations each, shifted up to ~1 cm. Robot-placed photos from pick recording count too. One photo per placement, no bursts. |
   | `test_normal` | 20+ | Good bricks in new placements, never trained on. Measures false rejects. |
   | `abnormal` | 20–40 | Several marker defect types and sizes on visible faces. Keep one type back to test unseen defects. |

   Keep defective bricks in a separate box; marker defects are permanent.
3. **Train and export:** `../.venv/bin/python train_export.py` (PatchCore, about 3 minutes, exports to
   OpenVINO in `exported_model/`).
4. **Three score bands** for the loop: clearly good, clearly defective, and **unsure** in between.
   Set the band edges from the `test_normal` and `abnormal` scores.
5. **Later:** add photos of bricks that ACT placed by itself, and retrain. They match the demo best.

---

## 9. Part C: the sort (SmolVLA, dataset `sort-v1`)

Create `sort-v1` in `policy-cell`. Each episode starts with the brick on the inspection spot,
slightly off-centre or turned (ACT won't place it perfectly); the arm puts it in the named bowl and
returns home.

**Sentences** (exact text, every time):

- "The brick is good. Put it in the blue bowl."
- "The brick is defective. Put it in the orange bowl."

| Stage | Episodes | What changes | Command for person B |
|---|---|---|---|
| 1 | ~50 | Bowls fixed on spots 1 and 2 | `python3 recording/layout.py sort --stage 1` |
| 2 | ~40 | Bowls moved between 4 layouts, including swapped colours | `python3 recording/layout.py sort --stage 2` |

- **Record in pairs:** the same layout and the same brick, once with each sentence. The brick type
  doesn't matter. This forces SmolVLA to follow the sentence instead of guessing from how the brick
  looks, so Anomalib's verdict really drives the robot.
- **Changing the sentence:** Studio's Task box keeps the last text. Double-click the word and change it
  (good ↔ defective, blue ↔ orange). The script flags when to change it.
- **Check for typos** in the dataset view's task list afterwards, and fix them with the episode's edit
  icon. A typo becomes a third instruction.
- If your bowls are different colours, use `--colours <good colour> <defective colour>` and change
  the sentences to match.

**Train:** Models → **Train**

| Setting | Value |
|---|---|
| Dataset | `sort-v1` |
| Policy | SmolVLA (needs the Hugging Face token) |
| Camera mapping | `top` → **Overview**, `wrist` → **Gripper**. SmolVLA was pretrained with the scene camera in its first slot. |
| Target | Modal, A100 |
| Batch size | Auto |
| Max epochs | 5–10 (watch the validation loss) |
| Augment images | On |
| SnapFlow | Off for the first run. On for round 2: it makes SmolVLA much faster at run time, and it only works on top of a well-trained first run. |

**Test:** Run model → OpenVINO, GPU → type one of the two sentences in the Task box → **Play**.
Check that it picks the right bowl for both sentences and several bowl layouts.

**Round 2, the re-check:** add about 20 episodes to `sort-v1` with "The brick is unclear. Turn it and
put it back on the inspection spot." The loop sends this when the score is in the unsure band, then
inspects again. This covers "recovery from uncertain defect detections" in the judging.

---

## 10. Part D: the closed loop

A single script (to write: `loop/run_cell.py`) runs the whole cell. Each cycle:

1. **Pick:** run the ACT model until the arm is back near home and still for about 1 second (the
   ending-at-home recording rule teaches it to wait there), or a timeout passes.
2. **Inspect:** take a photo with the inspection webcam, cropped exactly as in training
   (`anomaly/camera.py`), and run the Anomalib OpenVINO model. Get the score and heatmap.
3. **Decide:** good or defective → that sentence; unsure → the re-check sentence (round 2), then
   inspect again.
4. **Sort:** run SmolVLA with the sentence until the arm is home and still, or a timeout passes.
5. **Log** the time of every stage and inference step, then start the next cycle.

**Built on** OpenVINO Physical AI from Studio's backend environment:

- `physicalai.inference.InferenceModel(export_dir, backend="openvino", device="GPU")` loads an
  exported policy.
- `physicalai.runtime.RobotRuntime` runs the read-robot → ask-policy → send-action loop with cameras
  and timing callbacks.
- Studio exports every trained model to OpenVINO; download it from the Models page.

**Safety:** a key that stops the arm at once; someone at the station with the 12 V plug in reach; a
clear workspace; no runs from SSH without someone watching.

**Demo screen:** the inspection photo with its heatmap, the score and verdict, the sentence sent to
SmolVLA, and live timings. Judges score the clarity of the demo too.

---

## 11. Part E: OpenVINO and measurements

**Which model runs where.** Measure; don't assume. The trial Anomalib model was faster on the GPU
(11 ms) than on the NPU (100 ms).

| Model | Try | Ideas |
|---|---|---|
| Anomalib | GPU, NPU, CPU | INT8 with NNCF; a lighter model (PaDiM, EfficientAd) may suit the NPU better |
| ACT | GPU, CPU | OpenVINO export from Studio |
| SmolVLA | GPU | SnapFlow (one step instead of ten), then OpenVINO |

Studio's Run model offers OpenVINO on CPU or GPU. NPU runs go through our own scripts.

**Measure for each setup:**

- **Latency** per inference step for each model (median and worst), and per full sorting cycle.
  `physicalai.benchmark` has an `InferenceLatencyBenchmark` helper for the policies.
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
| Moving bowls are unreliable | Demo with bowls on spots 1 and 2. The same models handle it. |
| SmolVLA doesn't follow the sentence | Two small ACT drop models, one per bowl; the script picks one by the verdict. Costs some VLA points; the loop still runs. |
| ACT misses at some positions | Record 10–20 episodes there and retrain. For the demo, place bricks where it's reliable. |
| Unsure re-check isn't trained | Send unsure bricks to the defective bowl. |
| Anything breaks late | Demo the last version that worked. Keep a copy of every working model. |

---

## 13. Rough timeline

| When | What |
|---|---|
| Now | Modal + Hugging Face token, tape the table, lamp, recrop the Anomalib photos |
| Saturday morning | Pick stage 1 → train ACT; meanwhile Anomalib abnormal/test photos and training |
| Saturday 12:00 | Intel hands-on session: ask which judging table applies, and about anything stuck |
| Saturday afternoon | Test ACT, pick stage 2; sort stage 1 → train SmolVLA |
| Saturday evening | Test SmolVLA; write and test the loop; pick stage 3, sort stage 2 |
| Night / Sunday morning | Round 2 (re-check, SnapFlow), OpenVINO device choice, measurements, demo screen |
| Before the demo | Freeze the last working version; rehearse the explanation of the design and the numbers |

---

## 14. Troubleshooting

| Problem | Fix |
|---|---|
| Studio: `CaptureTimeoutError: no publisher responded within timeout` | Check nothing else uses the camera (`capture.py`, a browser preview). If nothing does, restart the Studio backend: Ctrl+C in its terminal, wait ~30 s, start it again. |
| Studio: `No camera found matching ...` | Reload the Studio browser tab, so only one preview or session uses the camera. |
| Studio: "Robot ... is in use by a runtime session" with nothing running | Restart the Studio backend. |
| Camera numbers changed after a reboot | Harmless: Studio and `capture.py` find cameras by name. Don't edit the numbers. |
| Policy completes once, then freezes | The episodes didn't end at home. Re-record into a new dataset. |
| Policy only works at the positions it saw | Record more episodes at the other positions. |
| Policy picks a random brick when several are out | The demos had no consistent selection rule. Always pick the nearest. |
| Policy ignores the target or brick | Camera framing, contrast or lighting, not the model. |
| Policy wobbles or hesitates | Inconsistent demos, or it needs more training. |
| SmolVLA goes to the same bowl whatever the sentence | Too few pairs, or the camera mapping is wrong (top must be Overview). |
| `capture.py` can't open the camera | Close any Studio preview of the inspection camera, or the other copy of `capture.py`. |
| Anomalib rejects good bricks | "Good" doesn't cover enough: add those colours, rotations or placements to `normal`. |

---

## 15. Repository map

| Path | What |
|---|---|
| `GUIDE.md` | This guide |
| `CHALLENGE_INFO.md`, `Intel_Physical AI Hackathon.pdf` | The challenge brief and Intel's slides (judging on page 7, end goal on page 9) |
| `STATION_SSH.md` | Reaching the station laptop over SSH |
| `recording/layout.py` | Tells person B where to put the brick and bowls for each episode |
| `anomaly/` | Inspection photos, Anomalib training and export ([README](anomaly/README.md)) |
| `physical-ai-studio/` | Studio, on the `junction2026` branch |
| `physical-ai-studio/JUNCTION2026.md` | The organisers' Studio walkthrough |
| `.venv/` | Python 3.12 with Anomalib 2.7, OpenVINO and OpenCV, for the anomaly tools |

## 16. Sources

- Challenge PDF, pages 3–9: overview, required stack, workflow, implementation expectations, judging, hardware, end goal.
- [`physical-ai-studio/JUNCTION2026.md`](physical-ai-studio/JUNCTION2026.md): station setup, Modal, Anomalib, policies, rubric.
- [`recording-a-dataset.md`](physical-ai-studio/library/docs/how-to/data/recording-a-dataset.md): recording rules, stages, sizing, training length, troubleshooting.
- Studio docs: [recording](physical-ai-studio/application/docs/05-recording-datasets.md), [training](physical-ai-studio/application/docs/06-training-policies.md), [deploying](physical-ai-studio/application/docs/08-deploying-model-policies.md).
- Library docs: [first deployment](physical-ai-studio/library/docs/getting-started/first-deployment.md), [image augmentations](physical-ai-studio/library/docs/how-to/training/image_augmentations.md), [SnapFlow](physical-ai-studio/library/docs/how-to/training/snapflow_distillation.md).
