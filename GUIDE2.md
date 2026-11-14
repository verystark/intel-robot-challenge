# Guide 2: recording plan with scripted showing

Written 2026-11-14 morning. This updates [GUIDE.md](GUIDE.md) for how we record and run the arm.
Where the two disagree, **this file wins** for sections 1, 7, 9 and 10 of GUIDE.md (the flow,
recording, inspection photos, the loop). Everything else in GUIDE.md still applies: station,
setup, recording rules, training settings, OpenVINO, fallbacks, troubleshooting.

**What changed:**

- **The showing is scripted, not learned.** The policy only picks the brick up and lifts it. A script
  moves the arm to one saved show pose, takes the photos and turns the brick.
- **No typing while recording.** The Task box is never touched. Sort episodes get their sentence
  afterwards from a script.
- **No `layout.py` needed.** Simple alternation rules decide the bowl, the brick and its position.
- **Inspection photos come from the show tool,** at exactly the pose and turns of the demo.

---

## 1. Learned vs scripted

| Part | How | Why |
|---|---|---|
| Grab the brick wherever it lies, lift it | **Learned** (SmolVLA, or ACT) | Different every time: position, rotation, other bricks |
| Move to the camera | **Scripted:** one saved arm pose | Should be identical every time |
| Show the brick: photo, turn the wrist 180°, photo | **Scripted** | Identical photos make Anomalib reliable ([ANOMALY_DATA_REVIEW.md](ANOMALY_DATA_REVIEW.md): "every photo in a different arm pose" caused false rejects) |
| Unsure → turn 90°, photo again | **Scripted** | Exact re-check, no demonstrations needed |
| Put it in the named bowl | **Learned** (SmolVLA + the sentence) | The bowl can move; the sentence decides which one |

Scripting the showing also makes it faster (a direct move, no policy calls) and makes the learned
pick shorter and easier to learn.

---

## 2. The run (robot on its own, at the demo)

```text
HOME ──SmolVLA──▶ LIFTED ──script──▶ SHOW POSE ──script──▶ photo, turn 180°, photo ──Anomalib──▶ verdict
     "Pick up the                      (saved)
      brick and lift it."
                                                   verdict ──script──▶ sentence ──SmolVLA──▶ BOWL ──▶ HOME
                                                                 "The brick is defective.
                                                                  Put it in the orange bowl."
```

1. **Pick:** SmolVLA with "Pick up the brick and lift it." runs until the arm holds still with the
   brick lifted (or a timeout).
2. **Show:** the script moves the arm straight up a little, then to the saved show pose.
3. **Inspect:** photo, turn the wrist 180°, photo, turn back. Anomalib scores both photos.
   - Either photo defective → **defective**.
   - Both clearly good → **good**.
   - Otherwise **unsure** → turn 90°, photo, score again. Still unsure → defective (reject when in doubt).
4. **Sort:** reset the policy's action queue, then SmolVLA with the verdict's sentence:
   "The brick is good. Put it in the blue bowl." or "The brick is defective. Put it in the orange bowl."
   It runs until the arm holds still at home.
5. **Log** every stage's time, then the next brick.

The robot never decides the bowl itself: Anomalib's verdict is in the sentence, and the policy obeys
the sentence.

---

## 3. The dataset: one flow = 2 episodes, 3 categories

Everything goes into **one** Studio dataset, `cell-v1`, in environment `policy-cell` (cameras `top` and
`wrist`). Each flow is recorded as **two episodes**, cut live while the arm holds still:

```text
A's motion:  home ─▶ grab ─▶ lift ─▶ [hold] ┄┄ move into the green box ┄┄ [hold] ─▶ bowl ─▶ home ─▶ [hold]
B's keys:    →                         →                                     →                         →
           start                    accept   (not recorded)                start                    accept
             └──── episode: PICK ──────┘                                     └──── episode: SORT ───────┘
```

At the end the dataset holds **three categories**, set by each episode's sentence:

| Category | Sentence | Share |
|---|---|---|
| Pick | "Pick up the brick and lift it." | ~50% |
| Good sort | "The brick is good. Put it in the blue bowl." | ~25% |
| Defective sort | "The brick is defective. Put it in the orange bowl." | ~25% |

