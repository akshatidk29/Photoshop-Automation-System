"""
Garment Detector using YOLO OBB Model with MediaPipe Pose Fallback.
Provides coordinates, rotation, and logo scale for garment regions.

When OBB model fails, uses MediaPipe Pose landmarks for accurate placement.
"""

import os
import cv2
import numpy as np
from pathlib import Path
from detectors.inference import InferenceEngine
from configuration.configLoader import (
    getCanonicalName, 
    getPositionBehavior
)

# Model Path
MODEL_PATH = Path(__file__).parent / "weights" / "garment" / "best.pt"

# Singleton Instance & Cache
_inferenceEngine = None
_detectionCache = {}

# MediaPipe Pose instance (lazy loaded)
_mediapipePose = None

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
    
    try:
        mtime = os.path.getmtime(imagePath)
    except:
        mtime = 0
    
    key = (str(imagePath), mtime)
    
    if key not in _detectionCache:
        engine = _getInferenceEngine()
        regions = engine.detect(str(imagePath))
        _detectionCache[key] = {r.className: r for r in regions}
        
    return _detectionCache[key]

# Location Mapping: Excel Name -> OBB Class Name
# Now handled dynamically via getCanonicalName
def _getObbClassName(locationName):
    """Get OBB class name for garments from location."""
    canonical = getCanonicalName(locationName)
    # Convert canonical name (e.g., "FULL-FRONT") to model class name (e.g., "FULL_FRONT")
    return canonical.replace("-", "_").replace(" ", "_")

def _normalizeLocation(locationName):
    """Normalize location name."""
    return getCanonicalName(locationName)

# ============================================================================
# MediaPipe Pose Fallback
# ============================================================================

def _getMediaPipePose():
    """Get or create MediaPipe Pose instance."""
    global _mediapipePose
    if _mediapipePose is None:
        try:
            import mediapipe as mp
            _mediapipePose = mp.solutions.pose.Pose(
                static_image_mode=True,
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.3
            )
            print("[GarmentDetector] MediaPipe Pose initialized for fallback")
        except Exception as e:
            print(f"[GarmentDetector] Failed to initialize MediaPipe: {e}")
            return None
    return _mediapipePose

def _getPoseLandmarks(imagePath):
    """
    Get pose landmarks from image using MediaPipe.
    Returns dict of landmark names to (x, y) pixel coordinates.
    """
    pose = _getMediaPipePose()
    if pose is None:
        return None
    
    img = cv2.imread(imagePath)
    if img is None:
        return None
    
    imgH, imgW = img.shape[:2]
    
    # Convert BGR to RGB for MediaPipe
    imgRgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    try:
        results = pose.process(imgRgb)
        
        if results.pose_landmarks is None:
            return None
        
        # MediaPipe landmark indices
        # https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
        LANDMARK_MAP = {
            'nose': 0,
            'left_eye': 2,
            'right_eye': 5,
            'left_ear': 7,
            'right_ear': 8,
            'left_shoulder': 11,
            'right_shoulder': 12,
            'left_elbow': 13,
            'right_elbow': 14,
            'left_wrist': 15,
            'right_wrist': 16,
            'left_hip': 23,
            'right_hip': 24,
            'left_knee': 25,
            'right_knee': 26,
        }
        
        landmarks = {}
        for name, idx in LANDMARK_MAP.items():
            lm = results.pose_landmarks.landmark[idx]
            # Convert normalized coordinates to pixel coordinates
            px = int(lm.x * imgW)
            py = int(lm.y * imgH)
            landmarks[name] = (px, py)
        
        return landmarks
        
    except Exception as e:
        print(f"[MediaPipe] Error processing image: {e}")
        return None

