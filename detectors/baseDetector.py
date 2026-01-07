import os
import cv2
import mediapipe as mp
import math

mpPose = mp.solutions.pose
LANDMARKS = mpPose.PoseLandmark

# Landmark cache: compute MediaPipe landmarks once per image path+mtime
_landmarkCache = {}


def _cacheKey(path: str):
    """Generate cache key from file path and modification time."""
    try:
        return (os.path.abspath(path), os.path.getmtime(path))
    except Exception:
        return (os.path.abspath(path), None)


def getLandmarksAndSize(imagePath):
    """Return (landmarks, (h,w)) using an in-memory cache keyed by path+mtime."""
    key = _cacheKey(imagePath)
    if key in _landmarkCache:
        return _landmarkCache[key]

    image = cv2.imread(imagePath)
    if image is None:
        raise ValueError("Image not found!")

    with mpPose.Pose(static_image_mode=True) as pose:
        results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        if not results.pose_landmarks:
            raise ValueError("No person detected!")

        landmarks = results.pose_landmarks.landmark
        h, w, _ = image.shape
        _landmarkCache[key] = (landmarks, (h, w))
        return _landmarkCache[key]


def getAngleBetweenPoints(p1, p2):
    """Calculate angle in degrees between two points."""
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    return math.degrees(math.atan2(dy, dx))


def getLocationCoordinates(imagePath, locationName, mapping, debug=False):
    """Generic coordinate detection using provided mapping configuration."""
    locationName = str(locationName).replace(" ", "-").upper()

    landmarks, (h, w) = getLandmarksAndSize(imagePath)

    if locationName not in mapping:
        raise ValueError(f"Location '{locationName}' not mapped!")

    config = mapping[locationName]
    landmarkNames = config["landmarks"]
    method = config["method"]
    alpha = config.get("alpha", 0.5)
    xOffset = config.get("xOffset", 0)
    yOffset = config.get("yOffset", 0)

    lmCoords = [(landmarks[getattr(LANDMARKS, name)].x,
                  landmarks[getattr(LANDMARKS, name)].y) for name in landmarkNames]
    
    if method == "single":
        x, y = lmCoords[0]
        x = int(x * w) + xOffset
        y = int(y * h) + yOffset

    elif method == "midpoint":
        x = sum(coord[0] for coord in lmCoords) / len(lmCoords)
        y = sum(coord[1] for coord in lmCoords) / len(lmCoords)
        x = int(x * w) + xOffset
        y = int(y * h) + yOffset

    elif method == "weighted":
        x = lmCoords[0][0] + alpha * (lmCoords[1][0] - lmCoords[0][0])
        y = lmCoords[0][1] + alpha * (lmCoords[1][1] - lmCoords[0][1])
        x = int(x * w) + xOffset
        y = int(y * h) + yOffset

    elif method == "shoulderBias":
        leftSh = lmCoords[0]
        rightSh = lmCoords[1]
        baseMidX = (leftSh[0] + rightSh[0]) / 2.0
        baseMidY = (leftSh[1] + rightSh[1]) / 2.0

        side = config.get("side", "left").strip().lower()
        a = config.get("alpha", 0.5)
        if side.startswith("left"):
            targetShX = leftSh[0]
            xOffset = 18
        else:
            targetShX = rightSh[0]
            xOffset = -20

        x = baseMidX + a * (targetShX - baseMidX)
        y = baseMidY
        x = int(x * w) + xOffset
        y = int(y * h) + yOffset

    elif method == "average":
        x = sum(coord[0] for coord in lmCoords) / len(lmCoords)
        y = sum(coord[1] for coord in lmCoords) / len(lmCoords)
        x = int(x * w) + xOffset
        y = int(y * h) + yOffset

    if debug:
        print(f"{locationName}: ({x}, {y})")
    
    return (x, y)


