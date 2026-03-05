import os
from pathlib import Path
from detectors.inference import InferenceEngine
from configuration.configLoader import getObbClassName

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


def _getObbClassName(locationName):
    """Get OBB class name for caps from location (uses config)."""
    return getObbClassName(locationName)


# Public Interface

def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """Get (x, y) coordinates for placement using OBB model only.
    No fallback - returns None if position not detected.
    
    Returns: tuple of ((x, y), detected) where:
        - If detected: ((x, y), True)
        - If not detected: (None, False)
    """
    # Try OBB only - NO FALLBACK
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        
        if targetClass in regions:
            region = regions[targetClass]
            coords = (int(region.center[0]), int(region.center[1]))
            return (coords, True)  # OBB succeeded
    except Exception as e:
        if debug: print(f"[CapDetector] OBB failed: {e}")

    # Position not detected by model - return None (no fallback)
    print(f"[NOT DETECTED] Position '{locationName}' not detected by model")
    return (None, False)  # Not detected


def getRotation(imagePath, locationName):
    """Get rotation angle from OBB detection. Returns 0.0 if not detected or below threshold."""
    from configuration.configLoader import getRotationThreshold
    threshold = getRotationThreshold()
    
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        
        if targetClass in regions:
            angle = -regions[targetClass].angle
            if abs(angle) < threshold:
                return 0.0
            return angle
    except:
        pass
    
    return 0.0
