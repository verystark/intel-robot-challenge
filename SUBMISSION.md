# Junction submission and video

What Junction's form asks for, what we put in each field, and how we make the video.

> **The paste-ready text for every field is in [JUNCTION_SUBMISSION_TEXT_V2.md](JUNCTION_SUBMISSION_TEXT_V2.md)** (pi0.5,
> measured on the arm). Sections 2 and 3 below are earlier drafts; where they differ, V2 wins. The form as
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

Nine 16:9 pages, built on tonight's measured arm runs with pi0.5 (`Pi0.5-v2-8gpu`). Technical,
plain wording (the rules in [VIDEO_PLAN.md](VIDEO_PLAN.md) §2 and §13.1), failures counted.
Updated 2026-11-15 about 00:30 laptop time.

### How it's built

In the video's Remotion project (`video/src/deck/`), one still per page, combined into
`video/out/jenssenit_deck.pdf` (`cd video && npm run deck`). Commands in
[video/README.md](video/README.md).

- **Data:** every number comes from `video/public/data.json`, which passes `video/facts.json`
  through: `results` (tonight's runs), `inspection`, `policy`, `models`, plus
  `public/coverage.json` and the run's photos in `public/inspect/`. Change a fact there and
  re-render; nothing is typed into the slides.
- **Look: screens of our own operator HMI** (`loop/dashboard`, after ISA-101), not a slide
  template. Each page is a "screen" of CELL 01: the same grey, faceplates with title bars,
  uppercase tags, monospace values, the process mimic, alarm and event tables, a trend display.
  Colours come from `loop/dashboard/palette.json`; colour only means plate identity or an
  abnormal state. Pages are tabs F1–F9. Code: `video/src/deck/hmi.tsx` (building blocks),
  `video/src/deck/Deck.tsx` (pages).
- **What's still open shows as an alarm:** a P2 `DATA.DRAFT` banner on every page lists it
  (now: landing plate not counted, PatchCore CPU / NPU times measured while the loop ran, team
  names), and missing values are amber badges.

### The pages

| # | Page | The one point | On it | Source |
|---|---|---|---|---|
| 1 | SYSTEM | A pi0.5 VLA picks and sorts randomly placed bricks onto movable plates, Anomalib checks every brick, all on one laptop | System description, key facts incl. 38 / 41 verdicts and 13 / 13 defects rejected, workspace coverage | `facts.json`, `coverage.json` |
| 2 | TASK | Nothing is in a fixed place, including the target surface | Spec table (bricks, target surface movable and named by colour, no coordinates in code), the three exact sentences, where the plates stood in training: green 84 left / 45 right, orange 51 / 62 | `coverage.json` (main-clean4) |
| 3 | PROCESS | Learned where the scene varies, scripted where it must not | Plant mimic: pick area → SO-101 arm (pi0.5, 240 ms chunk) → inspection station (brick square, ±90°, bands 0.45 / 0.56) → verdict → movable plates. Sequence with medians on the arm (7.6 / 3.9 / 5.7 s), interlocks | `facts.json`, `cell_config.json` |
| 4 | POLICY | pi0.5 fine-tuned in Physical AI Studio on 424 teleoperated episodes | Inputs → pi0.5 → 50 × 6 actions. Training: 8 × H100, 4 epochs, 5,116 steps, val split 0, augmentation off. Coverage map | `facts.json` `policy`, MODEL_RUN_NOTES.md |
| 5 | DATA | Raw data kept, labels checked, findings fixed | Pipeline (501 raw → 486 → main-clean4 424; new one-clean 298, labelled not measured). Findings as events (checkpoint trap, pick endings, top camera moved). Model history table, every model to tonight's | DATASET_MAIN_CLEAN3.md, MODEL_RUN_NOTES.md, Studio DB |
| 6 | INSPECTION | Only the brick is scored | Inspection faceplate with two real bricks from run `224325` (C69 clean 0.006 / 0.000, C34 marker 0.963), gauge with bands, settings (crop, stops, held-out separation 0.491 vs 0.588, 641 photos, INT8). Before / after heatmaps: the first live failure (whole crop, 1.0) vs the brick square | `facts.json` `inspection`, `loop/runs/20261114_201611`, `_224325` |
| 7 | COMPUTE | Each model where it runs, measured | Tonight on the arm: pi0.5 240 ms GPU, PatchCore 34 ms GPU (CPU 36 / NPU 119, measured while the loop ran). Earlier models' benchmark (SmolVLA-v2, ACT), labelled. Log-scale bars. Chunk timing: 833 ms budget, 593 ms to spare | `facts.json`, `bench/results/` |
| 8 | RESULTS | Measured on the arm, failures counted | Production faceplate: 41 bricks, 38 / 41 verdicts, 13 / 13 defects rejected, 25 / 28 clean accepted, 41 / 55 picks (+6 stopped), 20.2 s per brick. Failures as events. Trend of worst stop score per brick against the bands | `facts.json` `results`, run `224325` cycles |
| 9 | LIMITS | Where it's weak, and the work orders | Alarms from the failures (pick misses: top camera moved, no augmentation; 3 false rejects; blue marker near the limit; two faces only; no grasp signal; 91 °C peak). Work orders: realign camera + augment, more photos of long / tall bricks, test Pi0.5-one-8gpu-b, log landings, empty-grasp re-pick | `facts.json` `results` |

### Before uploading

- [ ] `python3 video/scripts/build_data.py`, then `npm run deck` in `video/`.
- [ ] If more cycles are counted, update `video/facts.json` `results` first.
- [ ] Team names in `video/facts.json`; the banner then lists only real gaps.
- [ ] Pages 3, 4 and 7 name the model actually used in the video and the demo.
- [ ] The PDF is under 20 MB (now 3.2 MB).
