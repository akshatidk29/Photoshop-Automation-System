from pdf2image import convert_from_path
import win32com.client
import os
from detectors.baseDetector import getRotationAngle, getArmRotationAngle
from services.logger import logError
import cv2
import numpy as np
import tempfile
from core.utils import computeLogoSize, parseCustomSize
from PIL import Image


def rotateLogo(logoPath, angle):
    """Rotate logo image by specified angle, handling PDFs."""
    # Handle PDF logos (convert first page to image)
    if logoPath.lower().endswith(".pdf"):
        images = convert_from_path(logoPath, first_page=1, last_page=1)
        pilImage = images[0].convert("RGBA")
        tempPath = os.path.join(tempfile.gettempdir(), f"converted_{os.path.basename(logoPath)}.png")
        pilImage.save(tempPath, "PNG", dpi=(72, 72))
        logoPath = tempPath

    # Read logo image with alpha channel
    image = cv2.imread(logoPath, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Logo image not found or unreadable: {logoPath}")

    # Add alpha channel if not present
    if image.shape[2] == 3:
        b, g, r = cv2.split(image)
        alpha = np.ones(b.shape, dtype=b.dtype) * 255
        image = cv2.merge((b, g, r, alpha))

    h, w = image.shape[:2]
    center = (w // 2, h // 2)

    # Rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # Compute new bounds so logo isn't clipped
    cosVal = np.abs(M[0, 0])
    sinVal = np.abs(M[0, 1])
    newW = int(h * sinVal + w * cosVal)
    newH = int(h * cosVal + w * sinVal)

    # Adjust rotation matrix to new center
    M[0, 2] += (newW / 2) - center[0]
    M[1, 2] += (newH / 2) - center[1]

    # Rotate with transparency
    rotated = cv2.warpAffine(image, M, (newW, newH), flags=cv2.INTER_LINEAR, 
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    # Save as transparent PNG
    tempFile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    cv2.imwrite(tempFile.name, rotated)

    return tempFile.name


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


def preparePairDoc(imagePath, logoPath, locationName, coordinates, garmentType, 
                   customLogoSize, decorationCode, targetName, canvasHeight=1200):
    """Create temporary Photoshop document with image and placed logo."""
    try:
        app = win32com.client.Dispatch("Photoshop.Application")
        app.Visible = True
        location = str(locationName).strip().upper().replace(" ", "-")
        # canvasSize = 1800 if garmentType == "T-SHIRT" else 1200  <-- REPLACED with argument usage

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

        # Open logo
        logoDoc = app.Open(logoPath)
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

        # Resolve desired size
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


def prepareComboPairDoc(imagePath, logoPath, positionsList, coordinatesList, 
                         garmentType, customLogoSize, decorationCode, targetName, canvasHeight=1200):
    """Create Photoshop document with image and MULTIPLE logos placed at different positions."""
    try:
        app = win32com.client.Dispatch("Photoshop.Application")
        app.Visible = True
        # canvasSize = 1800 if garmentType == "T-SHIRT" else 1200 <-- REPLACED

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

        # Open logo ONCE and copy it
        logoDoc = app.Open(logoPath)
        logoDoc.Selection.SelectAll()
        logoDoc.Selection.Copy()
        logoDoc.Close(2)

        # Place logo at EACH position
        for idx, (position, coordinates) in enumerate(zip(positionsList, coordinatesList)):
            if coordinates is None:
                print(f"    [WARN] Skipping position {position} - no coordinates")
                continue

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

            print(f"    [LOGO] Placed at {position}: ({x}, {y})")

        # Restore ruler units
        app.Preferences.RulerUnits = originalRulerUnits

        return doc

    except Exception as e:
        logError(f"prepareComboPairDoc error for {targetName}: {e}")
        return None
