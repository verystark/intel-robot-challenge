# Dataset `main-clean3`

The team's biggest cleaned dataset: 486 episodes, built from the raw recordings in `main`.
Reviewed and checked 2026-11-14, 13:30. Use this file before training on it.

## At a glance

| | |
|---|---|
| Studio dataset | `main-clean3` (project `intel`, environment `sorting-cell`) |
| ID | `ba1139d1-a28c-40bf-bc44-3fb1800e24f6` |
| Folder | `/home/intel/.local/share/physicalai/datasets/ba1139d1-a28c-40bf-bc44-3fb1800e24f6` |
| Size | 486 episodes, 96,454 frames at 30 fps (53.6 min) |
| Cameras | `top` (RealSense D415) and `wrist`, 640×480, AV1 video |
| Source | `main` episodes 0–500. Raw backup: `~/dataset-backups/main-raw-20261114-1157.zip` + `.labels.json` |
| Trained on it so far | Nothing yet |

| Task sentence (exact) | Episodes |
|---|---|
| `Pick up the brick.` | 244 |
| `The brick is good. Put it on the green plate.` | 129 |
| `The brick is defective. Put it on the orange plate.` | 113 |

The "green" plate is the teal one. The dataset's default task is `Pick up the brick.`

**Note:** it was recorded in the Studio environment `sorting-cell`, not `policy-cell` as GUIDE.md says.

## What an episode is

Each flow is two episodes: a **pick** (grab a brick from the table) and then a **sort** (carry it to a
plate, let go, go back home). Studio shows episode index `i` as `E{i+1}`; this file uses the E numbers.

## Checks done

| Check | Result |
|---|---|
| Sort labels: did the brick go to the plate the sentence names? | **All 242 correct** |
| Picks: does every pick end with a brick in the gripper? | **All 244 yes** (last wrist-camera frame of each) |
| Timestamps, normalisation stats, camera keys | Fine |

How the sort labels were checked:

- Automatically for all sorts: compare the top-camera frame at the start of the pick (brick on the
  table) with the last frame of the sort (brick on a plate), and see which plate area changed.
- On 53 hand-checked labels this agreed 49 times, and every miss had a weak margin. So all
  low-margin and disagreeing cases (35 sorts) were checked by eye at the moment the gripper opens.
  When the arm was out of the top camera's view, the wrist camera showed which plate was underneath.

Removed during the review: the old E147 and E148. Each was a pick and a sort recorded as one
episode (the brick ended up on a plate) but labelled `Pick up the brick.`

`main` episodes (0-based raw index) not in `main-clean3`:
1, 2, 21, 95, 144, 151, 152, 153, 154, 176, 201, 202, 203, 379, 390.

## Three recording batches

The data was recorded in three batches with different habits.

| | E1–E108 | E109–E310 | E311–E486 |
|---|---|---|---|
| Episodes (pick / good / defective) | 108 (55 / 29 / 24) | 202 (101 / 52 / 49) | 176 (88 / 48 / 40) |
| **Where a pick ends** | **At home** (54 of 55) | Lifted in mid-air (94 of 101) | Lifted in mid-air (87 of 88) |
| Pick length (median) | 6.8 s | 8.0 s | 7.6 s |
| Sort length (median) | 3.6 s | 4.9 s | 5.9 s |
| Still at the end (median, pick / sort) | 0.2 s / 0.2 s | 0.4 s / 0.1 s | 0.5 s / 0.7 s |
| Episodes still for ≥1 s at the end | 0 | 3 | 15 |
| Scene | Plates moved almost every flow; bricks pile up on plates and table | Plates moved every few flows; several bricks scattered | From about E407: plates look fixed, little clutter, the same brick reused for 5–9 flows |

"Lifted" picks end with shoulder_lift between about -83 and -51 (home is about -96) and wrist_flex
between about 16 and 66. The following sort starts from that lifted pose.

## Known problems

1. **Picks end in two different places.** 62 picks end at home (shoulder_lift below -85 at the end):
   54 in E1–E108, 7 in E109–E310, 1 in E311–E486. The other 182 stop in mid-air. A model trained
   on both gets two answers for what to do after lifting the brick. Expect hesitation or a wobble there.
