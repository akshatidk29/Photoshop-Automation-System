import cv2
import numpy as np
import tempfile
import os

_mask_cache = {}

# Erode the garment mask by this many pixels to keep logo fully inside garment boundary
# Increase this value if logo still extends outside the garment edge
CLIPPING_EROSION = 5


def getGarmentMask(image_path: str) -> np.ndarray:

    if image_path in _mask_cache:
        return _mask_cache[image_path]
    
    image = cv2.imread(image_path)
    if image is None:
        return None
    
    try:
        from rembg import remove
        from PIL import Image
        
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        result = remove(
            pil_image,
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=20,
            alpha_matting_erode_size=10
        )
        result_np = np.array(result)
        
        if result_np.shape[2] == 4:
            garment_mask = result_np[:, :, 3]
        else:
            garment_mask = cv2.cvtColor(result_np, cv2.COLOR_RGB2GRAY)
        
        _, garment_mask = cv2.threshold(garment_mask, 127, 255, cv2.THRESH_BINARY)
        
        # Erode mask to keep logo fully inside garment boundary
        if CLIPPING_EROSION > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLIPPING_EROSION * 2 + 1, CLIPPING_EROSION * 2 + 1))
            garment_mask = cv2.erode(garment_mask, kernel, iterations=1)
        
        _mask_cache[image_path] = garment_mask
        return garment_mask
        
    except Exception as e:
        print(f"[logoClipper] rembg failed, using simple detection: {e}")
        return _getGarmentMaskSimple(image)


# Fallback
def _getGarmentMaskSimple(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    b, g, r = cv2.split(image)
    
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
                       center_x: int, center_y: int, target_size: int = None) -> str:
    """Clip logo so only pixels over garment are visible. Returns temp file path."""
    logo = _loadLogo(logo_path)
    if logo is None:
        return logo_path
    
    garment_mask = getGarmentMask(garment_image_path)
    if garment_mask is None:
        return logo_path
    
    # Resize logo if target_size specified
    if target_size is not None:
        lh, lw = logo.shape[:2]
        if lw > 0 and lh > 0:
            scale = target_size / max(lw, lh)
            logo = cv2.resize(logo, (int(lw * scale), int(lh * scale)), interpolation=cv2.INTER_AREA)
    
    # Calculate logo position and extract mask region
    lh, lw = logo.shape[:2]
    gh, gw = garment_mask.shape[:2]
    
    px = center_x - lw // 2
    py = center_y - lh // 2
    
    x1, y1 = max(0, px), max(0, py)
    x2, y2 = min(gw, px + lw), min(gh, py + lh)
    
    lx1, ly1 = x1 - px, y1 - py
    lx2, ly2 = lx1 + (x2 - x1), ly1 + (y2 - y1)
    
    if lx2 <= lx1 or ly2 <= ly1:
        return logo_path
    
    # Apply garment mask to logo alpha channel
    mask_region = garment_mask[y1:y2, x1:x2]
    logo_mask = np.zeros((lh, lw), dtype=np.uint8)
    logo_mask[ly1:ly2, lx1:lx2] = mask_region
    
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

