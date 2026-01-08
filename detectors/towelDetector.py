import cv2
import numpy as np
from core.utils import normalizeLocation

# =============================================================================
# TOWEL CONFIGURATION - EDIT THIS SECTION TO ADJUST LOGIC
# =============================================================================
TOWEL_CONFIG = {
    "CORNER-ANGLED-TOWEL": {
        "x_percent": 0.85,    # Place at 85% of width (Right side)
        "y_percent": 0.85,    # Place at 85% of height (Bottom)
        "scale_ratio": 0.15,  # Logo should be 15% of the towel's width
        "rotation": -45       # Rotate logo -45 degrees (angled)
    },
    "FRONT_CENTER": {
        "x_percent": 0.50,    # Center X
        "y_percent": 0.50,    # Center Y
        "scale_ratio": 0.40,  # Logo should be 40% of the towel's width (Big center logo)
        "rotation": 0         # No rotation
    },
    "DEFAULT": {
        "x_percent": 0.50,
        "y_percent": 0.50,
        "scale_ratio": 0.25,
        "rotation": 0
    }
}
# =============================================================================

def getProductBoundingBox(imagePath):
    """
    Detect largest object in image using contours.
    """
    img = cv2.imread(imagePath)
    if img is None:
        raise ValueError(f"Image not found: {imagePath}")
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        h, w = img.shape[:2]
        return (w//4, h//4, w//2, h//2)
        
    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    return x, y, w, h

def _getConfigForLocation(locationName):
    """Helper to get config settings for a location."""
    normLoc = normalizeLocation(locationName)
    
    if "CORNER" in normLoc:
        return TOWEL_CONFIG["CORNER-ANGLED-TOWEL"]
    elif "CENTER" in normLoc or "FRONT" in normLoc:
        return TOWEL_CONFIG["FRONT_CENTER"]
    else:
        return TOWEL_CONFIG["DEFAULT"]

def getTowelCoordinates(imagePath, locationName, debug=False):
    """
    Get coordinates for Towels/Blankets using configurable offsets.
    """
    try:
        bx, by, bw, bh = getProductBoundingBox(imagePath)
    except:
        return (600, 600)
    
    config = _getConfigForLocation(locationName)
    
    # Calculate Center X, Y based on Bounding Box and Config percentages
    # origin is bx, by. We add width * percent.
    finalX = bx + int(bw * config["x_percent"])
    finalY = by + int(bh * config["y_percent"])
    
    return finalX, finalY

def getTowelLogoScale(imagePath, locationName, baseLogoSize=(100, 100)):
    """
    Calculate target logo size based on Towel Width and Config.
    """
    try:
        bx, by, bw, bh = getProductBoundingBox(imagePath)
    except:
        return baseLogoSize
        
    config = _getConfigForLocation(locationName)
    targetWidth = int(bw * config["scale_ratio"])
    
    # Maintain aspect ratio of original logo if possible?
    # Here we return a target bounding box size (W, H).
    # Since we usually only care about Width for scaling, we can set H to something generic 
    # or calculate it if we knew logo aspect ratio. 
    # But this function only returns the "Container" size.
    # Let's return (targetWidth, targetWidth) as a square reference, 
    # or modify standard behavior to respect input baseLogoSize aspect.
    
    # If baseLogoSize is provided, we scale it.
    baseW, baseH = baseLogoSize
    if baseW == 0: baseW = 100
    
    ratio = targetWidth / baseW
    targetHeight = int(baseH * ratio)
    
    return (targetWidth, targetHeight)

def getTowelRotationAngle(imagePath, locationName):
    """
    Get rotation angle from config.
    """
    config = _getConfigForLocation(locationName)
    return config["rotation"]






# Main

def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    return getTowelCoordinates(imagePath, locationName, debug)

def getLogoScale(imagePath, locationName, baseSize=(200, 100)):
    # Towel implementation takes (x, y) but standard interface is (imagePath, locationName, baseSize)
    # The existing function signature matches standard:
    # def getTowelLogoScale(imagePath, locationName, baseLogoSize=(100, 100)):
    return getTowelLogoScale(imagePath, locationName, baseSize)

def getRotation(imagePath, locationName):
    return getTowelRotationAngle(imagePath, locationName)
