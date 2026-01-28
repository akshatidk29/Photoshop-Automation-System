from pdf2image import convert_from_path
import win32com.client
import os

from services.logger import logError
import cv2
import numpy as np
import tempfile
from core.utils import computeLogoSize, parseCustomSize
from PIL import Image


# Global Photoshop app instance for faster COM calls
_psApp = None


def _getPhotoshopApp():
    """Get or create singleton Photoshop app instance."""
    global _psApp
    if _psApp is None:
        _psApp = win32com.client.Dispatch("Photoshop.Application")
        _psApp.Visible = True
    return _psApp


def rotateLogo(logoPath, angle, target_size=None):
    """Rotate logo image by specified angle, handling PDFs."""
    from pathlib import Path
    
    # Handle PDF logos (convert first page to image)
    if logoPath.lower().endswith(".pdf"):
        # Try PyMuPDF (fitz) first - faster and more reliable
        try:
            import fitz
            doc_pdf = fitz.open(logoPath)
            page = doc_pdf[0]
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=True)
            
            temp_path = os.path.join(tempfile.gettempdir(), f"converted_{os.path.basename(logoPath)}.png")
            pix.save(temp_path)
            logoPath = temp_path
            doc_pdf.close()
        except Exception:
            # Fallback to pdf2image
            poppler_path = Path(__file__).parent / "poppler" / "Library" / "bin"
            if poppler_path.exists():
                images = convert_from_path(logoPath, first_page=1, last_page=1, poppler_path=str(poppler_path))
            else:
                images = convert_from_path(logoPath, first_page=1, last_page=1)
            pil_image = images[0].convert("RGBA")
            temp_path = os.path.join(tempfile.gettempdir(), f"converted_{os.path.basename(logoPath)}.png")
            pil_image.save(temp_path, "PNG", dpi=(72, 72))
            logoPath = temp_path

    # Read logo image with alpha channel
    image = cv2.imread(logoPath, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Logo image not found or unreadable: {logoPath}")

    # Ensure we have BGRA
    if len(image.shape) == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    
    # Background removal using flood fill
    h, w = image.shape[:2]
    fn_bgr = image[:, :, :3].copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    
    corners = [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)]
    corners_are_white = False
    
    for cx, cy in corners:
        pixel = fn_bgr[cy, cx]
        if np.all(pixel > 240):
            corners_are_white = True
            break
            
    if corners_are_white:
        flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY
        
        for cx, cy in corners:
            pixel = fn_bgr[cy, cx]
            if np.all(pixel > 240):
                cv2.floodFill(fn_bgr, mask, (cx, cy), (0,0,0), (5,5,5), (5,5,5), flags)
                
        mask_cropped = mask[1:h+1, 1:w+1]
        b, g, r, a = cv2.split(image)
        new_alpha = np.where(mask_cropped == 255, 0, a).astype(np.uint8)
        
        non_zero_pixels = cv2.countNonZero(new_alpha)
        total_pixels = new_alpha.size
        
        if non_zero_pixels < (total_pixels * 0.01):
             print(f"Warning: Background removal wiped the logo. Keeping original.")
        else:
             a = new_alpha
        
        image = cv2.merge([b, g, r, a])

    # Resize BEFORE Rotation (if requested)
    if target_size is not None:
         h, w = image.shape[:2]
         if h > 0 and w > 0:
             scale = target_size / max(h, w)
             new_w = max(1, int(w * scale))
             new_h = max(1, int(h * scale))
             image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Rotation Logic
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos_val = np.abs(M[0, 0])
    sin_val = np.abs(M[0, 1])
    new_w = int(h * sin_val + w * cos_val)
    new_h = int(h * cos_val + w * sin_val)
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]
    rotated = cv2.warpAffine(image, M, (new_w, new_h), flags=cv2.INTER_LINEAR, 
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    cv2.imwrite(temp_file.name, rotated)

    return temp_file.name


def preparePairDoc(imagePath, logoPath, locationName, coordinates, rotation,
                   garmentType, customLogoSize, decorationCode, targetName, canvasHeight=1200,
                   clippingEnabled=False, clippingPositions=None):
    """
    Create temporary Photoshop document with image and placed logo.
    
    Args:
        clippingEnabled: Global clipping toggle from GUI
        clippingPositions: Dict of position -> bool for per-position clipping
    """
    try:
        app = _getPhotoshopApp()
        location = str(locationName).strip().upper().replace(" ", "-")

        # Determine if we should clip based on GUI settings
        should_clip = False
        if clippingEnabled and clippingPositions:
            # Check if this specific position has clipping enabled
            for pos, enabled in clippingPositions.items():
                posNorm = pos.upper().replace(" ", "-").replace("_", "-")
                if enabled and posNorm in location:
                    should_clip = True
                    break
        
        logo_was_clipped = False
        actualLogoPath = logoPath
        
        # Get the target logo size from customLogoSize (passed from GUI settings)
        if isinstance(customLogoSize, tuple) and len(customLogoSize) >= 2:
            targetLogoWidth = customLogoSize[0]
        elif isinstance(customLogoSize, (int, float)):
            targetLogoWidth = customLogoSize
        else:
            # Fallback to 99
            targetLogoWidth = 99
        
        # User-friendly status
        clipStatus = "ON" if should_clip else "OFF"
        print(f"    ► Placing logo at {location} (Size: {targetLogoWidth}px, Clipping: {clipStatus})")

        if should_clip:
            # Resize BEFORE rotation/clipping
            try:
                rot_angle = rotation if rotation else 0
                actualLogoPath = rotateLogo(logoPath, rot_angle, target_size=targetLogoWidth)
                if rot_angle != 0:
                    print(f"      • Logo rotated {rot_angle:.1f}° to match garment angle")
                logo_was_clipped = True
            except Exception as e:
                print(f"      ⚠ Warning: Logo rotation failed, using original")
                
        elif rotation:
            try:
                actualLogoPath = rotateLogo(logoPath, rotation)
                print(f"      • Logo rotated {rotation:.1f}° to match garment angle")
            except Exception as e:
                print(f"      ⚠ Warning: Logo rotation failed, using original")
                actualLogoPath = logoPath
        
        if should_clip and coordinates:
            try:
                from core.logoClipper import clipLogoToGarment
                clipped = clipLogoToGarment(
                    actualLogoPath, imagePath,
                    coordinates[0], coordinates[1],
                    target_size=None
                )
                if clipped and clipped != actualLogoPath:
                    actualLogoPath = clipped
                    logo_was_clipped = True
                    print(f"      • Logo clipped to fit within garment")
            except Exception as e:
                print(f"      ⚠ Warning: Clipping failed, logo may extend beyond garment")

        # Open main image and ensure canvas size
        doc = app.Open(imagePath)
        
        try:
            doc.ResizeImage(doc.Width, doc.Height, 150)
        except Exception as e:
            logError(f"Failed to set resolution: {e}")
        
        try:
            doc.ResizeCanvas(1200, canvasHeight)
        except Exception:
            pass

        try:
            imageLayer = doc.ArtLayers[0]
            imageLayer.Name = targetName
        except Exception:
            pass

        # Open logo
        logoDoc = app.Open(actualLogoPath)
        logoDoc.Selection.SelectAll()
        logoDoc.Selection.Copy()
        logoDoc.Close(2)

        # Paste logo
        doc.Paste()
        pastedLayer = doc.ArtLayers[0]
        try:
            pastedLayer.Name = decorationCode
        except Exception:
            pass

        # Set ruler units to pixels
        originalRulerUnits = app.Preferences.RulerUnits
        app.Preferences.RulerUnits = 1

        # Measure bounds
        bounds = pastedLayer.Bounds
        logoWidth = bounds[2] - bounds[0]
        logoHeight = bounds[3] - bounds[1]

        if logoWidth == 0 or logoHeight == 0:
            logError(f"Invalid logo dimensions: w={logoWidth}, h={logoHeight}")
        else:
            # Only resize if logo wasn't already sized during clipping prep
            if not logo_was_clipped:
                # Use the targetLogoWidth from GUI settings
                desiredWidth = targetLogoWidth
                desiredHeight = targetLogoWidth  # Square for aspect ratio calc
                
                scaleW = (desiredWidth / logoWidth) * 100
                scaleH = (desiredHeight / logoHeight) * 100
                scale = min(scaleW, scaleH)
                pastedLayer.Resize(scale, scale, 5)
                print(f"    [LOGO] Resized in Photoshop to {desiredWidth}px")

            # Recompute bounds after resize
            bounds = pastedLayer.Bounds
            newWidth = bounds[2] - bounds[0]
            newHeight = bounds[3] - bounds[1]
            x, y = coordinates
            
            # Center logo at coordinates
            offsetX = x - (bounds[0] + newWidth / 2)
            offsetY = y - (bounds[1] + newHeight / 2)
            
            try:
                pastedLayer.Translate(offsetX, offsetY)
            except Exception:
                pastedLayer.Translate(int(offsetX), int(offsetY))

        app.Preferences.RulerUnits = originalRulerUnits
        return doc

    except Exception as e:
        logError(f"preparePairDoc error for {targetName}: {e}")
        return None


def prepareComboPairDoc(imagePath, logoPath, positionsList, coordinatesList, rotationsList,
                         garmentType, customLogoSizes, decorationCode, targetName, canvasHeight=1200,
                         clippingEnabled=False, clippingPositions=None):
    """
    Create Photoshop document with image and MULTIPLE logos placed at different positions.
    
    Args:
        customLogoSizes: Can be a list of sizes (one per position) or a single size value
    """
    try:
        app = _getPhotoshopApp()

        doc = app.Open(imagePath)
        
        try:
            doc.ResizeImage(doc.Width, doc.Height, 150)
        except Exception:
            pass
        
        try:
            doc.ResizeCanvas(1200, canvasHeight)
        except Exception:
            pass

        try:
            imageLayer = doc.ArtLayers[0]
            imageLayer.Name = targetName
        except Exception:
            pass

        originalRulerUnits = app.Preferences.RulerUnits
        app.Preferences.RulerUnits = 1
        
        # Handle customLogoSizes - can be list or single value
        sizesList = []
        if isinstance(customLogoSizes, list):
            sizesList = customLogoSizes
        elif isinstance(customLogoSizes, tuple) and len(customLogoSizes) >= 2:
            sizesList = [customLogoSizes[0]] * len(positionsList)
        elif isinstance(customLogoSizes, (int, float)):
            sizesList = [customLogoSizes] * len(positionsList)
        else:
            sizesList = [99] * len(positionsList)

        # Place logo at EACH position
        for idx, (position, coordinates) in enumerate(zip(positionsList, coordinatesList)):
            if coordinates is None:
                print(f"    [WARN] Skipping position {position} - no coordinates")
                continue

            rotation = rotationsList[idx] if idx < len(rotationsList) else 0.0
            pos_upper = str(position).upper().replace(" ", "-")
            
            # Get size for THIS position
            targetLogoWidth = sizesList[idx] if idx < len(sizesList) else 99
            
            # Determine if we should clip based on GUI settings
            should_clip = False
            if clippingEnabled and clippingPositions:
                for pos, enabled in clippingPositions.items():
                    posNorm = pos.upper().replace(" ", "-").replace("_", "-")
                    if enabled and posNorm in pos_upper:
                        should_clip = True
                        break
            
            logo_was_clipped = False
            actualLogoPath = logoPath

            if should_clip:
                try:
                    rot_angle = rotation if rotation else 0
                    actualLogoPath = rotateLogo(logoPath, rot_angle, target_size=targetLogoWidth)
                    print(f"    [LOGO] Resized to {targetLogoWidth}px & Rotated {rot_angle:.1f}° for {position}")
                    logo_was_clipped = True
                except Exception as e:
                     print(f"    [WARN] Failed to prepare logo: {e}")
            elif rotation:
                try:
                    actualLogoPath = rotateLogo(logoPath, rotation)
                    print(f"    [LOGO] Rotated by {rotation:.1f}° for {position}")
                except Exception as e:
                    print(f"    [WARN] Failed to rotate logo: {e}")
                    actualLogoPath = logoPath
            
            if should_clip:
                try:
                    from core.logoClipper import clipLogoToGarment
                    clipped = clipLogoToGarment(
                        actualLogoPath, imagePath,
                        coordinates[0], coordinates[1],
                        target_size=None
                    )
                    if clipped and clipped != actualLogoPath:
                        actualLogoPath = clipped
                        logo_was_clipped = True
                        print(f"    [LOGO] Clipped to garment silhouette")
                except Exception:
                    pass
            
            # Open and copy the logo
            logoDoc = app.Open(actualLogoPath)
            logoDoc.Selection.SelectAll()
            logoDoc.Selection.Copy()
            logoDoc.Close(2)

            doc.Paste()
            pastedLayer = doc.ArtLayers[0]
            try:
                pastedLayer.Name = f"{decorationCode}_{position}"
            except Exception:
                pass

            bounds = pastedLayer.Bounds
            logoWidth = bounds[2] - bounds[0]
            logoHeight = bounds[3] - bounds[1]

            if logoWidth == 0 or logoHeight == 0:
                continue

            if not logo_was_clipped:
                desiredWidth = targetLogoWidth
                scaleW = (desiredWidth / logoWidth) * 100
                scaleH = (desiredWidth / logoHeight) * 100
                scale = min(scaleW, scaleH)
                pastedLayer.Resize(scale, scale, 5)

            bounds = pastedLayer.Bounds
            newWidth = bounds[2] - bounds[0]
            newHeight = bounds[3] - bounds[1]
            x, y = coordinates
            
            offsetX = x - (bounds[0] + newWidth / 2)
            offsetY = y - (bounds[1] + newHeight / 2)
            
            try:
                pastedLayer.Translate(offsetX, offsetY)
            except Exception:
                pastedLayer.Translate(int(offsetX), int(offsetY))

            print(f"    [LOGO] Placed at {position}: ({x}, {y})")

        app.Preferences.RulerUnits = originalRulerUnits
        return doc

    except Exception as e:
        logError(f"prepareComboPairDoc error for {targetName}: {e}")
        return None


def placeLogoInPhotoshop(imagePath, logoPath, locationName, coordinates, psdName, 
                          outputFolder, garmentType, customLogoSize, decorationCode, targetName):
    """Place logo on image in Photoshop with proper sizing and positioning."""
    try:
        app = win32com.client.Dispatch("Photoshop.Application")
        app.Visible = True
        location = str(locationName).strip().upper().replace(" ", "-")
        canvasSize = 1800 if garmentType == "T-SHIRT" else 1200
        
        doc = app.Open(imagePath)
        doc.ResizeCanvas(1200, canvasSize)
        
        try:
            doc.ResizeImage(doc.Width, doc.Height, 150)
        except Exception as e:
            logError(f"Failed to set resolution for {psdName}: {e}")
        
        imageLayer = doc.ArtLayers[0]
        imageLayer.Name = targetName

        logoDoc = app.Open(logoPath)
        logoLayer = logoDoc.ArtLayers[0]
        logoDoc.Selection.SelectAll()
        logoDoc.Selection.Copy()
        logoDoc.Close(2)

        doc.Paste()
        pastedLayer = doc.ArtLayers[0]
        pastedLayer.Name = decorationCode

        originalRulerUnits = app.Preferences.RulerUnits
        app.Preferences.RulerUnits = 1

        bounds = pastedLayer.Bounds
        logoWidth = bounds[2] - bounds[0]
        logoHeight = bounds[3] - bounds[1]

        customSize = parseCustomSize(customLogoSize)
        if customSize:
            desiredWidth, desiredHeight = customSize
        else:
            desiredWidth, desiredHeight = computeLogoSize(garmentType, logoPath, location)

        if logoWidth == 0 or logoHeight == 0:
            logError(f"Invalid logo dimensions for {psdName}")
            return None

        scale = (desiredWidth / logoWidth) * 100
        pastedLayer.Resize(scale, scale, 5)

        bounds = pastedLayer.Bounds
        newWidth = bounds[2] - bounds[0]
        newHeight = bounds[3] - bounds[1]

        x, y = coordinates
        offsetX = x - (bounds[0] + newWidth / 2)
        offsetY = y - (bounds[1] + newHeight / 2)
        pastedLayer.Translate(offsetX, offsetY)

        app.Preferences.RulerUnits = originalRulerUnits

        psdPath = os.path.join(outputFolder, f"{psdName}.psd")
        options = win32com.client.Dispatch("Photoshop.PhotoshopSaveOptions")
        doc.SaveAs(psdPath, options, True)

        return doc

    except Exception as e:
        logError(f"Photoshop error for {psdName}: {e}")
        return None
