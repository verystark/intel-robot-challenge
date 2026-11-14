"""Train a PatchCore anomaly model on the captured Duplo dataset and export it to OpenVINO.

Expects images captured with capture.py:
    dataset/normal       - good bricks (training)
    dataset/abnormal     - defective bricks (testing; optional, see below)
    dataset/test_normal  - extra good bricks (testing)

PatchCore learns from the good photos only. The defective ones measure how well it
catches defects and set the score where "defective" starts. Without them the
threshold becomes the highest score among the held-out good photos, so every good
brick seen so far passes but nothing says how many defects slip through: retrain
once there are defective photos.

test_normal must not be a random pick from normal: photos taken in quick bursts
are near-duplicates, which would make the threshold far too low. Move a block of
photos taken at a different time (other bricks, other grips).

Output:
    exported_model/weights/openvino/model.xml (+ .bin, metadata)
"""

import argparse
import sys
import time
from pathlib import Path

from PIL import Image
from anomalib.data import Folder
from anomalib.deploy import ExportType
from anomalib.engine import Engine
from anomalib.models import Patchcore

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
DATASET_DIR = HERE / "dataset"
EXPORT_DIR = HERE / "exported_model"
EXPORT_DIR_INT8 = HERE / "exported_model_int8"
RESULTS_DIR = HERE / "results"
IMAGE_SIZE = (256, 256)
SUBDIRS = ("normal", "abnormal", "test_normal")


def check_dataset() -> tuple[tuple[int, int], bool]:
    """Check the folders and that all photos are the same size.

    Returns that size as (height, width), and whether there are defective photos.
    """
    sizes: set[tuple[int, int]] = set()
    has_defects = False
    for sub in SUBDIRS:
        folder = DATASET_DIR / sub
        files = sorted(folder.glob("*.png")) if folder.exists() else []
        print(f"  {sub:<12} {len(files):>4} images")
        if sub == "abnormal":
            has_defects = bool(files)
        elif not files:
            raise SystemExit(f"No images in {folder}. Capture some with capture.py first.")
        for path in files:
            with Image.open(path) as image:
                sizes.add((image.height, image.width))
    if len(sizes) != 1:
        raise SystemExit(f"Photos have different sizes {sorted(sizes)}: run recrop.py so they all match the box.")
    return sizes.pop(), has_defects


def get_threshold(model) -> float | None:
    """Return the raw (un-normalized) image threshold learned during validation."""
    post = getattr(model, "post_processor", None)
    for obj, attr in ((post, "image_threshold"), (post, "_image_threshold"), (model, "image_threshold")):
        value = getattr(obj, attr, None) if obj is not None else None
        if value is None:
            continue
        value = getattr(value, "value", value)  # anomalib 1.x wraps it in a metric
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def xpu_available() -> bool:
    try:
        import torch

        return hasattr(torch, "xpu") and torch.xpu.is_available()
    except Exception:  # noqa: BLE001
        return False


def make_engine(accelerator: str) -> Engine:
    """Engine on the Intel GPU (xpu) or the CPU. 'auto' in Lightning never picks the Intel GPU."""
    if accelerator == "xpu":
        from anomalib.engine.accelerator import XPUAccelerator
        from anomalib.engine.strategy import SingleXPUStrategy

        return Engine(accelerator=XPUAccelerator(), strategy=SingleXPUStrategy(), devices=1,
                      max_epochs=1, default_root_dir=RESULTS_DIR)
    return Engine(accelerator="cpu", max_epochs=1, default_root_dir=RESULTS_DIR)


