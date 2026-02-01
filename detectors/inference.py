import os

# Disable ultralytics auto-update (prevents GPU package installation)
os.environ['YOLO_AUTOINSTALL'] = 'false'

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
    Automatically uses ONNX format if available for faster CPU inference.
    """
    
    def __init__(self, modelPath: str):
        """
        Initialize the inference engine with a model path.
        
        Args:
            modelPath: Path to the .pt model file. Will auto-use .onnx if exists.
        """
        self.modelPath = Path(modelPath)
        self.model = None
        self.classNames = {}
        self.usingOnnx = False
        
        # Check for ONNX version first (faster)
        onnxPath = self.modelPath.with_suffix('.onnx')
        
        if onnxPath.exists():
            # Use ONNX model (faster on CPU)
            self._loadModel(str(onnxPath))
            self.usingOnnx = True
            print(f"[InferenceEngine] Using ONNX model (faster): {onnxPath.name}")
        elif self.modelPath.exists():
            # Fallback to PyTorch model
            self._loadModel(str(self.modelPath))
            print(f"[InferenceEngine] Using PyTorch model: {self.modelPath.name}")
            print(f"    TIP: Run 'python detectors/convert_to_onnx.py' for faster inference")
        else:
            print(f"[InferenceEngine] Warning: Model not found at {modelPath}")
    
    def _loadModel(self, path: str):
        """Load model from path."""
        try:
            self.model = YOLO(path, task='obb')
            self.classNames = self.model.names
        except Exception as e:
            print(f"[InferenceEngine] Failed to load model: {e}")
            self.model = None
            self.classNames = {}

    def detect(self, imagePath: str, confThreshold: float = 0.01) -> List[OBBRegion]:
        """
        Run detection on an image.
        """
        if self.model is None:
            return []
            
        try:
            # Run inference with optimizations
            results = self.model(
                imagePath, 
                conf=confThreshold, 
                verbose=False,
                half=False  # CPU doesn't support half precision
            )
            
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


# Global cache for detection results (with LRU limit)
_detectionCache: Dict[str, Dict[str, OBBRegion]] = {}
_cacheOrder: List[str] = []
_MAX_CACHE_SIZE = 50  # Limit cache to 50 images


def getCachedDetection(engine: InferenceEngine, imagePath: str) -> List[OBBRegion]:
    """
    Get detection with caching. Limited to 50 entries to save memory.
    """
    global _detectionCache, _cacheOrder
    
    # Create cache key
    try:
        mtime = os.path.getmtime(imagePath)
    except:
        mtime = 0
    
    key = f"{imagePath}:{mtime}"
    
    if key in _detectionCache:
        return list(_detectionCache[key].values())
    
    # Run detection
    regions = engine.detect(imagePath)
    
    # Store in cache
    _detectionCache[key] = {r.className: r for r in regions}
    _cacheOrder.append(key)
    
    # Enforce cache limit
    while len(_cacheOrder) > _MAX_CACHE_SIZE:
        old_key = _cacheOrder.pop(0)
        if old_key in _detectionCache:
            del _detectionCache[old_key]
    
    return regions
