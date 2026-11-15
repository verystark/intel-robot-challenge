# Video plan

The plan for the submission video: what it has to prove, how we test it, what we film, and the
script. The tools (Remotion, data-driven graphics) are in [SUBMISSION.md](SUBMISSION.md) §5. The
live demo is in [PLAN_AND_SHOW.md](PLAN_AND_SHOW.md).

Draft 3, 2026-11-14, about 15:30 laptop time. The form closes at about **08:00 Sunday laptop
time**.

**Status (16:25 laptop time).** Built and checked, in `video/` ([README](video/README.md)):

| Done | Waiting for |
|---|---|
| All 8 scenes, data from `public/data.json`; yellow `[placeholders]` and a DRAFT banner for what's missing | Footage A1–A4, B1–B3 (`video/scripts/add_footage.sh`) |
| AI narration (Kokoro, `bm_george` by default), levelled; word-timed captions | Footage with our live voices (scenes 1 and 6) |
| Coverage map from the training data (scenes 3 and 7, thumbnail) | Evaluation rounds (`tools/random_layout.py`, `tools/eval_round.py`) |
| Draft render: `video/out/jenssenit_draft.mp4` (960×540, 2:10) | Quiet-laptop benchmarks; the filmed run's log, offset and segment times |
| Thumbnail: `video/out/thumbnail.png` | Repo link and team names in `video/facts.json` |

Length is 2:10 with the current narration; trim once the footage is in.

---

## 1. What we claim

**A VLA-driven cell that picks, inspects and sorts a variable number of bricks lying at random
positions, onto plates that can be anywhere within reach.**

- **Bricks:** any number on the table, at random positions and angles. Not one brick on a marked
  spot.
- **Plates:** movable. The sentence names a colour; the policy finds that plate wherever it is.
- **No coordinates in the code.** Picking and placing are learned by SmolVLA from teleoperated
  demonstrations. The only scripted motion is the inspection pose, and that's deliberate.
- **Defect check in the loop:** Anomalib PatchCore scores three views of each brick. Its verdict
  becomes the VLA's next task sentence.
- **All inference on the laptop,** with OpenVINO.

**Why this is our edge:** a replayed or hard-coded motion only works with one object in one place.
Most setups that work in a weekend are that. Ours copes with the table as it is.

**The risk:** this is also the least-tested part. Offline, SmolVLA-v2 headed the right way on only
8 of 13 picks at positions it hadn't seen. Nothing has run on the arm yet. So the video doesn't
assert generalisation; it measures it (section 3). If the numbers are weak, the claim shrinks to
fit them (section 10).

**What the training data covers** (`video/scripts/coverage.py`, forward kinematics on the
dataset of the model in `video/facts.json`). For SmolVLA-v2 and v2-long (`main-clean2`, 315
episodes): 155 grasps over roughly 32 × 40 cm in front of the arm, and 157 releases. **Both plates
appear on both sides of the centre line** (green 54 left / 28 right, orange 39 / 36; in the full
`main-clean3` set, in all three recording batches), so swapped plates are in the training data.
The arm test still has to confirm the swap works.

---

## 2. Style: technical, not a pitch

Model it on the videos robotics labs publish with their papers, not on a product ad. Intel's
judges are robotics engineers; they trust footage and numbers, and they discount adjectives.

| Do | Don't |
|---|---|
| Describe what's on screen, plainly: "Six bricks at random positions." | Slogans, rhetorical questions, "Here's the trick", three-word punchlines |
| Name the parts: SmolVLA, PatchCore, OpenVINO, NPU | "Cutting-edge", "revolutionary", "seamlessly" |
| Give numbers, with failures counted | Only the best take with no denominator |
| Corner labels: "Autonomous · 1×", "4×", "One take" | Music swells, whooshes, flashy transitions |
| One idea per scene, short captions | Text walls |
| A calm AI narrator over the graphics; our own voices in the real footage | An over-acted "announcer" voice; narration over the run |

**Audio has two layers:**

| Picture | What we hear |
|---|---|
| Graphics and the sped-up setup: diagrams, coverage map, tables, chips (scenes 2–5, 7, 8) | **AI narration:** one calm voice, generated from the script (section 13.4) |
| The real cell running (scenes 1 and 6) | **Our own voices, live on set:** short call-outs by the operator and whoever swaps the plates (section 7.1), plus the servos and the room |

