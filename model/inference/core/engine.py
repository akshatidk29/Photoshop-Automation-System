"""
Generic Inference Engine for YOLO OBB Models.

This module provides the core class for running inference on OBB models.
It is designed to be modular and decoupled from specific use cases.
"""

import os
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

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
    boxPoints: np.ndarray        # 4 corner points

class InferenceEngine:
    """
    Wrapper for YOLO OBB Model inference.
    """
    
    def __init__(self, modelPath: str, config: Dict[str, Any] = None):
        """
        Initialize the inference engine.
        
        Args:
            modelPath: Path to the .pt model file.
            config: Optional configuration dictionary.
        """
        self.config = config or {}
        
        # Check if model exists
        if not os.path.exists(modelPath):
            # Try resolving relative path if needed
            print(f"[InferenceEngine] Warning: Model path {modelPath} not found directly.")
            
        try:
            print(f"[InferenceEngine] Loading model from: {modelPath}")
            self.model = YOLO(str(modelPath))
            self.classNames = self.model.names
            print(f"[InferenceEngine] Model loaded successfully. Classes: {self.classNames}")
        except Exception as e:
            print(f"[InferenceEngine] Failed to load model: {e}")
            self.model = None
            self.classNames = {}
            
    def detect(self, imagePath: str, confThreshold: float = 0.01) -> List[OBBRegion]:
        """
        Run detection on an image.
        
        Args:
            imagePath: Path to input image.
            confThreshold: Confidence threshold.
            
        Returns:
            List of OBBRegion objects (best detection per class).
        """
        if self.model is None:
            print("[InferenceEngine] Model not initialized, cannot detect.")
            return []
            
        try:
            # Run inference
            results = self.model(imagePath, conf=confThreshold, verbose=False)
            
            detections: Dict[str, OBBRegion] = {}
            
            for r in results:
                if r.obb is None:
                    continue
                    
                boxes = r.obb
                for i in range(len(boxes)):
                    try:
                        clsId = int(boxes.cls[i].item())
                        conf = float(boxes.conf[i].item())
                        className = self.classNames.get(clsId, f"class_{clsId}")
                        
                        # Get points
                        xyxyxyxy = boxes.xyxyxyxy[i].cpu().numpy().reshape(4, 2)
                        
                        # Compute OBB Parameters
                        center, size, angle = self._computeParams(xyxyxyxy)
                        
                        region = OBBRegion(
                            classId=clsId,
                            className=className,
                            confidence=conf,
                            center=center,
                            size=size,
                            angle=angle,
                            boxPoints=xyxyxyxy.astype(np.int32)
                        )
                        
                        # Keep highest confidence per class
                        if className not in detections or conf > detections[className].confidence:
                            detections[className] = region
                            
                    except Exception as e:
                        print(f"[InferenceEngine] Error processing box {i}: {e}")
            
            return list(detections.values())
            
        except Exception as e:
            print(f"[InferenceEngine] Detection failed: {e}")
            return []
            
    def _computeParams(self, points: np.ndarray) -> Tuple[Tuple[float, float], Tuple[float, float], float]:
        """Compute center, size, and angle (degrees) from 4 points."""
        center = (points[:, 0].mean(), points[:, 1].mean())
        
        edge1 = np.linalg.norm(points[1] - points[0])
        edge2 = np.linalg.norm(points[2] - points[1])
        
        if edge1 >= edge2:
            width, height = edge1, edge2
            dx = points[1][0] - points[0][0]
            dy = points[1][1] - points[0][1]
        else:
            width, height = edge2, edge1
            dx = points[2][0] - points[1][0]
            dy = points[2][1] - points[1][1]
            
        angle = np.degrees(np.arctan2(dy, dx))
        
        # Normalize to [-90, 90]
        while angle > 90: angle -= 180
        while angle < -90: angle += 180
        
        return center, (width, height), angle
