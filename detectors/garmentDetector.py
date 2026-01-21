"""
Garment Detector using YOLO OBB Model.
Provides coordinates, rotation, and logo scale for garment regions.
"""

import os
from pathlib import Path
from detectors.inference import InferenceEngine

# Model Path
# Points to detectors/weights/garment/best.pt
MODEL_PATH = Path(__file__).parent / "weights" / "garment" / "best.pt"

# Location Mapping: Excel Name -> OBB Class Name
LOCATION_MAP = {
    # Front
    "FULL-FRONT": "FULL_FRONT",
    "LEFT-CHEST": "LEFT_CHEST",
    "RIGHT-CHEST": "RIGHT_CHEST",
    "LEFT-COLLAR": "LEFT_COLLAR",
    "RIGHT-COLLAR": "RIGHT_COLLAR",
    "LEFT-BICEP": "LEFT_BICEP",
    "RIGHT-BICEP": "RIGHT_BICEP",
    "LEFT-SLEEVE": "LEFT_SLEEVE",
    "RIGHT-SLEEVE": "RIGHT_SLEEVE",
    "LEFT-CUFF": "LEFT_CUFF",
    "RIGHT-CUFF": "RIGHT_CUFF",
    "LEFT-HIP": "LEFT_HIP",
    "RIGHT-HIP": "RIGHT_HIP",
    "LEFT-THIGH-HIGH": "LEFT_THIGH_HIGH",
    "RIGHT-THIGH-HIGH": "RIGHT_THIGH_HIGH",
    "ON-POCKET": "ON_POCKET",
    
    # Back
    "FULL-BACK": "FULL_BACK",
    "BACK-YOKE": "BACK_YOKE",
}

# Singleton Instance & Cache
_inferenceEngine = None
_detectionCache = {}

def _getInferenceEngine():
    """Get or create singleton inference engine."""
    global _inferenceEngine
    if _inferenceEngine is None:
        print(f"[GarmentDetector] Initializing model from {MODEL_PATH}")
        _inferenceEngine = InferenceEngine(str(MODEL_PATH))
    return _inferenceEngine

def _getRegions(imagePath):
    """Get detected regions (cached)."""
    global _detectionCache
    
    # Cache key based on path and modification time
    try:
        mtime = os.path.getmtime(imagePath)
    except:
        mtime = 0
    
    key = (str(imagePath), mtime)
    
    if key not in _detectionCache:
        engine = _getInferenceEngine()
        regions = engine.detect(str(imagePath))
        # Store as dict for fast lookup by className
        _detectionCache[key] = {r.className: r for r in regions}
        
    return _detectionCache[key]

def _normalizeLocation(locationName):
    """Normalize location name."""
    if not locationName: return ""
    return str(locationName).strip().upper().replace(" ", "-").replace("_", "-")

def _getObbClassName(locationName):
    """Get OBB class name from location."""
    norm = _normalizeLocation(locationName)
    return LOCATION_MAP.get(norm, norm.replace("-", "_"))

# ============================================================================
# Public Interface
# ============================================================================

def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """
    Get (x, y) coordinates for placement.
    Returns None if region not found.
    """
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        
        if debug:
            print(f"[getCoordinates] Looking for '{targetClass}' in detected regions")
            
        if targetClass in regions:
            region = regions[targetClass]
            coords = (int(region.center[0]), int(region.center[1]))
            if debug: print(f"[getCoordinates] Found at {coords}")
            return coords
            
        return None
        
    except Exception as e:
        print(f"[GarmentDetector] Error getting coordinates: {e}")
        return None

def getRotation(imagePath, locationName):
    """
    Get rotation angle (degrees).
    Returns 0.0 if region not found.
    """
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        
        if targetClass in regions:
            # Return negated angle (OBB is CCW, Photoshop needs CW)
            return -regions[targetClass].angle
            
        return 0.0
        
    except Exception as e:
        print(f"[GarmentDetector] Error getting rotation: {e}")
        return 0.0

def getLogoScale(imagePath, locationName, baseSize=(200, 100)):
    """
    Get logo sizing strategy.
    Returns (300, 300) for Full Front/Back, (99, 99) for others.
    """
    loc = _normalizeLocation(locationName)
    if "FULL-FRONT" in loc or "FULL-BACK" in loc:
        return (300, 300)
    return (99, 99)
