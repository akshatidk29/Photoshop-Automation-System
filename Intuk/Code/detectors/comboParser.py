import re
from configuration.configLoader import (
    getCanonicalName,
)

def parseComboPosition(locationName):
    """
    Parse a combo position into list of individual positions.
    Returns list of canonical position names.
    Single positions return [canonicalName].
    """
    if not locationName or not str(locationName).strip():
        return []
    
    locationStr = str(locationName).strip()
    
    # Priority 1: Check for comma-separated positions
    if "," in locationStr:
        parts = locationStr.split(",")
        result = []
        for part in parts:
            part = part.strip()
            if part:
                canonical = getCanonicalName(part)
                if canonical:
                    result.append(canonical)
        if result:  # If we successfully parsed any positions
            return result
    
    # Priority 2: Check for "&" separation
    if "&" in locationStr:
        parts = locationStr.split("&")
        result = []
        for part in parts:
            part = part.strip()
            if part:
                canonical = getCanonicalName(part)
                if canonical:
                    result.append(canonical)
        if len(result) >= 2:
            return result
    
    # Priority 3: Single position fallback
    canonical = getCanonicalName(locationStr)
    return [canonical]

