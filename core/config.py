import os
from datetime import datetime

# Base directory configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, "assets", "logs")
OUTPUT_ROOT = os.path.join(BASE_DIR, "Output")
OUTPUT_DIR = os.path.join(BASE_DIR, "assets", "output") # Kept for backward compatibility if needed, but mainly we use OUTPUT_ROOT now
IMAGE_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "For Printing")
PSD_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "photoshop")

# PSD canvas size presets based on garment type
PSD_SIZES = {
    "shirt": (1200, 1800),
    "capBag": (1200, 1200)
}

# Required Excel columns for validation
MANDATORY_COLUMNS = [
    "Product ID", "Supplier Part ID", "Supplier Color", "Decoration Code",
    "Decoration Color", "Decoration Location", "Final Image Name",
    "Supplier Name"
]

# PDF to PNG conversion DPI - Higher DPI means better quality but slower processing
PDF_CONVERSION_DPI = 300

# PNG normalization height for aspect ratio calculation (fallback if PyPDF2 fails)
PNG_NORMALIZE_HEIGHT = 2000

# Aspect ratio tolerance for square logo detection (kept as reference, now calculated dynamically)
ASPECT_RATIO_TOLERANCE = 0.1


def getLogFile():
    """Generate timestamped log file path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(LOGS_DIR, f"log_{timestamp}.txt")
