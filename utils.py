import os
import re
import cv2
import shutil
import tempfile
from typing import Tuple
from config import PDF_CONVERSION_DPI, PNG_NORMALIZE_HEIGHT, ASPECT_RATIO_TOLERANCE

# Try importing PyMuPDF first (preferred - no Poppler needed)
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    from pdf2image import convert_from_path  # Fallback to pdf2image (needs Poppler)


# ============================================================
#  FOLDER + FILE HELPERS
# ============================================================

def ensure_folder(path):
    """Create folder if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def clean_filename(name):
    """Sanitize filename by removing illegal characters."""
    return "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).rstrip()


def copy_file(src, dest_folder, new_name=None):
    """Copy file with optional new name."""
    ensure_folder(dest_folder)
    dest_path = os.path.join(dest_folder, new_name if new_name else os.path.basename(src))
    shutil.copy2(src, dest_path)
    return dest_path


def get_combined_name(*parts):
    """Join parts into a clean filename."""
    return clean_filename("_".join(str(p).strip() for p in parts if p))


def get_psd_size_from_name(name):
    """Detect PSD size from filename."""
    if "1200 x 1800" in name or "shirt" in name.lower():
        return (1200, 1800)
    elif "1200 x 1200" in name or any(x in name.lower() for x in ["cap", "bag", "towel"]):
        return (1200, 1200)
    return (1200, 1800)  # default


# ============================================================
#  LOCATION → GARMENT TYPE MAPPER
# ============================================================

def detect_garment_type_from_location(location_name):
    """Returns garment type from location name."""

    location = str(location_name).strip().upper().replace(" ", "-")

    canvas_1800 = [
        "FULL-BACK", "FULL-FRONT", "LEFT-BICEP", "RIGHT-BICEP",
        "LEFT-CHEST", "RIGHT-CHEST", "LEFT-COLLAR", "RIGHT-COLLAR",
        "LEFT-CUFF", "RIGHT-CUFF", "LEFT-HIP", "RIGHT-HIP",
        "LEFT-SLEEVE", "RIGHT-SLEEVE", "LEFT-THIGH-HIGH", "RIGHT-THIGH-HIGH",
        "ON-POCKET", "BACK-YOKE",
        "FULL-BACK & FULL-FRONT",
        "LEFT-BICEP-RIGHT-BICEP",
        "LEFT-CHEST-LEFT-BICEP-RIGHT-BICEP",
        "LEFT-CHEST-RIGHT-BICEP",
        "LEFT-CHEST-RIGHT-SLEEVE",
        "LEFT-SLEEVE-RIGHT-SLEEVE",
        "RIGHT-CHEST-LEFT-BICEP",
        "RIGHT-CHEST-LEFT-SLEEVE",
        "RIGHT-CHEST-LFT-BICEP-RIGHT-BICEP",
        "FULL-FRONT-FULL-BACK",
        "LEFT-CHEST-FULL-BACK",
        "RIGHT-CHEST-FULL-BACK"
    ]

    canvas_1200 = [
        "FRONT-CROWN", "CAP-BACK", "CAP-SIDE", "CAP-FRONT-SIDE",
        "LOWER-LEFT-CROWN", "LOWER-RIGHT-CROWN",
        "CORNER-ANGLED-TOWEL", "FRONT_CENTER",
        "FRONT (ON BAG)", "ON POCKET (ON BAG)"
    ]

    if location in canvas_1800:
        return "T-SHIRT"

    elif location in canvas_1200:
        if "CAP" in location or "CROWN" in location:
            return "CAP"
        if "BAG" in location:
            return "BAG"
        if "TOWEL" in location:
            return "BLANKET"
        return "UNKNOWN"

    return "UNKNOWN"


# ============================================================
#  POPPLER PATH (SMART DETECTION)
# ============================================================

def get_poppler_path():
    """
    Detect poppler path intelligently:
    1. Check bundled poppler in project
    2. Check system PATH
    3. Return None if not found (graceful fallback)
    """
    # Try bundled poppler first
    bundled_path = os.path.join(os.getcwd(), "poppler", "Library", "bin")
    if os.path.exists(bundled_path):
        return bundled_path
    
    # Try system poppler (installed via choco/msi)
    system_paths = [
        r"C:\Program Files\poppler\Library\bin",
        r"C:\Program Files (x86)\poppler\Library\bin",
    ]
    
    for path in system_paths:
        if os.path.exists(path):
            return path
    
    # If not found anywhere, return None (pdf2image will use system PATH)
    return None

POPPLER_PATH = get_poppler_path()


# ============================================================
#  PDF → PNG CONVERSION (NO POPPLER NEEDED IF FITZ AVAILABLE)
# ============================================================

def convert_pdf_to_png(pdf_path: str) -> str:
    """
    Converts PDF → PNG @ configurable DPI.
    Preferred: Uses PyMuPDF (fitz) - NO Poppler needed!
    Fallback: pdf2image (requires Poppler)
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Logo PDF not found: {pdf_path}")

    # ===== METHOD 1: PyMuPDF (fitz) - NO Poppler Needed =====
    if FITZ_AVAILABLE:
        try:
            pdf_document = fitz.open(pdf_path)
            page = pdf_document[0]  # First page
            
            # Render at DPI (default 72, we want 300)
            zoom = PDF_CONVERSION_DPI / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            temp_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
            pix.save(temp_png)
            
            pdf_document.close()
            return temp_png
        except Exception as e:
            # Fallback to pdf2image if fitz fails
            pass
    
    # ===== METHOD 2: pdf2image (needs Poppler) - Fallback =====
    try:
        kwargs = {
            "dpi": PDF_CONVERSION_DPI,
            "first_page": 1,
            "last_page": 1,
        }
        
        # Add poppler_path only if it was found
        if POPPLER_PATH:
            kwargs["poppler_path"] = POPPLER_PATH
        
        images = convert_from_path(pdf_path, **kwargs)
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {str(e)}. Install PyMuPDF (pip install PyMuPDF) or Poppler!") from e

    temp_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    images[0].save(temp_png, "PNG")

    return temp_png