The narrator explains; the real run speaks for itself. **No narration over the run:** the real
voices and sounds are part of the proof. The end card credits the narration as a synthetic voice.

No music, or a very low neutral bed under the graphics only.

---

## 3. The evaluation: how we prove it

One protocol gives us the video's numbers, the description's numbers and the live demo's story.

### 3.1 Setup per round

| Item | Rule |
|---|---|
| Bricks | 6 per round: 4 good, 2 with marker defects, mixed colours and sizes |
| Brick positions | `python3 tools/random_layout.py` draws them inside the area the training data covered, with random rotation, at least 8 cm apart centre to centre. `--outside N` puts N bricks outside that area on purpose. It prints a table and writes `video/layouts/round_NN.json` and `.svg` (the map) |
| Plates | Drawn by the same tool, where the training data released bricks, away from the bricks. In at least one round, swap them by hand mid-run |
| Measuring | Positions are in cm from the centre of the arm's turret: forward along a taped centre line, then sideways (left positive). **Tape the centre line once:** in Studio, set the follower's `shoulder_pan` to 0 (`loop/show_tool.py where` shows it), lower the gripper to the table and mark the point under its tip; the line from the turret centre through that mark is "forward" |
| Rounds | At least 3 (18 cycles); more if time allows |
| Takes | Phone A1 films every round in full (VIDEO_PLAN §6) |

### 3.2 What we record per cycle

After each cycle, answer four quick questions:

```bash
python3 tools/eval_round.py video/layouts/round_NN.json --run loop/runs/<run>
```

It asks which brick was picked (its number on the map), whether the pick worked first time, and
whether the brick went to the plate it was told; with `--run` the verdict and cycle time come from
the loop's log. The truth (good or defective) comes from the layout. It saves
`video/layouts/round_NN_eval.json` after every answer; `video/scripts/build_data.py` adds all
rounds up for the video.

### 3.3 What we report

