"""Compare inspection-model setups on real show-pose photos, with cross-validation.

Every good photo is scored by a model that never saw it: the good photos are split into folds,
each fold's model trains on the others and scores that fold plus all defective photos.

Setups (all PatchCore, as train_export.py trains it):
    full       the whole crop from the camera box (what the loop scored so far)
    roi        only the brick region at the gripper tips (anomaly/roi.json)
    roi_flip   the brick region, plus a vertically flipped copy of each good photo
               (turning the wrist 180 deg shows the brick upside down)

    ../.venv/bin/python eval_show.py                    # all setups, 4 folds
    ../.venv/bin/python eval_show.py --setups roi_flip --folds 3

Prints, per setup: AUROC (good vs defective), the highest good score, the lowest defective
score, and the per-photo scores. Writes results to results/eval_show.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from detector import Detector  # noqa: E402
from roi import apply_roi, load_roi  # noqa: E402

DATASET = HERE / "dataset_show"
OLD_NORMAL = HERE / "dataset" / "normal"  # good bricks photographed at the old, hand-held pose

# Named setups. extra = how many old good photos join the training (resized to the training size).
SETUPS = {
    "full":          dict(roi=False, flip=False, extra=0, backbone="resnet18", coreset=0.1, size=256),
    "roi":           dict(roi=True, flip=False, extra=0, backbone="resnet18", coreset=0.1, size=256),
    "roi_flip":      dict(roi=True, flip=True, extra=0, backbone="resnet18", coreset=0.1, size=256),
    "roi_all":       dict(roi=True, flip=False, extra=0, backbone="resnet18", coreset=1.0, size=256),
    "roi_old150":    dict(roi=True, flip=False, extra=150, backbone="resnet18", coreset=0.1, size=256),
    "roi_old400":    dict(roi=True, flip=False, extra=400, backbone="resnet18", coreset=0.1, size=256),
    "roi_wide":      dict(roi=True, flip=False, extra=0, backbone="wide_resnet50_2", coreset=0.1, size=256),
    "roi_old150_wide": dict(roi=True, flip=False, extra=150, backbone="wide_resnet50_2", coreset=0.1, size=256),
    "full_old150":   dict(roi=False, flip=False, extra=150, backbone="resnet18", coreset=0.1, size=256),
}


def auroc(good: list[float], bad: list[float]) -> float:
    pairs = [(g < b) + 0.5 * (g == b) for g in good for b in bad]
    return float(np.mean(pairs)) if pairs else float("nan")


def prepare(img: np.ndarray, setup: str, roi) -> np.ndarray:
    return img if setup == "full" else apply_roi(img, roi)


def train_and_export(train: list[np.ndarray], test_good: list[np.ndarray], bad: list[np.ndarray],
                     workdir: Path, backbone: str, coreset: float = 0.1, size: int = 256) -> Path:
    from anomalib.data import Folder
    from anomalib.deploy import ExportType
    from anomalib.engine import Engine
    from anomalib.models import Patchcore

    data = workdir / "data"
    for sub, images in (("normal", train), ("test_normal", test_good), ("abnormal", bad)):
        (data / sub).mkdir(parents=True, exist_ok=True)
        for i, im in enumerate(images):
            cv2.imwrite(str(data / sub / f"{i:04d}.png"), im)
    dm = Folder(name="show", root=data, normal_dir="normal", abnormal_dir="abnormal",
                normal_test_dir="test_normal", train_batch_size=16, eval_batch_size=16, num_workers=0)
    model = Patchcore(backbone=backbone, layers=["layer2", "layer3"], coreset_sampling_ratio=coreset,
                      pre_processor=Patchcore.configure_pre_processor(image_size=(size, size)))
    try:
        from anomalib.engine.accelerator import XPUAccelerator
        from anomalib.engine.strategy import SingleXPUStrategy
        engine = Engine(accelerator=XPUAccelerator(), strategy=SingleXPUStrategy(), devices=1, max_epochs=1,
                        default_root_dir=workdir / "results", logger=False, enable_progress_bar=False)
        engine.fit(model=model, datamodule=dm)
    except Exception:  # noqa: BLE001
        model = Patchcore(backbone=backbone, layers=["layer2", "layer3"], coreset_sampling_ratio=coreset,
                          pre_processor=Patchcore.configure_pre_processor(image_size=(size, size)))
        engine = Engine(accelerator="cpu", max_epochs=1, default_root_dir=workdir / "results",
                        logger=False, enable_progress_bar=False)
        engine.fit(model=model, datamodule=dm)
    h, w = train[0].shape[:2]
    path = engine.export(model=model.cpu(), export_type=ExportType.OPENVINO, export_root=workdir / "export",
                         input_size=(h, w), onnx_kwargs={"dynamic_axes": {}, "opset_version": 18})
    return Path(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--setups", nargs="+", default=["full", "roi", "roi_flip"], help=f"from {list(SETUPS)}")
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--backbone", default="resnet18")
    parser.add_argument("--device", default="GPU")
    args = parser.parse_args()

    roi = load_roi()
    goods = sorted((DATASET / "normal").glob("*.png")) + sorted((DATASET / "test_normal").glob("*.png"))
    bads = sorted((DATASET / "abnormal").glob("*.png"))
    good_imgs = [cv2.imread(str(p)) for p in goods]
    bad_imgs = [cv2.imread(str(p)) for p in bads]
    print(f"{len(goods)} good, {len(bads)} defective photos; ROI {roi}; backbone {args.backbone}")

    results = {}
    old = sorted(OLD_NORMAL.glob("*.png"))
    for setup in args.setups:
        cfg = SETUPS[setup]
        t0 = time.time()
        extra = []
        if cfg["extra"]:
            step = max(1, len(old) // cfg["extra"])
            extra = [cv2.imread(str(p)) for p in old[::step][: cfg["extra"]]]
        fold_aurocs = []
        good_scores = [None] * len(goods)
        bad_scores = [[] for _ in bads]
        folds = [list(range(k, len(goods), args.folds)) for k in range(args.folds)]
        for k, held in enumerate(folds):
            mode = "roi" if cfg["roi"] else "full"
            train = [prepare(good_imgs[i], mode, roi) for i in range(len(goods)) if i not in held]
            if cfg["flip"]:
                train += [cv2.flip(im, 0) for im in train]
            h, w = train[0].shape[:2]
            train += [cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA) for im in extra]
            test_good = [prepare(good_imgs[i], mode, roi) for i in held]
            bad = [prepare(im, mode, roi) for im in bad_imgs]
            with tempfile.TemporaryDirectory(prefix="evalshow_") as tmp:
                xml = train_and_export(train, test_good, bad, Path(tmp), cfg["backbone"], cfg["coreset"], cfg["size"])
                det = Detector(xml, args.device)
                fold_good = []
                for i, im in zip(held, test_good):
                    good_scores[i] = det.score(im)[0]
                    fold_good.append(good_scores[i])
                fold_bad = []
                for j, im in enumerate(bad):
                    bad_scores[j].append(det.score(im)[0])
                    fold_bad.append(bad_scores[j][-1])
                fold_aurocs.append(auroc(fold_good, fold_bad))
            print(f"  {setup}: fold {k + 1}/{len(folds)} done", flush=True)
        bad_mean = [float(np.mean(s)) for s in bad_scores]
        res = {
            "setup": cfg,
            "auroc": auroc(good_scores, bad_mean),
            "fold_auroc": round(float(np.mean(fold_aurocs)), 3),
            "max_good": max(good_scores), "min_bad": min(bad_mean),
            "good": {p.name: round(s, 3) for p, s in zip(goods, good_scores)},
            "bad": {p.name: round(s, 3) for p, s in zip(bads, bad_mean)},
            "minutes": round((time.time() - t0) / 60, 1),
        }
        results[setup] = res
        print(f"\n{setup}: AUROC {res['auroc']:.3f} (per fold {res['fold_auroc']:.3f}) | highest good {res['max_good']:.2f} | lowest defective "
              f"{res['min_bad']:.2f} | {res['minutes']} min")
        print("  good:     ", " ".join(f"{s:.2f}" for s in sorted(good_scores)))
        print("  defective:", " ".join(f"{p.stem[-12:]}={s:.2f}" for p, s in zip(bads, bad_mean)))
    out = HERE / "results" / "eval_show.json"
    out.parent.mkdir(exist_ok=True)
    previous = json.loads(out.read_text()) if out.exists() else {}
    previous.update(results)
    out.write_text(json.dumps(previous, indent=1) + "\n")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
