import os
import re

def ensureFolder(path):
    if not os.path.exists(path):
        os.makedirs(path)


def cleanFilename(name):
    return "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).rstrip()



from configuration.configLoader import (
    getCanonicalName, 
    getGarmentType
)

def normalizeLocation(locationName):
    return getCanonicalName(locationName)

def detectGarmentTypeFromLocation(locationName, partId=None):
    """
    Returns category: T-SHIRT (includes Dual), CAP, BAG, BLANKET.
    """
    return getGarmentType(locationName, partId)

def parseCustomSize(sizeText):
    """Parse size from text. Returns float, tuple (w,h), list, or None."""
    if not sizeText:
        return None

    text = str(sizeText).strip()

    if text.lower() in ["nan", "none", "-", ""]:
        return None

    # Comma-separated multiple sizes
    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        sizes = []
        for part in parts:
            parsed = _parseSingleSize(part)
            if parsed is not None:
                sizes.append(parsed)
        return sizes if sizes else None
    
    return _parseSingleSize(text)


def _parseSingleSize(text):
    """Parse single size: "150" → 150.0, "150x200" → (150.0, 200.0)."""
    if not text:
        return None
    
    text = str(text).strip().lower()
    if text in ["nan", "none", "-", ""]:
        return None

    match = re.findall(r"(\d+)", text)
    if len(match) == 2:
        return (float(match[0]), float(match[1]))
    elif len(match) == 1:
        return float(match[0])

    return None
