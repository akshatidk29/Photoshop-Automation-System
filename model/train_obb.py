# train_obb_forced.py
from ultralytics import YOLO
import ultralytics, sys

print("python:", sys.version.split()[0])
print("ultralytics:", ultralytics.__version__)

# load OBB model weights
model = YOLO("models/yolo11n-obb.pt")

# show some introspection to confirm this model is OBB-based
try:
    print("model.yaml nc:", model.model.yaml.get("nc", "N/A"))
except Exception:
    print("couldn't read model.model.yaml")

# Force training with explicit task argument
model.train(
    task="obb",
    data="model\\dataset\\data.yaml",
    epochs=150,
    imgsz=768,
    batch=8,
    optimizer="AdamW",
    lr0=0.001,
    lrf=0.01,
    cos_lr=True,
    warmup_epochs=3,
    degrees=10,
    scale=0.5,
    translate=0.1,
    hsv_h=0.015,
    hsv_s=0.5,
    hsv_v=0.4,
    patience=30,
    workers=4
)

