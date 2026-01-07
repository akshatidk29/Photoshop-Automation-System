from pdf2image import convert_from_path
import win32com.client
import os
from coordinate_detector import get_rotation_angle
from logger import log_error
import cv2
import numpy as np
import tempfile
from coordinate_detector import get_arm_rotation_angle
from utils import compute_logo_size, parse_custom_size
from PIL import Image

def rotate_logo(logo_path, angle):
    # --- Handle PDF logos (convert first page to image)
    if logo_path.lower().endswith(".pdf"):
        images = convert_from_path(logo_path, first_page=1, last_page=1)
        pil_image = images[0].convert("RGBA")  # keep transparency
        temp_path = os.path.join(tempfile.gettempdir(), f"converted_{os.path.basename(logo_path)}.png")
        pil_image.save(temp_path, "PNG", dpi=(72, 72))
        logo_path = temp_path

    # --- Read logo image with alpha channel
    image = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Logo image not found or unreadable: {logo_path}")

    # --- If image has no alpha channel, add one
    if image.shape[2] == 3:
        b, g, r = cv2.split(image)
        alpha = np.ones(b.shape, dtype=b.dtype) * 255
        image = cv2.merge((b, g, r, alpha))

    h, w = image.shape[:2]
    center = (w // 2, h // 2)

    # --- Rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # --- Compute new bounds so logo isn’t clipped
    cos_val = np.abs(M[0, 0])
    sin_val = np.abs(M[0, 1])
    new_w = int(h * sin_val + w * cos_val)
    new_h = int(h * cos_val + w * sin_val)

    # --- Adjust rotation matrix to new center
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]

    # --- Rotate with transparency
    rotated = cv2.warpAffine(image, M, (new_w, new_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # --- Save as transparent PNG
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    cv2.imwrite(temp_file.name, rotated)

    return temp_file.name

def place_logo_in_photoshop(image_path, logo_path, location_name, coordinates, psd_name, output_folder, garment_type,custom_logo_size,decoration_code,target_name):
    try:
        app = win32com.client.Dispatch("Photoshop.Application")
        app.Visible =True # False
        location = str(location_name).strip().upper().replace(" ","-")
        canvas_size = 1800 if garment_type == "T-SHIRT" else 1200
        # Open the main image
        doc = app.Open(image_path)
        doc.ResizeCanvas(1200, canvas_size)  # You can make this dynamic later
        
        # Set resolution to 150 DPI at the very start
        try:
            doc.ResizeImage(doc.Width, doc.Height, 150)
            try:
                # ensure metadata/property reflects the desired resolution
                setattr(doc, 'Resolution', 150)
            except Exception:
                pass
        except Exception as e:
            log_error(f"Failed to set initial resolution to 150 for {psd_name}: {e}")
        
        # === RENAME THE IMAGE LAYER HERE ===
        image_layer = doc.ArtLayers[0]
        image_layer.Name = target_name
        # ===================================
        # Get rotation angle and rotate logo if needed
        # angle = get_arm_rotation_angle(image_path, location_name)
        # if angle != 0:
        #     logo_path = rotate_logo(logo_path, angle)

        # Import logo
        logo_doc = app.Open(logo_path)
        logo_layer = logo_doc.ArtLayers[0]
        logo_doc.Selection.SelectAll()
        logo_doc.Selection.Copy()
        logo_doc.Close(2)  # SaveChanges = 2 means don't save

        # Paste logo into main document
        doc.Paste()
        pasted_layer = doc.ArtLayers[0]
        pasted_layer.Name = decoration_code

        # Set ruler units to pixels (1 = psPixels)
        original_ruler_units = app.Preferences.RulerUnits
        app.Preferences.RulerUnits = 1  # Pixels

        # Get current bounds (list: [left, top, right, bottom] in pixels)
        bounds = pasted_layer.Bounds
        logo_width = bounds[2] - bounds[0]
        logo_height = bounds[3] - bounds[1]
        # print(f"Bounds: {bounds}, Logo Width: {logo_width}, Logo Height: {logo_height}")

        custom_size = parse_custom_size(custom_logo_size)
        print("custom_size++++++++++++",custom_size)
        if custom_size:
            # desired_width, desired_height = compute_logo_size(garment_type, logo_path,location)
            # print("BACKEND SIZE:-----------", desired_width, desired_height)
            desired_width, desired_height = custom_size
            print("Using custom size:--------------", desired_width, desired_height)
        else:
            # Get desired size from compute_logo_size
            desired_width, desired_height = compute_logo_size(garment_type, logo_path,location)
            print("BACKEND SIZE:-----------", desired_width, desired_height)
        # Calculate scale percentages (avoid division by zero)
        if logo_width == 0 or logo_height == 0:
            log_error(f"Invalid logo dimensions for {psd_name}: width={logo_width}, height={logo_height}")
            return None

        # For proportional scaling (recommended for logos), use width-based scale
        scale = (desired_width / logo_width) * 100
        # For non-proportional, uncomment below and comment the proportional line
        # width_scale = (desired_width / logo_width) * 100
        # height_scale = (desired_height / logo_height) * 100

        # Resize the pasted layer (use proportional scaling; AnchorPosition.MiddleCenter = 5)
        pasted_layer.Resize(scale, scale, 5)  # 5 = psMiddleCenter
        # For non-proportional: pasted_layer.Resize(width_scale, height_scale, 5)

        # Recalculate bounds after resizing
        bounds = pasted_layer.Bounds
        new_width = bounds[2] - bounds[0]
        new_height = bounds[3] - bounds[1]
        # print(f"New Width: {new_width}, New Height: {new_height}")

        # Calculate translation to place logo center at coordinates
        x, y = coordinates
        offset_x = x - (bounds[0] + new_width / 2)
        offset_y = y - (bounds[1] + new_height / 2)
        # print(f"Offset X: {offset_x}, Offset Y: {offset_y}")
        pasted_layer.Translate(offset_x, offset_y)

        # Restore original ruler units
        app.Preferences.RulerUnits = original_ruler_units

         # --- Resample image down to 150 PPI so pixel dimensions reduce (reduces file size)
        try:
            target_res = 150
            # Ensure ruler units are pixels while reading Width/Height
            orig_units_for_read = app.Preferences.RulerUnits
            app.Preferences.RulerUnits = 1  # pixels

            # Try to read current resolution; fallback to 300 if unavailable
            try:
                current_res = float(getattr(doc, "Resolution", 300))
            except Exception:
                current_res = 300.0

            if current_res <= 0:
                current_res = 300.0

            scale = float(target_res) / current_res
            if abs(scale - 1.0) > 1e-6:
                try:
                    new_w = int(float(doc.Width) * scale)
                    new_h = int(float(doc.Height) * scale)
                except Exception:
                    # fallback: keep same pixel dims (rare)
                    new_w, new_h = doc.Width, doc.Height

                print(f"Resampling: {int(doc.Width)}x{int(doc.Height)} @ {current_res} -> {new_w}x{new_h} @ {target_res}")
                # This call WILL resample pixels and set new resolution
                doc.ResizeImage(new_w, new_h, target_res)
            else:
                # If same resolution, just ensure metadata updated
                doc.ResizeImage(doc.Width, doc.Height, target_res)

            # restore ruler units used for reading
            app.Preferences.RulerUnits = orig_units_for_read
 
        except Exception as e:
            print("ERROR RESAMPLING:", str(e))
            log_error(f"Failed to resample/set resolution for {psd_name}: {e}")
        # Save PSD
        psd_path = os.path.join(output_folder, f"{psd_name}.psd")
        options = win32com.client.Dispatch("Photoshop.PhotoshopSaveOptions")
        doc.SaveAs(psd_path, options, True)

        return doc  # Return doc for further export

    except Exception as e:
        log_error(f"Photoshop error for {psd_name}: {e}")
        return None


def prepare_pair_doc(image_path, logo_path, location_name, coordinates, garment_type, custom_logo_size, decoration_code, target_name):
    """Create a temporary Photoshop document with the image and placed logo.
    Returns the Photoshop Document COM object (not saved). This mirrors
    the placement/resize logic from `place_logo_in_photoshop` but avoids
    resampling and saving so callers (batch manager) can duplicate layers.
    """
    try:
        app = win32com.client.Dispatch("Photoshop.Application")
        app.Visible = True
        location = str(location_name).strip().upper().replace(" ", "-")
        canvas_size = 1800 if garment_type == "T-SHIRT" else 1200

        # Open main image and ensure canvas size
        doc = app.Open(image_path)
        
        # Set resolution to 150 DPI at the very start
        try:
            doc.ResizeImage(doc.Width, doc.Height, 150)
            try:
                setattr(doc, 'Resolution', 150)
            except Exception:
                pass
        except Exception as e:
            log_error(f"Failed to set initial resolution to 150 for temp doc {target_name}: {e}")
        
        try:
            doc.ResizeCanvas(1200, canvas_size)
        except Exception:
            # If ResizeCanvas fails for some reason, continue with original size
            pass

        # Rename base image layer
        try:
            image_layer = doc.ArtLayers[0]
            image_layer.Name = target_name
        except Exception:
            # If no art layers found, ignore naming
            pass

        # Open logo (PDFs are handled earlier in rotate_logo if caller used it)
        logo_doc = app.Open(logo_path)
        logo_doc.Selection.SelectAll()
        logo_doc.Selection.Copy()
        logo_doc.Close(2)

        # Paste logo into main document
        doc.Paste()
        pasted_layer = doc.ArtLayers[0]
        try:
            pasted_layer.Name = decoration_code
        except Exception:
            pass

        # Set ruler units to pixels while we compute sizes/transforms
        original_ruler_units = app.Preferences.RulerUnits
        app.Preferences.RulerUnits = 1  # pixels

        # Measure current pasted bounds
        bounds = pasted_layer.Bounds
        logo_width = bounds[2] - bounds[0]
        logo_height = bounds[3] - bounds[1]

        # Resolve desired size: prefer explicit custom size, else compute from logo
        desired_width = None
        desired_height = None
        desired_width, desired_height = custom_logo_size

        # Avoid divide-by-zero
        if logo_width == 0 or logo_height == 0:
            log_error(f"Invalid logo dimensions for temp doc {target_name}: w={logo_width}, h={logo_height}")
        else:
            # scale = (desired_width / logo_width) * 100
            scale_w = (desired_width / logo_width) * 100
            scale_h = (desired_height / logo_height) * 100
            scale = min(scale_w, scale_h)
            pasted_layer.Resize(scale, scale, 5)  # MiddleCenter anchor

            # Recompute bounds and translate to target coordinates
            bounds = pasted_layer.Bounds
            new_width = bounds[2] - bounds[0]
            new_height = bounds[3] - bounds[1]
            x, y = coordinates
            offset_x = x - (bounds[0] + new_width / 2)
            offset_y = y - (bounds[1] + new_height / 2)
            try:
                pasted_layer.Translate(offset_x, offset_y)
            except Exception:
                # Older Photoshop COM variations may expect ints
                pasted_layer.Translate(int(offset_x), int(offset_y))

        # Restore ruler units
        app.Preferences.RulerUnits = original_ruler_units

        # Return the document for the caller to duplicate layers from
        return doc

    except Exception as e:
        # Log full context to help debugging when prepare_pair_doc fails
        try:
            ctx = {
                'target_name': target_name,
                'image_path': image_path,
                'logo_path': logo_path,
                'location_name': location,
                'coordinates': coordinates,
                'garment_type': garment_type,
                'custom_logo_size': custom_logo_size,
                'decoration_code': decoration_code,
                'image_exists': os.path.exists(image_path) if image_path else False,
                'logo_exists': os.path.exists(logo_path) if logo_path else False,
            }
        except Exception:
            ctx = {'info': 'failed to build context'}

        log_error(f"prepare_pair_doc error for {target_name}: {e} | context: {ctx}")
        return None