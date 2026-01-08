import cv2
import mediapipe as mp
import math
import os
from core.utils import normalizeLocation, isDualImage

# Initialize MediaPipe Pose
mpPose = mp.solutions.pose
LANDMARKS = mpPose.PoseLandmark

# Cached landmarks to avoid re-processing the same image
_garmentLandmarkCache = {}

def r(val):
    """Round to int."""
    return int(round(val))

def _cacheKey(path, side="full"):
    """
    Cache key based on path, mtime, and crop side.
    side: 'full', 'left', 'right'
    """
    try:
        mtime = os.path.getmtime(path)
    except:
        mtime = 0
    return (os.path.abspath(path), mtime, side)

def getPoseLandmarks(imagePath, side="full"):
    """
    Get landmarks for the image (or a specific crop).
    side: 'full', 'left' (Back), 'right' (Front)
    """
    key = _cacheKey(imagePath, side)
    if key in _garmentLandmarkCache:
        return _garmentLandmarkCache[key]

    image = cv2.imread(imagePath)
    if image is None:
        raise ValueError(f"Image not found: {imagePath}")

    h, w, _ = image.shape
    
    # Handle Cropping for Dual Images
    # "left people is back side and right will be front"
    offsetX = 0
    offsetY = 0
    processImage = image
    
    if side == "left":
        # Left half (Back)
        processImage = image[:, :w//2]
        offsetX = 0
    elif side == "right":
        # Right half (Front)
        processImage = image[:, w//2:]
        offsetX = w//2
        
    ph, pw, _ = processImage.shape

    with mpPose.Pose(static_image_mode=True, min_detection_confidence=0.5) as pose:
        results = pose.process(cv2.cvtColor(processImage, cv2.COLOR_BGR2RGB))
        
        if not results.pose_landmarks:
            if side != "full":
                raise ValueError(f"No person detected in {side} half of image!")
            raise ValueError("No person detected in image!")

        landmarks = results.pose_landmarks.landmark
    
        _garmentLandmarkCache[key] = (landmarks, (ph, pw), (offsetX, offsetY))
        return _garmentLandmarkCache[key]

def getGarmentCoordinates(imagePath, locationName, debug=False):
    """
    Get coordinates using MediaPipe. 
    Handles logic for Single vs Dual(Split) images.
    """
    normLoc = normalizeLocation(locationName)    
    pass

# We will implement the signature assuming main.py passes original context.
# We will define the strict offsets here.

GARMENT_OFFSETS = {
    # Offsets are (x, y) relative to the calculated point
    # SINGLE / FRONT (Right side if dual)
    "FULL-FRONT": {"target": "SHOULDERS_MID", "x": 0, "y": 170},
    "LEFT-BICEP": {"target": "LEFT_BICEP_MID", "x": 42, "y": -35},
    "RIGHT-BICEP": {"target": "RIGHT_BICEP_MID", "x": -71, "y": -13},
    "LEFT-CHEST": {"target": "LEFT_CHEST_ZONE", "x": 0, "y": 80}, # Custom logic
    "RIGHT-CHEST": {"target": "RIGHT_CHEST_ZONE", "x": 0, "y": 80},
    "LEFT-COLLAR": {"target": "LEFT_SHOULDER", "x": -189, "y": -100},
    "RIGHT-COLLAR": {"target": "RIGHT_SHOULDER", "x": 185, "y": -110},
    "LEFT-CUFF": {"target": "LEFT_WRIST", "x": -10, "y": 2},
    "RIGHT-CUFF": {"target": "RIGHT_WRIST", "x": -11, "y": -16},
    "LEFT-HIP": {"target": "LEFT_HIP", "x": 50, "y": 16},
    "RIGHT-HIP": {"target": "RIGHT_HIP", "x": -40, "y": 16},
    "LEFT-SLEEVE": {"target": "LEFT_SLEEVE_ZONE", "x": 42, "y": -48},
    "RIGHT-SLEEVE": {"target": "RIGHT_SLEEVE_ZONE", "x": -9, "y": -46},
    "LEFT-THIGH-HIGH": {"target": "LEFT_HIP", "x": 60, "y": 16},
    "RIGHT-THIGH-HIGH": {"target": "RIGHT_HIP", "x": -60, "y": 16},
    "ON-POCKET": {"target": "HIPS_MID", "x": 220, "y": -634},
    
    # BACK (Left side if dual)
    "FULL-BACK": {"target": "SHOULDERS_MID", "x": -30, "y": 80},
    "BACK-YOKE": {"target": "SHOULDERS_MID", "x": -21, "y": -87},
}

def getGarmentCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    # If main.py hasn't been updated yet, originalLocation might be None.
    # Fallback: assume locationName is originalLocation if None
    contextLoc = originalLocation if originalLocation else locationName
    
    normLoc = normalizeLocation(locationName)
    isDual = isDualImage(contextLoc)
    
    # Determine side
    side = "full"
    if isDual:
        # Check if the specific target is on Back or Front
        if "BACK" in normLoc:
            side = "left" # Back is Left
        else:
            side = "right" # Front is Right
    
    # Get Landmarks
    try:
        landmarks, (ph, pw), (offX, offY) = getPoseLandmarks(imagePath, side)
    except Exception as e:
        if side == "full" and isDual:
             # Fallback: maybe we shouldn't have treated it as full?
             pass
        raise e

    # Helper to get point
    def getP(lm):
        return (landmarks[lm].x * pw, landmarks[lm].y * ph)

    targetConfig = GARMENT_OFFSETS.get(normLoc, GARMENT_OFFSETS.get("FULL-FRONT")) # Default to Front logic?
    
    # Basic calcs
    leftSh = getP(LANDMARKS.LEFT_SHOULDER)
    rightSh = getP(LANDMARKS.RIGHT_SHOULDER)
    
    x, y = 0, 0
    target = targetConfig.get("target", "SHOULDERS_MID")
    
    if target == "SHOULDERS_MID":
        x = (leftSh[0] + rightSh[0]) / 2
        y = (leftSh[1] + rightSh[1]) / 2
        
    elif target == "LEFT_BICEP_MID":
        lElbow = getP(LANDMARKS.LEFT_ELBOW)
        x = (leftSh[0] + lElbow[0]) / 2
        y = (leftSh[1] + lElbow[1]) / 2
        
    elif target == "RIGHT_BICEP_MID":
        rElbow = getP(LANDMARKS.RIGHT_ELBOW)
        x = (rightSh[0] + rElbow[0]) / 2
        y = (rightSh[1] + rElbow[1]) / 2
        
    elif target == "LEFT_CHEST_ZONE":
        # Shoulder bias
        x = leftSh[0]
        y = (leftSh[1] + rightSh[1]) / 2
        # Special logic from original: alpha=0.5 bias
        midX = (leftSh[0] + rightSh[0]) / 2
        x = midX + 0.5 * (leftSh[0] - midX)
        if side == "right" or not isDual: # Standard Front
             x += 18 # Offset from bias logic
        
    elif target == "RIGHT_CHEST_ZONE":
        midX = (leftSh[0] + rightSh[0]) / 2
        y = (leftSh[1] + rightSh[1]) / 2
        x = midX + 0.5 * (rightSh[0] - midX)
        if side == "right" or not isDual: 
             x += -20

    elif target == "LEFT_SHOULDER":
        x, y = leftSh
        
    elif target == "RIGHT_SHOULDER":
        x, y = rightSh
        
    elif target == "LEFT_WRIST":
        x, y = getP(LANDMARKS.LEFT_WRIST)
        
    elif target == "RIGHT_WRIST":
        x, y = getP(LANDMARKS.RIGHT_WRIST)
        
    elif target == "LEFT_HIP":
        x, y = getP(LANDMARKS.LEFT_HIP)
        
    elif target == "RIGHT_HIP":
        x, y = getP(LANDMARKS.RIGHT_HIP)
        
    elif target == "HIPS_MID":
        lH = getP(LANDMARKS.LEFT_HIP)
        rH = getP(LANDMARKS.RIGHT_HIP)
        x = (lH[0] + rH[0]) / 2
        y = (lH[1] + rH[1]) / 2
        
    elif target == "LEFT_SLEEVE_ZONE":
        lElbow = getP(LANDMARKS.LEFT_ELBOW)
        # Weighted 0.7
        x = leftSh[0] + 0.7 * (lElbow[0] - leftSh[0])
        y = leftSh[1] + 0.7 * (lElbow[1] - leftSh[1])
        
    elif target == "RIGHT_SLEEVE_ZONE":
        rElbow = getP(LANDMARKS.RIGHT_ELBOW)
        x = rightSh[0] + 0.7 * (rElbow[0] - rightSh[0])
        y = rightSh[1] + 0.7 * (rElbow[1] - rightSh[1])

    # Apply global offsets
    finalX = x + targetConfig["x"] + offX
    finalY = y + targetConfig["y"] + offY
    
    return int(finalX), int(finalY)


def getAngleBetweenPoints(p1, p2):
    """Calculate angle in degrees between two points (normalized 0..1)."""
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    return math.degrees(math.atan2(dy, dx))

def getGarmentRotationAngle(imagePath, locationName):
    """Get rotation angle for logo placement based on body pose."""
    normLoc = normalizeLocation(locationName)
    isDual = isDualImage(locationName)
    side = "full"
    if isDual:
        if "BACK" in normLoc:
            side = "left"
        else:
            side = "right"
            
    try:
        landmarks, (ph, pw), _ = getPoseLandmarks(imagePath, side)
    except:
        return 0

    if normLoc in ["LEFT-BICEP", "LEFT-SLEEVE"]:
        # If we are looking at Front (Right crop), Left Sleeve is on listener's right.
        # Check landmarks. MediaPipe is relative to the *person*.
        return getAngleBetweenPoints(landmarks[LANDMARKS.LEFT_SHOULDER], landmarks[LANDMARKS.LEFT_ELBOW])
        
    elif normLoc in ["RIGHT-BICEP", "RIGHT-SLEEVE"]:
        return getAngleBetweenPoints(landmarks[LANDMARKS.RIGHT_SHOULDER], landmarks[LANDMARKS.RIGHT_ELBOW])
        
    elif normLoc == "LEFT-CUFF":
        return getAngleBetweenPoints(landmarks[LANDMARKS.LEFT_ELBOW], landmarks[LANDMARKS.LEFT_WRIST])
        
    elif normLoc == "RIGHT-CUFF":
        return getAngleBetweenPoints(landmarks[LANDMARKS.RIGHT_ELBOW], landmarks[LANDMARKS.RIGHT_WRIST])
        
    elif normLoc == "LEFT-COLLAR":
        return getAngleBetweenPoints(landmarks[LANDMARKS.LEFT_SHOULDER], landmarks[LANDMARKS.LEFT_EAR])
        
    elif normLoc == "RIGHT-COLLAR":
        return getAngleBetweenPoints(landmarks[LANDMARKS.RIGHT_SHOULDER], landmarks[LANDMARKS.RIGHT_EAR])
        
    return 0


def getGarmentLogoScale(imagePath, locationName, baseLogoSize=(200, 100)):
    """Calculate appropriate logo scale based on body landmarks."""
    normLoc = normalizeLocation(locationName)
    isDual = isDualImage(locationName)
    
    side = "full"
    if isDual:
        if "BACK" in normLoc:
            side = "left"
        else:
            side = "right"

    try:
        landmarks, (ph, pw), _ = getPoseLandmarks(imagePath, side)
    except:
        return baseLogoSize
        
    p1, p2 = None, None
    
    if normLoc in ["LEFT-BICEP", "RIGHT-BICEP", "LEFT-SLEEVE", "RIGHT-SLEEVE"]:
        if "LEFT" in normLoc:
            p1 = landmarks[LANDMARKS.LEFT_SHOULDER]
            p2 = landmarks[LANDMARKS.LEFT_ELBOW]
        else:
            p1 = landmarks[LANDMARKS.RIGHT_SHOULDER]
            p2 = landmarks[LANDMARKS.RIGHT_ELBOW]
            
    elif normLoc in ["LEFT-CHEST", "RIGHT-CHEST"]:
        p1 = landmarks[LANDMARKS.NOSE]
        # Distance to shoulder
        if "LEFT" in normLoc:
            p2 = landmarks[LANDMARKS.LEFT_SHOULDER]
        else:
            p2 = landmarks[LANDMARKS.RIGHT_SHOULDER]
            
    elif normLoc in ["FULL-FRONT", "FULL-BACK", "FULL-BACK-FULL-FRONT"]: # Standardize?
        # Use simple shoulder width
        p1 = landmarks[LANDMARKS.LEFT_SHOULDER]
        p2 = landmarks[LANDMARKS.RIGHT_SHOULDER]
    else:
        return baseLogoSize
        
    if not p1 or not p2:
        return baseLogoSize

    # Calculate pixel distance
    dx = (p2.x - p1.x) * pw
    dy = (p2.y - p1.y) * ph
    distance = (dx*dx + dy*dy)**0.5
    
    if baseLogoSize[0] == 0: return baseLogoSize
    
    scaleFactor = distance / baseLogoSize[0]
    newWidth = int(baseLogoSize[0] * scaleFactor * 0.6)
    newHeight = int(baseLogoSize[1] * scaleFactor * 0.6)
    
    return (newWidth, newHeight)

def getGarmentArmRotation(imagePath, locationName):
    return getGarmentRotationAngle(imagePath, locationName)

