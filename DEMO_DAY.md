# Demo day: architecture, judging, run sheet

Everything for the Challenge Day demo in one place:
- what to say,
- what to show,
- what to run when a training run finishes,
- what to do when something breaks.

Measured numbers live in [bench/RESULTS.md](bench/RESULTS.md), generated from the benchmark and
loop logs. Quote that file, not this one.

---

## 1. The system in one paragraph

An SO-101 arm picks a Duplo brick with a vision-language-action policy trained in Physical AI
Studio. A script then holds the brick in front of an inspection webcam and turns it through three
wrist stops (0°, 90°, 180°). Anomalib (PatchCore) scores each stop and draws a heatmap; a clear
defect at any stop rejects the brick at once. The verdict becomes the
sentence the VLA is given next: *"The brick is good. Put it on the green plate."* or *"The brick
is defective. Put it on the orange plate."* The VLA puts the brick on that plate.

Unsure stops get a second look, and a brick that is still unsure is rejected. The scripted moves
keep the policy's grip on the brick, and a scripted move home hands it back to the VLA. Every model runs on
the laptop with OpenVINO, each on the device that suits it, and a live screen shows every
decision and timing.

## 2. Architecture

```text
PERCEIVE                DETECT                  REASON                   ACT                     OPTIMIZE
top RealSense  ─┐       inspection webcam ──▶   verdict ──▶ sentence ──▶ SmolVLA sort           OpenVINO everywhere
wrist camera   ─┴──▶ pick policy (SmolVLA      PatchCore score +        "…defective. Put it      device per model by
                     or ACT) ──▶ SO-101         heatmap, 3 stops         on the orange plate."    measurement, INT8,
                     picks the brick            (GPU, while the arm      ──▶ SO-101 sorts         zero-noise SmolVLA,
                     scripted show pose ──▶     turns the brick)                                  async chunks
```

| Stage | What runs | Where | Why there |
|---|---|---|---|
| Pick | SmolVLA `Pick up the brick.` (or ACT, `--pick-model latest:act`) | GPU (ACT: NPU) | SmolVLA needs the GPU: 214 ms per chunk, it won't compile for the NPU, and the CPU takes 4.8 s. ACT runs as fast on the NPU (17 ms) as on the GPU (15 ms). |
| Show | Scripted, eased joint move to a saved pose; wrist stops at 0°, 90°, 180°; then home, grip kept | CPU | The photo must be taken from the same pose every time. Anomalib flags anything that differs from its training photos (`ANOMALY_DATA_REVIEW.md`). |
| Inspect | Anomalib PatchCore, heatmap, good / unsure / defective bands | GPU | 18 ms per photo vs 184 ms on the NPU and 56 ms on the CPU. Its scores are also closest to FP32 on the CPU. The GPU is free then: no policy runs while the brick is shown. |
| Sort | The same SmolVLA, with the verdict in the sentence | GPU | The VLA reads the verdict. The sentence is the "structured signal" the brief asks for. |
| Measure | `bench/sysmon.py`: temperature, CPU / GPU / NPU busy, power | – | Judges want evidence. |

