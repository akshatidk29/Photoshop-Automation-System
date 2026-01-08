import cv2
import numpy as np
from core.utils import normalizeLocation

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

def getTowelCoordinates(imagePath, locationName, debug=False):
    """
    Get coordinates for Towels/Blankets.
    """
    normLoc = normalizeLocation(locationName)
    
    try:
        bx, by, bw, bh = getProductBoundingBox(imagePath)
    except:
        return (600, 600)
    
    centerX = bx + bw // 2
    centerY = by + bh // 2
    
    if "CORNER" in normLoc: # CORNER-ANGLED-TOWEL
        # Bottom Right Corner area
        # Typically indented a bit
        return int(bx + bw * 0.85), int(by + bh * 0.85)

    # Default: Center (FRONT_CENTER)
    return centerX, centerY
