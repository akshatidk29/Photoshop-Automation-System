# train_obb_forced.py
from ultralytics import YOLO
import ultralytics, sys
import os
import torch
from multiprocessing import freeze_support


def main():
    print("python:", sys.version.split()[0])
    print("ultralytics:", ultralytics.__version__)
    
    # Check GPU availability
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"CUDA Version: {torch.version.cuda}")
        print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        device = 0  # Use first GPU
    else:
        print("WARNING: No GPU detected, training on CPU (will be slow)")
        device = "cpu"

    # load OBB model weights
    model = YOLO("models/yolo11s-seg.pt")

    # Dynamically resolve path to data.yaml
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_yaml_path = os.path.join(current_dir, "dataset", "data.yaml")

    # show some introspection to confirm this model is OBB-based
    try:
        print("model.yaml nc:", model.model.yaml.get("nc", "N/A"))
    except Exception:
        print("couldn't read model.model.yaml")

    # GPU-optimized training configuration
    model.train(
        task="segment",
        data=data_yaml_path,
        epochs=150,
        imgsz=1024,
        batch=24,               # Increased batch size for GPU (adjust based on VRAM)
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        cos_lr=True,
        perspective=0.001,
        warmup_epochs=3,
        degrees=10,
        scale=0.5,
        translate=0.1,
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.4,
        patience=30,
        workers=4,              # Increased workers for faster data loading
        device=device,          # Explicitly use GPU
        close_mosaic=10,        # Disable mosaic augmentation for last 10 epochs
    )


if __name__ == '__main__':
    freeze_support()
    main()