Code:
- `loop/run_cell.py` is the loop and serves the live dashboard (http://localhost:8080, `--open` for full screen).
- `loop/show_tool.py` saves the show pose and collects photos.
- `anomaly/` trains, exports, quantises and calibrates Anomalib.
- `bench/` holds the measurements.

## 3. How we meet each judging criterion

The PDF's table (page 7) and `physical-ai-studio/JUNCTION2026.md`'s table differ. Ask a mentor
which one counts; the design covers both.

| Criterion (PDF) | Pts | What we show | Evidence |
|---|---|---|---|
| End-to-end physical AI solution | 25 | One program runs pick → inspect → sort in a loop. Nobody chooses anything. | Live run; `loop/runs/*/cycles.jsonl` |
| Defect detection with Anomalib | 20 | PatchCore at three wrist stops per brick (median of 3 frames each), a heatmap, three score bands, early reject and a second look. The verdict reaches the robot as the sentence. | The screen: photos, heatmaps, score bar, the sentence sent |
| VLA & Physical AI Studio | 20 | SmolVLA trained in Studio on our teleop data. One model, three sentences; the verdict changes what it is told. | Studio datasets and models; the sentence on screen |
| OpenVINO & Core Ultra | 20 | Every model in OpenVINO. Device chosen by measurement. INT8 Anomalib (4× smaller). Anomalib trained on the Intel GPU (Intel GPU 2.7 min vs CPU 12–17 min for the slowest step). | `bench/RESULTS.md` |
| Robotic execution & reliability | 10 | Recovery from uncertain detections: unsure stops get a second look → reject if still unsure. Stage timeouts; a stop key. | Re-check count on the screen and in the log |
| Innovation & demo clarity | 5 | The live screen. Zero-noise SmolVLA for smooth motion. Inspection hidden behind arm motion. | This file, the screen |

| Criterion (JUNCTION2026.md) | Pts | Our answer |
|---|---|---|
| Task success rate | 25 | Sorted correctly N of M (counted by a person), cycle time from the log, bricks anywhere in the pick area |
| Intel tech integration | 25 | OpenVINO for all models, each on the device measured best for it: SmolVLA and Anomalib on the GPU, ACT on the NPU; Studio for data and training |
| Dataset & pipeline quality | 20 | Raw `main` kept, cleaned copies `main-clean*` relabelled by script, episode review |
| System efficiency | 20 | Latency per step and per cycle, temperature, GPU/NPU load, power: `bench/RESULTS.md` |
| Creativity | 10 | Verdict-in-the-sentence, three-stop inspection with early reject and second look, scoring done while the arm turns the brick |

## 4. The moment a training run finishes

**A new policy (SmolVLA or ACT) in Studio:**

1. **Wait for the export.** The run must show its OpenVINO export in Studio's Models page:
   `~/.local/share/physicalai/models/<id>/exports/openvino/manifest.json`.
2. **Measure its speed** (no arm):
   `$PY bench/policy_bench.py --models <name> --devices GPU NPU CPU`.
3. **Check the plumbing and sentences** (no arm):
   `$PY loop/run_cell.py --sim --model <name> --cycles 1 --no-window`.
   It refuses to start if the sentences don't match the model's dataset.
4. **Test on the arm,** with someone at the 12 V plug:
   1. `$PY loop/run_cell.py --model <name> --cycles 1`, with a hand near Esc.
   2. Then 10 cycles. Count the correct sorts.
5. **Record the results:**
   1. Run `python3 bench/make_table.py`.
   2. Write "sorted correctly N of M" into `bench/RESULTS.md`.
   3. Commit.

`PY=physical-ai-studio/application/backend/.venv/bin/python`.
To use ACT for the pick: add `--pick-model <ACT name> --pick-device NPU`.

**New inspection photos (defects captured):**

1. `cd anomaly && ../.venv/bin/python train_export.py --int8`. It trains on the Intel GPU
   (about 3 min) and writes `exported_model/` and `exported_model_int8/`.
2. `../.venv/bin/python calibrate_bands.py` sets the good / unsure / defective bands on the GPU
   and writes `bands.json`. Check the printed table: how many good bricks are rejected, and how
   many defects pass.
3. `../.venv/bin/python inspect_live.py --device GPU`: a live check with real bricks. Close
   `capture.py` first.
4. `../.venv/bin/python ../bench/anomaly_bench.py` updates the latency table.

## 5. Run sheet for the demo

**One hour before:**
- [ ] Table locked down: tape, plates on their spots, lamp, backdrop. Top camera view clear.
- [ ] Follower rested and cool. `tools/servo_check.py` is clean (GUIDE.md section 4).
- [ ] Nothing else holds the arm or cameras: Studio sessions, `capture.py`, `inspect_live.py`.
- [ ] `show_tool.py where` is close to the saved show pose. `show_tool.py test-turn` is OK.
- [ ] `run_cell.py --inspect-only`: one good and one defective brick give the right verdicts.
- [ ] Power numbers wanted? Make the package power readable until reboot:
      `sudo chmod o+r /sys/class/powercap/intel-rapl:0/energy_uj`.
      Or run `sudo turbostat --quiet --interval 1 --show PkgWatt,CorWatt,GFXWatt,PkgTmp` in a
      terminal during the demo.
- [ ] Re-run both benchmarks on the quiet laptop, then `make_table.py`, so RESULTS.md isn't
      "contended".
- [ ] Laptop on mains power, other heavy programs closed. The package reached 90–97 °C under
      load today.

**The demo (about 5 minutes):**
1. **Problem (20 s).** Factories inspect parts by eye. We taught a small low-cost arm to pick, inspect
   and sort from a few hundred recorded demonstrations (say the episode count of the dataset you used).
2. **Start** `run_cell.py --open` (the dashboard opens full screen). While it picks: "SmolVLA sees the top and wrist cameras and was told
   'Pick up the brick.' It runs on the laptop's GPU with OpenVINO, at about N ms per action chunk
   (RESULTS.md)."
3. **Show and inspect:** "A script holds the brick at a fixed pose and turns it through three
   stops. Anomalib scores each stop while the wrist turns to the next; a clear defect stops the turn. It runs on the GPU in about 18 ms a photo, while the arm is still moving.
   The heatmap shows where it thinks the defect is."
4. **The verdict sentence:** point at "Sent to SmolVLA". "The verdict is not a hard-coded motion.
   It's what we tell the VLA, and the same model then chooses the plate."
5. **A defective brick and an unsure one:** show the early reject and the second look, "reject when in doubt".
6. **Numbers:** RESULTS.md on screen. Latency per model and device, cycle time, temperature and
   load. INT8 Anomalib at a quarter of the size, with scores within about 0.06.
7. **Q&A.**

**Likely questions:**
- *Why not one model end to end?* Inspection needs an identical viewpoint. A learned show pose
  varied too much (`ANOMALY_DATA_REVIEW.md`), so the show is scripted, and the VLA does what
  needs learning: grasping anywhere, and sorting by sentence.
- *How do you know it reads the sentence?* The sort sentence was drawn independently of the
  brick while recording, so only the sentence tells the plates apart. To show it: give a good brick
  the defective sentence in Studio's Run model, and it should go to orange (try it before the demo).
- *Why isn't Anomalib on the NPU?* We measured it: 184 ms on the NPU vs 18 ms on the GPU, and no
  policy needs the GPU while the brick is shown. The NPU runs the ACT pick instead, where it
  matches the GPU (17 vs 15 ms). The bench table shows every model on every device.
- *What about uncertain detections?* Three stops, a second look at unsure ones, reject if still unsure. The
  bands come from held-out good photos and real defects (`calibrate_bands.py`).

### Which part of the dashboard proves what

| Dashboard part | Criterion | Point at it when |
|---|---|---|
| Pipeline bar (Perceive → … → Optimize), lit stages, device and latency per stage | Closed loop, OpenVINO | Opening: "one system, every model on this laptop" |
| Inspection camera with the live heatmap; stop tiles with heatmaps; score bar | Anomalib | The judge's scribble lights up |
| Verdict → "Task sent to …" with the sentence | Detection reaching the VLA | Every verdict: the sentence changes, and so does the plate |
| Policy plan (measured vs planned joints, ms per plan, asynchronous) | VLA, efficiency | "It plans 1.7 s of motion in about 120–210 ms on the GPU, while the arm keeps moving" |
| On this laptop: GPU / NPU / CPU load, temperature, measured placement | OpenVINO, efficiency | "Device per model, measured: Anomalib 18 ms on the GPU vs 184 on the NPU" |
| Last bricks with ✓ / ✗, and the corner number | Task success | The end: "sorted correctly N of M, X s per brick" |

## 6. When something goes wrong

| Problem | Do this |
|---|---|
| "The follower is in use" | Close the Studio session or robot page using the arm; restart Studio's backend if none is open (GUIDE.md §14) |
| "Cannot open camera" (inspection) | Close `capture.py` / `inspect_live.py` |
| RealSense or wrist camera errors | Close Studio sessions using the environment; replug; Studio's backend restart |
| Pick ends by timeout | The arm holds; put the brick back in the pick area, press `r`. Repeated: record more picks at that position |
| Wrong plate | Check the sentence on screen. If the sentence was right, the sort policy needs more data; if wrong, check `bands.json` |
| Jerky motion | `zero_noise` and `execution: async` in `cell_config.json`; the safety clamp count is in the log (`clamped_ticks`) |
| Every brick unsure / defective | Lighting or backdrop changed since the photos: re-check `inspect_live.py`, recalibrate the bands |
| Anything late | Demo the last version that worked (GUIDE.md §12); keep every working model |
