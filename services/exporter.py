import os
import win32com.client
from .logger import logError
from core.config import IMAGE_OUTPUT_DIR


def exportJpg(doc, finalName):
    """Export document as JPG file."""
    try:
        jpgPath = os.path.join(IMAGE_OUTPUT_DIR, f"{finalName}.jpg")
        jpgOptions = win32com.client.Dispatch("Photoshop.JPEGSaveOptions")
        jpgOptions.Quality = 6
        doc.SaveAs(jpgPath, jpgOptions, True)
        doc.Close(2)
    except Exception as e:
        logError(f"JPG export failed for {finalName}: {e}")
