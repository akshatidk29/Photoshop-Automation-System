import os

# Base directory configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_ROOT = os.path.join(BASE_DIR, "Output")

# Required Excel columns for validation
MANDATORY_COLUMNS = [
    "Product ID", "Supplier Part ID", "Supplier Color", "Decoration Code",
    "Decoration Color", "Decoration Location", "Final Image Name",
    "Supplier Name"
]
