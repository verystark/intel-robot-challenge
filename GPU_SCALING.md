# Faster training on Modal: parallel jobs and multi-GPU

Status (2026-11-14, 12:45): **code ready, not active yet.** It switches on with one Studio backend
restart and one Modal redeploy (section 4). Nothing running today was changed.

## 1. Why

| Measured on `SmolVLA-v2` (Modal, 1 GPU) | Value |
|---|---|
| GPU Modal gave us | H200 (asked for H100; billed as H100) |
| Speed | 3.4 steps/s at batch 32 = about 108 samples/s |
| GPU busy | about 60–70% of the time |
| CPU | 8 reserved, 24 visible, about 6.4 busy (8 video-decoding data workers) |
| 20k steps | about 1 h 45 min of training |

Two limits in Studio:

- **Only one job per policy at a time on Modal.** A second SmolVLA job waits until the first one
  finishes, even though every Modal job has its own container. That's why `SmolVLA-v2-long`
  waited behind `SmolVLA-v2`.
- **One GPU per job.** Studio's GPU picker has no count, the training code always used one device,
  and Lightning's normal multi-GPU launcher doesn't work inside a Modal function.

## 2. What changed

All in `physical-ai-studio/application/backend/` (git submodule, **uncommitted**):

| File | Change | Active after |
|---|---|---|
| `src/services/training_targets/remote.py` | Modal jobs are queued per model name, not per policy: different names run side by side | backend restart |
| `src/schemas/remote_trainer.py` | New GPU options: `H100:2`, `H100:4`, `A100-80GB:2`, `A100-80GB:4` | backend restart |
| `src/services/training_backends/modal.py` | For N GPUs: asks Modal for N GPUs, 8N CPU cores, 32N GB memory, and sets `PHYSICALAI_NUM_GPUS=N` | backend restart |
| `src/training/device.py` | `PHYSICALAI_NUM_GPUS > 1` on CUDA: train on N GPUs with fork-based DDP | Modal redeploy |
| `src/training/job.py` | Multi-GPU only: progress reported from rank 0 only, rank 0 saves the final checkpoint (real step count), same data split on every rank, batch-size finder refused | Modal redeploy |
| `src/trainer/modal_app.py` | Ships our `training/` folder into the Modal image; only the parent process commits the Volume, plus a 5 s commit loop for multi-GPU jobs | Modal redeploy |
| `tests/...` | Updated key test, new multi-GPU test | |

Single-GPU jobs behave exactly as before: none of the multi-GPU code runs unless
`PHYSICALAI_NUM_GPUS` is above 1.

**Careful with git:** a `git pull` or `git submodule update` in `physical-ai-studio` can overwrite
these edits. Check `git -C physical-ai-studio status` first.

## 3. Checked so far

- Studio's own tests for the touched code: **318 passed** (run from a throwaway environment, so
  Studio's `.venv` wasn't touched; `uv sync` there would undo the arm driver edits).
- Local 2-process fork test on CPU with the same Lightning (2.6.6) as the Modal image:
  - progress reports come only from rank 0;
  - the parent process carries on after training and gets the trained weights;
  - rank 0's final checkpoint has the real step count (6 of 6). Without that fix the parent's
    checkpoint said step 0, which would hide the "early checkpoint" check;
  - the weights are the trained ones.
- **Not tested yet:** a real multi-GPU run on Modal (section 5).

## 4. Turning it on

**a) Restart the Studio backend** (parallel jobs and the new GPU options).
Only when no job is uploading its dataset or downloading its model (Studio shows "Uploading
dataset" / "Downloading trained model"). Running trainings are not affected: Studio reconnects to
them by their Modal call ID.

```bash
# in the backend terminal: Ctrl+C, wait until it exits (up to ~30 s), then
cd ~/intel-robot-challenge/physical-ai-studio/application/backend
uv run --extra xpu physicalai-studio serve
```

**b) Redeploy the Modal app** (multi-GPU training code). Running jobs finish on the old version.
Don't use Studio's "Deploy and connect" button: it refuses an existing app. Use the same names
Studio used:

