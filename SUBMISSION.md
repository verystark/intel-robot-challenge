# Junction submission and video

What Junction's form asks for, what we put in each field, and how we make the video.

> **The paste-ready text for every field is in [JUNCTION_SUBMISSION_TEXT.md](JUNCTION_SUBMISSION_TEXT.md).**
> Sections 2 and 3 below are the earlier drafts; where they differ, that file wins. The form as
pasted is in [JUNCTION_SUBMISSION_FORM.md](JUNCTION_SUBMISSION_FORM.md). The demo plan is in
[PLAN_AND_SHOW.md](PLAN_AND_SHOW.md).

**Deadline:** the form closes at about **08:00 Sunday laptop time** (16:00 UTC), going by its
countdown at 15:00 on Saturday. Submit a complete draft early and update it; don't leave it to
the last hour.

**Not known yet; ask a mentor or check the dashboard's Guide tab:**
- Is there a video length limit? Plan for 2 minutes or less.
- When is the live judging at the station, and is it before or after the form closes?
- What does the Tech Challenge Participation list contain? Does anything besides Intel fit us?
- Does Peer Review (in the dashboard) count, and what do reviewers see? Probably only this form
  and the video, so both must make sense without the live demo.

---

## 1. The fields

| Field | Required | What we put | Owner | Status |
|---|---|---|---|---|
| Project name | Yes | `Jenssenit` (already in the draft) | | Done |
| Punchline (≤200 characters) | Yes | Section 2 | | Draft |
| Description (≤5000 characters, markdown) | Yes | Section 3, with the real results filled in | | Draft |
| Challenge picker | Yes | The Intel Physical AI Challenge | | |
| Project demo | No | The video link again, or the repo's README | | |
| Source code | No, but judges look | A public GitHub repo (section 4) | | |
| Video | No, but it carries the peer review | YouTube, unlisted (section 5) | | |
| Other link | No | The unedited take of a full round (credibility; see JUNCTION_SUBMISSION_TEXT.md). `bench/RESULTS.md` is linked from the README | | |
| Presentation (≤20 MB) | No | A 7-slide PDF (section 6) | | |
| Tech challenges | No | Check the list | | |

Treat the optional fields as required: judges and peer reviewers who weren't at our station only
see this form.

---

## 2. Punchline (draft)

Pick one. Each is under 200 characters. All lead with the main point: random brick and plate
positions, handled by a learned policy, with the defect check in the loop.

1. `A VLA picks bricks lying at random positions, Anomalib inspects each one, and the VLA puts it on the right plate wherever the plates are. All inference on one Intel Core Ultra laptop.`
2. `SmolVLA picks and sorts any number of randomly placed bricks onto movable plates. Anomalib's verdict is passed to the VLA as its task sentence. OpenVINO on CPU, GPU and NPU.`
3. `Pick, inspect, sort with no coordinates in the code: a VLA trained on teleoperation handles random brick and plate positions, and Anomalib's verdict becomes its next task.`

---

## 3. Description (draft)

Fill in the `[brackets]` from real runs before submitting. Check each claim against the code on the
day, because the loop is still changing. Copy everything between the lines.

---

The cell picks, inspects and sorts Duplo bricks with an SO-101 arm. The number of bricks, where
they lie and where the two plates stand all change from run to run. **No positions are
hard-coded:** picking and placing are learned by a vision-language-action model (SmolVLA) from
our teleoperated demonstrations. Everything runs on one Intel Core Ultra laptop.

### What it does

1. **Pick:** SmolVLA, given *"Pick up the brick."*, picks one of the bricks on the table, wherever
   it lies.
2. **Inspect:** the arm moves to a fixed inspection pose and turns the brick to three angles.
   Anomalib PatchCore scores each view and draws a heatmap. An unsure view gets a second look.
3. **Sort:** the verdict becomes SmolVLA's next task sentence, *"The brick is good. Put it on the
   green plate."* or *"The brick is defective. Put it on the orange plate."* The policy finds the
   plate of that colour wherever it is.
4. Repeat until the table is empty. Nobody chooses anything during a run.

**Evaluation:** [R] rounds with brick and plate positions drawn at random, [M] cycles. Picks
first try [P]/[M], inspection correct [I]/[M], correct plate [S]/[M], median cycle [X] s.
Failures: [list].

