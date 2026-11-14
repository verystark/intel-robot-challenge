# Alternative pipeline: ACT pick-and-present

A proposal to compare with the team plan in [GUIDE.md](../GUIDE.md) section 1. Goal: bricks dropped
anywhere on the table, picked up smoothly, shown to the inspection camera, sorted to the right plate,
as fast and smooth as possible.

## The idea

```text
 brick anywhere          held in front of            Anomalib verdict           plate
 on the table ──ACT──▶  inspection webcam   ──photo──▶ good / defective ──place──▶ good plate
                         (fixed "present" pose)                                   defective plate
```

1. **Pick & present (ACT):** grasp the brick wherever it lies and stop at one fixed pose, holding
   the brick in front of the inspection webcam. Never put it down.
2. **Classify (Anomalib):** photo of the held brick → good / defective / unsure.
3. **Place:** from the present pose to the right plate, then home. Either:
   - **a fixed, recorded motion** per plate (replayed joint trajectory: fastest, smoothest, can't
     miss, because the start pose and the plate never move), or
   - **two small ACT models** (place-good, place-bad), if the plates move between layouts.
4. **Unsure:** rotate the wrist a little in place and take another photo. No re-grasp needed.

The decision happens in the middle of the motion, so the task is split there. Each part does one
thing, so no language input is needed, and ACT (small, fast, smooth action chunks) is used throughout.

## Comparison with GUIDE.md (version b01a2e8)

GUIDE.md was rewritten and **now uses the held-brick idea**: the arm shows the brick to the
inspection webcam instead of putting it down, and the wrist turns for an unsure re-check. The
remaining difference is **which model moves the arm**.

| | GUIDE.md now | This plan |
|---|---|---|
| Pick & show | **SmolVLA**, sentence "Pick up the brick and show it to the inspection camera." | **ACT** |
| Show pose | Policy gets near it, script moves to the saved exact pose | Same idea (fixed present pose) |
| Inspection photo | Brick held in the gripper | Same |
| Unsure re-check | Script turns the wrist ~90°, still unsure → defective | Same |
| Sort | **SmolVLA**, verdict in the sentence ("The brick is defective. Put it in the orange bowl.") | Replayed fixed motion per plate, or ACT per plate |
| Models | **1** SmolVLA, steered by 3 sentences | ACT pick + replay/ACT place |
| Dataset | One `cell-v1`, each cycle = pick episode + sort episode (~240 episodes over 3 stages) | Pick & present episodes; placing: 1 recording per plate or ~30 episodes each |
| Speed / smoothness at run time | Slower: SmolVLA is much heavier per step (SnapFlow planned to help) | **Faster**: ACT is small; replayed placing is instant and smooth |
| Grasp quality | GUIDE cites the SmolVLA paper beating ACT on SO-100 pick-and-place | ACT is precise with few demos, but generalises less to unseen placements |
| Training | SmolVLA on Modal A100 | ACT on A10G (cheaper, quicker iterations) |
| Verdict reaches the robot | **Visibly: inside the VLA's sentence** (PDF asks for exactly this) | Verdict picks which motion runs: a signal, but no VLA reads it |
| VLA + Studio integration (20 pts in the PDF table) | **Strong** | **Weak** |

**GUIDE.md already contains this plan as its fallbacks** (section 12): if SmolVLA's grasp is weak
or slow, split `cell-v1` and train ACT on the pick episodes only, with no new recording; if SmolVLA
ignores the sort sentence, train one small ACT per bowl.

## Verdict

GUIDE.md's current plan is the better first choice: one grasp, held-brick inspection (as proposed
here), the verdict visibly steering a VLA, and one dataset that can still be split for ACT later.
Recording `cell-v1` as described keeps every option in this file open.

What this file still adds:

- **ACT for the pick is the speed upgrade, not just a fallback.** If SmolVLA's grasp works but is
  slow, ACT-pick + SmolVLA-sort keeps the VLA points (the verdict sentence still goes to SmolVLA)
  and makes the longest, most variable part of the cycle fast. Measure both (GUIDE section 11).
- **Replayed placing** is the last-resort fallback if both learned sort options fail: from the
  saved show pose, a recorded joint trajectory to each bowl can't miss as long as the bowls don't move.
- **Test the split early** (GUIDE section 12 says the round trip hasn't been tried): it's the only
  route to ACT without re-recording.
