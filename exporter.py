import os
import win32com.client
from logger import log_error
from config import IMAGE_OUTPUT_DIR

def export_jpg(doc, final_name):
    try:
        jpg_path = os.path.join(IMAGE_OUTPUT_DIR, f"{final_name}.jpg")
        jpg_options = win32com.client.Dispatch("Photoshop.JPEGSaveOptions")
        jpg_options.Quality = 6
        doc.SaveAs(jpg_path, jpg_options, True)
        doc.Close(2)  # Don't save again
    except Exception as e:
        log_error(f"JPG export failed for {final_name}: {e}")
