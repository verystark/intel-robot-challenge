"""Run the exported Anomalib model with plain OpenVINO, and turn scores into a verdict.

Needs only openvino, numpy and opencv, so it works both in the repo venv (Anomalib)
and in Studio's backend venv, where the robot loop runs.

The exported model takes one RGB crop at the box size, exactly as camera.crop_box()
cuts it; resizing and normalisation happen inside the model. Its pred_score is
normalised so that 0.5 is the model's own threshold.

    det = Detector(device="NPU")
    score, heat, ms = det.score(crop_bgr)
    bands = load_bands()
    verdict(scores, bands)   # "GOOD" / "UNSURE" / "DEFECTIVE"
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = HERE / "exported_model" / "weights" / "openvino" / "model.xml"
INT8_MODEL = HERE / "exported_model_int8" / "weights" / "openvino" / "model.xml"
BANDS_PATH = HERE / "bands.json"
CACHE_DIR = HERE / "openvino_cache"

GOOD, UNSURE, DEFECTIVE = "GOOD", "UNSURE", "DEFECTIVE"


class Detector:
    """One compiled Anomalib model on one OpenVINO device."""

    def __init__(self, model_xml: str | Path = DEFAULT_MODEL, device: str = "GPU") -> None:
        import openvino as ov

        self.model_xml = Path(model_xml)
        if not self.model_xml.exists():
            raise FileNotFoundError(f"No model at {self.model_xml}. Run anomaly/train_export.py first.")
        self.device = device
        core = ov.Core()
        CACHE_DIR.mkdir(exist_ok=True)
        core.set_property({"CACHE_DIR": str(CACHE_DIR)})
        start = time.perf_counter()
        self.compiled = core.compile_model(core.read_model(str(self.model_xml)), device)
        self.compile_s = time.perf_counter() - start
        self.request = self.compiled.create_infer_request()
        shape = self.compiled.input(0).get_partial_shape()
        self.input_hw = (shape[2].get_length(), shape[3].get_length()) if shape.is_static else None
        self.outputs = {next(iter(o.get_names())): o for o in self.compiled.outputs}

    def score(self, crop_bgr: np.ndarray) -> tuple[float, np.ndarray, float]:
        """Score one crop (BGR, as OpenCV reads it).

        Returns the normalised score (0.5 = threshold), the anomaly map resized to the
        crop (float, roughly 0..1) and the inference time in ms.
        """
        if self.input_hw and crop_bgr.shape[:2] != self.input_hw:
            raise ValueError(
                f"Crop is {crop_bgr.shape[1]}x{crop_bgr.shape[0]} but the model expects "
                f"{self.input_hw[1]}x{self.input_hw[0]}: the box changed since training."
            )
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = np.ascontiguousarray(rgb.transpose(2, 0, 1)[np.newaxis])
        start = time.perf_counter()
        result = self.request.infer({0: tensor})
        ms = (time.perf_counter() - start) * 1000
        score = float(np.asarray(result[self.outputs["pred_score"]]).reshape(-1)[0])
        heat = np.asarray(result[self.outputs["anomaly_map"]], dtype=np.float32).squeeze()
        heat = cv2.resize(heat, (crop_bgr.shape[1], crop_bgr.shape[0]))
        return score, heat, ms


@dataclass
class Bands:
    """Scores below `low` are good, above `high` defective, in between unsure."""

    low: float = 0.4
    high: float = 0.6
    source: str = "default"


def load_bands(path: Path = BANDS_PATH) -> Bands:
    if not path.exists():
        return Bands()
    data = json.loads(path.read_text())
    return Bands(low=float(data["low"]), high=float(data["high"]), source=str(data.get("source", path.name)))


def save_bands(bands: Bands, extra: dict, path: Path = BANDS_PATH) -> None:
    path.write_text(json.dumps({**asdict(bands), **extra}, indent=2) + "\n")


def label(score: float, bands: Bands) -> str:
    if score > bands.high:
        return DEFECTIVE
    if score < bands.low:
        return GOOD
    return UNSURE


def verdict(scores: list[float], bands: Bands) -> str:
    """GUIDE2's rule: any view defective -> defective; all views good -> good; else unsure."""
    labels = [label(s, bands) for s in scores]
    if DEFECTIVE in labels:
        return DEFECTIVE
    if labels and all(lab == GOOD for lab in labels):
        return GOOD
    return UNSURE


def heatmap_overlay(crop_bgr: np.ndarray, heat: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    colour = cv2.applyColorMap((np.clip(heat, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)
    return cv2.addWeighted(crop_bgr, 1 - alpha, colour, alpha, 0)
