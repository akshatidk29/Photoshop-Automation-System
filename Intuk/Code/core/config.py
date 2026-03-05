import os

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(CODE_DIR)
OUTPUT_ROOT = os.path.join(BASE_DIR, "Output")
PROCESSED_IMG_DIR = os.path.join(BASE_DIR, "processedImg")
