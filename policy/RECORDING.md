# Recording session run sheet (for Claude on the station laptop)

You are helping the team record the `cell-v1` dataset in Physical AI Studio on this laptop (Linux,
repo at `~/intel-robot-challenge`). The full plan is in [GUIDE.md](../GUIDE.md) sections 5–7; this
file is the short version for running a session. GUIDE.md wins if they disagree.

> **Out of date for the recording itself: follow [GUIDE2.md](../GUIDE2.md) sections 4–7.** The pick
> episode now ends with the brick lifted (sentence "Pick up the brick and lift it."), the move into the
> green box happens between the episodes without recording, the Task box is never touched, and bowls
> follow alternation rules instead of `layout.py`.

## Your role

- **You prepare and check; people move the arm.** Two people record: **A** uses the leader arm and
  presses the arrow keys in Studio; **B** runs `layout.py` and `capture.py` and resets the table.
- **Never run anything that moves the follower arm** unless someone at the station has confirmed in
  this chat that the workspace is clear. Recording itself is teleoperation and is done by A, not you.
- **Interactive programs belong to the people.** `capture.py` (camera window, key presses) and
  `layout.py` (waits for Enter) must run in terminals that B uses directly. Start them only if asked,
  and say which terminal they're in.
- **Don't change locked settings.** Once the inspection camera box is set (step 3), don't edit
  `anomaly/camera_config.json` or move the box. Don't edit the Studio environment `policy-cell`.
- The anomaly **model is not needed** for recording. `capture.py` only shows the green target box and
  saves labelled photos; the model is trained from them later.

## Steps

### 0. Update the code
```bash
cd ~/intel-robot-challenge && git pull
```

### 1. Check the follower arm (read-only, safe to run)
```bash
cd ~/intel-robot-challenge
physical-ai-studio/application/backend/.venv/bin/python tools/servo_check.py           # follower
physical-ai-studio/application/backend/.venv/bin/python tools/servo_check.py leader    # leader
```
It needs Studio's backend Python (system `python3` has no `scservo_sdk`), and it refuses to run while
a Studio session holds the arm, so run it before opening the recording view.
Report any motor that is hot, weak, low on voltage or has errors. Fix before recording.

### 2. Start Studio (two long-running terminals)
```bash
# Terminal 1: backend, port 7860
cd ~/intel-robot-challenge/physical-ai-studio/application/backend
uv run --extra xpu physicalai-studio serve

# Terminal 2: UI, port 3000
cd ~/intel-robot-challenge/physical-ai-studio/application/ui
npm run start
```
Check: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:7860` and `...:3000` answer.

Then the people, in the browser at http://localhost:3000 (project `intel`):
**Datasets → new dataset** → name `cell-v1`, environment `policy-cell`, default task exactly:
`Pick up the brick and show it to the inspection camera.`

### 3. Inspection camera (terminal 3, person B keeps it open all session)
```bash
cd ~/intel-robot-challenge/anomaly
../.venv/bin/python capture.py
```
With the arm holding a brick at the showing point:
- click the brick to centre the box, `+` / `-` to size it
- `k` focus, `1` / `2` brightness to 110–150, `3` / `4` until white paper looks white
- then **don't change it again**; put the window where A can see it (it's A's target)

If it can't open the camera: Studio or another `capture.py` is using it (GUIDE section 14).

### 4. Layout script (terminal 4, person B)
```bash
cd ~/intel-robot-challenge
python3 recording/layout.py --stage 1
```
Add `--colours <good colour> <defective colour>` if the bowls aren't blue and orange.
Progress is saved per stage; `q` quits and it resumes later.

### 5. Practise 5–10 cycles without recording
Smooth, same technique every time: approach from above, same grip, same lift height, same speed.

### 6. Record
In Studio: `cell-v1` → **Add episode**; wait for both camera feeds (`top`, `wrist`) and the 3D arm.

One cycle = two episodes, back to back (don't put the brick down in between):

| | Person A (leader arm) | Person B |
|---|---|---|
| Setup | Arm at home | Places brick and bowls as `layout.py` says |
| Episode 1, pick | **→** start → grab the brick → into the green box → hold still ~1 s → **→** accept | While it's held: `g` or `b` in `capture.py` (as `layout.py` says) |
| Episode 2, sort | **→** start → named bowl → home → hold still ~1 s → **→** accept | Before: paste the sort sentence into Studio's Task box (click, Ctrl+A, Ctrl+V). After: paste the pick sentence back, then Enter in `layout.py` |

- **The arrow keys do nothing while the cursor is in the Task box** (Studio ignores shortcuts while
  you type). After pasting a sentence, click an empty part of the Studio page, then press **→**.
- **←** discards. Discarded sort: bring the brick back to the green box without recording, redo it.
- Enter in `layout.py` **only when both episodes are accepted**.
- Every ~10 cycles: replay a few episodes in Studio, look for joint-graph spikes, stalls, black or
  frozen frames; delete bad ones.
- Rest the follower every 30–40 min (hot motors get weak). Re-run step 1 if it feels off.

### 7. In parallel (not blocking recording)
- **Modal:** `uvx --python 3.13 --from 'modal[api-proxy-support]>=1.6.3,<2' modal setup`, then in Studio
  **Settings → Training Targets → Modal → Deploy and connect** (first build takes minutes).
- **Hugging Face token** (read-only) in Studio **Settings → General → Hugging Face**. Never commit it.
- After ~20 good cycles: train a short SmolVLA run on Modal and **measure its speed** on this laptop
  (OpenVINO, GPU). That decides early whether ACT is needed for the pick (see
  [ACT_PIPELINE.md](ACT_PIPELINE.md)).

## Checklist before the first recorded episode

- [ ] `git pull` done, `servo_check.py` clean
- [ ] Studio backend + UI running, `cell-v1` created in `policy-cell`
- [ ] Top camera view clear: no cables, bags, people; leader arm out of view
- [ ] Lamp on, diffuse light
- [ ] Inspection box set and locked in `capture.py`
- [ ] Wrist turned ±90° at the showing point by hand: wrist camera cable doesn't snag
- [ ] Brick colours and sizes mixed across episodes; spare defective bricks in a separate box
- [ ] Someone can reach the follower's 12 V plug (emergency stop)

## Where things end up

| What | Where |
|---|---|
| Episodes | Studio dataset `cell-v1` (LeRobot v3) |
| Inspection crops | `anomaly/dataset/normal` (`g`), `anomaly/dataset/abnormal` (`b`) |
| Full frames | `anomaly/dataset_full/` (for `recrop.py` if the box ever changes) |
| Layout progress | saved by `recording/layout.py` per stage |

Problems: GUIDE.md section 14 (troubleshooting).
