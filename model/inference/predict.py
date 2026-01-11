from ultralytics import YOLO
import torch
import os
import cv2
import json

model = YOLO("C:/Users/Akshat Mittal/Desktop/photoshopAutomation/model/runs/segment/train2/weights/best.pt")

results = model.predict(
    source="C:/Users/Akshat Mittal/Desktop/photoshopAutomation/model/inference/test5.jpg",
    conf=0.001,      # VERY low → keep everything
    iou=0.7,
    save=True,      # We'll handle saving manually below
    verbose=True
)

with open("C:/Users/Akshat Mittal/Desktop/photoshopAutomation/model/inference/outputs/results.txt", "w") as f:
    f.write(str(results))

# Ensure output directory exists
output_dir = "C:/Users/Akshat Mittal/Desktop/photoshopAutomation/model/inference/outputs"
os.makedirs(output_dir, exist_ok=True)

# Will collect detections for all images and write to JSON at end
all_detections = []

for i, r in enumerate(results):
    # Pick highest-confidence prediction per class across available types (OBB, boxes/masks)
    selected_indices = None

    # Prefer OBB if present
    if getattr(r, "obb", None) is not None and r.obb is not None and hasattr(r.obb, "conf") and r.obb.conf is not None and len(r.obb.conf) > 0:
        cls_ids = r.obb.cls.int()
        confs = r.obb.conf
    # Else use axis-aligned boxes (detection or segmentation still has boxes)
    elif getattr(r, "boxes", None) is not None and r.boxes is not None and hasattr(r.boxes, "conf") and r.boxes.conf is not None and hasattr(r.boxes, "cls") and r.boxes.cls is not None:
        # Ensure there are any boxes
        if hasattr(r.boxes, "data") and r.boxes.data is not None and len(r.boxes.data) > 0:
            cls_ids = r.boxes.cls.int()
            confs = r.boxes.conf
        else:
            cls_ids, confs = None, None
    else:
        cls_ids, confs = None, None

    # Compute best index per class if we have predictions
    if cls_ids is not None and confs is not None and len(confs) > 0:
        chosen = []
        for cls in torch.unique(cls_ids):
            class_mask = cls_ids == cls
            class_confs = confs[class_mask]
            best_idx_in_class = torch.argmax(class_confs)
            best_global_idx = torch.nonzero(class_mask)[best_idx_in_class]
            chosen.append(best_global_idx.item())
        selected_indices = torch.tensor(chosen)

        # Apply selection to the corresponding structures
        if getattr(r, "obb", None) is not None and r.obb is not None and hasattr(r.obb, "data") and r.obb.data is not None and len(r.obb.data) > 0:
            r.obb.data = r.obb.data[selected_indices]
            # Keep cls/conf in sync when available
            try:
                r.obb.cls = r.obb.cls[selected_indices]
                r.obb.conf = r.obb.conf[selected_indices]
            except Exception:
                pass
        elif getattr(r, "boxes", None) is not None and r.boxes is not None and hasattr(r.boxes, "data") and r.boxes.data is not None and len(r.boxes.data) > 0:
            r.boxes.data = r.boxes.data[selected_indices]
            # If masks exist (segmentation), subset them to match boxes
            if getattr(r, "masks", None) is not None and r.masks is not None:
                try:
                    if hasattr(r.masks, "data") and r.masks.data is not None:
                        r.masks.data = r.masks.data[selected_indices]
                    if hasattr(r.masks, "xy") and r.masks.xy is not None:
                        r.masks.xy = [r.masks.xy[idx] for idx in selected_indices.tolist()]
                except Exception:
                    pass

    # Save visualization using plot() -> cv2.imwrite for explicit control
    annotated = r.plot()  # BGR numpy array
    out_path = os.path.join(output_dir, f"per_class_best_{i}.jpg")
    cv2.imwrite(out_path, annotated)
    print(f"Saved: {out_path}")

    # Collect structured detection info for later use
    dets = []

    # Prefer OBB detection details if present
    try:
        if getattr(r, "obb", None) is not None and r.obb is not None and hasattr(r.obb, "data") and r.obb.data is not None and len(r.obb.data) > 0:
            num = len(r.obb.data)
            for idx in range(num):
                try:
                    cls_val = int(r.obb.cls[idx].item()) if hasattr(r.obb, "cls") else None
                except Exception:
                    cls_val = None
                try:
                    conf_val = float(r.obb.conf[idx].item()) if hasattr(r.obb, "conf") else None
                except Exception:
                    conf_val = None
                try:
                    coords = r.obb.data[idx].tolist()
                except Exception:
                    coords = None
                dets.append({
                    "type": "obb",
                    "cls": cls_val,
                    "conf": conf_val,
                    "coords": coords
                })
        # Else fall back to axis-aligned boxes
        elif getattr(r, "boxes", None) is not None and r.boxes is not None and hasattr(r.boxes, "data") and r.boxes.data is not None and len(r.boxes.data) > 0:
            num = len(r.boxes.data)
            for idx in range(num):
                try:
                    cls_val = int(r.boxes.cls[idx].item()) if hasattr(r.boxes, "cls") else None
                except Exception:
                    cls_val = None
                try:
                    conf_val = float(r.boxes.conf[idx].item()) if hasattr(r.boxes, "conf") else None
                except Exception:
                    conf_val = None
                # Try to get xyxy if available, else take first 4 values from data
                coords = None
                try:
                    if hasattr(r.boxes, "xyxy"):
                        coords = r.boxes.xyxy[idx].tolist()
                    else:
                        data_row = r.boxes.data[idx].tolist()
                        coords = data_row[:4]
                except Exception:
                    coords = None
                dets.append({
                    "type": "box",
                    "cls": cls_val,
                    "conf": conf_val,
                    "coords": coords
                })
        # If segmentation masks exist, try to store simple polygon / mask info
        if getattr(r, "masks", None) is not None and r.masks is not None:
            try:
                # attach mask metadata per detection when possible
                # prefer polygon xy lists if available
                if hasattr(r.masks, "xy") and r.masks.xy is not None:
                    # r.masks.xy is a list aligned with boxes
                    for mi, mask_xy in enumerate(r.masks.xy):
                        if mi < len(dets):
                            # Convert numpy array to list for JSON serialization
                            if hasattr(mask_xy, 'tolist'):
                                dets[mi]["mask_xy"] = mask_xy.tolist()
                            else:
                                dets[mi]["mask_xy"] = list(mask_xy) if mask_xy is not None else None
                elif hasattr(r.masks, "data") and r.masks.data is not None:
                    # binary mask arrays are large; store shape only
                    for mi in range(min(len(dets), len(r.masks.data))):
                        try:
                            dets[mi]["mask_shape"] = list(r.masks.data[mi].shape)
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        # be resilient to unexpected structure
        pass

    all_detections.append({
        "image_index": i,
        "annotated_path": out_path,
        "detections": dets
    })

# Write detections to JSON for later use
try:
    bboxes_path = os.path.join(output_dir, "bboxes.json")
    with open(bboxes_path, "w") as jf:
        json.dump(all_detections, jf, indent=2)
    print(f"Wrote bounding-box info to: {bboxes_path}")
except Exception as e:
    print(f"Failed to write bboxes.json: {e}")
