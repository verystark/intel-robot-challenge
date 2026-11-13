"""Train a PatchCore anomaly model on the captured Duplo dataset and export it to OpenVINO.

Expects images captured with capture.py:
    dataset/normal       - good bricks (training)
    dataset/abnormal     - defective bricks (testing)
    dataset/test_normal  - extra good bricks (testing)

Output:
    exported_model/weights/openvino/model.xml (+ .bin, metadata)
"""

from pathlib import Path

from anomalib.data import Folder
from anomalib.deploy import ExportType
from anomalib.engine import Engine
from anomalib.models import Patchcore

HERE = Path(__file__).resolve().parent
DATASET_DIR = HERE / "dataset"
EXPORT_DIR = HERE / "exported_model"
RESULTS_DIR = HERE / "results"
IMAGE_SIZE = (256, 256)
SUBDIRS = ("normal", "abnormal", "test_normal")


def check_dataset() -> None:
    for sub in SUBDIRS:
        folder = DATASET_DIR / sub
        n = len(list(folder.glob("*.png"))) if folder.exists() else 0
        print(f"  {sub:<12} {n:>4} images")
        if n == 0:
            raise SystemExit(f"No images in {folder}. Capture some with capture.py first.")


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


def main() -> None:
    print(f"Dataset: {DATASET_DIR}")
    check_dataset()

    datamodule = Folder(
        name="duplo",
        root=DATASET_DIR,
        normal_dir="normal",
        abnormal_dir="abnormal",
        normal_test_dir="test_normal",
        train_batch_size=32,
        eval_batch_size=32,
        num_workers=0,  # safest on Windows
    )

    model = Patchcore(
        backbone="resnet18",
        layers=["layer2", "layer3"],
        pre_processor=Patchcore.configure_pre_processor(image_size=IMAGE_SIZE),
    )

    engine = Engine(accelerator="auto", max_epochs=1, default_root_dir=RESULTS_DIR)

    print("\nTraining PatchCore...")
    engine.fit(model=model, datamodule=datamodule)

    print("\nTesting...")
    test_results = engine.test(model=model, datamodule=datamodule)

    print("\nExporting to OpenVINO IR...")
    export_path = engine.export(
        model=model,
        export_type=ExportType.OPENVINO,
        export_root=EXPORT_DIR,
        input_size=IMAGE_SIZE,
    )

    threshold = get_threshold(model)
    print("\n" + "=" * 50)
    print(f"Exported model:   {export_path}")
    if threshold is not None:
        print(f"Image threshold:  {threshold:.4f} (raw score; normalized threshold is 0.5)")
    else:
        print("Image threshold:  not found on model")
    print("Test metrics:")
    for result in test_results or []:
        for name, value in result.items():
            print(f"  {name:<20} {float(value):.4f}")
    print("=" * 50)


if __name__ == "__main__":
    main()
