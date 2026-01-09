from ultralytics import YOLO

model = YOLO("runs/obb/train/weights/best.pt")
model.export(format="onnx")
