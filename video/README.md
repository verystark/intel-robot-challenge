# Submission video

The video is rendered from code with [Remotion](https://www.remotion.dev): every frame is real
footage or graphics drawn by code. The plan and the script are in
[VIDEO_PLAN.md](../VIDEO_PLAN.md). Render only while the arm is idle: it loads the CPU.

| Path | What |
|---|---|
| `facts.json` | Facts typed in by hand: dataset, models in the take, evaluation results, repo link, team |
| `script.json` | The AI narration per scene. `{caption\|voice}` gives the voice another spelling; `{{NAME}}` is a number from `public/data.json` |
| `scripts/build_data.py` | Builds `public/data.json` from `facts.json`, `bench/results/`, a loop run, the evaluation rounds and the footage present |
| `scripts/coverage.py` | Where the training data grasped and released (forward kinematics) → `public/coverage.json`. Run with Studio's Python |
| `layouts/` | Evaluation rounds: `round_NN.json` / `.svg` from `tools/random_layout.py`, `round_NN_eval.json` from `tools/eval_round.py` |
| `tts/make_voice.py` | Kokoro-82M narration on the CPU → `public/vo/*.wav` + `timings.json` (captions) |
| `public/footage/` | Our footage, named by shot ID: `a1.mp4`, `a2.mp4`, `a4.mp4`, ... (not in git) |
| `src/` | The scenes. `src/data.ts` sets scene order and lengths |
| `src/deck/Deck.tsx` | The 9-slide submission deck (plan: SUBMISSION.md §6), from the same data and components. `scripts/deck.mjs` renders one PNG per slide, `scripts/deck_pdf.py` joins them into a PDF |
| `out/` | Renders, stills, voice samples (not in git) |

## Commands

From `video/`:

```bash
npm install                                    # once
python3 scripts/build_data.py                  # after new numbers, footage, a loop run or an evaluation round
../physical-ai-studio/application/backend/.venv/bin/python scripts/coverage.py   # after the training dataset changes
cd tts && uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python torch --index-url https://download.pytorch.org/whl/cpu && uv pip install --python .venv/bin/python kokoro soundfile 'misaki[en]' && cd ..   # once
tts/.venv/bin/python tts/make_voice.py --voice bm_george   # after changing script.json or the numbers
tts/.venv/bin/python tts/make_voice.py --samples           # one line in five voices → out/voice-samples/
node scripts/stills.mjs                        # a few still frames → out/stills/
npx remotion studio                            # preview in the browser
npm run render                                 # → out/jenssenit.mp4
npm run thumbnail                              # → out/thumbnail.png (YouTube thumbnail)
npm run deck                                   # → out/deck/slide_NN.png + out/jenssenit_deck.pdf (the submission deck)
```

## Adding footage

1. Convert and add each clip by its shot ID (phones record a variable frame rate; this makes it
   constant 30 fps 1080p and rebuilds the data): `scripts/add_footage.sh a1 ~/video-raw/round3/IMG_1234.MOV`
2. For the run (`a1`): set `run_take.loop_run` and `run_take.footage_offset_s` in `facts.json`, and
   the segment start times (`SEGMENTS`) in `src/scenes/Scenes6to8.tsx`.
3. `python3 scripts/build_data.py`, then check with `node scripts/stills.mjs`.

Placeholders show as yellow `[NAME]`, and the draft banner at the top says what is still missing.
