from ultralytics import YOLO
import torch

model = YOLO(r"C:\Users\Vansh\Desktop\photoshopAutomation\model\inference\best.pt")

results = model.predict(
    source=r"C:\Users\Vansh\Desktop\photoshopAutomation\model\inference\test.jpg",
    conf=0.001,      # VERY low → keep everything
    iou=0.7,
    save=False,
    verbose=False
)

for r in results:
    if r.obb is None or len(r.obb.conf) == 0:
        continue

    cls_ids = r.obb.cls.int()
    confs = r.obb.conf

    selected_indices = []

    # Loop over each unique class
    for cls in torch.unique(cls_ids):
        class_mask = cls_ids == cls
        class_confs = confs[class_mask]

        # Index of highest-confidence box for this class
        best_idx_in_class = torch.argmax(class_confs)

        # Convert to index in original tensor
        best_global_idx = torch.nonzero(class_mask)[best_idx_in_class]
        selected_indices.append(best_global_idx.item())

    # Keep only best box per class
    selected_indices = torch.tensor(selected_indices)
    r.obb.data = r.obb.data[selected_indices]

    # Save visualization
    r.save(filename="per_class_best.jpg")