def getRotationAngle(imagePath, locationName):
    """Get rotation angle for logo placement based on body pose."""
    locationName = str(locationName).strip().upper().replace(" ", "-")
    landmarks, (h, w) = getLandmarksAndSize(imagePath)

    if locationName in ["LEFT-BICEP", "LEFT-SLEEVE"]:
        return getAngleBetweenPoints(landmarks[LANDMARKS.LEFT_SHOULDER], landmarks[LANDMARKS.LEFT_ELBOW])
    elif locationName in ["RIGHT-BICEP", "RIGHT-SLEEVE"]:
        return getAngleBetweenPoints(landmarks[LANDMARKS.RIGHT_SHOULDER], landmarks[LANDMARKS.RIGHT_ELBOW])
    elif locationName == "LEFT-CUFF":
        return getAngleBetweenPoints(landmarks[LANDMARKS.LEFT_ELBOW], landmarks[LANDMARKS.LEFT_WRIST])
    elif locationName == "RIGHT-CUFF":
        return getAngleBetweenPoints(landmarks[LANDMARKS.RIGHT_ELBOW], landmarks[LANDMARKS.RIGHT_WRIST])
    elif locationName == "LEFT-COLLAR":
        return getAngleBetweenPoints(landmarks[LANDMARKS.LEFT_SHOULDER], landmarks[LANDMARKS.LEFT_EAR])
    elif locationName == "RIGHT-COLLAR":
        return getAngleBetweenPoints(landmarks[LANDMARKS.RIGHT_SHOULDER], landmarks[LANDMARKS.RIGHT_EAR])
    else:
        return 0


def getLogoScale(imagePath, locationName, baseLogoSize=(200, 100)):
    """Calculate appropriate logo scale based on body landmarks."""
    landmarks, (h, w) = getLandmarksAndSize(imagePath)

    if locationName in ["LEFT-BICEP", "RIGHT-BICEP", "LEFT-SLEEVE", "RIGHT-SLEEVE"]:
        if "LEFT" in locationName:
            p1 = landmarks[LANDMARKS.LEFT_SHOULDER]
            p2 = landmarks[LANDMARKS.LEFT_ELBOW]
        else:
            p1 = landmarks[LANDMARKS.RIGHT_SHOULDER]
            p2 = landmarks[LANDMARKS.RIGHT_ELBOW]
    elif locationName in ["LEFT-CHEST", "RIGHT-CHEST"]:
        p1 = landmarks[LANDMARKS.NOSE]
        p2 = landmarks[LANDMARKS.LEFT_SHOULDER if "LEFT" in locationName else LANDMARKS.RIGHT_SHOULDER]
    elif locationName in ["FULL-FRONT", "FULL-BACK"]:
        p1 = landmarks[LANDMARKS.LEFT_SHOULDER]
        p2 = landmarks[LANDMARKS.RIGHT_SHOULDER]
    else:
        return baseLogoSize

    dx = (p2.x - p1.x) * w
    dy = (p2.y - p1.y) * h
    distance = (dx**2 + dy**2)**0.5

    scaleFactor = distance / baseLogoSize[0]
    newWidth = int(baseLogoSize[0] * scaleFactor * 0.6)
    newHeight = int(baseLogoSize[1] * scaleFactor * 0.6)
    return (newWidth, newHeight)


def getArmRotationAngle(imagePath, locationName):
    """Get arm rotation angle for sleeve/bicep placements."""
    locationName = str(locationName).strip().upper().replace(" ", "-")
    landmarks, (h, w) = getLandmarksAndSize(imagePath)

    if locationName == "LEFT-BICEP":
        p1 = landmarks[LANDMARKS.LEFT_SHOULDER]
        p2 = landmarks[LANDMARKS.LEFT_ELBOW]
    elif locationName == "RIGHT-BICEP":
        p1 = landmarks[LANDMARKS.RIGHT_SHOULDER]
        p2 = landmarks[LANDMARKS.RIGHT_ELBOW]
    elif locationName == "LEFT-SLEEVE":
        p1 = landmarks[LANDMARKS.LEFT_SHOULDER]
        p2 = landmarks[LANDMARKS.LEFT_ELBOW]
    elif locationName == "RIGHT-SLEEVE":
        p1 = landmarks[LANDMARKS.RIGHT_SHOULDER]
        p2 = landmarks[LANDMARKS.RIGHT_ELBOW]
    else:
        return 0

    angleRadians = math.atan2(p2.y - p1.y, p2.x - p1.x)
    angleDegrees = math.degrees(angleRadians)
    return angleDegrees
