from pdf2image import convert_from_path
import win32com.client
import os

from services.logger import logError
import cv2
import numpy as np
import tempfile
from core.utils import computeLogoSize, parseCustomSize
from PIL import Image


def rotateLogo(logoPath, angle):
    """Rotate logo image by specified angle, handling PDFs."""
    from pathlib import Path
    
    # Handle PDF logos (convert first page to image)
    if logoPath.lower().endswith(".pdf"):
        # Try PyMuPDF (fitz) first - faster and more reliable
        try:
            import fitz
            doc_pdf = fitz.open(logoPath)
            page = doc_pdf[0]
            # 72 DPI is default, we want 300 DPI ideally but keeping 72 for consistency
            # If previous used 72 DPI, let's stick to 150 for better quality
            zoom = 2.0 # 72 * 2 = 144 DPI approximately
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=True) # Request alpha!
            
            temp_path = os.path.join(tempfile.gettempdir(), f"converted_{os.path.basename(logoPath)}.png")
            pix.save(temp_path)
            logoPath = temp_path
            doc_pdf.close()
        except Exception:
            # Fallback to pdf2image
            # Use local poppler installation
            poppler_path = Path(__file__).parent / "poppler" / "Library" / "bin"
            if poppler_path.exists():
                images = convert_from_path(logoPath, first_page=1, last_page=1, poppler_path=str(poppler_path))
            else:
                images = convert_from_path(logoPath, first_page=1, last_page=1)
            pil_image = images[0].convert("RGBA")  # keep transparency
            temp_path = os.path.join(tempfile.gettempdir(), f"converted_{os.path.basename(logoPath)}.png")
            pil_image.save(temp_path, "PNG", dpi=(72, 72))
            logoPath = temp_path

    # Read logo image with alpha channel
    image = cv2.imread(logoPath, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Logo image not found or unreadable: {logoPath}")

    # Ensure we have BGRA
    if len(image.shape) == 2:
        # Grayscale -> BGRA
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif image.shape[2] == 3:
        # BGR -> BGRA
        image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    
    # --- Robust Background Removal (Flood Fill) ---
    # Attempt to remove white background if corners are white.
    # We use MASK_ONLY mode to avoid altering the image colors during fill,
    # ensuring we don't accidentally wipe out black/dark logo parts.
    
    h, w = image.shape[:2]
    # IMPORTANT: Create a CONTIGUOUS copy of the BGR channels for floodFill
    # OpenCV's floodFill requires a contiguous array (C-order)
    fn_bgr = image[:, :, :3].copy()
    
    # Mask for floodFill must be 2 pixels larger
    mask = np.zeros((h + 2, w + 2), np.uint8)
    
    corners = [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)]
    corners_are_white = False
    
    # Check if we should try removing background (if corners are light)
    for cx, cy in corners:
        pixel = fn_bgr[cy, cx]
        if np.all(pixel > 240): # > 240 in B, G, and R
            corners_are_white = True
            break
            
    if corners_are_white:
        # Flood fill from all white corners
        # fill value 255 in mask. 
        # flags = 4 (connectivity) | (255 << 8) (value to write in mask) | FLOODFILL_MASK_ONLY
        flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY
        
        for cx, cy in corners:
            pixel = fn_bgr[cy, cx]
            if np.all(pixel > 240):
                # Tolerance of 5 ( stricter) for near-white to avoid eating into light logos
                cv2.floodFill(fn_bgr, mask, (cx, cy), (0,0,0), (5,5,5), (5,5,5), flags)
                
        # Apply mask to alpha channel
        # Mask is (h+2, w+2), so crop to image size
        mask_cropped = mask[1:h+1, 1:w+1]
        
        # Get existing channels
        b, g, r, a = cv2.split(image)
        
        # Where mask is 255 (background), set alpha to 0. Else keep existing alpha.
        new_alpha = np.where(mask_cropped == 255, 0, a).astype(np.uint8)
        
        # SAFETY CHECK: If we made the image completely transparent (or nearly so),
        # it means the logo effectively disappeared (e.g. white logo on white bg).
        # In this case, revert to original alpha (keep background) to avoid "Empty selection" error.
        non_zero_pixels = cv2.countNonZero(new_alpha)
        total_pixels = new_alpha.size
        
        if non_zero_pixels < (total_pixels * 0.01): # Less than 1% visible
             print(f"Warning: Background removal wiped the logo (white on white?). Keeping original background for {os.path.basename(logoPath)}")
             # Don't update 'a', keep original
        else:
             a = new_alpha
        
        image = cv2.merge([b, g, r, a])

    # --- Rotation Logic ---
    center = (w // 2, h // 2)

    # Rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # Compute new bounds
    cos_val = np.abs(M[0, 0])
    sin_val = np.abs(M[0, 1])
    new_w = int(h * sin_val + w * cos_val)
    new_h = int(h * cos_val + w * sin_val)

    # Adjust rotation matrix
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]

    # Rotate with transparent border
    rotated = cv2.warpAffine(image, M, (new_w, new_h), flags=cv2.INTER_LINEAR, 
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # Save
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    cv2.imwrite(temp_file.name, rotated)

    return temp_file.name


def placeLogoInPhotoshop(imagePath, logoPath, locationName, coordinates, psdName, 
                          outputFolder, garmentType, customLogoSize, decorationCode, targetName):
    """Place logo on image in Photoshop with proper sizing and positioning."""
    try:
        app = win32com.client.Dispatch("Photoshop.Application")
        app.Visible = True
        location = str(locationName).strip().upper().replace(" ", "-")
        canvasSize = 1800 if garmentType == "T-SHIRT" else 1200
        
        # Open the main image
        doc = app.Open(imagePath)
        doc.ResizeCanvas(1200, canvasSize)
        
        # Set resolution to 150 DPI
        try:
            doc.ResizeImage(doc.Width, doc.Height, 150)
            try:
                setattr(doc, 'Resolution', 150)
            except Exception:
                pass
        except Exception as e:
            logError(f"Failed to set initial resolution to 150 for {psdName}: {e}")
        
        # Rename the image layer
        imageLayer = doc.ArtLayers[0]
        imageLayer.Name = targetName

        # Import logo
        logoDoc = app.Open(logoPath)
        logoLayer = logoDoc.ArtLayers[0]
        logoDoc.Selection.SelectAll()
        logoDoc.Selection.Copy()
        logoDoc.Close(2)

        # Paste logo into main document
        doc.Paste()
        pastedLayer = doc.ArtLayers[0]
        pastedLayer.Name = decorationCode

        # Set ruler units to pixels
        originalRulerUnits = app.Preferences.RulerUnits
        app.Preferences.RulerUnits = 1

        # Get current bounds
        bounds = pastedLayer.Bounds
        logoWidth = bounds[2] - bounds[0]
        logoHeight = bounds[3] - bounds[1]

        customSize = parseCustomSize(customLogoSize)
        print("customSize:", customSize)
        if customSize:
            desiredWidth, desiredHeight = customSize
            print("Using custom size:", desiredWidth, desiredHeight)
        else:
            desiredWidth, desiredHeight = computeLogoSize(garmentType, logoPath, location)
            print("Backend size:", desiredWidth, desiredHeight)

        if logoWidth == 0 or logoHeight == 0:
            logError(f"Invalid logo dimensions for {psdName}: width={logoWidth}, height={logoHeight}")
            return None

        # Calculate scale percentage
        scale = (desiredWidth / logoWidth) * 100
        pastedLayer.Resize(scale, scale, 5)

        # Recalculate bounds after resizing
        bounds = pastedLayer.Bounds
        newWidth = bounds[2] - bounds[0]
        newHeight = bounds[3] - bounds[1]

        # Calculate translation to place logo center at coordinates
        x, y = coordinates
        offsetX = x - (bounds[0] + newWidth / 2)
        offsetY = y - (bounds[1] + newHeight / 2)
        pastedLayer.Translate(offsetX, offsetY)

        # Restore original ruler units
        app.Preferences.RulerUnits = originalRulerUnits

        # Resample image to 150 PPI
        try:
            targetRes = 150
            origUnitsForRead = app.Preferences.RulerUnits
            app.Preferences.RulerUnits = 1

            try:
                currentRes = float(getattr(doc, "Resolution", 300))
            except Exception:
                currentRes = 300.0

            if currentRes <= 0:
                currentRes = 300.0

            scaleRes = float(targetRes) / currentRes
            if abs(scaleRes - 1.0) > 1e-6:
                try:
                    newW = int(float(doc.Width) * scaleRes)
                    newH = int(float(doc.Height) * scaleRes)
                except Exception:
                    newW, newH = doc.Width, doc.Height

                print(f"Resampling: {int(doc.Width)}x{int(doc.Height)} @ {currentRes} -> {newW}x{newH} @ {targetRes}")
                doc.ResizeImage(newW, newH, targetRes)
            else:
                doc.ResizeImage(doc.Width, doc.Height, targetRes)

            app.Preferences.RulerUnits = origUnitsForRead
 
        except Exception as e:
            print("Error resampling:", str(e))
            logError(f"Failed to resample/set resolution for {psdName}: {e}")

        # Save PSD
        psdPath = os.path.join(outputFolder, f"{psdName}.psd")
        options = win32com.client.Dispatch("Photoshop.PhotoshopSaveOptions")
        doc.SaveAs(psdPath, options, True)

        return doc

    except Exception as e:
        logError(f"Photoshop error for {psdName}: {e}")
        return None


def preparePairDoc(imagePath, logoPath, locationName, coordinates, rotation,
                   garmentType, customLogoSize, decorationCode, targetName, canvasHeight=1200):
    """Create temporary Photoshop document with image and placed logo."""
    try:
        app = win32com.client.Dispatch("Photoshop.Application")
        app.Visible = True
        location = str(locationName).strip().upper().replace(" ", "-")

        # For T-SHIRT garments, use clipped logos for clean placement
        actualLogoPath = logoPath
        useClippedLogo = False
        clippedLogoOffset = (0, 0)
        
        if garmentType == "T-SHIRT":
            try:
                # Import clipping functions
                from detectors.garmentDetector import createClippedLogo, parseClippedLogoOffset
                
                # Create clipped logo masked to garment silhouette
                clippedPath = createClippedLogo(imagePath, logoPath, locationName, rotation, scaleFactor=0.8)
                
                if clippedPath:
                    actualLogoPath = clippedPath
                    clippedLogoOffset = parseClippedLogoOffset(clippedPath)
                    useClippedLogo = True
                    print(f"    [LOGO] Using clipped logo for {locationName}")
                else:
                    # Fallback to rotation-only
                    if rotation and abs(rotation) > 0.5:
                        actualLogoPath = rotateLogo(logoPath, rotation)
                        print(f"    [LOGO] Rotated by {rotation:.1f}° -> {actualLogoPath}")
            except Exception as e:
                print(f"    [WARN] Clipping failed: {e}, using rotation only")
                if rotation and abs(rotation) > 0.5:
                    try:
                        actualLogoPath = rotateLogo(logoPath, rotation)
                        print(f"    [LOGO] Rotated by {rotation:.1f}° -> {actualLogoPath}")
                    except Exception as e2:
                        print(f"    [WARN] Rotation failed: {e2}, using original")
        else:
            # Non-garment: just rotate if needed
            if rotation and abs(rotation) > 0.5:
                try:
                    actualLogoPath = rotateLogo(logoPath, rotation)
                    print(f"    [LOGO] Rotated by {rotation:.1f}° -> {actualLogoPath}")
                except Exception as e:
                    print(f"    [WARN] Failed to rotate logo: {e}, using original")

        # Open main image and ensure canvas size
        doc = app.Open(imagePath)
        
        # Set resolution to 150 DPI
        try:
            doc.ResizeImage(doc.Width, doc.Height, 150)
            try:
                setattr(doc, 'Resolution', 150)
            except Exception:
                pass
        except Exception as e:
            logError(f"Failed to set initial resolution to 150 for temp doc {targetName}: {e}")
        
        try:
            doc.ResizeCanvas(1200, canvasHeight)
        except Exception:
            pass

        # Rename base image layer
        try:
            imageLayer = doc.ArtLayers[0]
            imageLayer.Name = targetName
        except Exception:
            pass

        # Open logo (rotated if applicable)
        logoDoc = app.Open(actualLogoPath)
        logoDoc.Selection.SelectAll()
        logoDoc.Selection.Copy()
        logoDoc.Close(2)

        # Paste logo into main document
        doc.Paste()
        pastedLayer = doc.ArtLayers[0]
        try:
            pastedLayer.Name = decorationCode
        except Exception:
            pass

        # Set ruler units to pixels
        originalRulerUnits = app.Preferences.RulerUnits
        app.Preferences.RulerUnits = 1

        # Measure current pasted bounds
        bounds = pastedLayer.Bounds
        logoWidth = bounds[2] - bounds[0]
        logoHeight = bounds[3] - bounds[1]

        # Handle clipped logo positioning vs regular logo positioning
        if useClippedLogo:
            # Clipped logo: already sized and masked, position at offset (top-left)
            # The clipped logo is cropped from the full image, so its offset is where it should go
            offset_x, offset_y = clippedLogoOffset
            currentX = bounds[0]
            currentY = bounds[1]
            moveX = offset_x - currentX
            moveY = offset_y - currentY
            try:
                pastedLayer.Translate(moveX, moveY)
            except Exception:
                pastedLayer.Translate(int(moveX), int(moveY))
            print(f"    [LOGO] Positioned clipped logo at offset ({offset_x}, {offset_y})")
        else:
            # Regular logo: scale and center at coordinates
            desiredWidth, desiredHeight = customLogoSize

            # Avoid divide-by-zero
            if logoWidth == 0 or logoHeight == 0:
                logError(f"Invalid logo dimensions for temp doc {targetName}: w={logoWidth}, h={logoHeight}")
            else:
                scaleW = (desiredWidth / logoWidth) * 100
                scaleH = (desiredHeight / logoHeight) * 100
                scale = min(scaleW, scaleH)
                pastedLayer.Resize(scale, scale, 5)

                # Recompute bounds and translate to target coordinates
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

        # Restore ruler units
        app.Preferences.RulerUnits = originalRulerUnits

        return doc

    except Exception as e:
        try:
            ctx = {
                'targetName': targetName,
                'imagePath': imagePath,
                'logoPath': logoPath,
                'locationName': location,
                'coordinates': coordinates,
                'garmentType': garmentType,
                'customLogoSize': customLogoSize,
                'decorationCode': decorationCode,
                'imageExists': os.path.exists(imagePath) if imagePath else False,
                'logoExists': os.path.exists(logoPath) if logoPath else False,
            }
        except Exception:
            ctx = {'info': 'failed to build context'}

        logError(f"preparePairDoc error for {targetName}: {e} | context: {ctx}")
        return None


def prepareComboPairDoc(imagePath, logoPath, positionsList, coordinatesList, rotationsList,
                         garmentType, customLogoSize, decorationCode, targetName, canvasHeight=1200):
    """Create Photoshop document with image and MULTIPLE logos placed at different positions."""
    try:
        app = win32com.client.Dispatch("Photoshop.Application")
        app.Visible = True

        # Open main image and ensure canvas size
        doc = app.Open(imagePath)
        
        # Set resolution to 150 DPI
        try:
            doc.ResizeImage(doc.Width, doc.Height, 150)
        except Exception:
            pass
        
        try:
            doc.ResizeCanvas(1200, canvasHeight)
        except Exception:
            pass

        # Rename base image layer
        try:
            imageLayer = doc.ArtLayers[0]
            imageLayer.Name = targetName
        except Exception:
            pass

        # Set ruler units to pixels
        originalRulerUnits = app.Preferences.RulerUnits
        app.Preferences.RulerUnits = 1

        # Get desired logo size
        desiredWidth, desiredHeight = customLogoSize

        # Place logo at EACH position (with per-position clipping/rotation)
        for idx, (position, coordinates) in enumerate(zip(positionsList, coordinatesList)):
            if coordinates is None:
                print(f"    [WARN] Skipping position {position} - no coordinates")
                continue

            # Get rotation for this position
            rotation = rotationsList[idx] if idx < len(rotationsList) else 0.0
            
            # For T-SHIRT garments, use clipped logos
            actualLogoPath = logoPath
            useClippedLogo = False
            clippedLogoOffset = (0, 0)
            
            if garmentType == "T-SHIRT":
                try:
                    from detectors.garmentDetector import createClippedLogo, parseClippedLogoOffset
                    clippedPath = createClippedLogo(imagePath, logoPath, position, rotation, scaleFactor=0.8)
                    if clippedPath:
                        actualLogoPath = clippedPath
                        clippedLogoOffset = parseClippedLogoOffset(clippedPath)
                        useClippedLogo = True
                        print(f"    [LOGO] Using clipped logo for {position}")
                    else:
                        if rotation and abs(rotation) > 0.5:
                            actualLogoPath = rotateLogo(logoPath, rotation)
                except Exception as e:
                    print(f"    [WARN] Clipping failed for {position}: {e}")
                    if rotation and abs(rotation) > 0.5:
                        try:
                            actualLogoPath = rotateLogo(logoPath, rotation)
                        except:
                            pass
            else:
                if rotation and abs(rotation) > 0.5:
                    try:
                        actualLogoPath = rotateLogo(logoPath, rotation)
                        print(f"    [LOGO] Rotated by {rotation:.1f}° for {position}")
                    except Exception as e:
                        print(f"    [WARN] Failed to rotate logo: {e}, using original")
            
            # Open and copy the logo
            logoDoc = app.Open(actualLogoPath)
            logoDoc.Selection.SelectAll()
            logoDoc.Selection.Copy()
            logoDoc.Close(2)

            # Paste logo into main document
            doc.Paste()
            pastedLayer = doc.ArtLayers[0]
            try:
                pastedLayer.Name = f"{decorationCode}_{position}"
            except Exception:
                pass

            # Measure current pasted bounds
            bounds = pastedLayer.Bounds
            logoWidth = bounds[2] - bounds[0]
            logoHeight = bounds[3] - bounds[1]

            # Avoid divide-by-zero
            if logoWidth == 0 or logoHeight == 0:
                continue

            if useClippedLogo:
                # Clipped logo: position at offset
                offset_x, offset_y = clippedLogoOffset
                moveX = offset_x - bounds[0]
                moveY = offset_y - bounds[1]
                try:
                    pastedLayer.Translate(moveX, moveY)
                except Exception:
                    pastedLayer.Translate(int(moveX), int(moveY))
                print(f"    [LOGO] Placed clipped at {position}: offset ({offset_x}, {offset_y})")
            else:
                # Regular logo: scale and center
                scaleW = (desiredWidth / logoWidth) * 100
                scaleH = (desiredHeight / logoHeight) * 100
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

        # Restore ruler units
        app.Preferences.RulerUnits = originalRulerUnits

        return doc

    except Exception as e:
        logError(f"prepareComboPairDoc error for {targetName}: {e}")
        return None