2. **Episodes rarely end held still.** The model only learns "done, stay put" from still frames at the
   end of an episode, because SmolVLA's training masks out everything after an episode's end. The
   newest batch is better but still short of the 1 s rule.
3. **The gripper position does not show whether a brick is held.** The soft ribbed fingers close to
   about 3.5 on a brick and about 2.6 on nothing. Use the wrist camera to detect a held brick.
4. **Order breaks:** E1/E2, E82/E83 and E167/E168 are two picks in a row; E191/E192 are two sorts in
   a row. Each is where an episode in between was removed. Harmless for training.

## How to train on it

| Setting | Value |
|---|---|
| Camera mapping | `top` → Overview, `wrist` → Gripper |
| Validation split | **0**, so Studio keeps the final weights. With the default 10% it keeps the "best" epoch, which shipped an epoch-3 snapshot of the first SmolVLA. The UI hard-codes 0.1: submit through `POST /api/jobs:train` with `val_split: 0`, or set `TRAINING_VAL_SPLIT = 0` in `physical-ai-studio/application/ui/src/features/models/train-model-dialog/training-steps.ts` |
| Length | About 7 epochs at batch 32 ≈ 21,000 steps (one epoch ≈ 3,000 steps) |
| Augment images | On |

- **SmolVLA (all three sentences):** train on all 486 episodes.
- **Pick-only model (ACT):** use the picks, but leave out the 62 that end at home (problem 1).
- **Optional fix for problems 1 and 2:** make a copy where every pick is cut at the moment the brick
  is grasped and lifted, and ~0.5–1 s of still frames is added to the end of every episode. Write it
  as a new dataset; never edit `main`.

**For the loop script:** end the pick when the wrist camera shows a brick in the gripper and the arm
has lifted, instead of waiting for the policy to stop by itself. After the inspection, start the sort
from home or from a lifted pose, which are the two start poses the sort episodes contain.

## Related datasets

| Dataset | ID | Episodes | Notes | Model trained on it |
|---|---|---|---|---|
| `main` | `f19d2a22-abf6-40be-b06c-e8fbaf12e7d4` | 501 | Raw recordings. Never edit. | – |
| `main-clean` | `127c9227-8cf9-4e28-af00-8a6d7769e1d2` | 108 | Same as E1–E108 here | `SmolVLA` (first model, epoch-3 snapshot, jerky) |
| `main-clean2` | `985acd05-dbae-45d5-ae9a-ab9e556b77a8` | 315 | E1–E310 here, plus 5 episodes removed since (3 in the cleaning that made `main-clean3`, then the old E147 and E148) | `SmolVLA-v2` |
| `main-picks` | `107b6589-0b45-4440-8b73-fbae6b7e3844` | 158 | The picks of `main-clean2`, mixed endings | `ACT-pick-v1` |
| `main-clean3` | `ba1139d1-a28c-40bf-bc44-3fb1800e24f6` | 486 | This file | `Pi0.5` (team run, 10% validation) |
| `main-clean4` | `cf96b132-2e62-42e3-8885-9cf5b756a1c0` | 424 | `main-clean3` minus the 62 picks that end at home (problem 1): 182 pick / 129 good / 113 defective, 81,867 frames. Every pick ends lifted; all sorts kept. Delete list: `~/dataset-backups/main-clean4-delete-options.json` (option C) | – (planned: pi0.5, validation 0) |

## Reading the files

Episodes are not separate files. All episodes are joined end to end:

```text
data/chunk-000/file-*.parquet                        joint state and action for every frame
meta/episodes/chunk-000/file-000.parquet             one row per episode: task, length, offsets into data and videos
meta/tasks.parquet                                   the three sentences
videos/observation.images.top/chunk-000/file-*.mp4   top camera
videos/observation.images.wrist/chunk-000/file-*.mp4 wrist camera
```

Joint values are Studio's normalised units (-100…100; gripper 0…100), in the order shoulder_pan,
shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper. Decode the AV1 videos with ffmpeg, not
OpenCV. Change the dataset only through Studio's API or UI, and only while no recording session has
it open. Deleting episodes makes Studio re-encode the videos, which takes several minutes.