### How it works

| Stage | How | Runs on |
|---|---|---|
| Pick | Learned: [SmolVLA / ACT], from the top and wrist cameras | [GPU / NPU] |
| Show | Scripted: one saved pose, wrist stops at 0°, 90° and 180° | CPU |
| Inspect | Anomalib PatchCore, median of 3 frames per view; an unsure view gets a second look, still unsure → rejected | GPU |
| Sort | Learned: the same SmolVLA, told the verdict as a sentence | GPU |

**Why the show is scripted:** anomaly detection flags anything that differs from its training
photos. When the arm held the brick in a slightly different pose each time, good bricks were
rejected. A fixed pose gives identical photos, so the model judges the brick, not the arm.

**Safety:** every policy step is clamped, and the clamp ramps up over each stage's first second.
Stages time out, one key stops the arm, and a device lock stops two programs driving it at once.

### Data

- **501 teleoperated episodes** recorded in Physical AI Studio with the leader arm. The raw dataset
  is never edited; we train on cleaned copies.
- The cleaned set has **486 episodes (54 min)**: 244 picks, 129 good sorts and 113 defective
  sorts.
- **Every label is checked.** A script compares the top camera before and after each sort to see
  which plate the brick landed on. Unclear cases were checked by eye. Result: all 242 sorts
  correct. Every pick ends with a brick visible in the wrist camera.
- **We found a training trap.** Studio exports the epoch with the lowest validation loss, which
  shipped an undertrained epoch-3 model. We now train with no validation split for ~20k steps.
  Offline, the jumps between action chunks dropped by half.

### Intel optimisation

All numbers were measured on the laptop (Core Ultra X9 388H) with OpenVINO:

| Model | GPU | NPU | CPU |
|---|---|---|---|
| SmolVLA, 50-action chunk | [214] ms | won't compile | [4,764] ms |
| ACT, 100-action chunk | [15] ms | [17] ms | [218] ms |
| PatchCore, one 720 px crop | [18] ms | [184] ms | [56] ms |

- **Each model runs on the device we measured best for it.** SmolVLA runs on the GPU and finishes
  each chunk [3.8]× faster than the arm uses it up, with asynchronous chunking. ACT runs on the
  NPU, as fast as on the GPU. Anomalib runs on the GPU while no policy is using it.
- **INT8 Anomalib:** weight-only quantisation makes it 4× smaller (35 → 9 MB) with scores within
  0.06. Full INT8 shifted scores by up to 0.28, so we didn't use it.
- **Anomalib trains on the laptop's Intel GPU:** 2.7 min vs 12–17 min on the CPU.
- **Zero-noise SmolVLA** with a short blend between chunks: [5–10]× less jerk in offline tests.
- **Logged every cycle:** temperature, CPU / GPU / NPU load, [power].

### Stack

Physical AI Studio (recording, training on Modal H100s, OpenVINO export), SmolVLA, ACT,
Anomalib 2.7 (PatchCore), OpenVINO on CPU / GPU / NPU, OpenVINO Physical AI's runtime, SO-101 arm,
RealSense D415, webcam.

---

### Before submitting

- [ ] Every `[bracket]` replaced with a measured number, or the sentence removed.
- [ ] The pick model and its device are the ones actually used in the video and demo.
- [ ] Length under 5000 characters (`wc -m`, without this checklist).
- [ ] Re-read the claims against `loop/cell_config.json` and `bench/RESULTS.md`.

---

## 4. Source code

The repo `verystark/intel-robot-challenge` is **private**: an anonymous request gets 404. Judges
need to be able to open it.

**Recommended: a new public repo with a clean copy**, rather than making this one public. Its git
history contains things that shouldn't be published:

| File | Problem | Action |
|---|---|---|
| `STATION_SSH.md`, `SSH_CONNECT.md` | Station IP, Wi-Fi name, an authorised SSH key | Leave out |
| `Intel_Physical AI Hackathon.pdf` | Intel's slide deck | Leave out unless Intel says it's fine |
| `sudopsword.txt` | Untracked; must never be added | Leave out |
| `moi.txt` | Scratch file | Leave out |

