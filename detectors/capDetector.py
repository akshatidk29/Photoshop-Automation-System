"""
Cap Detector using YOLO OBB Model with Heuristic Fallback.
Provides coordinates, rotation, and logo scale for cap regions.
"""

import os
import cv2
import numpy as np
from pathlib import Path
from detectors.inference import InferenceEngine
from core.utils import normalizeLocation
from configuration.configLoader import (
    getCanonicalName, 
    getPositionBehavior,
    getObbClassName
)

# Model Path
MODEL_PATH = Path(__file__).parent / "weights" / "cap" / "best.pt"

# Singleton Instance & Cache
_inferenceEngine = None
_detectionCache = {}

def _getInferenceEngine():
    """Get or create singleton inference engine."""
    global _inferenceEngine
    if _inferenceEngine is None and MODEL_PATH.exists():
        print(f"[CapDetector] Initializing model from {MODEL_PATH}")
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

# Location Mapping: Excel Name -> OBB Class Name
# Now handled via getObbClassName from configLoader
def _getObbClassName(locationName):
    """Get OBB class name for caps from location (uses config)."""
    return getObbClassName(locationName)

# ============================================================================
# Heuristic Fallback Logic
# ============================================================================

def _getProductBoundingBox(image, offsetX=0, offsetY=0):
    """Detect largest object in image using contours."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        h, w = image.shape[:2]
        return (offsetX + w//4, offsetY + h//4, w//2, h//2)
        
    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    
    return x + offsetX, y + offsetY, w, h

def _getHeuristicCoordinates(imagePath, locationName):
    """Fallback logic using image processing."""
    normLoc = normalizeLocation(locationName)
    
    img = cv2.imread(imagePath)
    if img is None:
        return None
        
    h, w, _ = img.shape
    processImage = img
    offX, offY = 0, 0
    aspect = w / h
    usageSide = "full"
    
    # Dual Split Logic
    if "BACK" in normLoc and aspect > 1.2:
        usageSide = "left"
    if "SIDE" in normLoc and aspect > 1.2:
        usageSide = "right"

    if usageSide == "left":
        processImage = img[:, :w//2]
        offX = 0
    elif usageSide == "right":
        processImage = img[:, w//2:]
        offX = w//2
        
    bx, by, bw, bh = _getProductBoundingBox(processImage, offX, offY)
    
    centerX = bx + bw // 2
    centerY = by + bh // 2
    
    # Use canonical/OBB class name for checking logic
    obbClass = _getObbClassName(locationName)
    
    if "FRONT_CROWN" in obbClass:
        return centerX, int(by + bh * 0.25)
        
    if "CAP_BACK" in obbClass or "CAP_SIDE" in obbClass:
        return centerX, centerY
        
    if "CAP_FRONT_SIDE" in obbClass:
        return int(bx + bw * 0.75), int(by + bh * 0.4)
        
    if "LOWER_LEFT_CROWN" in obbClass:
        return int(bx + bw * 0.3), int(by + bh * 0.6)

    if "LOWER_RIGHT_CROWN" in obbClass:
        return int(bx + bw * 0.7), int(by + bh * 0.6)

    return centerX, centerY

# ============================================================================
# Public Interface
# ============================================================================

def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """Get (x, y) coordinates for placement (OBB -> Heuristic)."""
    # 1. Try OBB
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        
        if targetClass in regions:
            region = regions[targetClass]
            coords = (int(region.center[0]), int(region.center[1]))
            if debug: print(f"[CapDetector] Found OBB {targetClass} at {coords}")
            return coords
    except Exception as e:
        if debug: print(f"[CapDetector] OBB failed: {e}")

    # 2. Fallback Heuristic
    if debug: print(f"[CapDetector] Using heuristic fallback for {locationName}")
    return _getHeuristicCoordinates(imagePath, locationName)

def getRotation(imagePath, locationName):
    """
    Get rotation angle (degrees).
    Uses behavior flags from registry.
    """
    behavior = getPositionBehavior(locationName)
    rotationMode = behavior.get('rotation', 'standard')
    
    if rotationMode == 'fixed_0':
        return 0.0
    
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        
        if targetClass in regions:
            return -regions[targetClass].angle
            
    except Exception:
        pass
    
    return 0.0

def getLogoScale(imagePath, locationName, baseSize=(200, 100)):
    """
    DEPRECATED: Logo sizing is handled by core/utils.computeLogoSize.
    """
    return (99, 99)
