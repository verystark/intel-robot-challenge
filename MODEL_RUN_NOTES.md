# First SmolVLA model: notes from running it on the arm

Written 2026-11-14 after the first test run of the first trained model.

## The model

- Studio model `SmolVLA` v1 (id `dd2dead8-3efe-4928-96f1-d9c1a62c8441`), trained on dataset `main-clean`
  (108 episodes, 30 fps).
- Trained on Modal on an H100 in 54 min: 10 epochs, batch 32, 5,169 steps, image augmentation on,
  BF16 mixed precision. Exported to OpenVINO and PyTorch.
- Cameras: `top` → camera1 (Overview), `wrist` → camera2 (Gripper).
- On the arm it ran as OpenVINO on the laptop GPU.

## Task names in `main-clean`

| Episodes | Exact sentence |
|---|---|
| 55 | `Pick up the brick.` |
| 29 | `The brick is good. Put it on the green plate.` |
| 24 | `The brick is defective. Put it on the orange plate.` |

When you run the model, paste these exactly into the **Task** box in Studio's inference panel,
including the full stop. That box fills in the dataset's default task, which may not be one of these
three. (The model we trained is SmolVLA. ACT doesn't read a prompt at all.)

## Jerkiness: don't lower the acceleration first

- **Acceleration is already at the servos' fastest setting (254), and Studio rewrites it every time
  it connects.** To change it you'd have to edit the plugin. Lowering it also makes the arm lag
  behind the model's path, which costs grasp accuracy.
- **The likely cause is that the run used Studio's default "Synchronous" execution mode.** In that
  mode the arm plays 25 actions (0.83 s), then stops while the next chunk is computed. Measured on
  the laptop GPU, that computation takes about 160 ms (120–230 ms), so the arm stutters roughly
  once a second.
- **Fix:** in the inference panel, set **Execution → Asynchronous** before pressing Play, and keep
  "Request the next chunk at" at 50%. The next chunk is then computed while the arm is still moving.
  The 160 ms is well inside the 830 ms the remaining actions take to play, so the pauses should
  disappear.

**If it's still jerky in Asynchronous mode, check which kind of jerky it is:**

- **A steady stop-start rhythm about once a second** is the sync pause. Asynchronous fixes it.
- **Constant twitching or buzzing** is probably the servo P gain, raised from 16 to 32 on
  2026-11-14. That makes the servos snap to every small step. Setting it back to 16 changes a
  setting only and doesn't move the arm. (The change is an edit inside Studio's installed SO-101
  plugin, `_configure_servos` in `physicalai_so101_plugin/so101.py` under `backend/.venv`; a
  `uv sync` also reverts it.)
- **Big sudden lurches** come from the model itself (confirmed below).

Try Asynchronous first, then note which kind of jerkiness is left.

## Result: Asynchronous was still very jerky. The model is the cause.

**Tests (offline, arm not moving).** The model was run on recorded `main-clean` episodes (0, 2, 3,
60), with an inference every 25 frames, the way the arm runs it.

| | Model | Teleop data |
|---|---|---|
| Largest step between frames inside a chunk | 14–19° | 99% of steps under 6°, largest 12° |
| Jump when the next chunk takes over | up to 49° (shoulder_lift) | — |
| Same input run twice | up to 48° different | — |
| Mean error vs. the recorded teleop | ~10° on shoulder_lift and elbow | — |

OpenVINO on the CPU gives the same numbers as on the GPU, so GPU precision isn't the cause. The
normalisation stats in the checkpoint match the export. The PyTorch export couldn't be tested: it
failed on the GPU with "device lost", and the run on the CPU ended without printing results.

**Why the model is so unsure: the saved model is the epoch-3 checkpoint, not the final one.**
Studio's `ModelCheckpoint` keeps the epoch with the lowest `val/loss`
(`application/backend/src/training/job.py`), and the export is made from that checkpoint. Here
that was epoch 3, step 2,068, when training loss was still about 0.15–0.2. So the model on the arm
saw about 66k samples. The LeRobot SmolVLA recipe is 20k steps at batch 64 (about 1.28M samples),
roughly 20 times more. The validation loss swings from 0.03 to 1.27 between batches, so it is too
noisy to choose a checkpoint for this policy.

**Training timeline** (H100, 5,170 steps at batch 32):

