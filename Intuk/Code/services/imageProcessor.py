import os
import cv2
import numpy as np
from PIL import Image
from rembg import remove, new_session
import shutil
from typing import Tuple
from configuration.configLoader import (
    getDualViewSettings,
    getBackgroundRemovalSettings, getOutputSettings
)

# Hardcoded padding values (affects model prediction - do not change)

# T-SHIRT / GARMENT (1200x1800)
TSHIRT_CANVAS_WIDTH = 1200
TSHIRT_CANVAS_HEIGHT = 1800
TSHIRT_PERSON_TOP_PADDING = 30
TSHIRT_PERSON_BOTTOM_PADDING = 0
TSHIRT_FLAT_TOP_PADDING = 50
TSHIRT_FLAT_BOTTOM_PADDING = 50

# CAP / BAG / TOWEL (1200x1200)
CAP_CANVAS_WIDTH = 1200
CAP_CANVAS_HEIGHT = 1200
CAP_PADDING = 50


class ImageProcessor:
    """Handles image processing: background removal, resizing, dual-view composition."""
    
    def __init__(self, tempDir: str = "processedImg"):
        """Initialize with temp directory for processed images."""
        self.tempDir = os.path.abspath(tempDir)
        if not os.path.exists(self.tempDir):
            os.makedirs(self.tempDir)
        
        # Create reusable rembg session (avoids re-initializing model per call)
        # Use OpenVINO provider if available for faster CPU inference
        self._rembgSession = self._createRembgSession()
    
    def cleanup(self):
        """Remove temp directory and recreate empty."""
        if os.path.exists(self.tempDir):
            try:
                shutil.rmtree(self.tempDir)
                os.makedirs(self.tempDir)
            except Exception as e:
                print(f"[WARNING] Failed to cleanup temp dir: {e}")

    @staticmethod
    def _createRembgSession():
        """Create rembg session, preferring OpenVINO for speed."""
        # Check if OpenVINO provider is actually available in onnxruntime
        ovinoAvailable = False
        try:
            import onnxruntime
            ovinoAvailable = "OpenVINOExecutionProvider" in onnxruntime.get_available_providers()
        except Exception:
            pass
        
        if ovinoAvailable:
            try:
                session = new_session("u2net", providers=["OpenVINOExecutionProvider"])
                print("[ImageProcessor] rembg using OpenVINO (faster)")
                return session
            except Exception:
                pass
        
        try:
            session = new_session("u2net")
            print("[ImageProcessor] rembg using default ONNX CPU")
            return session
        except Exception:
            print("[ImageProcessor] rembg session creation failed, will use default per-call")
            return None

    def _extractForeground(self, imageArray: np.ndarray) -> Image.Image:
        """Extract foreground with transparent background using rembg."""
        bgSettings = getBackgroundRemovalSettings()
        pilImage = Image.fromarray(cv2.cvtColor(imageArray, cv2.COLOR_BGR2RGB))
        kwargs = dict(
            alpha_matting=bgSettings.get('alphaMatting', True),
            alpha_matting_foreground_threshold=bgSettings.get('alphaMattingForegroundThreshold', 240),
            alpha_matting_background_threshold=bgSettings.get('alphaMattingBackgroundThreshold', 20),
            alpha_matting_erode_size=bgSettings.get('alphaMattingErodeSize', 10)
        )
        if self._rembgSession is not None:
            kwargs['session'] = self._rembgSession
        removedBg = remove(pilImage, **kwargs)
        return removedBg

    def _detectObjectBounds(self, alphaChannel: np.ndarray) -> Tuple[int, int, int, int]:
        """Detect bounding box (top, bottom, left, right) from alpha channel."""
        rows = np.any(alphaChannel > 10, axis=1)
        cols = np.any(alphaChannel > 10, axis=0)
        
        if not np.any(rows) or not np.any(cols):
            return 0, alphaChannel.shape[0], 0, alphaChannel.shape[1]
        
        top = np.argmax(rows)
        bottom = len(rows) - np.argmax(rows[::-1])
        left = np.argmax(cols)
        right = len(cols) - np.argmax(cols[::-1])
        
        return top, bottom, left, right

    def processImage(self, inputPath: str, targetHeight: int = 1800, isFlatGarment: bool = None) -> str:
        """Process image: remove background, resize, center on canvas."""
        # Auto-detect flat garment if not specified
        if isFlatGarment is None:
            from locators.imageLocator import isFlatGarmentImage
            isFlatGarment = isFlatGarmentImage(inputPath)
        
        # Use hardcoded constants for padding (not from YAML - affects model prediction)
        if targetHeight == 1800:
            targetWidth = TSHIRT_CANVAS_WIDTH
            targetH = TSHIRT_CANVAS_HEIGHT
            if isFlatGarment:
                topPadding = TSHIRT_FLAT_TOP_PADDING
                bottomPadding = TSHIRT_FLAT_BOTTOM_PADDING
            else:
                topPadding = TSHIRT_PERSON_TOP_PADDING
                bottomPadding = TSHIRT_PERSON_BOTTOM_PADDING
            # Left/Right padding calculated to center
        else:
            # Default/Fallback to 1200x1200 logic (CAP)
            targetWidth = CAP_CANVAS_WIDTH
            targetH = CAP_CANVAS_HEIGHT
            topPadding = CAP_PADDING
            bottomPadding = CAP_PADDING
            leftPadding = CAP_PADDING
            rightPadding = CAP_PADDING
            isFlatGarment = False  # Not used in square mode
            
        # Load image
        image = cv2.imread(inputPath)
        if image is None:
            raise ValueError(f"Could not load image: {inputPath}")
            
        # Extract foreground
        foreground = self._extractForeground(image)
        
        # Get bounds
        fgArray = np.array(foreground)
        alpha = fgArray[:, :, 3]
        objTop, objBottom, objLeft, objRight = self._detectObjectBounds(alpha)
        
        objHeight = objBottom - objTop
        objWidth = objRight - objLeft
        
        # Crop to object
        croppedFg = foreground.crop((objLeft, objTop, objRight, objBottom))
        
        # Calculate scaling and positioning
        if targetH == 1800:
            availableHeight = targetH - topPadding - bottomPadding
            availableWidth = targetWidth
            
            scaleH = availableHeight / objHeight
            scaleW = availableWidth / objWidth
            scale = min(scaleH, scaleW)
            
            newObjWidth = int(objWidth * scale)
            newObjHeight = int(objHeight * scale)
            
            # Center horizontally (always)
            pasteX = (targetWidth - newObjWidth) // 2
            
            if isFlatGarment:
                # Flat garment: center vertically within available space
                pasteY = topPadding + (availableHeight - newObjHeight) // 2
            else:
                # Human model: top-aligned, touch bottom if possible
                pasteY = topPadding
                # If object doesn't reach bottom, adjust to touch bottom
                if pasteY + newObjHeight < targetH:
                    pasteY = targetH - newObjHeight
                    if pasteY < topPadding:
                        pasteY = topPadding
        else:
            # 1200x1200 logic
            availableHeight = targetH - topPadding - bottomPadding
            availableWidth = targetWidth - leftPadding - rightPadding
            
            scaleH = availableHeight / objHeight
            scaleW = availableWidth / objWidth
            scale = min(scaleH, scaleW)
            
            newObjWidth = int(objWidth * scale)
            newObjHeight = int(objHeight * scale)
            
            pasteX = (targetWidth - newObjWidth) // 2
            pasteY = (targetH - newObjHeight) // 2
            
        # Resize
        resizedFg = croppedFg.resize((newObjWidth, newObjHeight), Image.Resampling.LANCZOS)
        
        # Post-process alpha channel to eliminate grey halos
        resizedArray = np.array(resizedFg)
        if resizedArray.shape[2] == 4:
            alpha = resizedArray[:, :, 3]
            # Erode alpha slightly to remove grey fringe
            kernel = np.ones((3, 3), np.uint8)
            alpha = cv2.erode(alpha, kernel, iterations=1)
            # Threshold semi-transparent pixels to clean edges
            alpha = np.where(alpha > 200, 255, np.where(alpha < 50, 0, alpha)).astype(np.uint8)
            resizedArray[:, :, 3] = alpha
            resizedFg = Image.fromarray(resizedArray)
        
        # Create white background canvas
        result = Image.new('RGB', (targetWidth, targetH), (255, 255, 255))
        result.paste(resizedFg, (pasteX, pasteY), resizedFg)
        
        # Save to temp file
        filename = os.path.basename(inputPath)
        name, _ = os.path.splitext(filename)
        outputPath = os.path.join(self.tempDir, f"{name}_processed.jpg")
        
        outputSettings = getOutputSettings()
        result.save(outputPath, quality=outputSettings.get('jpegQuality', 95))
        
        return outputPath

    def processDualViewImage(self, backImagePath: str, frontImagePath: str, 
                              targetHeight: int = 1800,
                              backScalePercent: float = None,
                              frontScalePercent: float = None) -> str:
        """Create dual-view image for T-SHIRT/BLANKET: back at top-left, front at bottom-right."""
        # Load settings from YAML
        settings = getDualViewSettings('tshirt')
        targetWidth = settings.get('canvasWidth', 1200)
        targetH = settings.get('canvasHeight', 1800)
        edgeMargin = settings.get('edgeMargin', 10)  # Separation from canvas edges
        
        # Use configured values if not provided as arguments
        if backScalePercent is None:
            backScalePercent = settings.get('backScalePercent', 0.70)
        if frontScalePercent is None:
            frontScalePercent = settings.get('frontScalePercent', 0.80)
        
        # Override canvas if targetHeight is explicitly different
        if targetHeight != 1800:
            targetWidth = 1200
            targetH = targetHeight
        
        # Process back image - align to LEFT
        backProcessedRGBA, backLayout = self._processImageForDualViewRGBA(
            backImagePath, targetWidth, targetH, isDualView=True, 
            alignment='left', edgeMargin=edgeMargin
        )
        # Process front image - align to RIGHT
        frontProcessedRGBA, frontLayout = self._processImageForDualViewRGBA(
            frontImagePath, targetWidth, targetH, isDualView=True,
            alignment='right', edgeMargin=edgeMargin
        )
        
        # Scale processed images
        # Back image scales to configured %
        backScaledW = int(targetWidth * backScalePercent)
        backScaledH = int(targetH * backScalePercent)
        backScaled = backProcessedRGBA.resize((backScaledW, backScaledH), Image.Resampling.LANCZOS)
        
        # Front image scales to configured %
        frontScaledW = int(targetWidth * frontScalePercent)
        frontScaledH = int(targetH * frontScalePercent)
        frontScaled = frontProcessedRGBA.resize((frontScaledW, frontScaledH), Image.Resampling.LANCZOS)
        
        # Position on canvas: back at TOP-LEFT, front at BOTTOM-RIGHT
        backX = 0
        backY = 0
        
        # Front at BOTTOM-RIGHT
        frontX = targetWidth - frontScaledW
        frontY = targetH - frontScaledH
        
        # Create canvas and paste images
        result = Image.new('RGB', (targetWidth, targetH), (255, 255, 255))
        result.paste(backScaled, (backX, backY), backScaled)
        result.paste(frontScaled, (frontX, frontY), frontScaled)
        
        # Save to temp file
        filename = os.path.basename(backImagePath)
        name, _ = os.path.splitext(filename)
        outputPath = os.path.join(self.tempDir, f"{name}_dualview.jpg")
        
        outputSettings = getOutputSettings()
        result.save(outputPath, quality=outputSettings.get('jpegQuality', 95))
        
        # Store layout info for coordinate transformation
        # Combines: original image processing + scaling + final placement
        self._lastDualViewLayout = {
            # Back image info
            'backX': backX,
            'backY': backY,
            'backScalePercent': backScalePercent,
            'backScaledW': backScaledW,
            'backScaledH': backScaledH,
            'backLayout': backLayout,  # Original processing layout
            # Front image info
            'frontX': frontX,
            'frontY': frontY,
            'frontScalePercent': frontScalePercent,
            'frontScaledW': frontScaledW,
            'frontScaledH': frontScaledH,
            'frontLayout': frontLayout,  # Original processing layout
            # Canvas info
            'canvasW': targetWidth,
            'canvasH': targetH
        }
        
        return outputPath

    def _processImageForDualView(self, inputPath: str, targetWidth: int, targetHeight: int, isDualView: bool = True) -> tuple:
        """Process single image for dual-view, returns (image, layout_dict)."""
        # Check if flat garment
        from locators.imageLocator import isFlatGarmentImage
        isFlatGarment = isFlatGarmentImage(inputPath)
        
        # Use hardcoded padding values (not from YAML - affects model prediction)
        if targetHeight == 1800:
            if isFlatGarment:
                topPadding = TSHIRT_FLAT_TOP_PADDING
                bottomPadding = TSHIRT_FLAT_BOTTOM_PADDING
            else:
                topPadding = TSHIRT_PERSON_TOP_PADDING
                bottomPadding = TSHIRT_PERSON_BOTTOM_PADDING
        else:
            topPadding = CAP_PADDING
            bottomPadding = CAP_PADDING
        
        # Load and process image
        image = cv2.imread(inputPath)
        if image is None:
            raise ValueError(f"Could not load image: {inputPath}")
        
        # Extract foreground
        foreground = self._extractForeground(image)
        
        # Get bounds
        fgArray = np.array(foreground)
        alpha = fgArray[:, :, 3]
        objTop, objBottom, objLeft, objRight = self._detectObjectBounds(alpha)
        
        objHeight = objBottom - objTop
        objWidth = objRight - objLeft
        
        # Crop to object
        croppedFg = foreground.crop((objLeft, objTop, objRight, objBottom))
        
        # Calculate scaling
        availableHeight = targetHeight - topPadding - bottomPadding
        availableWidth = targetWidth
        
        scaleH = availableHeight / objHeight
        scaleW = availableWidth / objWidth
        scale = min(scaleH, scaleW)
        
        newObjWidth = int(objWidth * scale)
        newObjHeight = int(objHeight * scale)
        
        # Center horizontally
        pasteX = (targetWidth - newObjWidth) // 2
        
        # Vertical positioning
        if isFlatGarment:
            pasteY = topPadding + (availableHeight - newObjHeight) // 2
        else:
            # Human model: bottom-aligned
            pasteY = targetHeight - newObjHeight
            if pasteY < topPadding:
                pasteY = topPadding
        
        # Resize
        resizedFg = croppedFg.resize((newObjWidth, newObjHeight), Image.Resampling.LANCZOS)
        resizedFg = self._cleanAlpha(resizedFg)
        
        # Create canvas with white background
        result = Image.new('RGB', (targetWidth, targetHeight), (255, 255, 255))
        result.paste(resizedFg, (pasteX, pasteY), resizedFg)
        
        # Layout info for coordinate transformation
        layout = {
            'cropLeft': objLeft,
            'cropTop': objTop,
            'scale': scale,
            'pasteX': pasteX,
            'pasteY': pasteY,
            'newW': newObjWidth,
            'newH': newObjHeight
        }
        
        return result, layout

    def _processImageForDualViewRGBA(self, inputPath: str, targetWidth: int, targetHeight: int, 
                                       isDualView: bool = True, alignment: str = 'center',
                                       edgeMargin: int = 0) -> tuple:
        """Process single image for dual-view with RGBA transparency, returns (image, layout_dict)."""
        # Check if flat garment
        from locators.imageLocator import isFlatGarmentImage
        isFlatGarment = isFlatGarmentImage(inputPath)
        
        # Use hardcoded padding values (not from YAML - affects model prediction)
        if targetHeight == 1800:
            if isFlatGarment:
                topPadding = TSHIRT_FLAT_TOP_PADDING
                bottomPadding = TSHIRT_FLAT_BOTTOM_PADDING
            else:
                topPadding = TSHIRT_PERSON_TOP_PADDING
                bottomPadding = TSHIRT_PERSON_BOTTOM_PADDING
        else:
            topPadding = CAP_PADDING
            bottomPadding = CAP_PADDING
        
        # Load and process image
        image = cv2.imread(inputPath)
        if image is None:
            raise ValueError(f"Could not load image: {inputPath}")
        
        # Extract foreground
        foreground = self._extractForeground(image)
        
        # Get bounds
        fgArray = np.array(foreground)
        alpha = fgArray[:, :, 3]
        objTop, objBottom, objLeft, objRight = self._detectObjectBounds(alpha)
        
        objHeight = objBottom - objTop
        objWidth = objRight - objLeft
        
        # Crop to object
        croppedFg = foreground.crop((objLeft, objTop, objRight, objBottom))
        
        # Calculate scaling
        availableHeight = targetHeight - topPadding - bottomPadding
        availableWidth = targetWidth
        
        scaleH = availableHeight / objHeight
        scaleW = availableWidth / objWidth
        scale = min(scaleH, scaleW)
        
        newObjWidth = int(objWidth * scale)
        newObjHeight = int(objHeight * scale)
        
        # Horizontal positioning based on alignment
        if alignment == 'left':
            # Align garment to left edge with margin
            pasteX = edgeMargin
        elif alignment == 'right':
            # Align garment to right edge with margin
            pasteX = targetWidth - newObjWidth - edgeMargin
        else:
            # Center horizontally (default)
            pasteX = (targetWidth - newObjWidth) // 2
        
        # Vertical positioning
        if isFlatGarment:
            pasteY = topPadding + (availableHeight - newObjHeight) // 2
        else:
            # Human model: bottom-aligned
            pasteY = targetHeight - newObjHeight
            if pasteY < topPadding:
                pasteY = topPadding
        
        # Resize
        resizedFg = croppedFg.resize((newObjWidth, newObjHeight), Image.Resampling.LANCZOS)
        resizedFg = self._cleanAlpha(resizedFg)
        
        # Create RGBA canvas with TRANSPARENT background (not white)
        result = Image.new('RGBA', (targetWidth, targetHeight), (255, 255, 255, 0))
        result.paste(resizedFg, (pasteX, pasteY), resizedFg)
        
        # Layout info for coordinate transformation
        layout = {
            'cropLeft': objLeft,
            'cropTop': objTop,
            'scale': scale,
            'pasteX': pasteX,
            'pasteY': pasteY,
            'newW': newObjWidth,
            'newH': newObjHeight
        }
        
        return result, layout

    def processCapDualViewImage(self, frontImagePath: str, backSideImagePath: str,
                                 scalePercent: float = None,
                                 logoPositionOnBackSide: tuple = None) -> str:
        """Create dual-view image for CAPs based on logo position."""
        # Load settings from YAML
        settings = getDualViewSettings('cap')
        targetWidth = settings.get('canvasWidth', 1200)
        targetH = settings.get('canvasHeight', 1200)
        edgeMargin = settings.get('edgeMargin', 10)  # Separation from canvas edges
        
        # Use configured value if not provided as argument
        if scalePercent is None:
            scalePercent = settings.get('scalePercent', 0.65)
        
        # Determine placement based on logo position
        logoOnRight = False
        if logoPositionOnBackSide:
            logoX, logoY = logoPositionOnBackSide
        
        # Process with center alignment to get layout for logo position check
        tempBackSide, tempLayout = self._processCapImageForDualViewRGBA(backSideImagePath, targetWidth, targetH)
        
        if logoPositionOnBackSide:
            logoX, logoY = logoPositionOnBackSide
            # Transform logo position using temp layout
            transformedX = (logoX - tempLayout['cropLeft']) * tempLayout['scale'] + tempLayout['pasteX']
            logoOnRight = transformedX > (targetWidth / 2)
        
        # Process images with correct alignment
        if logoOnRight:
            # Logo on right → back/side at TOP-RIGHT, front at BOTTOM-LEFT
            backSideProcessedRGBA, backSideLayout = self._processCapImageForDualViewRGBA(
                backSideImagePath, targetWidth, targetH, alignment='right', edgeMargin=edgeMargin
            )
            frontProcessedRGBA, frontLayout = self._processCapImageForDualViewRGBA(
                frontImagePath, targetWidth, targetH, alignment='left', edgeMargin=edgeMargin
            )
        else:
            # Logo on left → back/side at TOP-LEFT, front at BOTTOM-RIGHT
            backSideProcessedRGBA, backSideLayout = self._processCapImageForDualViewRGBA(
                backSideImagePath, targetWidth, targetH, alignment='left', edgeMargin=edgeMargin
            )
            frontProcessedRGBA, frontLayout = self._processCapImageForDualViewRGBA(
                frontImagePath, targetWidth, targetH, alignment='right', edgeMargin=edgeMargin
            )
        
        # Scale both images
        scaledSize = int(targetWidth * scalePercent)
        frontScaled = frontProcessedRGBA.resize((scaledSize, scaledSize), Image.Resampling.LANCZOS)
        backSideScaled = backSideProcessedRGBA.resize((scaledSize, scaledSize), Image.Resampling.LANCZOS)
        
        # Position on canvas
        if logoOnRight:
            backSideX = targetWidth - scaledSize
            backSideY = 0
            frontX = 0
            frontY = targetH - scaledSize
        else:
            backSideX = 0
            backSideY = 0
            frontX = targetWidth - scaledSize
            frontY = targetH - scaledSize
        
        # Create canvas and paste images
        result = Image.new('RGB', (targetWidth, targetH), (255, 255, 255))
        result.paste(backSideScaled, (backSideX, backSideY), backSideScaled)
        result.paste(frontScaled, (frontX, frontY), frontScaled)
        
        # Save to temp file
        filename = os.path.basename(frontImagePath)
        name, _ = os.path.splitext(filename)
        outputPath = os.path.join(self.tempDir, f"{name}_cap_dualview.jpg")
        
        outputSettings = getOutputSettings()
        result.save(outputPath, quality=outputSettings.get('jpegQuality', 95))
        
        # Store layout info for coordinate transformation
        self._lastCapDualViewLayout = {
            # Front image info
            'frontX': frontX,
            'frontY': frontY,
            'frontScalePercent': scalePercent,
            'frontScaledSize': scaledSize,
            'frontLayout': frontLayout,
            # Back/Side image info
            'backSideX': backSideX,
            'backSideY': backSideY,
            'backSideScalePercent': scalePercent,
            'backSideScaledSize': scaledSize,
            'backSideLayout': backSideLayout,
            # Canvas info
            'canvasW': targetWidth,
            'canvasH': targetH,
            'logoOnRight': logoOnRight
        }
        
        return outputPath

    def _processCapImageForDualView(self, inputPath: str, targetWidth: int, targetHeight: int) -> tuple:
        """Process CAP image for dual-view, returns (image, layout_dict)."""
        # Use hardcoded padding
        padding = CAP_PADDING
        
        # Load and process image
        image = cv2.imread(inputPath)
        if image is None:
            raise ValueError(f"Could not load image: {inputPath}")
        
        # Extract foreground
        foreground = self._extractForeground(image)
        
        # Get bounds
        fgArray = np.array(foreground)
        alpha = fgArray[:, :, 3]
        objTop, objBottom, objLeft, objRight = self._detectObjectBounds(alpha)
        
        objHeight = objBottom - objTop
        objWidth = objRight - objLeft
        
        # Crop to object
        croppedFg = foreground.crop((objLeft, objTop, objRight, objBottom))
        
        # Calculate scaling (fit within padded area)
        availableSize = targetWidth - (2 * padding)
        
        scaleH = availableSize / objHeight
        scaleW = availableSize / objWidth
        scale = min(scaleH, scaleW)
        
        newObjWidth = int(objWidth * scale)
        newObjHeight = int(objHeight * scale)
        
        # Center in canvas
        pasteX = (targetWidth - newObjWidth) // 2
        pasteY = (targetHeight - newObjHeight) // 2
        
        # Resize
        resizedFg = croppedFg.resize((newObjWidth, newObjHeight), Image.Resampling.LANCZOS)
        resizedFg = self._cleanAlpha(resizedFg)
        
        # Create canvas with white background
        result = Image.new('RGB', (targetWidth, targetHeight), (255, 255, 255))
        result.paste(resizedFg, (pasteX, pasteY), resizedFg)
        
        # Layout info for coordinate transformation
        layout = {
            'cropLeft': objLeft,
            'cropTop': objTop,
            'scale': scale,
            'pasteX': pasteX,
            'pasteY': pasteY,
            'newW': newObjWidth,
            'newH': newObjHeight
        }
        
        return result, layout

    def _processCapImageForDualViewRGBA(self, inputPath: str, targetWidth: int, targetHeight: int,
                                          alignment: str = 'center', edgeMargin: int = 0) -> tuple:
        """Process CAP image for dual-view with RGBA transparency, returns (image, layout_dict)."""
        # Use hardcoded padding
        padding = CAP_PADDING
        
        # Load and process image
        image = cv2.imread(inputPath)
        if image is None:
            raise ValueError(f"Could not load image: {inputPath}")
        
        # Extract foreground
        foreground = self._extractForeground(image)
        
        # Get bounds
        fgArray = np.array(foreground)
        alpha = fgArray[:, :, 3]
        objTop, objBottom, objLeft, objRight = self._detectObjectBounds(alpha)
        
        objHeight = objBottom - objTop
        objWidth = objRight - objLeft
        
        # Crop to object
        croppedFg = foreground.crop((objLeft, objTop, objRight, objBottom))
        
        # Calculate scaling (fit within padded area)
        availableSize = targetWidth - (2 * padding)
        
        scaleH = availableSize / objHeight
        scaleW = availableSize / objWidth
        scale = min(scaleH, scaleW)
        
        newObjWidth = int(objWidth * scale)
        newObjHeight = int(objHeight * scale)
        
        # Horizontal positioning based on alignment
        if alignment == 'left':
            pasteX = edgeMargin
        elif alignment == 'right':
            pasteX = targetWidth - newObjWidth - edgeMargin
        else:
            # Center in canvas (default)
            pasteX = (targetWidth - newObjWidth) // 2
        
        # Center vertically
        pasteY = (targetHeight - newObjHeight) // 2
        
        # Resize
        resizedFg = croppedFg.resize((newObjWidth, newObjHeight), Image.Resampling.LANCZOS)
        resizedFg = self._cleanAlpha(resizedFg)
        
        # Create RGBA canvas with TRANSPARENT background
        result = Image.new('RGBA', (targetWidth, targetHeight), (255, 255, 255, 0))
        result.paste(resizedFg, (pasteX, pasteY), resizedFg)
        
        # Layout info for coordinate transformation
        layout = {
            'cropLeft': objLeft,
            'cropTop': objTop,
            'scale': scale,
            'pasteX': pasteX,
            'pasteY': pasteY,
            'newW': newObjWidth,
            'newH': newObjHeight
        }
        
        return result, layout

    def transformCoordsForCapFront(self, originalCoords: tuple) -> tuple:
        """Transform coords from original front cap image to dual-view canvas."""
        layout = getattr(self, '_lastCapDualViewLayout', None)
        if not layout or 'frontLayout' not in layout:
            return originalCoords
        
        frontLayout = layout['frontLayout']
        origX, origY = originalCoords
        
        # Step 1: Transform to processed image coordinates
        adjustedX = origX - frontLayout.get('cropLeft', 0)
        adjustedY = origY - frontLayout.get('cropTop', 0)
        processedX = adjustedX * frontLayout.get('scale', 1.0) + frontLayout.get('pasteX', 0)
        processedY = adjustedY * frontLayout.get('scale', 1.0) + frontLayout.get('pasteY', 0)
        
        # Step 2: Apply the dual-view scaling (e.g., 65%)
        scalePercent = layout.get('frontScalePercent', 0.65)
        scaledX = processedX * scalePercent
        scaledY = processedY * scalePercent
        
        # Step 3: Add position offset
        finalX = int(scaledX + layout.get('frontX', 0))
        finalY = int(scaledY + layout.get('frontY', 0))
        
        return (finalX, finalY)

    def transformCoordsForCapBackSide(self, originalCoords: tuple) -> tuple:
        """Transform coords from original back/side cap image to dual-view canvas."""
        layout = getattr(self, '_lastCapDualViewLayout', None)
        if not layout or 'backSideLayout' not in layout:
            return originalCoords
        
        backSideLayout = layout['backSideLayout']
        origX, origY = originalCoords
        
        # Step 1: Transform to processed image coordinates
        adjustedX = origX - backSideLayout.get('cropLeft', 0)
        adjustedY = origY - backSideLayout.get('cropTop', 0)
        processedX = adjustedX * backSideLayout.get('scale', 1.0) + backSideLayout.get('pasteX', 0)
        processedY = adjustedY * backSideLayout.get('scale', 1.0) + backSideLayout.get('pasteY', 0)
        
        # Step 2: Apply the dual-view scaling (e.g., 65%)
        scalePercent = layout.get('backSideScalePercent', 0.65)
        scaledX = processedX * scalePercent
        scaledY = processedY * scalePercent
        
        # Step 3: Add position offset
        finalX = int(scaledX + layout.get('backSideX', 0))
        finalY = int(scaledY + layout.get('backSideY', 0))
        
        return (finalX, finalY)

    def getCapDualViewScaleFactors(self):
        """Get (frontScale, backSideScale) for CAP dual-view."""
        layout = getattr(self, '_lastCapDualViewLayout', None)
        if layout:
            frontLayout = layout.get('frontLayout', {})
            backSideLayout = layout.get('backSideLayout', {})
            # Total scale = processing scale * dual-view scale
            frontTotal = frontLayout.get('scale', 1.0) * layout.get('frontScalePercent', 0.65)
            backSideTotal = backSideLayout.get('scale', 1.0) * layout.get('backSideScalePercent', 0.65)
            return (frontTotal, backSideTotal)
        return (1.0, 1.0)

    def getLastCapDualViewLayout(self):
        """Get the last CAP dual-view layout info for external use."""
        return getattr(self, '_lastCapDualViewLayout', None)

    def _cleanAlpha(self, img: Image.Image) -> Image.Image:
        """Clean alpha channel to remove grey halos after resize."""
        imgArray = np.array(img)
        if imgArray.shape[2] == 4:
            alpha = imgArray[:, :, 3]
            kernel = np.ones((3, 3), np.uint8)
            alpha = cv2.erode(alpha, kernel, iterations=1)
            alpha = np.where(alpha > 200, 255, np.where(alpha < 50, 0, alpha)).astype(np.uint8)
            imgArray[:, :, 3] = alpha
            return Image.fromarray(imgArray)
        return img

    def transformCoordinatesForDualView(self, originalCoords: tuple, originalImagePath: str) -> tuple:
        """Transform coords from original back image to T-SHIRT dual-view canvas."""
        if not hasattr(self, '_lastDualViewLayout') or self._lastDualViewLayout is None:
            return originalCoords
        
        layout = self._lastDualViewLayout
        backLayout = layout.get('backLayout', {})
        origX, origY = originalCoords
        
        # Step 1: Transform to processed image coordinates
        # Subtract crop offset, apply scale, add paste position
        adjustedX = origX - backLayout.get('cropLeft', 0)
        adjustedY = origY - backLayout.get('cropTop', 0)
        processedX = adjustedX * backLayout.get('scale', 1.0) + backLayout.get('pasteX', 0)
        processedY = adjustedY * backLayout.get('scale', 1.0) + backLayout.get('pasteY', 0)
        
        # Step 2: Apply the 70% scaling for dual-view
        scaledX = processedX * layout.get('backScalePercent', 0.70)
        scaledY = processedY * layout.get('backScalePercent', 0.70)
        
        # Step 3: Add position offset (back is at top-left: 0, 0)
        finalX = int(scaledX + layout.get('backX', 0))
        finalY = int(scaledY + layout.get('backY', 0))
        
        return (finalX, finalY)

    def transformCoordsForDualViewFront(self, originalCoords: tuple) -> tuple:
        """Transform coords from original front image to T-SHIRT dual-view canvas."""
        layout = getattr(self, '_lastDualViewLayout', None)
        if not layout or 'frontLayout' not in layout:
            return originalCoords
        
        frontLayout = layout['frontLayout']
        origX, origY = originalCoords
        
        # Step 1: Transform to processed image coordinates
        adjustedX = origX - frontLayout.get('cropLeft', 0)
        adjustedY = origY - frontLayout.get('cropTop', 0)
        processedX = adjustedX * frontLayout.get('scale', 1.0) + frontLayout.get('pasteX', 0)
        processedY = adjustedY * frontLayout.get('scale', 1.0) + frontLayout.get('pasteY', 0)
        
        # Step 2: Apply the 80% scaling for dual-view
        scaledX = processedX * layout.get('frontScalePercent', 0.80)
        scaledY = processedY * layout.get('frontScalePercent', 0.80)
        
        # Step 3: Add position offset (front is at bottom-right)
        finalX = int(scaledX + layout.get('frontX', 0))
        finalY = int(scaledY + layout.get('frontY', 0))
        
        return (finalX, finalY)

    def getDualViewScaleFactors(self):
        """Get (backScale, frontScale) for T-SHIRT dual-view."""
        layout = getattr(self, '_lastDualViewLayout', None)
        if layout:
            backLayout = layout.get('backLayout', {})
            frontLayout = layout.get('frontLayout', {})
            # Total scale = processing scale * dual-view scale
            backTotal = backLayout.get('scale', 1.0) * layout.get('backScalePercent', 0.70)
            frontTotal = frontLayout.get('scale', 1.0) * layout.get('frontScalePercent', 0.80)
            return (backTotal, frontTotal)
        return (1.0, 1.0)

    def getDualViewScaleFactor(self):
        """Get back image scale factor (backward compatible)."""
        scales = self.getDualViewScaleFactors()
        return scales[0]

    def getLastDualViewLayout(self):
        """Get the last dual view layout info for external use."""
        return getattr(self, '_lastDualViewLayout', None)
