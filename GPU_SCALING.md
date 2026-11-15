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
| `src/training/device.py` | `PHYSICALAI_NUM_GPUS > 1` on CUDA: N devices, Lightning DDP (it sees torchrun started the processes and launches none) | Modal redeploy |
| `src/training/multi_gpu.py` (new) | Multi-GPU jobs train in fresh processes started with `torchrun`, one per GPU; rank 0 writes progress lines that the Modal function forwards to Studio | Modal redeploy |
| `src/training/job.py` | Multi-GPU only: hands the job to `torchrun`; progress from rank 0 only; rank 0 saves the final checkpoint and alone publishes and exports; same data split on every rank; batch-size finder refused | Modal redeploy |
| `src/trainer/modal_app.py` | Ships our `training/` folder into the Modal image; only the Modal function itself commits the Volume, plus a 5 s commit loop for multi-GPU jobs | Modal redeploy |
| `tests/...` | Updated key test, new multi-GPU test | |

Single-GPU jobs behave exactly as before: none of the multi-GPU code runs unless
`PHYSICALAI_NUM_GPUS` is above 1.

**Careful with git:** a `git pull` or `git submodule update` in `physical-ai-studio` can overwrite
these edits. Check `git -C physical-ai-studio status` first.

The submodule's remote is upstream Studio, so the edits aren't pushed there. They are saved in
this repo as `patches/physical-ai-studio-multi-gpu.patch` (against submodule commit `285924d9`).
To restore them on a clean checkout:

```bash
git -C physical-ai-studio apply ../patches/physical-ai-studio-multi-gpu.patch
```

## 3. Checked so far

- Studio's own tests for the touched code: **318 passed** (run from a throwaway environment, so
  Studio's `.venv` wasn't touched; `uv sync` there would undo the arm driver edits).
- First design (fork-based, replaced, see next points): a local 2-process fork test on CPU passed,
  and showed that a forked parent's own checkpoint says step 0. That's why rank 0 saves the final
  checkpoint itself, which the torchrun version keeps.
- **Fork-based multi-GPU failed on Modal twice** (14:17, 14:21; pi0.5 on `H100:2`, a few minutes
  each): "Cannot re-initialize CUDA in forked subprocess". Code in the parent (pi0.5 / Hugging Face
  model loading) touches CUDA before the fork, and Lightning 2.6.6 no longer checks for that.
  Setting `PYTORCH_NVML_BASED_CUDA_CHECK=1` didn't help.
- **Switched to `torchrun`** (14:27): every GPU gets a fresh process, so it doesn't matter what the
  parent touched. Local CPU test under torchrun (2 processes, gloo): Lightning started no extra
  processes, the checkpoint has the real step count (6 of 6), weights trained, progress only from
  rank 0. Studio's tests: 309 passed.

Status: Modal app redeployed with the multi-GPU code (latest: 14:28, torchrun version). The backend part is active
since the 13:11 restart, except `H100:8`, which was added later and needs one more backend restart.

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

Both parts are done (backend restarted 14:36 with the fixes, Modal app redeployed 14:32).

## 5. Test runs on Modal (2026-11-14)

**Length is set in epochs only.** Studio ignores `max_steps` (a legacy field): with `max_epochs`
missing it trains 100 epochs. Use a small dataset and `"max_epochs": 1` for short tests.

| Time | Run | Result |
|---|---|---|
| 14:17 | pi0.5, `H100:2`, fork-based | Failed: "Cannot re-initialize CUDA in forked subprocess" |
| 14:21 | same, with `PYTORCH_NVML_BASED_CUDA_CHECK=1` | Same failure |
| 14:31 | pi0.5, `H100:2`, torchrun | Both ranks started, then failed: Hugging Face 401 (the `env=` option had replaced the HF_TOKEN secret) |
| 14:42 | pi0.5, `H100:2`, torchrun, token fixed | **Trained on both GPUs** (100% and 81% busy, about 53 GB each). Cancelled: `max_steps` was ignored, so it was set for 100 epochs |
| 14:43 | pi0.5, `H100:2`, small dataset `eka`, 1 epoch | Checks the end of a run: final checkpoint, export on rank 0, model download |

To see the GPUs while a job runs: `modal container list`, then
`modal container exec <id> nvidia-smi`.

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

## 8. Smaller model downloads (2026-11-14)

A pi0.5 model package from Modal was **33.7 GB**, most of it the optimizer state inside
`model.ckpt`. On the venue Wi-Fi (about 25 MB/s at best) that's 25–40 minutes per model.

**Two changes, both in `physical-ai-studio/application/backend/src`:**

| Change | File | Active after |
|---|---|---|
| Downloads go to a folder next to the model's output folder (on the SSD), not `/tmp`. `/tmp` here is a 31 GB RAM disk with a per-user quota; the first pi0.5 test download failed with "Disk quota exceeded" at 23 GB. | `services/training_backends/modal.py` | Backend restart (done 15:52) |
| **Full checkpoints stay on Modal.** After training, the job copies `model.ckpt` with its optimizer state to the Modal Volume, then ships a weights-only `model.ckpt` plus the export. | `training/job.py` (`_offload_full_checkpoints`), `trainer/modal_app.py` (sets `PHYSICALAI_FULL_CHECKPOINT_DIR`) | Modal redeploy: **done 16:17** |

- **What the laptop still gets:** the OpenVINO export (to run the model) and a weights-only
  `model.ckpt`. That's enough for Studio's "retrain from this model" and for re-exporting: both load
  weights with `load_from_checkpoint`. Only continuing the exact same run needs the optimizer state.
- **Expected size for pi0.5:** about 13–14 GB instead of 34 (about 9–10 min on this Wi-Fi).
  SmolVLA packages shrink too.
- **Where the full checkpoint is:** on the Modal Volume, `jobs/<Studio job id>/full-checkpoint/model.ckpt`.
  Fetch it with:

  ```bash
  cd ~/intel-robot-challenge/physical-ai-studio/application/backend
  .venv/bin/python -m modal volume get --env main physicalai-training-bbbcdfa03cd74755b4c1c81cde8483db \
      jobs/<job id>/full-checkpoint/model.ckpt ./model-full.ckpt
  ```

- **Storage:** these files pile up on the Volume (about 27 GB per pi0.5 run). Delete old job
  folders with `modal volume rm --env main <volume> jobs/<job id> -r` when they're no longer needed.
- **Checked:** a real Lightning checkpoint, before and after: the full copy keeps the optimizer
  state; the shipped file has none, keeps the step count, is 63% smaller in that test, and loads
  with `load_from_checkpoint` with identical weights. Without the environment variable (local
  training in Studio) nothing changes. Two new tests in
  `tests/training/test_offload_full_checkpoint.py`; Studio's tests: 270 passed.
- **Doesn't apply to** `Pi0.5-v2-8gpu` (started before this change): its package is 34 GB.

## 9. Undo

```bash
git -C ~/intel-robot-challenge/physical-ai-studio checkout -- application/backend
```

Then redeploy the Modal app (section 4b) and restart the backend (4a).