# ============================================================
#  PDF NATIVE DIMENSIONS (PyPDF2 - NO conversion needed)
# ============================================================

def get_pdf_native_dimensions(pdf_path: str) -> Tuple[float, float]:
    """
    Read ACTUAL dimensions from PDF file itself (not from conversion).
    Bypasses DPI/conversion issues entirely.
    Returns: (width, height) in pixels
    """
    try:
        from PyPDF2 import PdfReader
        
        reader = PdfReader(pdf_path)
        page = reader.pages[0]
        
        # Get MediaBox (actual page dimensions in points)
        mediabox = page.mediabox
        width_pts = float(mediabox.width)
        height_pts = float(mediabox.height)
        
        # Convert points to pixels (1 point = 1/72 inch, 1 inch = 96 pixels)
        width_px = (width_pts / 72) * 96
        height_px = (height_pts / 72) * 96
        
        return width_px, height_px
    
    except Exception as e:
        # Fallback to conversion method if PyPDF2 unavailable
        return None


# ============================================================
#  LOGO SIZE CALCULATION (MAIN LOGIC)
# ============================================================

def compute_logo_size(garment_type: str, logo_path: str, location: str) -> Tuple[float, float]:
    """
    FLOW - Aspect Ratio Explained:
    
    1. Read PDF logo dimensions: width = 100px, height = 120px
    2. Calculate aspect_ratio = height / width = 120 / 100 = 1.2
    3. Determine target_width based on garment (e.g., 200px)
    4. Calculate target_height = target_width * aspect_ratio
       target_height = 200 * 1.2 = 240px
    
    KEY FORMULA: target_height = target_width * aspect_ratio
    This ensures: if width increases by 50%, height also increases by 50%
    Ratio maintained: 200/240 = 100/120 ✓
    
    Returns: (target_width, target_height)
    """
    
    # ===== STEP 1: Get Logo Dimensions =====
    native_dims = get_pdf_native_dimensions(logo_path)
    pdf_width = None
    
    if native_dims:
        # ✅ Use native PDF dimensions (BEST - no conversion quality loss)
        pdf_width, pdf_height = native_dims
        aspect_ratio = pdf_height / pdf_width if pdf_width > 0 else 1.0
        
    else:
        # Fallback: Convert PDF to PNG and measure
        temp_png = convert_pdf_to_png(logo_path)
        img = cv2.imread(temp_png)
        
        if img is None:
            raise ValueError(f"Failed to read PNG: {temp_png}")
        
        h, w = img.shape[:2]
        pdf_width = w
        aspect_ratio = h / w if w > 0 else 1.0
        
        # Cleanup
        try:
            if os.path.exists(temp_png):
                os.remove(temp_png)
        except:
            pass

    # ===== STEP 2: Calculate Dynamic Tolerance =====
    if pdf_width and pdf_width < 100:
        dynamic_tolerance = 0.15
    elif pdf_width and pdf_width < 200:
        dynamic_tolerance = 0.12
    else:
        dynamic_tolerance = 0.08

    # ===== STEP 3: Determine Target Width =====
    garment_type = garment_type.upper().strip()
    target_width = 99  # Default
    
    if garment_type in ["T-SHIRT", "SHIRT", "SCRUB TOP", "SCRUB PANT", "JACKET", "HOODIE", "SWEAT SHIRT"]:
        if location not in ["FULL-BACK", "FULL-FRONT"]:
            target_width = 99
        else:
            target_width = 300
        
        # Square logo detection
        if abs(aspect_ratio - 1.0) < dynamic_tolerance:
            target_width = 70
    
    elif garment_type in ["BAG", "CAP", "HAT"]:
        target_width = 250
    
    elif garment_type == "BLANKET":
        if aspect_ratio > 1.2:
            target_width = 66
        else:
            target_width = 99

    # ===== STEP 4: Calculate Target Height (CRITICAL) =====
    # Formula: target_height = target_width * aspect_ratio
    # 
    # This is the KEY formula - it maintains proportional scaling
    # 
    # Example:
    # Original logo: 100 x 120 → aspect_ratio = 120/100 = 1.2
    # If target_width = 200:
    #   target_height = 200 * 1.2 = 240
    # Check: 200:240 = 100:120? YES! Ratio maintained ✓
    
    target_height = target_width * aspect_ratio
    print(f"Computed logo size for {garment_type} at {location}: {target_width:.2f} x {target_height:.2f} (Aspect Ratio: {aspect_ratio:.4f})")
    return float(target_width), float(target_height)


# ============================================================
#  CUSTOM SIZE PARSER
# ============================================================

def parse_custom_size(size_text):
    """Returns (width, height) if valid, else None."""
    if not size_text:
        return None

    text = str(size_text).strip().lower()

    if text in ["nan", "none", "-", ""]:
        return None

    match = re.findall(r"(\d+)", text)
    # print(f"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXParsing custom size from text: '{size_text}' → found matches: {match}")
    if len(match) == 2:
        width = float(match[0])
        height = float(match[1])
        # print(f"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXParsed custom size: {width} x {height}")
        return width, height

    return None


# ============================================================
#  DEBUG INFO FOR TROUBLESHOOTING
# ============================================================

def log_environment_info():
    """Log system environment info for debugging."""
    info = {
        "python_version": __import__("sys").version,
        "working_directory": os.getcwd(),
        "poppler_path": POPPLER_PATH,
        "pymupdf_available": FITZ_AVAILABLE,
        "pdf_conversion_dpi": PDF_CONVERSION_DPI,
    }
    return info