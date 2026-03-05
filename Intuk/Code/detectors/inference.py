import os

# Disable ultralytics auto-install (prevents CUDA / GPU surprises)
os.environ["YOLO_AUTOINSTALL"] = "false"

import numpy as np
from typing import List, Tuple, Dict
from dataclasses import dataclass
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    raise ImportError("Please install ultralytics: pip install ultralytics")


# -----------------------------
# Data structure for OBB output
# -----------------------------
@dataclass
class OBBRegion:
    classId: int
    className: str
    confidence: float
    center: Tuple[float, float]      # (cx, cy)
    size: Tuple[float, float]        # (width, height)
    angle: float                     # degrees, range [-90, 90]
    boxPoints: np.ndarray            # shape (4, 2)


# -----------------------------
# Inference Engine (PT / OpenVINO)
# -----------------------------
class InferenceEngine:
    """YOLO-OBB inference engine. Prefers OpenVINO format for speed, falls back to PyTorch."""

    def __init__(self, modelPath: str):
        self.modelPath = Path(modelPath)
        self.model = None
        self.classNames: Dict[int, str] = {}
        self.usingOpenVINO = False

        if not self.modelPath.exists():
            raise FileNotFoundError(f"Model not found: {self.modelPath}")

        # Check for OpenVINO export alongside the .pt file
        ovinoDir = self.modelPath.parent / (self.modelPath.stem + "_openvino_model")
        if ovinoDir.is_dir():
            try:
                self._loadModel(str(ovinoDir))
                self.usingOpenVINO = True
                print(f"[InferenceEngine] Using OpenVINO model: {ovinoDir.name}  (faster)")
            except Exception as e:
                print(f"[InferenceEngine] OpenVINO load failed ({e}), falling back to PyTorch")
                self._loadModel(str(self.modelPath))
                print(f"[InferenceEngine] Using PyTorch model: {self.modelPath.name}")
        else:
            self._loadModel(str(self.modelPath))
            print(f"[InferenceEngine] Using PyTorch model: {self.modelPath.name}")

    def _loadModel(self, path: str):
        try:
            self.model = YOLO(path, task="obb")
            if not path.endswith("_openvino_model") and not Path(path).is_dir():
                self.model.to("cpu")  # force CPU for PyTorch, not needed for OpenVINO
            self.classNames = self.model.names
        except Exception as e:
            raise RuntimeError(f"[InferenceEngine] Failed to load model: {e}")

    # -----------------------------
    # Detection
    # -----------------------------
    def detect(self, imagePath: str, confThreshold: float = 0.01) -> List[OBBRegion]:
        if self.model is None:
            return []

        try:
            results = self.model(
                imagePath,
                conf=confThreshold,
                device="cpu",
                verbose=False,
            )

            detectionsByClass: Dict[str, OBBRegion] = {}

            for r in results:
                if r.obb is None:
                    continue

                boxes = r.obb

                for i in range(len(boxes)):
                    clsId = int(boxes.cls[i].item())
                    conf = float(boxes.conf[i].item())
                    className = self.classNames.get(clsId, f"class_{clsId}")

                    # 4 corner points (x1,y1,...,x4,y4)
                    points = boxes.xyxyxyxy[i].cpu().numpy().reshape(4, 2)

                    center, size, angle = self._computeOBBParams(points)

                    region = OBBRegion(
                        classId=clsId,
                        className=className,
                        confidence=conf,
                        center=center,
                        size=size,
                        angle=angle,
                        boxPoints=points.astype(np.int32),
                    )

                    # Keep only highest-confidence detection per class
                    if (
                        className not in detectionsByClass
                        or conf > detectionsByClass[className].confidence
                    ):
                        detectionsByClass[className] = region

            return list(detectionsByClass.values())

        except Exception as e:
            print(f"[InferenceEngine] Detection error: {e}")
            return []

    # -----------------------------
    # OBB geometry helpers
    # -----------------------------
    def _computeOBBParams(
        self, points: np.ndarray
    ) -> Tuple[Tuple[float, float], Tuple[float, float], float]:

        # Center
        cx = float(points[:, 0].mean())
        cy = float(points[:, 1].mean())

        # Edge lengths
        edge1 = np.linalg.norm(points[1] - points[0])
        edge2 = np.linalg.norm(points[2] - points[1])

        if edge1 >= edge2:
            width, height = edge1, edge2
            dx, dy = points[1] - points[0]
        else:
            width, height = edge2, edge1
            dx, dy = points[2] - points[1]

        angle = float(np.degrees(np.arctan2(dy, dx)))

        # Normalize angle to [-90, 90]
        if angle > 90:
            angle -= 180
        elif angle < -90:
            angle += 180

        return (cx, cy), (width, height), angle

