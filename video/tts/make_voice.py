#!/usr/bin/env python3
"""Narration for the video with Kokoro-82M, locally on the CPU.

    .venv/bin/python make_voice.py --samples              # one line in several voices, to choose one
    .venv/bin/python make_voice.py --voice bm_george      # every scene -> public/vo/*.wav + timings.json

Reads ../script.json (narration with {caption|voice} spellings and {{NUMBER}} placeholders) and
../public/data.json (the numbers; run scripts/build_data.py first). Writes one WAV per scene and
word timings for the captions.
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf

VIDEO = Path(__file__).resolve().parents[1]
RATE = 24000
SAMPLE_VOICES = ["bm_george", "bm_lewis", "bf_emma", "am_michael", "af_heart"]
SAMPLE_EXTRA = " The project is called Jenssenit."

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def words_for(n: int) -> str:
    """Integers below 10,000 as English words, for the voice."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else "-" + ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return ONES[n // 100] + " hundred" + ("" if rest == 0 else " " + words_for(rest))
    rest = n % 1000
    return words_for(n // 1000) + " thousand" + ("" if rest == 0 else " " + words_for(rest))


def fill(text: str, numbers: dict) -> str | None:
    """Replace {{NAME}} with {digits|words}. None if a number is missing."""
    missing = False

    def sub(m):
        nonlocal missing
        value = numbers.get(m.group(1))
        if value is None:
            missing = True
            return m.group(0)
        n = round(float(value))
        return "{" + f"{n:,}" + "|" + words_for(n) + "}"

    out = re.sub(r"\{\{(\w+)\}\}", sub, text)
    return None if missing else out


def units(text: str) -> list[tuple[str, str]]:
    """Split marked-up text into (caption word, voice text) units."""
    out = []
    for m in re.finditer(r"\{([^|}]+)\|([^}]+)\}([^\s{]*)|(\S+)", text):
        if m.group(4):
            out.append((m.group(4), m.group(4)))
        else:  # punctuation right after a {caption|voice} unit belongs to it
            out.append((m.group(1) + m.group(3), m.group(2) + m.group(3)))
    return out


def synthesise(pipeline, voice: str, text: str, speed: float):
    """Audio plus (token text, start, end) for every word-like token, across chunks."""
    audio_parts, tokens, offset = [], [], 0.0
    for result in pipeline(text, voice=voice, speed=speed):
        audio = result.audio.numpy() if hasattr(result.audio, "numpy") else np.asarray(result.audio)
        for t in result.tokens or []:
            if any(c.isalnum() for c in t.text):
                start = None if t.start_ts is None else offset + t.start_ts
                end = None if t.end_ts is None else offset + t.end_ts
                tokens.append((t.text, start, end))
        audio_parts.append(audio)
        offset += len(audio) / RATE
    return np.concatenate(audio_parts), tokens


def fill_times(tokens):
    """Fill missing token times from their neighbours."""
    out = [list(t) for t in tokens]
    for i, t in enumerate(out):
        if t[1] is None:
            t[1] = out[i - 1][2] if i and out[i - 1][2] is not None else 0.0
        if t[2] is None:
            nxt = next((u[1] for u in out[i + 1:] if u[1] is not None), None)
            t[2] = nxt if nxt is not None else t[1]
    return out


def align(unit_list, tokens, duration: float) -> list[dict]:
    """Word timings for the caption words, matched to the voice tokens letter by letter
    (so it doesn't matter how the phonemiser splits hyphens or 's). Falls back to timing by
    length if the letters don't line up."""
    tokens = fill_times(tokens)
    owner = [i for i, (text, _, _) in enumerate(tokens) for ch in text if ch.isalnum()]
    lengths = [sum(ch.isalnum() for ch in v) for _, v in unit_list]
    words = []
    if tokens and sum(lengths) == len(owner):
        pos = 0
        for (caption, _), n in zip(unit_list, lengths):
            if n == 0:
                end = words[-1]["end"] if words else 0.0
                words.append({"text": caption, "start": end, "end": end})
                continue
            first, last = tokens[owner[pos]], tokens[owner[pos + n - 1]]
            words.append({"text": caption, "start": round(first[1], 3), "end": round(last[2], 3)})
            pos += n
        return words
    print(f"  timing fallback: {sum(lengths)} letters in the script vs {len(owner)} in the voice tokens")
    total = sum(len(c) + 1 for c, _ in unit_list)
    t = 0.0
    for caption, _ in unit_list:
        length = duration * (len(caption) + 1) / total
        words.append({"text": caption, "start": round(t, 3), "end": round(t + length, 3)})
        t += length
    return words


TARGET_RMS_DB = -19.0  # speech loudness; peaks are kept under -1 dBFS


def normalise(audio):
    """Bring speech to a steady loudness, so the narration isn't quiet next to the footage."""
    audio = np.asarray(audio, dtype=np.float32)
    voiced = audio[np.abs(audio) > 0.01]
    rms = float(np.sqrt(np.mean(voiced ** 2))) if voiced.size else 0.0
    if rms == 0.0:
        return audio
    gain = 10 ** (TARGET_RMS_DB / 20) / rms
    peak = float(np.max(np.abs(audio))) * gain
    if peak > 0.89:  # -1 dBFS
        gain *= 0.89 / peak
    return audio * gain


def pipeline_for(voice: str):
    import os

    import torch
    from kokoro import KPipeline

    # The laptop also runs the robot: stay on a few cores (TTS_THREADS to change).
    torch.set_num_threads(int(os.environ.get("TTS_THREADS", "2")))
    return KPipeline(lang_code="b" if voice.startswith("b") else "a", repo_id="hexgrad/Kokoro-82M")


def samples(numbers: dict, script: dict, speed: float) -> None:
    out = VIDEO / "out" / "voice-samples"
    out.mkdir(parents=True, exist_ok=True)
    text = fill(script["s3"], numbers) + SAMPLE_EXTRA
    voice_text = " ".join(v for _, v in units(text))
    gap = np.zeros(int(RATE * 0.8), dtype=np.float32)
    joined = []
    for voice in SAMPLE_VOICES:
        pipeline = pipeline_for(voice)
        audio, _ = synthesise(pipeline, voice, voice_text, speed)
        audio = normalise(audio)
        sf.write(out / f"{voice}.wav", audio, RATE)
        joined += [audio, gap]
        print(f"{voice}: {len(audio) / RATE:.1f} s -> {out / (voice + '.wav')}")
    sf.write(out / "all_voices.wav", np.concatenate(joined), RATE)
    print(f"all voices, in this order: {', '.join(SAMPLE_VOICES)} -> {out / 'all_voices.wav'}")


def narration(numbers: dict, script: dict, voice: str, speed: float, only: list[str] | None = None) -> None:
    out = VIDEO / "public" / "vo"
    out.mkdir(parents=True, exist_ok=True)
    pipeline = pipeline_for(voice)
    timings = {"voice": voice, "speed": speed, "rate": RATE, "scenes": {}}
    existing = out / "timings.json"
    if only and existing.exists():  # keep the other scenes as they are
        old = json.loads(existing.read_text())
        if old.get("voice") != voice:
            raise SystemExit(f"timings.json uses {old.get('voice')}; regenerate every scene to switch voice")
        timings["scenes"] = old["scenes"]
    for scene, raw in script.items():
        if scene.startswith("_") or scene.endswith("_draft") or (only and scene not in only):
            continue
        text = fill(raw, numbers)
        draft = False
        if text is None:  # numbers not measured yet: use the draft line, never invented numbers
            text, draft = script.get(scene + "_draft"), True
            if text is None:
                print(f"{scene}: numbers missing and no draft line, skipped")
                continue
        unit_list = units(text)
        audio, tokens = synthesise(pipeline, voice, " ".join(v for _, v in unit_list), speed)
        duration = len(audio) / RATE
        sf.write(out / f"{scene}.wav", normalise(audio), RATE)
        (out / f"{scene}.tokens.json").write_text(json.dumps({"units": unit_list, "tokens": tokens, "duration": duration}))
        words = align(unit_list, tokens, duration)
        timings["scenes"][scene] = {"file": f"vo/{scene}.wav", "duration": round(duration, 3),
                                    "draft": draft, "words": words}
        print(f"{scene}: {duration:.1f} s, {len(words)} words{' (draft line)' if draft else ''}")
    (out / "timings.json").write_text(json.dumps(timings, indent=2))
    print(f"wrote {out / 'timings.json'}")


def retime() -> None:
    """Recompute the caption timings from the saved tokens, without synthesising again."""
    path = VIDEO / "public" / "vo" / "timings.json"
    timings = json.loads(path.read_text())
    for scene, entry in timings["scenes"].items():
        saved = json.loads((path.parent / f"{scene}.tokens.json").read_text())
        entry["words"] = align([tuple(u) for u in saved["units"]], [tuple(t) for t in saved["tokens"]], saved["duration"])
        print(f"{scene}: {len(entry['words'])} words")
    path.write_text(json.dumps(timings, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--samples", action="store_true", help="render one line in several voices")
    parser.add_argument("--voice", default="bm_george")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--retime", action="store_true", help="only recompute caption timings from saved tokens")
    parser.add_argument("--normalise-only", action="store_true", help="only re-level the saved WAVs")
    parser.add_argument("--scenes", nargs="+", help="only these scenes, e.g. s3 s7 (keeps the others)")
    args = parser.parse_args()
    if args.retime:
        retime()
        return
    if args.normalise_only:
        for wav in sorted((VIDEO / "public" / "vo").glob("*.wav")) + sorted((VIDEO / "out" / "voice-samples").glob("*.wav")):
            audio, rate = sf.read(wav, dtype="float32")
            sf.write(wav, normalise(audio), rate)
            print(f"levelled {wav.name}")
        return
    numbers = json.loads((VIDEO / "public" / "data.json").read_text())["numbers"]
    script = json.loads((VIDEO / "script.json").read_text())
    if args.samples:
        samples(numbers, script, args.speed)
    else:
        narration(numbers, script, args.voice, args.speed, args.scenes)


if __name__ == "__main__":
    main()