def _getCoordinatesFromLandmarks(landmarks, locationName, imgW, imgH):
    """
    Calculate logo placement coordinates from pose landmarks.
    
    Args:
        landmarks: Dict of pose landmarks {name: (x, y)}
        locationName: Target position name
        imgW, imgH: Image dimensions
        
    Returns:
        (x, y) tuple for logo placement
    """
    obbClass = _getObbClassName(locationName)
    
    # Get key landmarks
    lShoulder = landmarks.get('left_shoulder')
    rShoulder = landmarks.get('right_shoulder')
    lHip = landmarks.get('left_hip')
    rHip = landmarks.get('right_hip')
    lElbow = landmarks.get('left_elbow')
    rElbow = landmarks.get('right_elbow')
    lWrist = landmarks.get('left_wrist')
    rWrist = landmarks.get('right_wrist')
    nose = landmarks.get('nose')
    
    # Safety check
    if not lShoulder or not rShoulder:
        return None
    
    # Calculate helpful reference points
    shoulderMidX = (lShoulder[0] + rShoulder[0]) // 2
    shoulderMidY = (lShoulder[1] + rShoulder[1]) // 2
    shoulderWidth = abs(rShoulder[0] - lShoulder[0])
    
    if lHip and rHip:
        hipMidX = (lHip[0] + rHip[0]) // 2
        hipMidY = (lHip[1] + rHip[1]) // 2
        torsoHeight = hipMidY - shoulderMidY
    else:
        hipMidY = shoulderMidY + int(shoulderWidth * 1.5)
        torsoHeight = int(shoulderWidth * 1.5)
    
    # Calculate position based on landmarks
    # NOTE: MediaPipe left/right is from the person's perspective (same as wearer)
    
    if obbClass == "FULL_FRONT" or obbClass == "FULL_BACK":
        # Center of torso
        x = shoulderMidX
        y = shoulderMidY + int(torsoHeight * 0.4)
        return (x, y)
    
    if obbClass == "LEFT_CHEST":
        # Wearer's left chest = viewer's right side = near left_shoulder
        x = lShoulder[0] + int(shoulderWidth * 0.15)
        y = lShoulder[1] + int(torsoHeight * 0.25)
        return (x, y)
    
    if obbClass == "RIGHT_CHEST":
        # Wearer's right chest = viewer's left side = near right_shoulder
        x = rShoulder[0] - int(shoulderWidth * 0.15)
        y = rShoulder[1] + int(torsoHeight * 0.25)
        return (x, y)
    
    if obbClass == "LEFT_COLLAR":
        # Near left shoulder/neck
        x = lShoulder[0] + int(shoulderWidth * 0.1)
        y = lShoulder[1] - int(torsoHeight * 0.05)
        return (x, y)
    
    if obbClass == "RIGHT_COLLAR":
        # Near right shoulder/neck
        x = rShoulder[0] - int(shoulderWidth * 0.1)
        y = rShoulder[1] - int(torsoHeight * 0.05)
        return (x, y)
    
    if obbClass == "LEFT_BICEP":
        # On left upper arm (between shoulder and elbow)
        if lElbow:
            x = (lShoulder[0] + lElbow[0]) // 2
            y = (lShoulder[1] + lElbow[1]) // 2
        else:
            x = lShoulder[0] - int(shoulderWidth * 0.3)
            y = lShoulder[1] + int(torsoHeight * 0.15)
        return (x, y)
    
    if obbClass == "RIGHT_BICEP":
        # On right upper arm
        if rElbow:
            x = (rShoulder[0] + rElbow[0]) // 2
            y = (rShoulder[1] + rElbow[1]) // 2
        else:
            x = rShoulder[0] + int(shoulderWidth * 0.3)
            y = rShoulder[1] + int(torsoHeight * 0.15)
        return (x, y)
    
    if obbClass == "LEFT_SLEEVE":
        # On left forearm (between elbow and wrist)
        if lElbow and lWrist:
            x = (lElbow[0] + lWrist[0]) // 2
            y = (lElbow[1] + lWrist[1]) // 2
        elif lElbow:
            x = lElbow[0]
            y = lElbow[1] + int(torsoHeight * 0.2)
        else:
            x = lShoulder[0] - int(shoulderWidth * 0.5)
            y = lShoulder[1] + int(torsoHeight * 0.4)
        return (x, y)
    
    if obbClass == "RIGHT_SLEEVE":
        # On right forearm
        if rElbow and rWrist:
            x = (rElbow[0] + rWrist[0]) // 2
            y = (rElbow[1] + rWrist[1]) // 2
        elif rElbow:
            x = rElbow[0]
            y = rElbow[1] + int(torsoHeight * 0.2)
        else:
            x = rShoulder[0] + int(shoulderWidth * 0.5)
            y = rShoulder[1] + int(torsoHeight * 0.4)
        return (x, y)
    
    if obbClass == "LEFT_CUFF":
        # Near left wrist
        if lWrist:
            return lWrist
        elif lElbow:
            x = lElbow[0] - int(shoulderWidth * 0.2)
            y = lElbow[1] + int(torsoHeight * 0.3)
            return (x, y)
        return (lShoulder[0] - int(shoulderWidth * 0.6), lShoulder[1] + int(torsoHeight * 0.6))
    
    if obbClass == "RIGHT_CUFF":
        # Near right wrist
        if rWrist:
            return rWrist
        elif rElbow:
            x = rElbow[0] + int(shoulderWidth * 0.2)
            y = rElbow[1] + int(torsoHeight * 0.3)
            return (x, y)
        return (rShoulder[0] + int(shoulderWidth * 0.6), rShoulder[1] + int(torsoHeight * 0.6))
    
    if obbClass == "LEFT_HIP":
        # Near left hip - more to the left
        if lHip:
            x = lHip[0]  # Use exact hip X position
            y = lHip[1] - int(torsoHeight * 0.05)
            return (x, y)
        return (lShoulder[0], shoulderMidY + int(torsoHeight * 0.8))
    
    if obbClass == "RIGHT_HIP":
        # Near right hip - more to the right
        if rHip:
            x = rHip[0]  # Use exact hip X position
            y = rHip[1] - int(torsoHeight * 0.05)
            return (x, y)
        return (rShoulder[0], shoulderMidY + int(torsoHeight * 0.8))
    
    if obbClass == "ON_POCKET":
        # Lower left area (pocket)
        if lHip:
            x = lHip[0] + int(shoulderWidth * 0.15)
            y = lHip[1] - int(torsoHeight * 0.15)
            return (x, y)
        return (shoulderMidX - int(shoulderWidth * 0.2), shoulderMidY + int(torsoHeight * 0.7))
    
    if obbClass == "BACK_YOKE":
        # Upper back, below shoulders
        x = shoulderMidX
        y = shoulderMidY + int(torsoHeight * 0.15)
        return (x, y)
    
    if obbClass == "LEFT_THIGH_HIGH":
        # Wearer's LEFT thigh = VIEWER'S RIGHT = right side of image center
        # For pants images, use a reliable position on the left leg
        if lHip:
            # Move towards image center (left leg is on right side for viewer)
            x = lHip[0] + int(shoulderWidth * 0.15)  # Offset inward toward leg center
            offset = max(int(torsoHeight * 0.3), int(imgH * 0.12))
            y = lHip[1] + offset
            return (x, y)
        # Fallback: 55% across (right of center), 45% down
        return (int(imgW * 0.55), int(imgH * 0.45))
    
    if obbClass == "RIGHT_THIGH_HIGH":
        # Wearer's RIGHT thigh = VIEWER'S LEFT = left side of image center
        # For pants images, use a reliable position on the right leg
        if rHip:
            # Move towards image center (right leg is on left side for viewer)
            x = rHip[0] - int(shoulderWidth * 0.15)  # Offset inward toward leg center
            offset = max(int(torsoHeight * 0.3), int(imgH * 0.12))
            y = rHip[1] + offset
            return (x, y)
        # Fallback: 45% across (left of center), 45% down
        return (int(imgW * 0.45), int(imgH * 0.45))
    
    # Default fallback: center of torso
    return (shoulderMidX, shoulderMidY + int(torsoHeight * 0.3))

