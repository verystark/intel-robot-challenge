"""Make an INT8 copy of the exported Anomalib model with NNCF.

Two modes, measured on this PatchCore model (22 held-out good photos, 2026-11-14):

| Mode | What becomes INT8 | Size | Score change vs FP32 |
|---|---|---|---|
| `weights` (default) | weights only; activations stay floating point | 35 MB -> 9 MB | mean 0.016, max 0.06 |
| `full` | weights and activations, calibrated on good photos | ~32 MB | mean 0.07, max 0.28 |

PatchCore scores a crop by its distance to stored "normal" patch features, and
INT8 activations shift those features enough to move scores a lot, so `full`
needs its own bands (calibrate_bands.py on that model) and a check with real
defects before use. Compare both with bench/anomaly_bench.py.

    ../.venv/bin/python quantize_int8.py                       # weights -> exported_model_int8/
    ../.venv/bin/python quantize_int8.py --mode full --out exported_model_int8_full/weights/openvino/model.xml
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from detector import DEFAULT_MODEL, INT8_MODEL  # noqa: E402

DATASET_DIR = HERE / "dataset"


def to_input(path: Path) -> np.ndarray:
    """Same preprocessing as detector.Detector.score: RGB, 0..1, NCHW, batch of one."""
    rgb = cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return np.ascontiguousarray(rgb.transpose(2, 0, 1)[np.newaxis])


def quantize(model_xml: Path, out_xml: Path, photos: list[Path] | None = None, mode: str = "weights") -> Path:
    import nncf
    import openvino as ov

    model = ov.Core().read_model(str(model_xml))
    if mode == "weights":
        quantized = nncf.compress_weights(model, mode=nncf.CompressWeightsMode.INT8_ASYM)
    elif mode == "full":
        if not photos:
            raise ValueError("Full INT8 needs calibration photos.")
        quantized = nncf.quantize(model, nncf.Dataset(photos, to_input), subset_size=len(photos))
    else:
        raise ValueError(f"Unknown mode {mode!r}")
    out_xml.parent.mkdir(parents=True, exist_ok=True)
    ov.save_model(quantized, str(out_xml))
    return out_xml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, default=INT8_MODEL)
    parser.add_argument("--mode", choices=("weights", "full"), default="weights")
    parser.add_argument("--samples", type=int, default=150, help="calibration photos from dataset/normal (full mode)")
    args = parser.parse_args()

    photos = sorted((DATASET_DIR / "normal").glob("*.png"))
    random.Random(0).shuffle(photos)
    photos = photos[: args.samples]
    if args.mode == "full" and not photos:
        sys.exit("No photos in dataset/normal to calibrate on.")
    print(f"Quantising {args.model} to INT8 ({args.mode})...")
    start = time.perf_counter()
    out = quantize(args.model, args.out, photos, args.mode)
    size = out.with_suffix(".bin").stat().st_size / 1e6
    print(f"INT8 model: {out}  ({size:.1f} MB, {time.perf_counter() - start:.0f} s)")


if __name__ == "__main__":
    main()