**How it learns which bowl:** training works like flashcards. The model is shown the camera images,
the arm position and the sentence, and must reproduce the recorded motion. The only thing that
consistently tells "blue" sort episodes from "orange" ones is the sentence, so it learns that the word
in the sentence decides the bowl. That only works if **every sort episode's sentence matches the bowl
the arm really went to.**

**SmolVLA trains on all three categories at once.** Splitting by category is only needed for ACT,
which can't read sentences (section 8).

---

## 4. Before recording (once)

- [ ] **Clean up Studio datasets:** delete `eka` (it's in `sorting-cell`, which has no cameras, so its
      episodes would have no images), `pick-v1` and `gtesr`.
- [ ] **Create `cell-v1`:** environment `policy-cell`, default task exactly
      `Pick up the brick and lift it.`
- [ ] **Modal:** the login is done; still click **Settings → Training Targets → Modal → Deploy and connect**.
- [ ] **Hugging Face token** (read-only) in **Settings → General → Hugging Face**.
- [ ] **Servo check** with no Studio session open:
      `physical-ai-studio/application/backend/.venv/bin/python tools/servo_check.py` (and `... leader`).
- [ ] **Table** (GUIDE.md section 5): 3×3 pick grid, bowl spots 1–4, blue bowl on spot 1, orange on
      spot 2, lamp, plain backdrop behind the show point, nothing moving in the top camera view.
- [ ] **Green box:** `cd anomaly && ../.venv/bin/python capture.py`. Set the box once at the show point
      (GUIDE.md section 9), then leave the window where A can see it. It's A's target for the show pose.
- [ ] **Wrist check at the show point:** turn the wrist 180° each way by hand. It must not hit its limit
      or pull the wrist camera's cable. If it does, the script will use ±90° instead.
- [ ] **Practise 5–10 flows without recording.**

**Grid squares**, numbered as seen in Studio's top camera view:

```text
far row      7  8  9
middle row   4  5  6
near row     1  2  3      (near = closest to the robot's base)
```

---

## 5. Recording rules (instead of `layout.py`)

| What | Rule |
|---|---|
| **Bowl** | Alternate every flow: **blue, orange, blue, orange, …** The first flow of a session is always blue. |
| **Brick type** | Change every **2** flows: good, good, defective, defective, … |
| **Brick position** | Squares 1 → 9 in order. After each full round, turn the brick a further 45° (0°, 45°, 90°, 135°). |
| **Bowls** | Take the brick out of the bowl after every flow. Both bowls look the same at the start of every flow. |
| **Sessions and batches** | Always stop after an **orange** flow, so the next start is blue. |
| **Discards** | ← discards. Redo the same flow with the same bowl. Only accepted episodes count. |

**Why these rules:**

- Bowl and brick type change on different rhythms, so every combination (good→blue, good→orange,
  defective→blue, defective→orange) comes up equally often. If good bricks always went to blue, the
  robot could learn "good-looking brick → blue" instead of reading the sentence.
- Empty bowls: otherwise the brick count gives the answer away (before every orange flow, blue would
  hold one brick more).
- Stopping after orange keeps the alternation unbroken across sessions, which the labelling relies on.

---

## 6. One flow, step by step

**Roles:** A only uses the leader arm, both hands, and says "done" when the arm is still.
B does everything else: keys, table, counting.

| Step | Person A | Person B |
|---|---|---|
| Set up | Arm at home, still | Brick and bowl as the rules say; bowls empty |
| Pick: start | | Click an empty part of the Studio page, press **→** |
| Pick | Grab the brick, lift it about 10 cm straight up, hold still, "done" | Count one second, press **→** (accept) |
| Hand-over (not recorded) | Move the brick into the green box, hold still, "done" | |
| Sort: start | | Press **→** |
| Sort | Into this flow's bowl, open, back home, hold still, "done" | Count one second, press **→** (accept) |
| Reset | | Take the brick out of the bowl, next flow |

- **Never touch the Task box.** Every episode is saved with the default pick sentence; the sort
  episodes get their sentence afterwards (section 7).
- **The arrow keys don't work while the cursor is in the Task box** (Studio ignores shortcuts while you
  type). If they do nothing, click an empty part of the page.
- **Discarded pick:** arm home, brick back in the same place, redo. **Discarded sort:** bring the brick
  back into the green box (not recorded), redo with the same bowl.
- **Every ~10 flows** (stop after an orange one): leave the recording view, run the relabel script
  (section 7), replay a couple of episodes (joint-graph spikes, frozen frames), rest the follower.

