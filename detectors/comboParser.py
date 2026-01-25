from core.utils import VALID_LOCATIONS

SINGLE_POSITIONS = {
    "FULL-BACK", "FULL-FRONT",
    "LEFT-BICEP", "RIGHT-BICEP",
    "LEFT-CHEST", "RIGHT-CHEST",
    "LEFT-COLLAR", "RIGHT-COLLAR",
    "LEFT-CUFF", "RIGHT-CUFF",
    "LEFT-HIP", "RIGHT-HIP",
    "LEFT-SLEEVE", "RIGHT-SLEEVE",
    "LEFT-THIGH-HIGH", "RIGHT-THIGH-HIGH",
    "ON-POCKET", "BACK-YOKE",
    "FRONT-CROWN", "CAP-BACK", "CAP-SIDE", "CAP-FRONT-SIDE",
    "LOWER-LEFT-CROWN", "LOWER-RIGHT-CROWN",
    "CORNER-ANGLED-TOWEL", "FRONT_CENTER", "FRONT_NAPKIN",
    "FRONT (ON BAG)", "ON POCKET (ON BAG)"
}

# Known combo position mappings (explicit parsing for complex names)
COMBO_MAPPINGS = {
    "FULL-BACK & FULL-FRONT": ["FULL-BACK", "FULL-FRONT"],
    "FULL-FRONT-FULL-BACK": ["FULL-FRONT", "FULL-BACK"],
    "LEFT-BICEP-RIGHT-BICEP": ["LEFT-BICEP", "RIGHT-BICEP"],
    "LEFT-SLEEVE-RIGHT-SLEEVE": ["LEFT-SLEEVE", "RIGHT-SLEEVE"],
    "LEFT-CHEST-RIGHT-BICEP": ["LEFT-CHEST", "RIGHT-BICEP"],
    "LEFT-CHEST-RIGHT-SLEEVE": ["LEFT-CHEST", "RIGHT-SLEEVE"],
    "RIGHT-CHEST-LEFT-BICEP": ["RIGHT-CHEST", "LEFT-BICEP"],
    "RIGHT-CHEST-LEFT-SLEEVE": ["RIGHT-CHEST", "LEFT-SLEEVE"],
    "LEFT-CHEST-FULL-BACK": ["LEFT-CHEST", "FULL-BACK"],
    "RIGHT-CHEST-FULL-BACK": ["RIGHT-CHEST", "FULL-BACK"],
    "LEFT-CHEST-LEFT-BICEP-RIGHT-BICEP": ["LEFT-CHEST", "LEFT-BICEP", "RIGHT-BICEP"],
    "RIGHT-CHEST-LFT-BICEP-RIGHT-BICEP": ["RIGHT-CHEST", "LEFT-BICEP", "RIGHT-BICEP"],
}


def isComboPosition(locationName):
    """Check if a position is a combo position (requires multiple logos)."""
    normalized = str(locationName).strip().upper().replace(" ", "-")
    
    # Check explicit mappings first
    if normalized in COMBO_MAPPINGS:
        return True
    
    # Check for & separator
    if " & " in locationName.upper() or "&" in locationName:
        return True
    
    # Check if it's a known single position
    if normalized in SINGLE_POSITIONS:
        return False
    
    # Try to detect combo by counting position keywords
    positionCount = 0
    for pos in SINGLE_POSITIONS:
        if pos in normalized:
            positionCount += 1
    
    return positionCount > 1


def parseComboPosition(locationName):
    """Parse a combo position into list of individual positions.
    
    Returns list of position names. Single positions return [positionName].
    Combo positions return [pos1, pos2, ...].
    """
    normalized = str(locationName).strip().upper().replace(" ", "-")
    
    # Check explicit mappings first
    if normalized in COMBO_MAPPINGS:
        return COMBO_MAPPINGS[normalized]
    
    # Handle & separator
    if " & " in locationName.upper():
        parts = locationName.upper().split(" & ")
        return [p.strip().replace(" ", "-") for p in parts]
    
    if "&" in normalized:
        parts = normalized.split("&")
        return [p.strip() for p in parts]
    
    # Check if it's a known single position
    if normalized in SINGLE_POSITIONS:
        return [normalized]
    
    # Try intelligent parsing - find all matching single positions
    foundPositions = []
    remaining = normalized
    
    # Sort by length (longest first) to avoid partial matches
    sortedPositions = sorted(SINGLE_POSITIONS, key=len, reverse=True)
    
    for pos in sortedPositions:
        if pos in remaining:
            foundPositions.append(pos)
            # Remove to avoid double counting (but keep for multi-match)
            remaining = remaining.replace(pos, "", 1)
    
    if foundPositions:
        return foundPositions
    
    # Fallback: return as single position
    return [normalized]


def getPositionCount(locationName):
    """Get the number of logo placements needed for a position."""
    return len(parseComboPosition(locationName))
