"""
Utility functions for OBB Inference visualization and testing.
Includes logo loading, rotation, masking, and debug drawing.
"""

import cv2
import numpy as np
import tempfile
import os
import glob
from pathlib import Path
from typing import Tuple, List
from .engine import OBBRegion, InferenceEngine

def runDetectorTest(detector: InferenceEngine, inputDir: str, outputDir: str, logoPath: str = None):
    """
    Run visual test for a detector.
    
    Args:
        detector: Initialized detector instance.
        inputDir: Directory containing test images.
        outputDir: Directory to save results.
        logoPath: Path to logo file (optional).
    """
    inputPath = Path(inputDir)
    outputPath = Path(outputDir)
    outputPath.mkdir(parents=True, exist_ok=True)
    
    # Resolve images
    extensions = ["*.jpg", "*.jpeg", "*.png"]
    images = []
    if inputPath.is_file():
        images = [inputPath]
    else:
        for ext in extensions:
            images.extend(inputPath.glob(ext))
            
    if not images:
        print(f"[RunTest] No images found in {inputDir}")
        return
        
    print(f"[RunTest] Found {len(images)} images. Processing...")
    
    # Load Logo if provided
    logo = None
    if logoPath and os.path.exists(logoPath):
        logo = loadLogo(logoPath)
    
    for imgFile in images:
        print(f"  -> Processing {imgFile.name}...")
        
        # Detect
        regions = detector.detect(str(imgFile))
        print(f"     Detected {len(regions)} regions.")
        
        # Load Image
        image = cv2.imread(str(imgFile))
        if image is None: continue
        
        # Draw Debug
        debugImg = drawDebugInfo(image, regions)
        
        # Place Logo Visualization
        if logo is not None:
            for r in regions:
                try:
                    # Get config for this class if available
                    config = detector.config.get(r.className, {})
                    baseSize = config.get("baseSize", 99)
                    align = config.get("align", "center")
                    
                    debugImg = placeLogoOnRegion(debugImg, logo, r, baseSize, align)
                except Exception as e:
                    print(f"     Failed to place logo on {r.className}: {e}")
        
        # Save
        savePath = outputPath / f"result_{imgFile.name}"
        cv2.imwrite(str(savePath), debugImg)
        print(f"     Saved: {savePath}")
        
    print(f"[RunTest] Completed. Check {outputDir}")

def loadLogo(logoPath: str) -> np.ndarray:
    """Load logo with alpha channel (handles PDF conversion if needed)."""
    pathStr = str(logoPath)
    
    # PDF Handling
    if pathStr.lower().endswith('.pdf'):
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pathStr)
            page = doc[0]
            zoom = 2.0  # ~144 DPI
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=True)
            
            imgData = np.frombuffer(pix.samples, dtype=np.uint8)
            imgData = imgData.reshape(pix.height, pix.width, pix.n)
            doc.close()
            
            if pix.n == 4:
                return cv2.cvtColor(imgData, cv2.COLOR_RGBA2BGRA)
            else:
                return cv2.cvtColor(imgData, cv2.COLOR_RGB2BGRA)
        except Exception as e:
            print(f"Error loading PDF: {e}")
            return None
            
    # Regular Image
    logo = cv2.imread(pathStr, cv2.IMREAD_UNCHANGED)
    if logo is None:
        return None
        
    # Ensure BGRA
    if len(logo.shape) == 2:
        logo = cv2.cvtColor(logo, cv2.COLOR_GRAY2BGRA)
    elif logo.shape[2] == 3:
        # Create alpha from white background
        b, g, r = cv2.split(logo)
        whiteMask = (b > 240) & (g > 240) & (r > 240)
        alpha = np.where(whiteMask, 0, 255).astype(np.uint8)
        logo = cv2.merge([b, g, r, alpha])
        
    return logo