**Stages** (from Studio's recording guide: add variety one stage at a time, train and test after each):

| Stage | Flows (episodes) | What changes |
|---|---|---|
| 1 | ~50 (~100) | One brick, squares 1–9, bowls fixed on spots 1 and 2 |
| 2 | ~30 (~60) | Plus 1–2 other bricks further from the robot; the brick to pick is in squares 1–6. Always pick the one nearest the robot. |
| 3 | ~40 (~80) | Bowls move to a new layout every 10 flows: spots (1,2), (2,1), (3,4), (4,3) for (blue, orange) |

---

## 7. Labelling: `recording/relabel.py` (to build)

Run it after each batch, **with the recording view closed**: Studio refuses to change a dataset while a
session has it open (the session works on a copy).

What it does, through Studio's API (`PATCH /api/dataset/{id}/episodes/{index}`, the same call as the
edit icon in the dataset view):

1. Reads all episodes of `cell-v1` in order.
2. **Checks first, changes nothing if anything is off:**
   - the episodes alternate pick, sort, pick, sort (a pick ends lifted away from home; a sort ends back
     at home), using the recorded arm positions;
   - each blue/orange pair of sort episodes dropped the brick in clearly different directions (the arm
     position when the gripper opened), so the bowl alternation wasn't broken.
3. Sets the sentences: pick episodes keep "Pick up the brick and lift it."; the 1st, 3rd, 5th… sort
   episodes get the blue sentence and the 2nd, 4th, 6th… get the orange one.
4. Prints a summary: how many of each category, and any episode it flagged.

If it flags something, check those episodes in the dataset view, delete or fix them, and run it again.

---

## 8. Training

- **SmolVLA on all of `cell-v1`** after each stage: settings in GUIDE.md section 8 (Modal A100,
  camera mapping `top` → Overview and `wrist` → Gripper, 5–10 epochs, augment images on).
- **Test with Run model:** "Pick up the brick and lift it." from home with bricks across the grid;
  each sort sentence starting from the green box. Pass: 7/10 or better.
- **After ~20 flows:** train a short run and measure its speed on the laptop (OpenVINO, GPU). That shows
  early whether ACT should do the pick ([policy/ACT_PIPELINE.md](policy/ACT_PIPELINE.md)).
- **ACT for the pick (option):** make a pick-only dataset from the pick category (export → split →
  import, GUIDE.md section 12; not yet tested) and train ACT on it. SmolVLA keeps the sort, so the
  verdict still steers a VLA.

---

## 9. Inspection photos: the show tool (to build)

The show tool runs the same scripted showing as the demo, so the photos match it exactly.

**Collect mode** (Studio must not be using the arm; someone at the station confirms the workspace is
clear before it moves):

1. The tool moves the arm to the saved show pose and opens the gripper.
2. B puts a brick between the jaws, gripped the way the robot grips (across the narrow side, roughly
   centred, small natural variations).
3. B presses `g` (good, training), `t` (good, test only) or `b` (defective). The tool closes the
   gripper, takes a photo, turns the wrist 180°, takes a second photo, turns back and opens the gripper.
4. About 10 seconds per brick.

| Folder | Bricks | Photos |
|---|---|---|
| `normal` | ~150 good, every colour and size | ~300 (two views each) |
| `test_normal` | ~20 other good ones | ~40 |
| `abnormal` | ~30 defective: several marker types and sizes; keep one type out of training | ~60 |

Then `cd anomaly && ../.venv/bin/python train_export.py`. Set the good / unsure / defective score bands
from the `test_normal` and `abnormal` scores.

**Saving the show pose:** the same tool saves the current arm position as the show pose: A teleoperates
the brick into the green box in Studio, then the tool records the follower's joint angles once Studio
has let go of the arm.

---

## 10. To build (Claude on the station laptop)

| # | What | Moves the arm? |
|---|---|---|
| 1 | `recording/relabel.py`: checks and sets the sort sentences (section 7) | No |
| 2 | Show tool: save the show pose, move to it, photo–turn–photo, collect mode (section 9) | **Yes:** someone at the station must confirm the workspace is clear |
| 3 | `loop/run_cell.py`: the full run (section 2), with a stop key and timing log | **Yes:** same |

Safety for anything that moves the arm: slow moves, a stop key, someone with the follower's 12 V plug
in reach, and no runs over SSH without someone watching.