| Stage | Time |
|---|---|
| Upload | 3 min |
| Training (about 2.9 steps/s, including 10 validations of about 35 s each) | 36 min |
| Export | 2 min |
| Model download (3.2 GB) | 12 min |

**Next run:**
- Set the validation split to 0. With no validation, Studio saves the final weights. The train
  dialog hard-codes 0.1 in `application/ui/src/features/models/train-model-dialog/training-steps.ts`
  (`TRAINING_VAL_SPLIT`).
- Train much longer: about 20k steps. At batch 32 that's about 35 epochs, roughly 2 h on the H100
  and about $10.
- Before putting the new model on the arm, run the same offline test and check that the jumps and
  the run-to-run spread are much smaller.
- More data still helps the sorts: 29 good and 24 defective episodes is about half of the ~50 per
  task the SmolVLA paper used. Picks (55) are already at that level.
- Servo acceleration was halved to 127 (Studio's SO-101 driver, `_configure_servos`, in the venv).
  Put it back to 254 for teleop recording if the follower lags.

## SmolVLA-v2 (2026-11-14, ready 12:35)

- Studio model `SmolVLA-v2` (id `44dfbee9-…`), OpenVINO only. Data `main-clean2`: 315 episodes
  (158 pick, 82 green, 75 orange), 60k frames.
- Modal H100 (ran on an H200), 6 epochs = 11,322 steps at batch 32, validation split 0 (submitted
  through `POST /api/jobs:train`). Training took about 55 min at 3.4 steps/s.
- **Checkpoint is the final one:** epoch 6, `global_step` 11,322.
- Training loss went down steadily all run: about 0.30 (first 1k steps), 0.13 (3k–6k),
  0.06 (last 2k). v1's shipped checkpoint was at about 0.15.

**Offline test** (recorded episodes, arm not moving; same script and episodes as for v1;
degrees, shoulder_lift / elbow):

| | v1 (epoch 3) | v2 |
|---|---|---|
| Same input, 5 runs: spread | 18–24 / 12–44 | 11–15 / 11–18 |
| Average of the 5 runs vs teleop (next 50 actions) | 5–6 / 4–10 | 2–5 / 3–6 |
| Jerkiness in Asynchronous playback (99th pct. change in speed per frame) | 19.6 / 16.4 | 8.5 / 7.6 |
| Same, with zero noise and a 12-frame blend | 1.6 / 1.3 | 1.5 / 1.1 |
| Teleop, for reference | 2.1 / 1.7 | |

v2 is clearly better: about half as jerky with the default settings and noticeably less scattered.
It still varies from run to run, so the zero-noise + 12-frame-blend tweak would still help (not
applied yet; it needs small edits in Studio's inference code).

**Running it:** Studio → inference → model `SmolVLA-v2`, OpenVINO, GPU; **Execution →
Asynchronous**; the task sentence exactly as in the table at the top.

`SmolVLA-v2-long` (same data, 11 epochs ≈ 20.7k steps) started at about 12:35; expected around
14:40.

## ACT-pick-v1 (2026-11-14, ready 13:15)

- Studio model `ACT-pick-v1` (id `d093c0c3-…`), OpenVINO. Data `main-picks`: the 158 pick
  episodes of `main-clean2`. Modal A10G, 15 epochs = 18,120 steps at batch 32, validation split 0.
- Final checkpoint confirmed (epoch 15, `global_step` 18,120). Training loss levelled off at
  about 0.16 for the last ~6k steps.
- No task sentence (ACT doesn't read one). Chunk of 100 actions = 3.3 s at 30 Hz.

**Offline pick test** (same episodes as for SmolVLA-v2; "unseen" = 176 newer episodes from
`main-clean3` that neither model trained on):

| | SmolVLA-v2 | ACT-pick-v1 |
|---|---|---|
| Inference on the laptop GPU | about 160 ms | **about 18 ms** |
| Trained picks: heads the same way as teleop | 16/16 | 16/16 |
| Trained picks: error, first 50 steps | 5–8° | 6.6° |
| Unseen picks: heads the same way as teleop | 8/13 | 6/13 |
| Unseen picks: error | 10.7° | 10.2° |

Both reproduce the trained layouts well and both struggle with bricks in new places. ACT is
about 9× faster, so it can re-plan much more often.

**Running it:** Studio → inference → `ACT-pick-v1`, OpenVINO, GPU, Asynchronous. Because each
inference takes only ~18 ms, set "Request the next chunk at" to about 70–80% (re-plans every
0.7–1 s instead of every 1.7 s at 50%).

## SmolVLA-v2-long (2026-11-14, ready 14:43)

- Studio model `SmolVLA-v2-long` (id `bf872bab-…`), OpenVINO. Same data and settings as v2
  (`main-clean2`, batch 32, validation split 0), 11 epochs = 20,757 steps. Final checkpoint
  confirmed (epoch 11, `global_step` 20,757).
- Offline test run on the CPU (the arm was using the GPU), so small numeric differences from v2's
  GPU numbers are possible.

| | v2 | v2-long |
|---|---|---|
| Jerkiness, Asynchronous, default settings (shoulder_lift / elbow; same episodes) | 8.5 / 7.6 | **6.1 / 5.0** |
| Error vs teleop in that playback (shoulder_lift / elbow) | 12.8 / 9.4 | 11.5 / 8.2 |
| Unseen picks: heads the same way as teleop | 8/13 | 8/14 |
| Unseen sorts: right sentence closer to teleop than wrong one | 15/20 | 14/20 |
| Unseen sorts: pans the same way as teleop | 13/19 | 12/20 |

The unseen-episode rows used slightly different episodes for the two models (another session
deleted 2 episodes from `main-clean3` in between, which shifted the indices), so treat them as
"about the same", not as a ranking.

v2-long is about 25–35% smoother than v2 and slightly closer to the teleop, and just as weak on
new layouts, as expected from training longer on the same data. Use layouts that appear in the
recordings.

## Model downloads from Modal (2026-11-14)

From the next Modal run on, the full checkpoint (with optimizer state) stays on the Modal Volume and
the laptop gets a weights-only `model.ckpt` plus the export: about 13–14 GB for pi0.5 instead of
34 GB. Models download to the SSD, not `/tmp`. Details, and how to fetch a full checkpoint:
`GPU_SCALING.md` section 8.

## Pi0.5-v2-8gpu (2026-11-14, laptop time)

- pi0.5 on `main-clean4` (424 episodes), 8×H100 on Modal via torchrun, batch 8 per GPU (64 total),
  4 epochs = 5,116 steps, validation split 0. Studio job `29fe2a9d-6160-4b48-8439-87f645abe23b`.
- **Imported into Studio at about 18:15 as `Pi0.5-v2-8gpu`** (model id `4822d9e2-36d4-49ff-96be-2f6796ee002f`, dataset
  `main-clean4`, OpenVINO): weights-only `model.ckpt` (9.36 GB, all 823 tensors identical to the full
  checkpoint, step 5,116) plus the export. Loads on the laptop GPU in about 26 s, about 300 ms per
  chunk. The training job itself shows "canceled". What happened:
  1. 15:24–16:06 trained fine (loss about 0.35 → 0.03), then Modal **preempted** the container
     during the export (16:10, "Container terminated due to preemption"). That run's weights were
     only on the container's disk and were lost.
  2. Modal re-ran the job by itself (16:10–17:05, same result). Its checkpoint was copied to the
     Modal Volume by hand at 17:07.
  3. The export finished about 17:20, but the 7 other GPU processes never exited, so the job hung
     with 8 GPUs billing. The export was copied to the Volume and the job was cancelled at 17:31.
- **Where the model is:**
  - Modal Volume `physicalai-training-bbbcdfa03cd74755b4c1c81cde8483db`,
    `jobs/29fe2a9d-6160-4b48-8439-87f645abe23b/`: `full-checkpoint/model.ckpt` (29.9 GB, with
    optimizer state) and `salvage/exports/openvino/` (6.3 GB, the model to run).
  - Laptop copy (complete, checked identical to the Volume copy, 18:12): `/home/intel/pi05-models/Pi0.5-v2-8gpu/` (`salvage/exports/openvino/`
    and `full-checkpoint/model.ckpt`).
- **Run it** in Studio (Inference → `Pi0.5-v2-8gpu`, OpenVINO, GPU, Execution → Asynchronous), or with the
  loop, which also accepts an export folder:
  `$PY loop/run_cell.py --model /home/intel/pi05-models/Pi0.5-v2-8gpu/salvage/exports/openvino`
- **Before the next multi-GPU run, fix the hang:** the GPU processes other than rank 0 must shut down
  their process group and exit right after training (see GPU_SCALING.md).
