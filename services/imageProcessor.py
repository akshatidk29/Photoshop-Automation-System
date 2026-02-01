import os
import cv2
import numpy as np
from PIL import Image
from rembg import remove
import shutil
from typing import Tuple


class ImageProcessor:
    
    def __init__(self, tempDir: str = "processedImg"):
        """
        Initialize the image processor.
        """
        self.tempDir = os.path.abspath(tempDir)
        if not os.path.exists(self.tempDir):
            os.makedirs(self.tempDir)
    
    def cleanup(self):
        """Remove the temporary directory and all files."""
        if os.path.exists(self.tempDir):
            try:
                shutil.rmtree(self.tempDir)
                # Recreate empty folder
                os.makedirs(self.tempDir)
            except Exception as e:
                print(f"[WARNING] Failed to cleanup temp dir: {e}")

    def _extractForeground(self, imageArray: np.ndarray) -> Image.Image:
        """
        Extract the foreground object with transparent background using rembg.
        """
        pilImage = Image.fromarray(cv2.cvtColor(imageArray, cv2.COLOR_BGR2RGB))
        removedBg = remove(pilImage)
        return removedBg

    def _detectObjectBounds(self, alphaChannel: np.ndarray) -> Tuple[int, int, int, int]:
        """
        Detect bounding box from alpha channel.
        """
        rows = np.any(alphaChannel > 10, axis=1)
        cols = np.any(alphaChannel > 10, axis=0)
        
        if not np.any(rows) or not np.any(cols):
            return 0, alphaChannel.shape[0], 0, alphaChannel.shape[1]
        
        top = np.argmax(rows)
        bottom = len(rows) - np.argmax(rows[::-1])
        left = np.argmax(cols)
        right = len(cols) - np.argmax(cols[::-1])
        
        return top, bottom, left, right

    def processImage(self, inputPath: str, targetHeight: int = 1800) -> str:
        """
        Process an image: remove background, resize, and center on canvas.
        """
        # Determine mode logic
        if targetHeight == 1800:
            targetWidth = 1200
            targetH = 1800
            topPadding = 30
            bottomPadding = 0
            # Left/Right padding calculated to center
        else:
            # Default/Fallback to 1200x1200 logic
            targetWidth = 1200
            targetH = 1200
            topPadding = 50
            bottomPadding = 50
            leftPadding = 50
            rightPadding = 50
            
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
            
            pasteX = (targetWidth - newObjWidth) // 2
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
        
        # Create white background canvas
        result = Image.new('RGB', (targetWidth, targetH), (255, 255, 255))
        result.paste(resizedFg, (pasteX, pasteY), resizedFg)
        
        # Save to temp file
        filename = os.path.basename(inputPath)
        name, _ = os.path.splitext(filename)
        outputPath = os.path.join(self.tempDir, f"{name}_processed.jpg")
        
        result.save(outputPath, quality=95)
        
        return outputPath
