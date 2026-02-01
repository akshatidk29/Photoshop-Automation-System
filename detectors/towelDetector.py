import os
import cv2
from pathlib import Path
from detectors.inference import InferenceEngine
from configuration.configLoader import (
    getPositionBehavior,
    getObbClassName
)

# Model Path
MODEL_PATH = Path(__file__).parent / "weights" / "towel" / "best.pt"


# Heuristic Config
TOWEL_CONFIG = {
    "CORNER": {
        "xPercent": 0.85,    # Right
        "yPercent": 0.85,    # Bottom
        "scaleRatio": 0.15,  # 15% width
        "rotation": -45
    },
    "CENTER": {
        "xPercent": 0.50,
        "yPercent": 0.50,
        "scaleRatio": 0.40,
        "rotation": 0
    },
    "DEFAULT": {
        "xPercent": 0.50,
        "yPercent": 0.50,
        "scaleRatio": 0.25,
        "rotation": 0
    }
}

# Singleton & Cache
_inferenceEngine = None
_detectionCache = {}

def _getInferenceEngine():
    """Get or create singleton inference engine."""
    global _inferenceEngine
    if _inferenceEngine is None and MODEL_PATH.exists():
        print(f"[TowelDetector] Initializing model from {MODEL_PATH}")
        _inferenceEngine = InferenceEngine(str(MODEL_PATH))
    return _inferenceEngine

def _getRegions(imagePath):
    """Get detected regions (cached)."""
    global _detectionCache
    try:
        mtime = os.path.getmtime(imagePath)
    except:
        mtime = 0
    key = (str(imagePath), mtime)
    
    if key not in _detectionCache:
        engine = _getInferenceEngine()
        if engine:
            regions = engine.detect(str(imagePath))
            _detectionCache[key] = {r.className: r for r in regions}
        else:
            _detectionCache[key] = {}
    return _detectionCache[key]

def _getObbClassName(locationName):
    """Get OBB class name for towels from location (uses config)."""
    return getObbClassName(locationName)

def _getConfigForLocation(locationName):
    """Get heuristic config based on OBB class name."""
    obbClass = _getObbClassName(locationName)
    if "CORNER" in obbClass: return TOWEL_CONFIG["CORNER"]
    if "CENTER" in obbClass or "FRONT" in obbClass: return TOWEL_CONFIG["CENTER"]
    
    return TOWEL_CONFIG["DEFAULT"]

# Heuristic Fallback Logic

def _getProductBoundingBox(imagePath):
    img = cv2.imread(imagePath)
    if img is None: raise ValueError(f"Image not found: {imagePath}")
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        h, w = img.shape[:2]
        return (w//4, h//4, w//2, h//2)
        
    c = max(contours, key=cv2.contourArea)
    return cv2.boundingRect(c)

def _getHeuristicCoordinates(imagePath, locationName):
    """Fallback logic."""
    try:
        bx, by, bw, bh = _getProductBoundingBox(imagePath)
    except:
        return (600, 600)
    
    config = _getConfigForLocation(locationName)
    finalX = bx + int(bw * config["xPercent"])
    finalY = by + int(bh * config["yPercent"])
    return finalX, finalY

# Public Interface

def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """Get (x, y) coordinates."""
    # 1. Try OBB
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        if targetClass in regions:
            region = regions[targetClass]
            return (int(region.center[0]), int(region.center[1]))
    except: pass
    
    # 2. Fallback
    return _getHeuristicCoordinates(imagePath, locationName)

def getRotation(imagePath, locationName):
    """
    Get rotation angle (degrees).
    """
    # 1. FIRST: Try OBB model detection (most accurate)
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        if targetClass in regions:
            # Model detected the region - use its angle
            return -regions[targetClass].angle
    except: 
        pass
    
    # 2. SECOND: Fall back to behavior flags (from registry)
    behavior = getPositionBehavior(locationName)
    rotationMode = behavior.get('rotation', 'standard')
    
    if rotationMode == 'fixed_0':
        return 0.0
    if rotationMode == 'fixed_45':
        return -45.0
    
    # 3. THIRD: Fallback to heuristic config (legacy support)
    config = _getConfigForLocation(locationName)
    return config["rotation"]