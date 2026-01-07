import os
from datetime import datetime

# Base folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "assets", "logs")
OUTPUT_DIR = os.path.join(BASE_DIR, "assets", "output")
IMAGE_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "For Printing")
PSD_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "photoshop")

# PSD size presets
PSD_SIZES = {
    "shirt": (1200, 1800),
    "cap_bag": (1200, 1200)
}

# Mandatory Excel columns
MANDATORY_COLUMNS = [
    "Product ID", "Supplier Part ID", "Supplier Color", "Decoration Code",
    "Decoration Color", "Decoration Location", "Final Image Name",
    "Supplier Name"
]

# ============================================================
#  LOGO PROCESSING CONFIGURATION (TUNABLE FOR CLIENT SYSTEMS)
# ============================================================

# PDF to PNG conversion DPI
# Higher DPI = Better quality but slower + larger files
# Range: 150-300 (Default: 300)
PDF_CONVERSION_DPI = 300

# PNG normalization height for aspect ratio calculation
# This is used to standardize aspect ratio calculation across systems
# NOTE: Now mostly bypassed - native PDF dimensions used when available
# Range: 1000-2500 (Default: 2000)
# Used only as fallback if PyPDF2 fails
PNG_NORMALIZE_HEIGHT = 2000

# Aspect ratio tolerance for square logo detection
# ⚠️ NOW DYNAMIC - Value calculated based on actual logo dimensions!
# This is kept as reference but code now calculates dynamically:
#   - Small logos (< 100px): tolerance = 0.15
#   - Medium logos (100-200px): tolerance = 0.12
#   - Large logos (> 200px): tolerance = 0.08
# Range: 0.05-0.2 (Default: 0.1 - rarely used now)
ASPECT_RATIO_TOLERANCE = 0.1

# Timestamped log file
def get_log_file():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(LOGS_DIR, f"log_{ts}.txt")