def make_model() -> Patchcore:
    return Patchcore(
        backbone="resnet18",
        layers=["layer2", "layer3"],
        pre_processor=Patchcore.configure_pre_processor(image_size=IMAGE_SIZE),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train PatchCore on dataset/ and export it to OpenVINO.")
    parser.add_argument("--accelerator", choices=("auto", "xpu", "cpu"), default="auto",
                        help="train on the Intel GPU (xpu) or the CPU; auto = xpu when available")
    parser.add_argument("--int8", action="store_true",
                        help=f"also export an INT8 model (post-training quantisation) to {EXPORT_DIR_INT8.name}/")
    args = parser.parse_args()

    print(f"Dataset: {DATASET_DIR}")
    crop_size, has_defects = check_dataset()
    if not has_defects:
        print(
            "\nNo defective photos: the threshold will be the highest score among the held-out good\n"
            "photos, and testing is skipped. Retrain once dataset/abnormal has photos."
        )

    datamodule = Folder(
        name="duplo",
        root=DATASET_DIR,
        normal_dir="normal",
        abnormal_dir="abnormal" if has_defects else None,
        normal_test_dir="test_normal",
        train_batch_size=32,
        eval_batch_size=32,
        num_workers=0,  # safest on Windows
    )

    accelerator = args.accelerator
    if accelerator == "auto":
        accelerator = "xpu" if xpu_available() else "cpu"

    model = make_model()
    engine = make_engine(accelerator)
    print(f"\nTraining PatchCore on {'the Intel GPU (xpu)' if accelerator == 'xpu' else 'the CPU'}...")
    start = time.perf_counter()
    try:
        engine.fit(model=model, datamodule=datamodule)
    except Exception as error:  # noqa: BLE001
        if accelerator != "xpu":
            raise
        print(f"\nTraining on the Intel GPU failed ({type(error).__name__}: {error}). Retrying on the CPU...")
        accelerator = "cpu"
        model, engine = make_model(), make_engine("cpu")
        start = time.perf_counter()
        engine.fit(model=model, datamodule=datamodule)
    train_s = time.perf_counter() - start

    test_results = []
    if has_defects:  # AUROC and F1 need both good and defective photos
        print("\nTesting...")
        test_results = engine.test(model=model, datamodule=datamodule)

    # The exported model contains the pre-processor (resize to IMAGE_SIZE + normalize), so it
    # takes the crop exactly as capture.py / camera.crop_box() produce it. A fixed shape of one
    # image suits live inspection and the NPU. Without "dynamic_axes": {} the PatchCore export
    # gets locked to a batch of 2 and rejects single images.
    model = model.cpu()
    export_kwargs = {
        "model": model,
        "export_type": ExportType.OPENVINO,
        "input_size": crop_size,
        "onnx_kwargs": {"dynamic_axes": {}, "opset_version": 18},
    }
    print(f"\nExporting to OpenVINO IR (input: 1 crop of {crop_size[1]}x{crop_size[0]})...")
    export_path = engine.export(export_root=EXPORT_DIR, **export_kwargs)
    int8_path = None
    if args.int8:
        # Weight-only INT8 of the exported model (see quantize_int8.py for why not full INT8).
        # Anomalib's own INT8_PTQ export also fails here: it calibrates with whole batches,
        # which the single-crop model rejects.
        from quantize_int8 import quantize

        print("\nMaking the INT8 (weight-only) model...")
        int8_path = quantize(Path(export_path), EXPORT_DIR_INT8 / "weights" / "openvino" / "model.xml")

    threshold = get_threshold(model)
    print("\n" + "=" * 50)
    print(f"Trained on:       {accelerator} in {train_s / 60:.1f} min")
    print(f"Exported model:   {export_path}")
    if int8_path is not None:
        print(f"INT8 model:       {int8_path}")
    if threshold is not None:
        print(f"Image threshold:  {threshold:.4f} (raw score; normalized threshold is 0.5)")
    else:
        print("Image threshold:  not found on model")
    print("Test metrics:" if has_defects else "Test metrics:     skipped (no defective photos)")
    for result in test_results or []:
        for name, value in result.items():
            print(f"  {name:<20} {float(value):.4f}")
    print("=" * 50)


if __name__ == "__main__":
    main()
