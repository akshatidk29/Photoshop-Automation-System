"""
Garment Detector using YOLO OBB Model.

Provides coordinates, rotation, and logo scale for garment regions.
Uses OBB (Oriented Bounding Box) detection for accurate region detection.
"""

import os
from pathlib import Path

# Import OBB detector
try:
    from model.inference.obb_garment_detector import OBBGarmentDetector, PLACEMENT_CONFIG
except ImportError:
    # Fallback for different import paths
    import sys
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    from model.inference.obb_garment_detector import OBBGarmentDetector, PLACEMENT_CONFIG


# Location name mapping: Excel format -> OBB class names
LOCATION_MAP = {
    # Front regions
    "FULL-FRONT": "FULL_FRONT",
    "LEFT-CHEST": "LEFT_CHEST",
    "RIGHT-CHEST": "RIGHT_CHEST",
    "LEFT-COLLAR": "LEFT_COLLAR",
    "RIGHT-COLLAR": "RIGHT_COLLAR",
    "LEFT-BICEP": "LEFT_BICEP",
    "RIGHT-BICEP": "RIGHT_BICEP",
    "LEFT-SLEEVE": "LEFT_SLEEVE",
    "RIGHT-SLEEVE": "RIGHT_SLEEVE",
    "LEFT-CUFF": "LEFT_CUFF",
    "RIGHT-CUFF": "RIGHT_CUFF",
    "LEFT-HIP": "LEFT_HIP",
    "RIGHT-HIP": "RIGHT_HIP",
    "LEFT-THIGH-HIGH": "LEFT_THIGH_HIGH",
    "RIGHT-THIGH-HIGH": "RIGHT_THIGH_HIGH",
    "ON-POCKET": "ON_POCKET",
    
    # Back regions
    "FULL-BACK": "FULL_BACK",
    "BACK-YOKE": "BACK_YOKE",
}


# Singleton OBB detector instance (lazy loaded)
_obb_detector = None
_detection_cache = {}


def _get_obb_detector():
    """Get or create the OBB detector singleton."""
    global _obb_detector
    if _obb_detector is None:
        print("[GarmentDetector] Initializing OBB detector...")
        _obb_detector = OBBGarmentDetector()
        print("[GarmentDetector] OBB detector ready.")
    return _obb_detector


def _get_cached_regions(imagePath):
    """Get cached detection results for an image."""
    global _detection_cache
    
    # Create cache key from path and mtime
    try:
        mtime = os.path.getmtime(imagePath)
    except:
        mtime = 0
    
    key = (os.path.abspath(imagePath), mtime)
    
    if key not in _detection_cache:
        detector = _get_obb_detector()
        regions = detector.detect(imagePath)
        _detection_cache[key] = {r.class_name: r for r in regions}
    
    return _detection_cache[key]


def _normalize_location(locationName):
    """Normalize location name to match LOCATION_MAP keys."""
    if not locationName:
        return ""
    # Uppercase and replace spaces with hyphens
    normalized = str(locationName).strip().upper().replace(" ", "-").replace("_", "-")
    return normalized


def _get_obb_class_name(locationName):
    """Convert Excel location name to OBB class name."""
    normalized = _normalize_location(locationName)
    return LOCATION_MAP.get(normalized, normalized.replace("-", "_"))


def getCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """
    Get (x, y) coordinates for logo placement using OBB detector.
    
    Args:
        imagePath: Path to the garment image.
        locationName: Location name (e.g., "LEFT-CHEST", "FULL-FRONT").
        originalLocation: Optional, original location context (for combo positions).
        debug: Enable debug output.
        
    Returns:
        (x, y) tuple of coordinates, or None if region not found.
    """
    try:
        regions = _get_cached_regions(imagePath)
        obb_name = _get_obb_class_name(locationName)
        
        if debug:
            print(f"[getCoordinates] Looking for '{obb_name}' in {list(regions.keys())}")
        
        if obb_name in regions:
            region = regions[obb_name]
            coords = (int(region.center[0]), int(region.center[1]))
            if debug:
                print(f"[getCoordinates] Found {obb_name} at {coords}")
            return coords
        
        # Not found
        if debug:
            print(f"[getCoordinates] Region '{obb_name}' not found!")
        return None
        
    except Exception as e:
        print(f"[getCoordinates] Error: {e}")
        return None


def getLogoScale(imagePath, locationName, baseSize=(200, 100)):
    """
    Get (width, height) for logo based on OBB placement config.
    
    Args:
        imagePath: Path to the garment image.
        locationName: Location name.
        baseSize: Default base size (unused, kept for interface compatibility).
        
    Returns:
        (width, height) tuple for the logo.
    """
    obb_name = _get_obb_class_name(locationName)
    config = PLACEMENT_CONFIG.get(obb_name, {"base_size": 99})
    base = config.get("base_size", 99)
    
    # Return square size based on config
    return (base, base)


def getRotation(imagePath, locationName):
    """
    Get rotation angle for logo placement using OBB detector.
    
    The rotation angle comes directly from the OBB bounding box orientation.
    Logo should be rotated by this angle to align with the garment region.
    
    Args:
        imagePath: Path to the garment image.
        locationName: Location name.
        
    Returns:
        Rotation angle in degrees (for OpenCV/Photoshop).
    """
    try:
        regions = _get_cached_regions(imagePath)
        obb_name = _get_obb_class_name(locationName)
        
        if obb_name in regions:
            region = regions[obb_name]
            # Return negated angle (OBB uses counterclockwise, Photoshop uses clockwise)
            return -region.angle
        
        return 0.0
        
    except Exception as e:
        print(f"[getRotation] Error: {e}")
        return 0.0


# ============================================
# Legacy compatibility functions
# ============================================

def getGarmentCoordinates(imagePath, locationName, originalLocation=None, debug=False):
    """Legacy function name - calls getCoordinates."""
    return getCoordinates(imagePath, locationName, originalLocation, debug)


def getGarmentLogoScale(imagePath, locationName, baseLogoSize=(200, 100)):
    """Legacy function name - calls getLogoScale."""
    return getLogoScale(imagePath, locationName, baseLogoSize)


def getGarmentRotationAngle(imagePath, locationName):
    """Legacy function name - calls getRotation."""
    return getRotation(imagePath, locationName)


# ============================================
# Testing
# ============================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python garmentDetector.py <image_path> [location]")
        sys.exit(1)
    
    img_path = sys.argv[1]
    location = sys.argv[2] if len(sys.argv) > 2 else "FULL-FRONT"
    
    print(f"\nTesting OBB Garment Detector")
    print(f"Image: {img_path}")
    print(f"Location: {location}")
    print("-" * 40)
    
    coords = getCoordinates(img_path, location, debug=True)
    scale = getLogoScale(img_path, location)
    rotation = getRotation(img_path, location)
    
    print(f"\nResults:")
    print(f"  Coordinates: {coords}")
    print(f"  Logo Scale: {scale}")
    print(f"  Rotation: {rotation:.1f}°")