def rotateLogo(logo: np.ndarray, angle: float) -> np.ndarray:
    """Rotate logo by angle (degrees), preserving alpha."""
    h, w = logo.shape[:2]
    center = (w / 2, h / 2)
    
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    newW = int(h * sin + w * cos)
    newH = int(h * cos + w * sin)
    
    M[0, 2] += (newW - w) / 2
    M[1, 2] += (newH - h) / 2
    
    return cv2.warpAffine(
        logo, M, (newW, newH),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0)
    )

def createObbMask(imageShape: Tuple[int, int], boxPoints: np.ndarray) -> np.ndarray:
    """Create binary mask from OBB points."""
    mask = np.zeros(imageShape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [boxPoints], 255)
    return mask

def drawDebugInfo(image: np.ndarray, regions: List[OBBRegion]) -> np.ndarray:
    """Draw OBB boxes and labels on image."""
    debugImg = image.copy()
    
    for r in regions:
        # Draw Poly
        pts = r.boxPoints.reshape((-1, 1, 2))
        cv2.polylines(debugImg, [pts], True, (0, 0, 255), 2)
        
        # Draw Center
        cx, cy = int(r.center[0]), int(r.center[1])
        cv2.circle(debugImg, (cx, cy), 5, (255, 0, 255), -1)
        
        # Label
        label = f"{r.className} ({r.confidence:.0%})"
        cv2.putText(debugImg, label, (cx - 50, cy - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                   
        # Angle
        angleText = f"Angle: {r.angle:.1f}"
        cv2.putText(debugImg, angleText, (cx - 50, cy + 15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                   
    return debugImg

def placeLogoOnRegion(image: np.ndarray, logo: np.ndarray, region: OBBRegion, 
                     baseSize: int = 99, align: str = "center") -> np.ndarray:
    """
    Place logo on detected region for visualization.
    Uses OBB masking.
    """
    result = image.copy()
    
    # 1. Resize
    lh, lw = logo.shape[:2]
    aspect = lh / lw if lw > 0 else 1.0
    targetW = baseSize
    targetH = int(baseSize * aspect)
    logoResized = cv2.resize(logo, (targetW, targetH), interpolation=cv2.INTER_AREA)
    
    # 2. Rotate
    angle = -region.angle # Negate for CV2
    logoRotated = rotateLogo(logoResized, angle)
    
    # 3. Position
    lh, lw = logoRotated.shape[:2]
    cx, cy = region.center
    obbW, obbH = region.size
    
    if align == "left":
         angleRad = np.radians(region.angle)
         offX = (obbW/2 - lw/2) * np.cos(angleRad)
         offY = (obbW/2 - lw/2) * np.sin(angleRad)
         px = int(cx - offX - lw/2)
         py = int(cy - offY - lh/2)
    elif align == "right":
         angleRad = np.radians(region.angle)
         offX = (obbW/2 - lw/2) * np.cos(angleRad)
         offY = (obbW/2 - lw/2) * np.sin(angleRad)
         px = int(cx + offX - lw/2)
         py = int(cy + offY - lh/2)
    else: # Center
         px = int(cx - lw/2)
         py = int(cy - lh/2)
         
    # 4. Mask
    mask = createObbMask(image.shape, region.boxPoints)
    
    # 5. Composite (Simplified)
    # Clip to valid range
    h, w = image.shape[:2]
    x1, y1 = max(0, px), max(0, py)
    x2, y2 = min(w, px + lw), min(h, py + lh)
    
    lx1 = x1 - px
    ly1 = y1 - py
    lx2 = lx1 + (x2 - x1)
    ly2 = ly1 + (y2 - y1)
    
    if lx2 <= lx1 or ly2 <= ly1:
        return result
        
    roi = result[y1:y2, x1:x2].astype(np.float32)
    logoCrop = logoRotated[ly1:ly2, lx1:lx2].astype(np.float32)
    maskCrop = mask[y1:y2, x1:x2].astype(np.float32) / 255.0
    
    alpha = logoCrop[:, :, 3] / 255.0
    alpha = alpha * maskCrop
    
    for c in range(3):
        roi[:, :, c] = logoCrop[:, :, c] * alpha + roi[:, :, c] * (1 - alpha)
        
    result[y1:y2, x1:x2] = roi.astype(np.uint8)
    return result
