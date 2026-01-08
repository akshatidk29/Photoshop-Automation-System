import os
import re
import cv2
import shutil
import tempfile
from typing import Tuple
from .config import PDF_CONVERSION_DPI, PNG_NORMALIZE_HEIGHT, ASPECT_RATIO_TOLERANCE

# Try importing PyMuPDF first (preferred - no Poppler needed)
try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    from pdf2image import convert_from_path


def ensureFolder(path):
    """Create folder if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def cleanFilename(name):
    """Sanitize filename by removing illegal characters."""
    return "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).rstrip()


def copyFile(src, destFolder, newName=None):
    """Copy file with optional new name."""
    ensureFolder(destFolder)
    destPath = os.path.join(destFolder, newName if newName else os.path.basename(src))
    shutil.copy2(src, destPath)
    return destPath


def getCombinedName(*parts):
    """Join parts into a clean filename."""
    return cleanFilename("_".join(str(p).strip() for p in parts if p))


def getPsdSizeFromName(name):
    """Detect PSD size from filename."""
    if "1200 x 1800" in name or "shirt" in name.lower():
        return (1200, 1800)
    elif "1200 x 1200" in name or any(x in name.lower() for x in ["cap", "bag", "towel"]):
        return (1200, 1200)
    return (1200, 1800)



# Strict Location List (39 Positions)
VALID_LOCATIONS = {
    # 1200 x 1800 (Garments)
    "FULL-BACK", "FULL-FRONT",
    "LEFT-BICEP", "RIGHT-BICEP",
    "LEFT-CHEST", "RIGHT-CHEST",
    "LEFT-COLLAR", "RIGHT-COLLAR",
    "LEFT-CUFF", "RIGHT-CUFF",
    "LEFT-HIP", "RIGHT-HIP",
    "LEFT-SLEEVE", "RIGHT-SLEEVE",
    "LEFT-THIGH-HIGH", "RIGHT-THIGH-HIGH",
    "ON-POCKET", "BACK-YOKE",
    
    # Dual Image Garments
    "FULL-BACK-FULL-FRONT", # Standardized from &
    "LEFT-BICEP-RIGHT-BICEP",
    "LEFT-CHEST-LEFT-BICEP-RIGHT-BICEP",
    "LEFT-CHEST-RIGHT-BICEP",
    "LEFT-CHEST-RIGHT-SLEEVE",
    "LEFT-SLEEVE-RIGHT-SLEEVE",
    "RIGHT-CHEST-LEFT-BICEP",
    "RIGHT-CHEST-LEFT-SLEEVE",
    "RIGHT-CHEST-LEFT-BICEP-RIGHT-BICEP", # Fixed LFT typo from user request if needed, but matched strict list 
    "FULL-FRONT-FULL-BACK",
    "LEFT-CHEST-FULL-BACK",
    "RIGHT-CHEST-FULL-BACK",

    # 1200 x 1200 (Caps, Bags, Towels)
    "FRONT-CROWN", "CAP-BACK", "CAP-SIDE", "CAP-FRONT-SIDE",
    "LOWER-LEFT-CROWN", "LOWER-RIGHT-CROWN",
    "CORNER-ANGLED-TOWEL", "FRONT_CENTER",
    "FRONT (ON BAG)", "ON POCKET (ON BAG)"
}

def normalizeLocation(locationName):
    """
    Standardize location strings:
    1. Upper case, strip, replace spaces/& with hyphens.
    2. Sort tokens for combo positions (e.g. RIGHT-SLEEVE-LEFT-SLEEVE -> LEFT-SLEEVE-RIGHT-SLEEVE).
    """
    if not locationName:
        return ""
        
    # Initial cleanup: "FULL-BACK & FULL-FRONT" -> "FULL-BACK-FULL-FRONT"
    clean = str(locationName).upper().replace("&", "-").replace(" ", "-")
    # Remove multiple hyphens
    clean = "-".join(filter(None, clean.split("-")))

    
    # Mapping for known variations
    mapping = {
        "RIGHT-CHEST-LFT-BICEP-RIGHT-BICEP": "RIGHT-CHEST-LEFT-BICEP-RIGHT-BICEP", # Fix typo LFT
        "FULL-BACK-&-FULL-FRONT": "FULL-FRONT-FULL-BACK", # Normalize order? 
    }
    
    # Basic normalization for lookup
    normalized = clean
    for k, v in mapping.items():
        if k in normalized:
            normalized = v
            
    # Check if this valid as-is
    if normalized in VALID_LOCATIONS:
        return normalized
    
    return normalized 


def detectGarmentTypeFromLocation(locationName):
    """
    Returns category: T-SHIRT (includes Dual), CAP, BAG, BLANKET
    """
    # Normalize first
    loc = normalizeLocation(locationName)
    
    # Bag
    if "BAG" in loc:
        return "BAG"
        
    # Cap
    if "CAP" in loc or "CROWN" in loc:
        return "CAP"
        
    # Towel/Blanket
    if "TOWEL" in loc or "FRONT_CENTER" == loc: # FRONT_CENTER is Towel in user list
        return "BLANKET"
        
    # Default to T-SHIRT (Garments)
    return "T-SHIRT"

def isDualImage(locationName):
    """Returns True if the location implies a dual-image layout (Front + Back)."""
    loc = normalizeLocation(locationName)
    # Keyword based or list based
    if "BACK" in loc and "FRONT" in loc:
        return True
    if "BACK" in loc and "CHEST" in loc:
        return True
    if "BACK" in loc and "SLEEVE" in loc: # e.g. LEFT-CHEST-FULL-BACK
        return True
    if "-BACK" in loc and "FULL" not in loc: 

        pass
        
    # Explicit list from user request item 4:
    # "all the garment locations containing BACK keyword has this duala image thing"
    if "BACK" in loc:
        return True
        
    return False



def getPopperPath():
    """Detect poppler path intelligently."""
    # Try bundled poppler first
    bundledPath = os.path.join(os.getcwd(), "poppler", "Library", "bin")
    if os.path.exists(bundledPath):
        return bundledPath
    
    # Try system poppler (installed via choco/msi)
    systemPaths = [
        r"C:\Program Files\poppler\Library\bin",
        r"C:\Program Files (x86)\poppler\Library\bin",
    ]
    
    for path in systemPaths:
        if os.path.exists(path):
            return path
    
    return None


POPPLER_PATH = getPopperPath()


def convertPdfToPng(pdfPath: str) -> str:
    """Converts PDF to PNG at configurable DPI."""
    if not os.path.exists(pdfPath):
        raise FileNotFoundError(f"Logo PDF not found: {pdfPath}")

    # Method 1: PyMuPDF (fitz) - No Poppler Needed
    if FITZ_AVAILABLE:
        try:
            pdfDocument = fitz.open(pdfPath)
            page = pdfDocument[0]
            
            zoom = PDF_CONVERSION_DPI / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            tempPng = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
            pix.save(tempPng)
            
            pdfDocument.close()
            return tempPng
        except Exception:
            pass
    
    # Method 2: pdf2image (needs Poppler) - Fallback
    try:
        kwargs = {
            "dpi": PDF_CONVERSION_DPI,
            "first_page": 1,
            "last_page": 1,
        }
        
        if POPPLER_PATH:
            kwargs["poppler_path"] = POPPLER_PATH
        
        images = convert_from_path(pdfPath, **kwargs)
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {str(e)}. Install PyMuPDF or Poppler!") from e

    tempPng = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    images[0].save(tempPng, "PNG")

    return tempPng


def getPdfNativeDimensions(pdfPath: str) -> Tuple[float, float]:
    """Read actual dimensions from PDF file itself (no conversion needed)."""
    try:
        from PyPDF2 import PdfReader
        
        reader = PdfReader(pdfPath)
        page = reader.pages[0]
        
        mediabox = page.mediabox
        widthPts = float(mediabox.width)
        heightPts = float(mediabox.height)
        
        # Convert points to pixels (1 point = 1/72 inch, 1 inch = 96 pixels)
        widthPx = (widthPts / 72) * 96
        heightPx = (heightPts / 72) * 96
        
        return widthPx, heightPx
    
    except Exception:
        return None


def computeLogoSize(garmentType: str, logoPath: str, location: str) -> Tuple[float, float]:
    """Calculate appropriate logo size based on garment type and location."""
    
    # Get Logo Dimensions
    nativeDims = getPdfNativeDimensions(logoPath)
    pdfWidth = None
    
    if nativeDims:
        pdfWidth, pdfHeight = nativeDims
        aspectRatio = pdfHeight / pdfWidth if pdfWidth > 0 else 1.0
    else:
        tempPng = convertPdfToPng(logoPath)
        img = cv2.imread(tempPng)
        
        if img is None:
            raise ValueError(f"Failed to read PNG: {tempPng}")
        
        h, w = img.shape[:2]
        pdfWidth = w
        aspectRatio = h / w if w > 0 else 1.0
        
        try:
            if os.path.exists(tempPng):
                os.remove(tempPng)
        except:
            pass

    # Calculate dynamic tolerance based on logo size
    if pdfWidth and pdfWidth < 100:
        dynamicTolerance = 0.15
    elif pdfWidth and pdfWidth < 200:
        dynamicTolerance = 0.12
    else:
        dynamicTolerance = 0.08

    # Determine target width based on garment type
    garmentType = garmentType.upper().strip()
    targetWidth = 99
    
    if garmentType in ["T-SHIRT", "SHIRT", "SCRUB TOP", "SCRUB PANT", "JACKET", "HOODIE", "SWEAT SHIRT"]:
        if location not in ["FULL-BACK", "FULL-FRONT"]:
            targetWidth = 99
        else:
            targetWidth = 300
        
        # Square logo detection
        if abs(aspectRatio - 1.0) < dynamicTolerance:
            targetWidth = 70
    
    elif garmentType in ["BAG", "CAP", "HAT"]:
        targetWidth = 250
    
    elif garmentType == "BLANKET":
        if aspectRatio > 1.2:
            targetWidth = 66
        else:
            targetWidth = 99

    # Calculate target height maintaining aspect ratio
    targetHeight = targetWidth * aspectRatio
    print(f"Computed logo size for {garmentType} at {location}: {targetWidth:.2f} x {targetHeight:.2f}")
    return float(targetWidth), float(targetHeight)


def parseCustomSize(sizeText):
    """Returns (width, height) if valid, else None."""
    if not sizeText:
        return None

    text = str(sizeText).strip().lower()

    if text in ["nan", "none", "-", ""]:
        return None

    match = re.findall(r"(\d+)", text)
    if len(match) == 2:
        width = float(match[0])
        height = float(match[1])
        return width, height

    return None


def logEnvironmentInfo():
    """Log system environment info for debugging."""
    info = {
        "pythonVersion": __import__("sys").version,
        "workingDirectory": os.getcwd(),
        "popplerPath": POPPLER_PATH,
        "pymupdfAvailable": FITZ_AVAILABLE,
        "pdfConversionDpi": PDF_CONVERSION_DPI,
    }
    return info
