"""
Simple logo clipping based on garment silhouette.

This module provides functions to create pre-clipped logos where pixels
that would fall outside the garment are made transparent.
"""

import cv2
import numpy as np
import tempfile
import os

# Cache for garment masks to avoid recomputing
_mask_cache = {}


def getGarmentMask(image_path: str) -> np.ndarray:
    """
    Get a mask of the garment (non-background) pixels using deep learning.
    
    Uses rembg library for accurate foreground detection.
    
    Args:
        image_path: Path to garment image.
        
    Returns:
        Binary mask where 255 = garment, 0 = background.
    """
    # Check cache first
    if image_path in _mask_cache:
        return _mask_cache[image_path]
    
    image = cv2.imread(image_path)
    if image is None:
        return None
    
    try:
        # Use rembg for accurate background removal
        from rembg import remove
        from PIL import Image
        
        # Convert to PIL Image
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        # Remove background (returns RGBA image)
        result = remove(pil_image)
        
        # Extract alpha channel as mask
        result_np = np.array(result)
        if result_np.shape[2] == 4:
            garment_mask = result_np[:, :, 3]  # Alpha channel
        else:
            # Fallback - convert to grayscale
            garment_mask = cv2.cvtColor(result_np, cv2.COLOR_RGB2GRAY)
        
        # Threshold to get binary mask
        _, garment_mask = cv2.threshold(garment_mask, 127, 255, cv2.THRESH_BINARY)
        
        # Cache the result
        _mask_cache[image_path] = garment_mask
        return garment_mask
        
    except Exception as e:
        print(f"[logoClipper] rembg failed, using simple detection: {e}")
        # Fallback to simple color-based detection
        return _getGarmentMaskSimple(image)


def _getGarmentMaskSimple(image: np.ndarray) -> np.ndarray:
    """Fallback: simple color-based background detection."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    b, g, r = cv2.split(image)
    
    # Detect background (white/light pixels)
    is_light = (gray > 240) | ((b > 230) & (g > 230) & (r > 230))
    is_white = (np.abs(b.astype(np.int16) - g.astype(np.int16)) < 10) & \
               (np.abs(g.astype(np.int16) - r.astype(np.int16)) < 10) & \
               (gray > 220)
    
    background = (is_light | is_white).astype(np.uint8) * 255
    garment_mask = cv2.bitwise_not(background)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    garment_mask = cv2.morphologyEx(garment_mask, cv2.MORPH_CLOSE, kernel)
    garment_mask = cv2.morphologyEx(garment_mask, cv2.MORPH_OPEN, kernel)
    
    return garment_mask


def clipLogoToGarment(logo_path: str, garment_image_path: str, 
                       center_x: int, center_y: int) -> str:
    """
    Clip a logo so only pixels that fall on the garment are visible.
    
    NO RESIZING - uses logo at its current size.
    
    Args:
        logo_path: Path to logo file (PNG or rotated temp file).
        garment_image_path: Path to garment image.
        center_x, center_y: Where logo center will be placed.
        
    Returns:
        Path to clipped logo temp file.
    """
    # Load logo
    logo = _loadLogo(logo_path)
    if logo is None:
        return logo_path  # Return original on failure
    
    # Get garment mask
    garment_mask = getGarmentMask(garment_image_path)
    if garment_mask is None:
        return logo_path  # Return original on failure
    
    # Logo stays at original size - NO RESIZING
    lh, lw = logo.shape[:2]
    gh, gw = garment_mask.shape[:2]
    
    # Calculate where logo will be placed (center position)
    px = center_x - lw // 2
    py = center_y - lh // 2
    
    # Extract the garment mask region where logo will be placed
    x1 = max(0, px)
    y1 = max(0, py)
    x2 = min(gw, px + lw)
    y2 = min(gh, py + lh)
    
    lx1 = x1 - px
    ly1 = y1 - py
    lx2 = lx1 + (x2 - x1)
    ly2 = ly1 + (y2 - y1)
    
    if lx2 <= lx1 or ly2 <= ly1:
        return logo_path  # Logo outside image
    
    # Get the mask region from garment
    mask_region = garment_mask[y1:y2, x1:x2]
    
    # Create full logo mask (for the logo's coordinate space)
    logo_mask = np.zeros((lh, lw), dtype=np.uint8)
    logo_mask[ly1:ly2, lx1:lx2] = mask_region
    
    # Apply mask to logo alpha channel
    # Where mask is 0 (background), make logo transparent
    logo_clipped = logo.copy()
    logo_clipped[:, :, 3] = np.minimum(logo_clipped[:, :, 3], logo_mask)
    
    # Save to temp file
    import uuid
    temp_path = os.path.join(tempfile.gettempdir(), f"clipped_{uuid.uuid4().hex[:8]}.png")
    cv2.imwrite(temp_path, logo_clipped)
    
    return temp_path


def _loadLogo(logo_path: str) -> np.ndarray:
    """Load logo with alpha channel, handling PDF files."""
    logo_path = str(logo_path)
    
    if logo_path.lower().endswith('.pdf'):
        try:
            import fitz
            doc = fitz.open(logo_path)
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=True)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            doc.close()
            if pix.n == 4:
                return cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)
            else:
                return cv2.cvtColor(img, cv2.COLOR_RGB2BGRA)
        except Exception:
            return None
    else:
        logo = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
        if logo is None:
            return None
        if len(logo.shape) == 2:
            logo = cv2.cvtColor(logo, cv2.COLOR_GRAY2BGRA)
        elif logo.shape[2] == 3:
            b, g, r = cv2.split(logo)
            white_mask = (b > 240) & (g > 240) & (r > 240)
            alpha = np.where(white_mask, 0, 255).astype(np.uint8)
            logo = cv2.merge([b, g, r, alpha])
        return logo


def _rotateLogo(logo: np.ndarray, angle: float) -> np.ndarray:
    """Rotate logo preserving alpha."""
    h, w = logo.shape[:2]
    center = (w / 2, h / 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2
    return cv2.warpAffine(logo, M, (new_w, new_h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