def _getHeuristicCoordinates(imagePath, locationName):
    """
    Fallback using MediaPipe Pose landmarks.
    Returns (x, y) tuple.
    """
    img = cv2.imread(imagePath)
    if img is None:
        return (600, 500)
    
    imgH, imgW = img.shape[:2]
    
    # Try MediaPipe pose detection
    landmarks = _getPoseLandmarks(imagePath)
    
    if landmarks:
        coords = _getCoordinatesFromLandmarks(landmarks, locationName, imgW, imgH)
        if coords:
            return coords
    
    # Absolute fallback if MediaPipe fails
    # Use simple proportional positioning based on image dimensions
    obbClass = _getObbClassName(locationName)
    
    SIMPLE_FALLBACK = {
        "FULL_FRONT": (0.50, 0.35),
        "FULL_BACK": (0.50, 0.35),
        "LEFT_CHEST": (0.60, 0.25),
        "RIGHT_CHEST": (0.40, 0.25),
        "LEFT_BICEP": (0.80, 0.28),
        "RIGHT_BICEP": (0.20, 0.28),
        "LEFT_SLEEVE": (0.88, 0.35),
        "RIGHT_SLEEVE": (0.12, 0.35),
        "LEFT_HIP": (0.60, 0.55),
        "RIGHT_HIP": (0.40, 0.55),
        "LEFT_THIGH_HIGH": (0.58, 0.65),
        "RIGHT_THIGH_HIGH": (0.42, 0.65),
        "BACK_YOKE": (0.50, 0.20),
        "DEFAULT": (0.50, 0.30),
    }
    
    percentages = SIMPLE_FALLBACK.get(obbClass, SIMPLE_FALLBACK["DEFAULT"])
    x = int(imgW * percentages[0])
    y = int(imgH * percentages[1])
    
    return (x, y)