Also:
- [ ] Add a README a judge can read in 2 minutes: what it is, the video, the architecture, the
      results, where each part of the code lives.
- [ ] Our edits inside the `physical-ai-studio` submodule (multi-GPU Modal training, validation
      split) are uncommitted and would be invisible. Export them as
      `patches/physical-ai-studio.patch` so judges can see them.
- [ ] Before publishing, look over the list of files that will go public.

---

## 5. Video

### What it must do

Peer reviewers, and maybe some judges, see only the video. It has to show the whole loop working
on the real arm, with no sound needed (captions carry the story), in 2 minutes or less.

**Film from now on.** Every real test cycle tonight is possible footage. Don't wait for the perfect
run: film the first good cycles, then re-shoot if a better run comes.

### How we build it: code, not generated video

Every frame is either real footage or graphics drawn by code. No diffusion model makes any image.

| Part | Tool | Why |
|---|---|---|
| Video | **[Remotion](https://www.remotion.dev)**: scenes are React components, rendered frame by frame to MP4 by headless Chrome + FFmpeg | Mature (since 2021), deterministic, has official agent skills (`npx skills add remotion-dev/skills`). Free for individuals and very small teams; check the licence page |
| Numbers | A `data.json` built from `bench/results/`, `loop/runs/` and the dataset stats | The charts in the video are our measurements. New numbers → re-render, no hand edits |
| Voice | **AI narration** (Kokoro-82M, local, Apache 2.0) over the graphics; **our own voices, live**, in the real footage | The narrator explains; the run speaks for itself (VIDEO_PLAN.md §2, §7.1) |
| Captions | Narration: from the voice's word timestamps. Live speech: Whisper run locally, or by hand | The video works with the sound off |
| Sound | The arm's real servo sound from the phone; UI ticks synthesised in code | Nothing generated by a model |
| Footage | Phone + GNOME screen recordings, converted to constant-frame-rate H.264 with ffmpeg | Remotion embeds them in rounded frames, side by side |

**Look:** a dark background with one accent colour per stage (pick, show, inspect, sort). The
pipeline diagram (PERCEIVE → DETECT → REASON → ACT → OPTIMIZE) lights up stage by stage over the
real footage. Moving parts:
- an episode counter ticking to 486, and a "242 / 242 labels checked" stamp;
- the heatmap wiping over the real inspection photo;
- the verdict sentence typed into a prompt box that feeds the VLA block;
- CPU / GPU / NPU chips lighting up with their measured milliseconds;
- latency bars growing to their real values.

**Where:** a `video/` folder in the repo: the script with the narration, the Remotion project, a
TTS script. The rendered MP4 goes outside git.

**Render only when the arm isn't running.** Rendering loads the CPU and heats the laptop, which
would disturb the loop's timing.

**Alternative:** [HyperFrames](https://github.com/heygen-com/hyperframes) (HeyGen, Apache 2.0,
April 2026) does the same with plain HTML + GSAP and is built for agents. It's newer, so it has
less of a track record; Remotion is the safer choice with a deadline.

### Structure, shots and filming

The structure, the "It works" section (an uncut, real-time take on the arm), the shot list, the
filming guide and the fallbacks are in **[VIDEO_PLAN.md](VIDEO_PLAN.md)**.

### What the laptop can make without the arm

These need no person and no hardware:

- The **3×3 grid of recorded episodes**, from the `main-clean3` videos (ffmpeg).
- The **inspection gallery**: photos and heatmaps from `loop/runs/`.
- The **title, result and device-map cards.**
- **The whole edit as a draft**, with placeholder boxes where the arm footage will go: Remotion
  scenes, voice, captions, animated charts. When the footage arrives it drops into
  `video/public/footage/` and the video is rendered again.

### Upload

A teammate uploads it to YouTube as **Unlisted** from their own account, then pastes the link into
the form and the README. Check the link in a private browser window.

### Timeline

See [VIDEO_PLAN.md](VIDEO_PLAN.md) §10.

---

## 6. Presentation (PDF, ≤20 MB)

Nine 16:9 slides. Technical, plain wording (the rules in [VIDEO_PLAN.md](VIDEO_PLAN.md) §2 and
§13.1): what we built, how, and the measured numbers with failures counted. The deck tells the
same story as the video, so a judge who reads only the PDF gets the full picture.

### How it's built

In the video's Remotion project (`video/src/deck/`), one still per slide, combined into
`video/out/jenssenit_deck.pdf`. Commands in [video/README.md](video/README.md).

- **Why Remotion and not the Slides artifact type:** the deck uses the video's components and
  reads the same `video/public/data.json`. When the evaluation rounds or new benchmarks come in,
  one command rebuilds both the deck and the video with the new numbers; nothing is typed in by
  hand. It works offline, and nothing leaves the laptop. (A Slides artifact would mean
  publishing to claude.ai and editing numbers by hand.)
- Unmeasured numbers show as yellow `[NAME]` placeholders, and a footer line says what's still a
  draft, the same as in the video.

### The slides

| # | Title | The one point | On the slide | Source |
|---|---|---|---|---|
| 1 | Jenssenit | A VLA picks and sorts randomly placed bricks onto movable plates, with Anomalib inspection in the loop, all on one laptop | One-sentence claim, the four facts (variable brick count, random positions, movable plates, no coordinates in code), a frame of the cell (the coverage map until footage exists), team | `facts.json`, footage `a1` |
| 2 | The task | Nothing is in a fixed place; a replayed motion would fail | Spec table: bricks, positions, plates, coordinates in code, defect check. The three exact task sentences. A round's random draw (map) | `cell_config.json` sentences, `video/layouts/` |
| 3 | The cell | Learned where it varies, scripted where it must be identical | Pipeline PICK → SHOW → INSPECT → SORT, each marked learned or scripted, with its model and device. The verdict becoming the next task sentence | `cell_config.json`, CLAUDE.md |
| 4 | The policy and its data | SmolVLA, fine-tuned in Physical AI Studio on teleoperation, covers the table | Inputs → SmolVLA → 50-action chunk. Dataset numbers. The coverage map: 241 grasps, 242 releases, both plates on both sides in all three recording batches | `DATASET_MAIN_CLEAN3.md`, `video/public/coverage.json` |
| 5 | Data and training checks | Raw data kept, every label checked, and a training trap found and fixed | Raw `main` (501) never edited → cleaned copies (486). 242 / 242 sort labels and 244 / 244 picks checked. The validation-split trap (epoch-3 snapshot shipped). v1 vs v2 offline numbers | `DATASET_MAIN_CLEAN3.md`, `MODEL_RUN_NOTES.md` |
| 6 | Inspection | Anomaly detection needs an identical view, so the pose is scripted | Why: the first photo set (arm pose different in every photo) rejected 3 of 15 good bricks. Now: fixed pose, 0° / 90° / 180°, median of 3 frames, bands, second look. Heatmaps. Trained on good bricks only, on the Intel GPU (2.7 vs 12–17 min). INT8 weight-only | `ANOMALY_DATA_REVIEW.md`, `CLAUDE.md`, `loop/runs/` |
| 7 | On the laptop | Every model in OpenVINO, each on the device measured best for it | Latency table: model × CPU / GPU / NPU. Why each device. Async chunking headroom. INT8 size and score change. Temperature | `bench/results/` via `data.json`, `bench/RESULTS.md` |
| 8 | Results | Measured over random rounds, failures counted | Evaluation table: rounds, cycles, pick first try, verdict correct, placed as told, end to end, median cycle. Test positions ✓ / ✗ on the coverage map. Failures, one line each | `video/layouts/round_*_eval.json` |
| 9 | Limits and next steps | Where it's weak, and what we'd do next | Offline: unseen picks 8 / 13 (SmolVLA-v2), 6 / 13 (ACT). No grasp signal from the gripper. Laptop at 90–97 °C under load. Next: more data, empty-grasp re-pick from the inspection photo, more defect types | `MODEL_RUN_NOTES.md`, `WORK_LOG.md` |

### Before uploading

- [ ] `python3 video/scripts/build_data.py`, then `npm run deck` in `video/`.
- [ ] No yellow placeholders left; the footer has no draft line.
- [ ] Slides 3 and 7 name the models and devices actually used in the video and the demo.
- [ ] The PDF is under 20 MB.
