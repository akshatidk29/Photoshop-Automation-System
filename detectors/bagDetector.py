import cv2
import numpy as np
from core.utils import normalizeLocation

def getProductBoundingBox(imagePath):
    """
    Detect the bag/backpack in image using robust contour detection.
    Returns (x, y, w, h) of the bounding box.
    """
    img = cv2.imread(imagePath)
    if img is None:
        raise ValueError(f"Image not found: {imagePath}")
    
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Simple threshold - assuming white/light background
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    
    # Clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return (w//4, h//4, w//2, h//2)
    
    # Get largest contour
    c = max(contours, key=cv2.contourArea)
    x, y, bw, bh = cv2.boundingRect(c)
    
    return x, y, bw, bh

def segmentBagRegions(imagePath, bagBox):
    """
    Segment bag into distinct regions using kmeans clustering and spatial analysis.
    Returns dict with region centers: {'upper': (x,y), 'lower': (x,y), 'pocket': (x,y)}
    """
    img = cv2.imread(imagePath)
    if img is None:
        return None
    
    bx, by, bw, bh = bagBox
    roi = img[by:by+bh, bx:bx+bw].copy()
    
    if roi.size == 0:
        return None
    
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    roi_h, roi_w = gray_roi.shape
    
    # Detect horizontal separators (zippers, seams) using gradient analysis
    # Calculate horizontal gradients
    sobelx = cv2.Sobel(gray_roi, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray_roi, cv2.CV_64F, 0, 1, ksize=3)
    
    # Focus on strong horizontal edges
    abs_sobely = np.absolute(sobely)
    
    # Compute horizontal edge strength for each row
    row_edges = np.mean(abs_sobely, axis=1)
    
    # Smooth the signal
    from scipy.ndimage import gaussian_filter1d
    smoothed = gaussian_filter1d(row_edges, sigma=5)
    
    # Find peaks (strong horizontal lines)
    threshold = np.mean(smoothed) + 0.5 * np.std(smoothed)
    peaks = []
    
    for i in range(10, len(smoothed)-10):
        if smoothed[i] > threshold:
            # Check if it's a local maximum
            if smoothed[i] > smoothed[i-5:i].max() and smoothed[i] > smoothed[i+1:i+6].max():
                peaks.append(i)
    
    # Filter peaks - keep only significant ones
    if len(peaks) > 1:
        # Remove peaks too close to each other (keep strongest)
        filtered_peaks = []
        i = 0
        while i < len(peaks):
            group = [peaks[i]]
            j = i + 1
            while j < len(peaks) and peaks[j] - peaks[i] < roi_h * 0.1:
                group.append(peaks[j])
                j += 1
            # Keep the strongest in the group
            strongest = max(group, key=lambda p: smoothed[p])
            filtered_peaks.append(strongest)
            i = j
        
        peaks = filtered_peaks
    
    regions = {}
    centerX = bx + bw // 2
    
    # Analyze detected peaks to identify regions
    if len(peaks) >= 1:
        # Most prominent horizontal line likely separates main body from pocket
        main_separator = peaks[0] if peaks[0] > roi_h * 0.4 else (peaks[1] if len(peaks) > 1 else peaks[0])
        
        # Upper region (main body above separator)
        upper_y = by + main_separator // 2
        regions['upper'] = (centerX, upper_y)
        
        # Pocket region (below separator)
        pocket_start = main_separator + int((roi_h - main_separator) * 0.1)
        pocket_y = by + pocket_start + (roi_h - pocket_start) // 2
        regions['pocket'] = (centerX, pocket_y)
        
    else:
        # No clear separator found - use heuristic division
        # Upper 50% for main body
        regions['upper'] = (centerX, by + int(bh * 0.3))
        # Lower 30% for pocket
        regions['pocket'] = (centerX, by + int(bh * 0.75))
    
    regions['lower'] = (centerX, by + int(bh * 0.6))
    
    return regions

def getBagCoordinates(imagePath, locationName, debug=False):
    """
    Get coordinates for logo placement using intelligent region segmentation.
    Returns (x, y) tuple for logo center position.
    """
    normLoc = normalizeLocation(locationName)
    
    try:
        bagBox = getProductBoundingBox(imagePath)
        bx, by, bw, bh = bagBox
    except Exception as e:
        print(f"Error detecting bag: {e}")
        return (600, 600)
    
    centerX = bx + bw // 2
    
    # Try to segment bag into regions
    try:
        regions = segmentBagRegions(imagePath, bagBox)
    except:
        regions = None
    
    if "ON-POCKET" in normLoc or "POCKET" in normLoc:
        # Place on pocket region
        if regions and 'pocket' in regions:
            return regions['pocket']
        else:
            # Fallback: lower portion
            return (centerX, by + int(bh * 0.78))
        
    elif "FRONT" in normLoc or "ON-BAG" in normLoc:
        # Place on upper/main body
        if regions and 'upper' in regions:
            return regions['upper']
        else:
            # Fallback: upper-center
            return (centerX, by + int(bh * 0.32))
    
    # Default: center
    return (centerX, by + bh // 2)

# Standard Interface Functions

def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """
    Standard Interface: Get (x, y) coordinates for logo placement.
    """
    return getBagCoordinates(imagePath, locationName, debug)

def getLogoScale(imagePath, locationName, baseSize=(200, 100)):
    """
    Standard Interface: Get (width, height) for logo based on bag size.
    """
    try:
        bx, by, bw, bh = getProductBoundingBox(imagePath)
        
        # Scale logo based on bag size
        scale_factor = (bw * 0.18) / baseSize[0]
        
        new_width = int(baseSize[0] * scale_factor)
        new_height = int(baseSize[1] * scale_factor)
        
        # Ensure reasonable sizes
        new_width = max(100, min(400, new_width))
        new_height = max(50, min(200, new_height))
        
        return (new_width, new_height)
        
    except Exception as e:
        print(f"Error calculating logo scale: {e}")
        return baseSize

def getRotation(imagePath, locationName):
    """
    Standard Interface: Get rotation angle for logo.
    """
    return 0

# Main

def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """Standard Interface: Get (x, y) coordinates."""
    return getBagCoordinates(imagePath, locationName, debug)

def getLogoScale(imagePath, locationName, baseSize=(200, 100)):
    """Standard Interface: Get (width, height) for logo."""
    # Dummy implementation for now
    return baseSize

def getRotation(imagePath, locationName):
    """Standard Interface: Get rotation angle."""
    return 0