# ============================================================================
# Public Interface
# ============================================================================

def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """
    Get (x, y) coordinates for placement.
    Uses OBB model first, falls back to MediaPipe Pose if not detected.
    """
    # 1. Try OBB detection first
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        
        if debug:
            print(f"[getCoordinates] Looking for '{targetClass}' in {list(regions.keys())}")
            
        if targetClass in regions:
            region = regions[targetClass]
            coords = (int(region.center[0]), int(region.center[1]))
            if debug: print(f"[getCoordinates] Found OBB at {coords}")
            return coords
            
    except Exception as e:
        if debug: print(f"[GarmentDetector] OBB failed: {e}")
    
    # 2. Fallback to MediaPipe + heuristic
    coords = _getHeuristicCoordinates(imagePath, locationName)
    
    # Log clearly that fallback was used
    print(f"[FALLBACK] Position '{locationName}' not detected — using MediaPipe placement at {coords}")
    
    return coords

def getRotation(imagePath, locationName):
    """
    Get rotation angle (degrees).
    Uses behavior flags from registry:
      - standard: Use OBB angle
      - vertical_lock: Force 0 (vertical)
      - fixed_0: Force 0
      - fixed_45: Force 45 (for towels)
    """
    behavior = getPositionBehavior(locationName)
    rotationMode = behavior.get('rotation', 'standard')
    
    if rotationMode == 'fixed_0':
        return 0.0
    if rotationMode == 'fixed_90':
        return 90.0
    if rotationMode == 'vertical_lock':
        return 0.0
        
    try:
        regions = _getRegions(imagePath)
        targetClass = _getObbClassName(locationName)
        
        if targetClass in regions:
            angle = -regions[targetClass].angle
            return angle
            
    except Exception:
        pass
    
    return 0.0

def getLogoScale(imagePath, locationName, baseSize=(200, 100)):
    """
    DEPRECATED: Logo sizing logic is now handled in core/utils.py via computeLogoSize.
    This function is kept for interface compatibility but returns standard fallback.
    """
    return (99, 99)