```bash
cd ~/intel-robot-challenge/physical-ai-studio/application/backend
PHYSICALAI_MODAL_APP=physicalai-bbbcdfa03cd74755b4c1c81cde8483db \
PHYSICALAI_MODAL_VOLUME=physicalai-training-bbbcdfa03cd74755b4c1c81cde8483db \
PHYSICALAI_MODAL_SECRET= \
PHYSICALAI_MODAL_IMAGE=ghcr.io/open-edge-platform/physicalai-trainer-cuda:main \
.venv/bin/python -m modal deploy --env main src/trainer/modal_app.py
```

Until b) is done, don't submit `H100:2` or `H100:4`: the job would get (and pay for) N GPUs but
train on one.

## 5. Smoke tests after turning it on (a few minutes each, about $3–6 total)

1. **Single GPU still fine:** short job, `"modal_gpu": "H100"`, `"max_steps": 200`. It completes,
   exports, and the checkpoint step is 200.
2. **2 GPUs:** same with `"modal_gpu": "H100:2"`, `"batch_size": 32`, `"max_steps": 300`. While it
   runs, `modal container list` and then
   `modal container exec <id> nvidia-smi` should show both GPUs busy. Studio shows live progress.
   The checkpoint step is 300 and the OpenVINO export exists.
3. **4 GPUs:** `"modal_gpu": "H100:4"`, `"batch_size": 16`, same checks.
4. Offline test of one export (the script used for v1/v2) to check the outputs look sane.

If 2) fails, the fallback is to start the GPU processes with `torchrun` instead of forking; see
`~/.claude/plans/splendid-snacking-hejlsberg.md`.

## 6. Submitting a multi-GPU job

Through Studio's API (the train dialog doesn't offer the new options and fixes the validation
split at 10%):

```bash
curl -s -X POST http://localhost:7860/api/jobs:train -H 'Content-Type: application/json' -d '{
  "project_id": "4b65ec52-5559-4023-8a69-bf7e5ae36b8a",
  "dataset_id": "<dataset id>",
  "model_name": "SmolVLA-v3-2gpu",
  "policy": "smolvla",
  "max_epochs": 11,
  "batch_size": 32,
  "num_workers": "auto",
  "auto_scale_batch_size": false,
  "precision": "bf16-mixed",
  "compile_model": false,
  "image_key_reorder_map": {"top": 0, "wrist": 1},
  "num_cameras": 3,
  "export_backends": ["openvino"],
  "augment_images": true,
  "val_split": 0.0,
  "training_target": "remote",
  "remote_trainer_id": "d9d99f90-6122-4e12-8259-2db895ffc5c0",
  "modal_gpu": "H100:2"
}'
```

**Batch rule:** `batch_size` is per GPU. Keep the total at 64 (LeRobot's SmolVLA reference, which
its learning rate and 1,000-step warmup are tuned for):

| GPUs | `modal_gpu` | `batch_size` | Total batch |
|---|---|---|---|
| 1 | `H100` | 32 (or 64) | 32 (64) |
| 2 | `H100:2` | 32 | 64 |
| 4 | `H100:4` | 16 | 64 |

With the total batch at 64, one epoch is half as many steps as at batch 32. For "about 20k steps
at batch 32" worth of training, use the same number of epochs; the step count halves.

## 7. Expected speed and cost (estimates until the smoke test measures them)

| Setup | 11 epochs on `main-clean2` | Cost per run |
|---|---|---|
| 1×H100, batch 32 | about 1 h 45 min | about $8–9 |
| 2×H100, 2×32 | about 1 h (about 1.7× faster) | about the same GPU-hours, plus CPU |
| 4×H100, 4×16 | about 35–40 min (about 3× faster) | about the same GPU-hours, plus CPU |

Modal warns that more than 2 GPUs in one container can mean longer waits for capacity.

## 8. Undo

```bash
git -C ~/intel-robot-challenge/physical-ai-studio checkout -- application/backend
```

Then redeploy the Modal app (section 4b) and restart the backend (4a).
