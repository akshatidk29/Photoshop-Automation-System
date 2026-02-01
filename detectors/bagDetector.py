import os
import cv2
import numpy as np
from pathlib import Path
from detectors.inference import InferenceEngine
from configuration.configLoader import (
    getCanonicalName, 
    getPositionBehavior,
    getObbClassName
)

# Model Path
MODEL_PATH = Path(__file__).parent / "weights" / "bag" / "best.pt"

# Singleton & Cache
_inferenceEngine = None
_detectionCache = {}

def _getInferenceEngine():
    """Get or create singleton inference engine."""
    global _inferenceEngine
    if _inferenceEngine is None and MODEL_PATH.exists():
        print(f"[BagDetector] Initializing model from {MODEL_PATH}")
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
    """Get OBB class name for bags from location (uses config)."""
    return getObbClassName(locationName)

# Heuristic Fallback Logic

def _getProductBoundingBox(imagePath):
    """Detect bag bounding box."""
    img = cv2.imread(imagePath)
    if img is None: raise ValueError(f"Image not found: {imagePath}")
    
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return (w//4, h//4, w//2, h//2)
    
    c = max(contours, key=cv2.contourArea)
    return cv2.boundingRect(c)



def _segmentBagRegions(imagePath, bagBox):
    """Segment bag into regions (upper, lower, pocket)."""
    img = cv2.imread(imagePath)
    if img is None: return None
    
    bx, by, bw, bh = bagBox
    roi = img[by:by+bh, bx:bx+bw].copy()
    if roi.size == 0: return None
    
    grayRoi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    roiH, roiW = grayRoi.shape
    
    # Horizontal gradients
    sobely = cv2.Sobel(grayRoi, cv2.CV_64F, 0, 1, ksize=3)
    rowEdges = np.mean(np.absolute(sobely), axis=1)
    
    # Smooth and find peaks
    from scipy.ndimage import gaussian_filter1d
    smoothed = gaussian_filter1d(rowEdges, sigma=5)
    threshold = np.mean(smoothed) + 0.5 * np.std(smoothed)
    
    peaks = []
    for i in range(10, len(smoothed)-10):
        if smoothed[i] > threshold:
             if smoothed[i] > smoothed[i-5:i].max() and smoothed[i] > smoothed[i+1:i+6].max():
                 peaks.append(i)
                 
    # Filter peaks logic
    if len(peaks) > 1:
        filtered = []
        i = 0
        while i < len(peaks):
            group = [peaks[i]]
            j = i + 1
            while j < len(peaks) and peaks[j] - peaks[i] < roiH * 0.1:
                group.append(peaks[j])
                j += 1
            strongest = max(group, key=lambda p: smoothed[p])
            filtered.append(strongest)
            i = j
        peaks = filtered
        
    regions = {}
    centerX = bx + bw // 2
    
    if len(peaks) >= 1:
        sep = peaks[0] if peaks[0] > roiH * 0.4 else (peaks[1] if len(peaks) > 1 else peaks[0])
        regions['upper'] = (centerX, by + sep // 2)
        pocketStart = sep + int((roiH - sep) * 0.1)
        regions['pocket'] = (centerX, by + pocketStart + (roiH - pocketStart) // 2)
    else:
        regions['upper'] = (centerX, by + int(bh * 0.3))
        regions['pocket'] = (centerX, by + int(bh * 0.75))
        
    regions['lower'] = (centerX, by + int(bh * 0.6))
    return regions



def _getHeuristicCoordinates(imagePath, locationName):
    """Fallback logic."""
    try:
        bagBox = _getProductBoundingBox(imagePath)
        bx, by, bw, bh = bagBox
    except:
        return (600, 600)
    
    centerX = bx + bw // 2
    regions = None
    try:
        regions = _segmentBagRegions(imagePath, bagBox)
    except: pass
    
    # Use canonical name for checking
    canonical = getCanonicalName(locationName)
    
    if "ON-POCKET" in canonical or "POCKET" in canonical:
        if regions and 'pocket' in regions: return regions['pocket']
        return (centerX, by + int(bh * 0.78))
        
    if "FRONT" in canonical or "ON-BAG" in canonical:
        if regions and 'upper' in regions: return regions['upper']
        return (centerX, by + int(bh * 0.32))
        
    return (centerX, by + bh // 2)


# Public Interface

def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """Get (x, y) coordinates for placement (OBB -> Heuristic).
    
    Returns: tuple of ((x, y), usedFallback) where usedFallback is a bool
    """
    # 1. Try OBB
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        if targetClass in regions:
            region = regions[targetClass]
            return ((int(region.center[0]), int(region.center[1])), False)  # OBB succeeded
    except: pass
    
    # 2. Fallback
    coords = _getHeuristicCoordinates(imagePath, locationName)
    return (coords, True)  # Fallback was used

def getRotation(imagePath, locationName):
    """
    Get rotation angle (degrees).
    """
    # 1. FIRST: Try OBB model detection (most accurate)
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        if targetClass in regions:
            return -regions[targetClass].angle
    except:
        pass
    
    # 2. SECOND: Fall back to behavior flags
    behavior = getPositionBehavior(locationName)
    rotationMode = behavior.get('rotation', 'standard')
    
    if rotationMode == 'fixed_0':
        return 0.0
    if rotationMode == 'fixed_45':
        return -45.0
    
    # 3. Default
    return 0.0
