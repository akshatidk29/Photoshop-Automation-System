import os
import re

def ensureFolder(path):
    """Create folder if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def cleanFilename(name):
    """Sanitize filename by removing illegal characters."""
    return "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).rstrip()



from configuration.configLoader import (
    getCanonicalName, 
    getGarmentType
)

def normalizeLocation(locationName):
    """
    Standardize location strings using the configuration registry.
    Maps aliases to their canonical names.
    """
    return getCanonicalName(locationName)

def detectGarmentTypeFromLocation(locationName, partId=None):
    """
    Returns category: T-SHIRT (includes Dual), CAP, BAG, BLANKET.
    Uses centralized configuration registry.
    
    Raises:
        PositionNotFoundError: If position is not found in positionRegistry.yaml
    """
    return getGarmentType(locationName, partId)

def parseCustomSize(sizeText):
    """Returns parsed size(s) from text. Supports multiple formats:
    
    Single size formats:
    - "150x200" or "150 x 200" → (150.0, 200.0)
    - "150" → 150.0 (width-only)
    
    Multiple sizes (comma-separated) for multi-position:
    - "99,120" → [99.0, 120.0]
    - "99x150,120x180" → [(99.0, 150.0), (120.0, 180.0)]
    - "99,120x180" → [99.0, (120.0, 180.0)]  (mixed)
    
    Returns:
    - None if invalid
    - float for single width
    - tuple (width, height) for single WxH
    - list of floats/tuples for comma-separated multiple sizes
    """
    if not sizeText:
        return None

    text = str(sizeText).strip()

    if text.lower() in ["nan", "none", "-", ""]:
        return None

    # Check for comma-separated multiple sizes
    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        sizes = []
        for part in parts:
            parsed = _parseSingleSize(part)
            if parsed is not None:
                sizes.append(parsed)
        # Return list only if we got valid sizes
        return sizes if sizes else None
    
    # Single size
    return _parseSingleSize(text)


def _parseSingleSize(text):
    """Parse a single size value (helper for parseCustomSize).
    
    Returns:
    - float for width-only (e.g., "150")
    - tuple (width, height) for WxH (e.g., "150x200")
    - None if invalid
    """
    if not text:
        return None
    
    text = str(text).strip().lower()
    if text in ["nan", "none", "-", ""]:
        return None

    match = re.findall(r"(\d+)", text)
    if len(match) == 2:
        width = float(match[0])
        height = float(match[1])
        return (width, height)
    elif len(match) == 1:
        return float(match[0])

    return None
