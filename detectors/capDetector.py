import cv2
import numpy as np
from core.utils import normalizeLocation

def getProductBoundingBox(image, offsetX=0, offsetY=0):
    """
    Detect largest object in image using contours.
    Returns (x, y, w, h) in absolute coordinates (img reference).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        h, w = image.shape[:2]
        return (offsetX + w//4, offsetY + h//4, w//2, h//2)
        
    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    
    return x + offsetX, y + offsetY, w, h

def getCapCoordinates(imagePath, locationName, debug=False):
    """
    Get coordinates for caps using Object Detection.
    Handles Dual Image splitting if keywords found.
    """
    normLoc = normalizeLocation(locationName)
    
    img = cv2.imread(imagePath)
    if img is None:
        raise ValueError(f"Image not found: {imagePath}")
        
    h, w, _ = img.shape

    processImage = img
    offX = 0
    offY = 0

    aspect = w / h
    
    # Or strict keyword?
    usageSide = "full"

    
    if "BACK" in normLoc:
        # Assuming Back is Left side? similar to garments?
        # Or Back is the *Only* thing in the image?
        # If Single image: Full.
        # If Dual image: Left.
        if aspect > 1.2: # Likely Dual
            usageSide = "left"
            
    if "SIDE" in normLoc:
        if aspect > 1.2:
            usageSide = "right" # Assuming Side is on Right? Wrapper logic.

    if usageSide == "left":
        processImage = img[:, :w//2]
        offX = 0
    elif usageSide == "right":
        processImage = img[:, w//2:]
        offX = w//2
        
    bx, by, bw, bh = getProductBoundingBox(processImage, offX, offY)
    
    # Calculate geometric points
    centerX = bx + bw // 2
    centerY = by + bh // 2
    topY = by
    bottomY = by + bh
    
    if "FRONT-CROWN" in normLoc:
        # Upper area
        return centerX, int(by + bh * 0.25)
        
    if "CAP-BACK" in normLoc:
        # Center?
        return centerX, centerY
        
    if "CAP-SIDE" in normLoc:
        # Center
        return centerX, centerY
        
    if "CAP-FRONT-SIDE" in normLoc:
        # Bit to the side?
        return int(bx + bw * 0.75), int(by + bh * 0.4)
        
    if "LOWER-LEFT-CROWN" in normLoc:
        return int(bx + bw * 0.3), int(by + bh * 0.6)

    if "LOWER-RIGHT-CROWN" in normLoc:
        return int(bx + bw * 0.7), int(by + bh * 0.6)

    # Default
    return centerX, centerY

# Main

def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """Standard Interface: Get (x, y) coordinates."""
    return getCapCoordinates(imagePath, locationName, debug)

def getLogoScale(imagePath, locationName, baseSize=(200, 100)):
    """Standard Interface: Get (width, height) for logo."""
    # Dummy implementation for now - return base size
    return baseSize

def getRotation(imagePath, locationName):
    """Standard Interface: Get rotation angle."""
    # Caps usually dont need rotation unless curved text on back arch?
    return 0
