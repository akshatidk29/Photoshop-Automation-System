import cv2
import numpy as np
from core.utils import normalizeLocation

def getProductBoundingBox(imagePath):
    """
    Detect largest object in image using contours (assuming white background).
    Returns (x, y, w, h) of the bounding box.
    """
    img = cv2.imread(imagePath)
    if img is None:
        raise ValueError(f"Image not found: {imagePath}")
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Threshold (assuming object is darker than white background, or simple diff)
    # White background usually > 240
    # Invert so object is white, bg is black
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        # Fallback: return center of image
        h, w = img.shape[:2]
        return (w//4, h//4, w//2, h//2)
        
    # Find largest contour
    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    
    return x, y, w, h

def getBagCoordinates(imagePath, locationName, debug=False):
    """
    Get coordinates for bag using Object Detection (Contours).
    """
    normLoc = normalizeLocation(locationName)
    
    try:
        bx, by, bw, bh = getProductBoundingBox(imagePath)
    except Exception as e:
        print(f"Error checking bag: {e}")
        # Default to center of image 1200x1200
        return (600, 600)
    
    centerX = bx + bw // 2
    centerY = by + bh // 2
    
    if "ON-POCKET" in normLoc: # ON POCKET (ON BAG)
        # Lower center
        # Move down by 15% of height?
        return centerX, int(centerY + bh * 0.15)
        
    # Default: Center (FRONT ON BAG)
    return centerX, centerY
