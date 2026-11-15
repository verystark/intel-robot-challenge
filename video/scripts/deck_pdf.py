#!/usr/bin/env python3
"""Join out/deck/slide_NN.png into out/jenssenit_deck.pdf (Junction's limit is 20 MB).

Needs Pillow: the repo's .venv has it (`../.venv/bin/python scripts/deck_pdf.py`, from video/).
"""
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parents[1] / "out"
slides = sorted((OUT / "deck").glob("slide_*.png"))
if not slides:
    raise SystemExit("No slides: run node scripts/deck.mjs first.")
pages = [Image.open(p).convert("RGB") for p in slides]
pdf = OUT / "jenssenit_deck.pdf"
pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=144, quality=92)
size = pdf.stat().st_size / 1e6
print(f"wrote {pdf}: {len(pages)} slides, {size:.1f} MB{'  (OVER the 20 MB limit)' if size > 20 else ''}")
