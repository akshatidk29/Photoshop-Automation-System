# Garment Part Detection using YOLO-v11 OBB

## Classes
- left_shoulder
- right_shoulder
- left_bicep
- right_bicep
- left_cuff
- right_cuff
- left_collar
- right_collar

## Train
yolo obb train model=models/yolov11n-obb.pt data=dataset/data.yaml epochs=100 imgsz=640

## Predict
yolo obb predict model=best.pt source=image.jpg
