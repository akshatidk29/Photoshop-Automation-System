"""
Generic Inference Engine for YOLO OBB Models.

Handles model loading and inference for OBB detection.
Decoupled from specific product logic (garments, caps, etc.).
"""

import os
import numpy as np
from typing import List, Tuple, Dict
from dataclasses import dataclass
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    raise ImportError("Please install ultralytics: pip install ultralytics")

@dataclass
class OBBRegion:
    """Detected region with oriented bounding box details."""
    classId: int
    className: str
    confidence: float
    center: Tuple[float, float]  # (cx, cy)
    size: Tuple[float, float]    # (width, height)
    angle: float                 # rotation angle in degrees
    boxPoints: np.ndarray        # 4 corner points of the OBB

class InferenceEngine:
    """
    Generic Wrapper for YOLO OBB Inference.
    """
    
    def __init__(self, modelPath: str):
        """
        Initialize the inference engine with a model path.
        
        Args:
            modelPath: Absolute or relative path to the .pt model file.
        """
        if not os.path.exists(modelPath):
            # Try resolving relative to current working directory if generic path fails
            if not Path(modelPath).exists():
                 print(f"[InferenceEngine] Warning: Model not found at {modelPath}")
        
        # Load model
        try:
            self.model = YOLO(str(modelPath))
            self.classNames = self.model.names
        except Exception as e:
            print(f"[InferenceEngine] Failed to load model: {e}")
            self.model = None
            self.classNames = {}

    def detect(self, imagePath: str, confThreshold: float = 0.01) -> List[OBBRegion]:
        """
        Run detection on an image.
        
        Args:
            imagePath: Path to the input image.
            confThreshold: Confidence threshold (default 0.01).
            
        Returns:
            List of OBBRegion objects (best detection per class).
        """
        if self.model is None:
            return []
            
        try:
            # Run inference
            results = self.model(imagePath, conf=confThreshold, verbose=False)
            
            detectionsByClass: Dict[str, OBBRegion] = {}
            
            for r in results:
                if r.obb is None:
                    continue
                    
                boxes = r.obb
                for i in range(len(boxes)):
                    try:
                        clsId = int(boxes.cls[i].item())
                        conf = float(boxes.conf[i].item())
                        className = self.classNames.get(clsId, f"class_{clsId}")
                        
                        # Get 4 corner points
                        xyxyxyxy = boxes.xyxyxyxy[i].cpu().numpy().reshape(4, 2)
                        
                        # Compute params
                        center, size, angle = self._computeOBBParams(xyxyxyxy)
                        
                        region = OBBRegion(
                            classId=clsId,
                            className=className,
                            confidence=conf,
                            center=center,
                            size=size,
                            angle=angle,
                            boxPoints=xyxyxyxy.astype(np.int32)
                        )
                        
                        # Keep only best confidence per class
                        if className not in detectionsByClass or conf > detectionsByClass[className].confidence:
                            detectionsByClass[className] = region
                            
                    except Exception as e:
                        print(f"[InferenceEngine] Error processing detection: {e}")
                        continue
            
            return list(detectionsByClass.values())
            
        except Exception as e:
            print(f"[InferenceEngine] Detection error: {e}")
            return []

    def _computeOBBParams(self, points: np.ndarray) -> Tuple[Tuple[float, float], Tuple[float, float], float]:
        """Compute center, size, and angle from 4 corner points."""
        # Center
        center = (points[:, 0].mean(), points[:, 1].mean())
        
        # Edges
        edge1 = np.linalg.norm(points[1] - points[0])
        edge2 = np.linalg.norm(points[2] - points[1])
        
        # Width/Height and Angle
        if edge1 >= edge2:
            width, height = edge1, edge2
            dx = points[1][0] - points[0][0]
            dy = points[1][1] - points[0][1]
        else:
            width, height = edge2, edge1
            dx = points[2][0] - points[1][0]
            dy = points[2][1] - points[1][1]
        
        angle = np.degrees(np.arctan2(dy, dx))
        
        # Normalize angle to [-90, 90]
        while angle > 90: angle -= 180
        while angle < -90: angle += 180
        
        return center, (width, height), angle
