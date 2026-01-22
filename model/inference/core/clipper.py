"""
Advanced Logo Clipping Utility for Model Testing.
Handles OBB-based clipping with background removal logic.
"""

import os
import cv2
import numpy as np
import tempfile
import uuid
from ..core.engine import InferenceEngine

def createClippedLogo(detector: InferenceEngine, imagePath: str, logoPath: str, 
                     className: str, rotation: float = None, scaleFactor: float = 0.8) -> str:
    """
    Create a logo image clipped/masked to the OBB region.
    """
    # 1. Detect
    regions = detector.detect(imagePath)
    
    targetRegion = None
    for r in regions:
        if r.className == className:
            targetRegion = r
            break
            
    if targetRegion is None:
        print(f"[createClippedLogo] Region '{className}' not found")
        return None
        
    # 2. Load Logo (Using utils or custom load?)
    # We'll use a local helper or assume passed logo matches expectations
    # For now, implementing basic load to be self congruent or importing from utils
    from .utils import loadLogo, rotateLogo
    
    logo = loadLogo(logoPath)
    if logo is None:
        print(f"[createClippedLogo] Failed to load logo: {logoPath}")
        return None
        
    # 3. Setup Params
    if rotation is None:
        rotation = -targetRegion.angle
        
    obbW, obbH = targetRegion.size
    targetLogoW = int(obbW * scaleFactor)
    
    # 4. Resize
    lh, lw = logo.shape[:2]
    if lw > 0:
        scale = targetLogoW / lw
        newW = int(lw * scale)
        newH = int(lh * scale)
        logoScaled = cv2.resize(logo, (newW, newH), interpolation=cv2.INTER_AREA)
    else:
        logoScaled = logo
        
    # 5. Rotate
    logoRotated = rotateLogo(logoScaled, rotation)
    
    # 6. Place on Canvas
    origImage = cv2.imread(imagePath)
    if origImage is None: return None
    
    imgH, imgW = origImage.shape[:2]
    canvas = np.zeros((imgH, imgW, 4), dtype=np.uint8)
    
    lh, lw = logoRotated.shape[:2]
    cx, cy = int(targetRegion.center[0]), int(targetRegion.center[1])
    
    px = cx - lw // 2
    py = cy - lh // 2
    
    # Valid Region
    x1, y1 = max(0, px), max(0, py)
    x2, y2 = min(imgW, px + lw), min(imgH, py + lh)
    
    lx1 = x1 - px
    ly1 = y1 - py
    lx2 = lx1 + (x2 - x1)
    ly2 = ly1 + (y2 - y1)
    
    if lx2 > lx1 and ly2 > ly1:
        canvas[y1:y2, x1:x2] = logoRotated[ly1:ly2, lx1:lx2]
        
    # 7. Create Garment Mask (Logic ported)
    obbMask = np.zeros((imgH, imgW), dtype=np.uint8)
    cv2.fillPoly(obbMask, [targetRegion.boxPoints], 255)
    
    gray = cv2.cvtColor(origImage, cv2.COLOR_BGR2GRAY)
    b, g, r = cv2.split(origImage)
    
    isLight = (gray > 240) | ((b > 230) & (g > 230) & (r > 230))
    isWhite = (np.abs(b.astype(np.int16) - g.astype(np.int16)) < 10) & \
              (np.abs(g.astype(np.int16) - r.astype(np.int16)) < 10) & \
              (gray > 220)
              
    background = (isLight | isWhite).astype(np.uint8) * 255
    garmentMask = cv2.bitwise_and(obbMask, cv2.bitwise_not(background))
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    garmentMask = cv2.morphologyEx(garmentMask, cv2.MORPH_CLOSE, kernel)
    garmentMask = cv2.morphologyEx(garmentMask, cv2.MORPH_OPEN, kernel)
    
    contours, _ = cv2.findContours(garmentMask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        garmentMaskFilled = np.zeros_like(garmentMask)
        cv2.drawContours(garmentMaskFilled, [largest], -1, 255, -1)
        garmentMask = garmentMaskFilled
        
    garmentMask = cv2.erode(garmentMask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    
    # Apply to canvas
    canvas[:, :, 3] = np.minimum(canvas[:, :, 3], garmentMask)
    
    # Crop
    pts = targetRegion.boxPoints
    minX = max(0, int(pts[:, 0].min()) - 10)
    maxX = min(imgW, int(pts[:, 0].max()) + 10)
    minY = max(0, int(pts[:, 1].min()) - 10)
    maxY = min(imgH, int(pts[:, 1].max()) + 10)
    
    cropped = canvas[minY:maxY, minX:maxX]
    
    # Save
    tempId = uuid.uuid4().hex[:8]
    tempPath = os.path.join(tempfile.gettempdir(), f"clipped_{minX}_{minY}_{tempId}.png")
    cv2.imwrite(tempPath, cropped)
    
    return tempPath

def parseClippedLogoOffset(clippedLogoPath: str) -> Tuple[int, int]:
    """Parse offset from filename."""
    filename = os.path.basename(clippedLogoPath)
    if filename.startswith("clipped_"):
        parts = filename.split("_")
        if len(parts) >= 3:
            try:
                return int(parts[1]), int(parts[2])
            except ValueError:
                pass
    return (0, 0)