| Metric | Example line |
|---|---|
| Pick success, first try | 15 / 18 |
| Inspection verdict correct | 17 / 18 |
| Placed on the plate it was told (the policy's part) | 16 / 18 |
| Correct end to end (judged right and placed right) | 14 / 18 |
| Median cycle time | 24 s |
| Failures, one line each | "C7: grasp slipped on a 2×2 brick lying on its side" |

Per-stage numbers matter: they show we know where it fails. The **coverage map** (section 8)
shows the trial positions against the positions in the training data.

---

## 4. Structure (about 2:00)

| Time | Scene | What it shows |
|---|---|---|
| 0:00–0:08 | 1. Cold open | The cluttered table, plates at odd spots, the arm picking. "Autonomous · 1×" |
| 0:08–0:21 | 2. The task | Bricks and plates placed by a random draw (4×). The spec list: variable count, random positions, movable plates, no coordinates in code |
| 0:21–0:34 | 3. The policy | SmolVLA's inputs and outputs, the training data, the coverage map |
| 0:34–0:47 | 4. Inspection | The scripted pose, three angles, heatmaps, score bands |
| 0:47–0:55 | 5. Verdict → VLA | The verdict typed in as the next task sentence; the arm goes to that plate |
| 0:55–1:38 | 6. The run | One take: clearing the table, the plates swapped mid-run |
| 1:38–1:50 | 7. Results | The evaluation table over all rounds, failures included |
| 1:50–2:00 | 8. Compute | Model, device and latency; end card |

The full words are in section 13.

---

## 5. The run (scene 6)

The longest scene, and the proof.

### 5.1 The take must show

- [ ] **The whole cell in one locked frame:** pick area, arm, inspection camera, both plates and
      the **laptop screen** with the loop window. The screen's clock ticking shows there are no cuts.
- [ ] **A full round: the table cleared,** 6 bricks, with at least one defective brick going to
      orange.
- [ ] **A plate swap mid-run:** between two cycles a teammate swaps the plates, in shot, and the
      next brick still goes to the right colour. Include it only if it worked in testing.
- [ ] **Nobody touches the arm or the laptop.** The leader arm lies still in frame.

### 5.2 In the edit (about 40 s)

| Part | Speed | Length |
|---|---|---|
| The first cycle, every overlay from the log: stage, scores, verdict, task sentence | 1× | ~18 s |
| Cycles 2–3 | 4×, labelled | ~10 s |
| The plate swap and the next cycle's placement | 1× | ~7 s |
| The rest until the table is empty; a counter | 4×, labelled | ~5 s |

A corner badge throughout: **One take · no cuts**. The speed label changes with the speed.

### 5.3 Optional, only if it works 3 of 3 times in testing

| Moment | What it shows |
|---|---|
| Someone outside the team draws the defect on a brick just before the round | A defect type nobody trained on |
| An unsure view getting its second look | Recovery from uncertain detections |
| Bricks touching each other | Clutter |
| NPU busy rising during the pick (`bench/sysmon.py`) | The NPU is really used (if ACT picks on the NPU) |

### 5.4 The unedited take

Upload the whole round, as filmed, as a second unlisted video. Link it in the form's "Other link"
and in the README.

---

## 6. Shot list

| ID | Shot | Camera | Needs the loop | Status |
|---|---|---|---|---|
| A1 | Every evaluation round, in full, locked wide, screen in frame | Phone 1 | **Yes** | |
| A2 | Close on the inspection point and the plates during rounds | Phone 2, if we have one | **Yes** | |
| A3 | Screen recording of the loop window during rounds | GNOME recorder | **Yes** | |
| A4 | Setup of a round: bricks and plates placed from the random draw | Phone 1 (same position) | No | |
| B1 | A hand moves the leader arm and the follower copies (teleoperation) | Phone, both arms in frame | No | |
| B2 | Studio: recording page, the dataset, a training job, the Models page with the OpenVINO export | Screen recording, 3–4 s each | No | |
| B3 | Close-ups: a marked brick, the inspection camera, the plates | Phone | No | |
| C1 | Grid of recorded episodes showing bricks and plates in different places | Made by code from `main-clean3` | No | |
| C2 | Coverage map, heatmaps, diagrams, tables, chips | Made by code | No | |

**From now on, phone 1 films every test on the arm.** The best take may be an unplanned one.

---

## 7. Filming guide

| Topic | Rule |
|---|---|
| Phones | Landscape, 1080p, on a stand or clamp, never handheld. Lock exposure and focus (long-press) |
| Flicker | LED lamps flicker at 50 Hz here. Film a 5 s test: if dark bands roll through the picture, use 25 or 50 fps or the phone's anti-flicker setting |
| Frame A1 | From the side opposite the inspection camera, high enough to see the whole pick area and both plates. Laptop screen at the edge, readable. Nothing moving in the background. **Same position for every round**, so rounds can be compared |
| Light | The inspection lamp as during photo collection. Nobody stands between the lamp and the inspection point |
| Sound | Keep the phone's sound. No music in the room |
| Slate | At the start of every take, say the round number to the phone and clap once in view, to sync with the screen recording |
| Screen | Notifications off. Nothing personal or with credentials visible. Loop window full screen (`f`) |
| People | Ask before filming anyone outside the team. Avoid name badges and other teams' screens |
| Files | Copy to `~/video-raw/<round>/` (outside the repo). Note in `~/video-raw/takes.md`: round, time, loop run folder, what happened |

**Overlays come from the log:** each round has a `loop/runs/<run>/` folder. One time offset per
take lines up the log with the footage, so the scores and timings on screen are that round's real
values.

### 7.1 Our voices on set

The real footage carries our own voices. They make it obviously real.

| Topic | Rule |
|---|---|
| Who speaks | The operator (at the laptop) and whoever swaps the plates. Everyone else stays quiet during a take |
| What | Short call-outs of what's happening, in your own words, in English. Not memorised narration, not performed for the camera |
| Mic | The venue is loud. A second phone in the speaker's shirt pocket, or on the table in front of them, records a voice memo. The clap at the start syncs it. Use phone 1's mic only if the room is quiet |
| Honesty | Say what really happened, including a failure: "That one slipped, it's retrying" |

Call-outs that work (say them your own way):

- Before a round: "Round three. Positions from the draw. Two defective bricks: the white one and
  the blue one."
- At the start: "Starting the loop. Hands off."
- At a plate swap: "Swapping the plates now."
- At the end: "Table's clear. Five of six right; the yellow one went to the wrong plate."

---

## 8. Graphics (drawn by code)

| Graphic | Data | Scene |
|---|---|---|
| Spec list: "Bricks: variable · Positions: random · Plates: movable · Coordinates in code: none" | | 2 |
| The random draw for the round, as a small top-view map | The layout script's output | 2 |
| SmolVLA diagram: top camera, wrist camera, joint state, task sentence → 50-action chunk | | 3 |
| **Coverage map:** grasp points (gripper closes) and release points (gripper opens) from every training episode, as dots over the workspace; the trial positions on top, ✓ or ✗ | `video/scripts/coverage.py` (done); test positions and ✓ / ✗ from the evaluation rounds | 3, 7 |
| Three inspection views with heatmaps; the score bar with the good / unsure / defective bands | `loop/runs/<run>/` | 4, 6 |
| The task box: the verdict sentence typed in, going into the SmolVLA block | `cycles.jsonl` | 5, 6 |
| Stage, score and verdict overlays during the run | `cycles.jsonl` | 6 |
| The evaluation table | `video/layouts/round_*_eval.json` | 7 |
| Model / device / latency chips | `bench/results/` | 8 |

**Look:** dark grey background, white text, one accent colour per stage (the same as the loop's
screen), one sans-serif font, a monospace font for sentences and numbers. No 3D, no glow, no
bouncing. Diagrams appear part by part, with short cuts or simple fades.

**Thumbnail:** a frame from the run, with the cluttered table and both plates visible, and a small
caption: "random bricks · movable plates · VLA + Anomalib".

---

## 9. Honesty rules

- "No cuts" only on footage with no cuts. Real time unless labelled with its speed.
- Every number from a log, a benchmark or the evaluation files. Offline numbers say "offline".
- Success rates count every cycle, failures included, with the failures listed.
- Positions come from the random draw. If we re-did a round, say so.
- Nothing teleoperated is shown as autonomous.
- If only parts work, say "stage by stage" (section 10).

---

## 10. Fallbacks

Decide at **03:00 laptop time** at the latest.

| Level | When | The video claims |
|---|---|---|
| **A** | Random rounds mostly succeed | Everything in section 1, with the evaluation table |
| **B** | Picks fail at some positions | "Random positions inside the area covered by our training data", with the coverage map showing where it works and where it doesn't |
| **C** | Plate swaps fail | Drop the swap. Plates stay where they were during recording; say so |
| **D** | The full loop doesn't run on the arm | "Stage by stage", labelled: Studio running the policy on the arm, `--inspect-only` on the arm, the loop in simulation. Say plainly what's missing |

---

## 11. Timeline (laptop time)

| By | Station | Laptop (code) |
|---|---|---|
| Now | Film B1–B3. Every arm test is filmed | Video project, coverage map from the training data, diagrams |
| First working cycles | The first random round; film everything | Draft render with placeholders |
| 02:00 | At least 3 rounds done and logged | Footage and numbers dropped in |
| **03:00** | **Decide level A–D** | |
| 04:00 | Watch the rough cut on a phone, once with sound off | Rough cut (render only while the arm is idle) |
| 05:30 | Final video and the unedited take uploaded, unlisted; links checked | Final render, thumbnail |
| 06:30 | Form complete with real numbers, saved as a draft | |
| Before 08:00 | Final submit | |

| Role | Job |
|---|---|
| Director | One teammate decides what's in and signs off the cut |
| Camera | Phones, slates, files, `takes.md` |
| Station | Runs the rounds; answers `tools/eval_round.py` after each cycle |
| Voices | On set: the operator and the plate swapper, live. Narration: AI voice, generated from the script by Claude |
| Editor (Claude) | Builds and renders the video from code, fills the numbers from the logs |

---

## 12. Open questions

- [x] Narration voice: **default bm_george** (British, male). To change it, listen to
      `video/out/voice-samples/all_voices.wav` (bm_george, bm_lewis, bf_emma, am_michael, af_heart)
      and rerun `tts/make_voice.py --voice <name>`.
- [ ] How many phones (one is enough, two is better)? Who directs, who films?
- [ ] Is there a video length limit (Guide tab or a mentor)?
- [x] Did the training data include swapped plates? Yes: both plates on both sides in every batch (section 1).
- [ ] Can Claude install Remotion and start the draft?

---

## 13. Script

Draft 3. Plain and specific; it describes what is on screen. Placeholders in `[brackets]` are
filled from the logs (13.2).

- **[AI]** lines are the generated narration, about 160 words (about 65 s). In the render each
  scene is as long as its planned time or its narration, whichever is longer, so the times below
  are nominal.
- **[LIVE]** lines are said by us on set, in our own words (section 7.1). The quoted examples are
  only a guide.

### 13.1 Wording rules

- Say what the viewer is looking at, then one fact they can't see.
- Numbers, names and units, not adjectives.
- Short, normal sentences. Contractions are fine. No em dashes, no rhetorical questions, no
  punchline endings.
- Read it aloud before recording. Change anything you wouldn't say to a colleague.

### 13.2 Placeholders

| Placeholder | Meaning | Source |
|---|---|---|
| `[EPISODES]` | Episodes in the dataset of the model actually used (`main-clean3`: 486, `main-clean4`: 424, `main-clean2`: 315) | Studio |
| `[R]`, `[M]` | Random rounds and cycles in the evaluation | `video/layouts/round_*_eval.json` |
| `[P]`, `[I]`, `[S]`, `[E]` | First-try picks, correct verdicts, bricks placed where the policy was told, correct end to end | `video/layouts/round_*_eval.json` (`tools/eval_round.py`) |
| `[X]` | Median cycle time, seconds | `cycles.jsonl` |
| `[SORT_MS]`, `[INSPECT_MS]`, `[PICK_MS]` | Median latency of SmolVLA per chunk, Anomalib per view, the pick model per chunk | `bench/results/` |

An episode is a pick or a sort, so `[EPISODES]` is not the number of full demonstrations.

### 13.3 Scenes

#### Scene 1: Cold open (0:00–0:08)

| | |
|---|---|
| **Picture** | A1 wide: six bricks scattered, plates at odd spots. The arm reaches for one and lifts it |
| **On screen** | Corner: "Autonomous · 1×". Lower left, small: "Jenssenit · Intel Physical AI Challenge, Junction 2026" |
| **Voice** | **[LIVE]** The operator, on set, before starting, e.g. "Six bricks, random positions, two with marker defects. Plates wherever. Starting the loop." |

#### Scene 2: The task (0:08–0:21)

| | |
|---|---|
| **Picture** | A4 at 4×: a teammate places bricks and plates following the random draw, shown as a small map in the corner |
| **On screen** | "Setup · 4×". The spec list builds line by line: "Bricks: variable count · Positions: random · Plates: movable · Coordinates in code: none" |
| **Voice** | **[AI]** "A recorded motion only works if the brick is always in the same place. Here nothing is fixed, and there are no coordinates in our code. Picking and placing are learned." |

#### Scene 3: The policy (0:21–0:34)

| | |
|---|---|
| **Picture** | Pick footage on the left. On the right, the diagram: top camera, wrist camera, joint state and "Pick up the brick." → SmolVLA → 50-action chunk. Then B1 (teleoperation) for 2 s and the coverage map |
| **On screen** | "SmolVLA · fine-tuned in Physical AI Studio" · "`[EPISODES]` teleoperated episodes, bricks and plates moved between them" |
| **Voice** | **[AI]** "The policy is SmolVLA, a vision-language-action model. Camera images, joint positions and a task sentence go in; joint actions come out. It's fine-tuned on `[EPISODES]` teleoperated episodes." |

#### Scene 4: Inspection (0:34–0:47)

| | |
|---|---|
| **Picture** | The scripted move to the inspection pose. The wrist turns; three views appear with their heatmaps; the score bar fills toward its band |
| **On screen** | "Scripted: fixed pose, 3 angles" · "Anomalib PatchCore · trained on good bricks only · `[INSPECT_MS]` ms per view" · bands "good / unsure / defective" |
| **Voice** | **[AI]** "Inspection is the one scripted step. A fixed pose and three wrist angles mean the anomaly model sees every brick the same way. Anomalib's PatchCore, trained only on good bricks, scores each view." |

#### Scene 5: Verdict → VLA (0:47–0:55)

| | |
|---|---|
| **Picture** | The task box: the sentence types out and moves into the SmolVLA block. Cut to the arm carrying the brick to the orange plate |
| **On screen** | `task: "The brick is defective. Put it on the orange plate."` |
| **Voice** | **[AI]** "The verdict becomes the VLA's next task sentence. The model then finds the plate of that colour, wherever it is." |

#### Scene 6: The run (0:55–1:38)

A1, one take. Corner badge: "One take · no cuts", with the speed label. **No narration in this
scene:** only our live voices, the servos and the room.

| Beat | Picture | On screen | Voice |
|---|---|---|---|
| 6a (0:55–1:15) | Cycle 1 at 1×, the whole cycle | Overlays from the log at each moment: stage, scores per view, verdict, task sentence | **[LIVE]** Operator: "Hands off." |
| 6b (1:15–1:25) | Cycles 2–3 | "4×" · "Cycle 2 / 6", "3 / 6" | None |
| 6c (1:25–1:32) | A teammate swaps the plates; the next brick goes to the right colour at its new spot | "1×" · "Plates swapped by hand" · "It goes by colour, not by the old position" | **[LIVE]** Plate swapper: "Swapping the plates now." |
| 6d (1:32–1:38) | The rest until the table is empty | "4×" · "Table cleared · `[N]` / 6 on the correct plate" | **[LIVE]** Operator says the result as it is, failures included |

#### Scene 7: Results (1:38–1:50)

| | |
|---|---|
| **Picture** | The evaluation table builds row by row. Beside it, the coverage map with the trial positions marked ✓ or ✗ |
| **On screen** | "`[R]` random layouts · `[M]` cycles" · "Pick, first try `[P]`/`[M]`" · "Verdict correct `[I]`/`[M]`" · "Correct plate `[S]`/`[M]`" · "Median cycle `[X]` s" · the failures, one line each |
| **Voice** | **[AI]** "Across `[R]` random layouts and `[M]` cycles: `[P]` picks worked on the first try, the inspection was right `[I]` times, the policy put `[S]` bricks on the plate it was told, and `[E]` were right end to end." |

#### Scene 8: Compute and end (1:50–2:00)

| | |
|---|---|
| **Picture** | Three chips (CPU, GPU, NPU) with the model on each and its latency. Then the end card |
| **On screen** | "SmolVLA · GPU · `[SORT_MS]` ms per chunk" · "PatchCore · GPU · `[INSPECT_MS]` ms per view" · "Loop and scripted motion · CPU" · (if ACT picks: "ACT pick · NPU · `[PICK_MS]` ms") · "OpenVINO · Core Ultra X9 388H". End card: "Jenssenit", repo link, team names, and small: "Narration: synthetic voice (Kokoro)" |
| **Voice** | **[AI]** "All inference runs on the laptop with OpenVINO. SmolVLA takes `[SORT_MS]` milliseconds per chunk on the GPU; PatchCore, `[INSPECT_MS]` per view." (Add "The ACT pick runs on the NPU." if used.) |

### 13.4 The AI narration

| Topic | Rule |
|---|---|
| Voice | **Kokoro-82M**, local on the laptop's CPU (Apache 2.0). One even, mid-pace English voice for the whole video. Claude renders scene 3 in 2–3 voices; the team picks one |
| Alternative | A cloud voice (e.g. ElevenLabs) if a teammate has an account. Only the script text leaves the laptop |
| Pace | About 2.5 words per second; 0.3 s between sentences |
| Captions | From the voice's word timestamps; normal spelling |
| Mix | Narration at full level, room and servo sound at about 25% under it. Scenes 1 and 6 have no narration, so their live sound stays at full level |
| Rendering | Only while the arm is idle |

Pronunciation: the narrator gets the spelling on the right, the captions keep the normal one.

| Word | Text for the voice |
|---|---|
| Anomalib | `Anomah-lib` |
| OpenVINO | `Open Veeno` |
| SmolVLA | `Smol V L A` |
| `[EPISODES]` and other numbers | Written as words, e.g. `four hundred eighty-six` |
| Jenssenit | Unchanged: plain English, JEN-sen-it |

### 13.5 If the plate swap doesn't work

Cut 6c. Change scene 2's spec line to "Plates: placed as during recording". Give the 7 s to 6a.

### 13.6 Before the final render

- [ ] Every placeholder filled from the evaluation files, a log or a benchmark; none left in captions.
- [ ] The claims match the level chosen in section 10.
- [ ] The device chips match `loop/cell_config.json` during the take.
- [ ] "No cuts" really has no cuts; every sped-up part is labelled.
- [ ] Anyone outside the team who appears has agreed.
- [ ] Watched once on a phone with the sound off, and once with sound.
- [ ] Read aloud by someone who didn't write it; any wording that sounds generated is rewritten.
- [ ] The end card credits the synthetic narration.

### 13.7 The video project

The video is built from code in [`video/`](video/README.md): Remotion scenes, the narration
script `video/script.json`, the facts `video/facts.json`, and the voice tool `video/tts/`.
`video/README.md` has the commands.
