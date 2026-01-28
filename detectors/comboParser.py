"""
Combo Position Parser
Parses position names from Excel into individual position components.
Uses positionAliases.yaml for configuration.
"""

from core.utils import VALID_LOCATIONS

# Try to load from YAML config, fall back to hardcoded values
try:
    from configuration.configLoader import (
        getPositionAliases, getValidPositions, getComboMappings
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False


def _getPositionAliases():
    """Get position aliases (from YAML or fallback)."""
    if CONFIG_AVAILABLE:
        return getPositionAliases()
    # Fallback hardcoded values
    return {
        "BAG-FRONT": "FRONT (ON BAG)",
        "FRONT-ON-BAG": "FRONT (ON BAG)",
        "BAG-POCKET": "ON POCKET (ON BAG)",
        "CAP-FRONT": "FRONT-CROWN",
        "CORNER-TOWEL": "CORNER-ANGLED-TOWEL",
    }


def _getSinglePositions():
    """Get valid single positions (from YAML or fallback)."""
    if CONFIG_AVAILABLE:
        return getValidPositions()
    # Fallback hardcoded values
    return {
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


def _getComboMappings():
    """Get combo position mappings (from YAML or fallback)."""
    if CONFIG_AVAILABLE:
        return getComboMappings()
    # Fallback hardcoded values
    return {
        "FULL-BACK & FULL-FRONT": ["FULL-BACK", "FULL-FRONT"],
        "FULL-FRONT-FULL-BACK": ["FULL-FRONT", "FULL-BACK"],
        "LEFT-BICEP-RIGHT-BICEP": ["LEFT-BICEP", "RIGHT-BICEP"],
    }


def isComboPosition(locationName):
    """Check if a position is a combo position (requires multiple logos)."""
    normalized = str(locationName).strip().upper().replace(" ", "-")
    
    comboMappings = _getComboMappings()
    singlePositions = _getSinglePositions()
    
    # Check explicit mappings first
    if normalized in comboMappings:
        return True
    
    # Check for & separator
    if " & " in locationName.upper() or "&" in locationName:
        return True
    
    # Check if it's a known single position
    if normalized in singlePositions:
        return False
    
    # Try to detect combo by counting position keywords
    positionCount = 0
    for pos in singlePositions:
        if pos in normalized:
            positionCount += 1
    
    return positionCount > 1


def parseComboPosition(locationName):
    """Parse a combo position into list of individual positions.
    
    Returns list of position names. Single positions return [positionName].
    Combo positions return [pos1, pos2, ...].
    """
    normalized = str(locationName).strip().upper().replace(" ", "-")
    
    positionAliases = _getPositionAliases()
    comboMappings = _getComboMappings()
    singlePositions = _getSinglePositions()
    
    # Check position aliases first (e.g., BAG-FRONT -> FRONT (ON BAG))
    if normalized in positionAliases:
        return [positionAliases[normalized]]
    
    # Check explicit combo mappings
    if normalized in comboMappings:
        return list(comboMappings[normalized])
    
    # Handle & separator
    if " & " in locationName.upper():
        parts = locationName.upper().split(" & ")
        result = []
        for p in parts:
            pNorm = p.strip().replace(" ", "-")
            result.append(positionAliases.get(pNorm, pNorm))
        return result
    
    if "&" in normalized:
        parts = normalized.split("&")
        result = []
        for p in parts:
            pNorm = p.strip()
            result.append(positionAliases.get(pNorm, pNorm))
        return result
    
    # Check if it's a known single position
    if normalized in singlePositions:
        return [normalized]
    
    # Try intelligent parsing - find all matching single positions
    foundPositions = []
    remaining = normalized
    
    # Sort by length (longest first) to avoid partial matches
    sortedPositions = sorted(singlePositions, key=len, reverse=True)
    
    for pos in sortedPositions:
        if pos in remaining:
            foundPositions.append(pos)
            remaining = remaining.replace(pos, "", 1)
    
    if foundPositions:
        return foundPositions
    
    # Fallback: check aliases one more time, then return normalized
    return [positionAliases.get(normalized, normalized)]


def getPositionCount(locationName):
    """Get the number of logo placements needed for a position."""
    return len(parseComboPosition(locationName))

