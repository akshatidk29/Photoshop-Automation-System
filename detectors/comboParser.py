"""
Combo Position Parser
Parses position names from Excel into individual position components.
Uses positionRegistry.yaml for configuration.
"""

from configuration.configLoader import (
    getCanonicalName,
    getComboMappings,
    isComboPosition as isComboPositionCheck
)

def _getComboMappings():
    """Get combo position mappings."""
    return getComboMappings()

def isComboPosition(locationName):
    """Check if a position is a combo position (requires multiple logos)."""
    return isComboPositionCheck(locationName)

def parseComboPosition(locationName):
    """
    Parse a combo position into list of individual positions.
    Returns list of canonical position names.
    Single positions return [canonicalName].
    Combo positions return [pos1, pos2, ...].
    """
    # 1. First cleanup/normalize
    canonical = getCanonicalName(locationName)
    
    # 2. Check if it's a known combo in the registry
    combos = getComboMappings()
    
    # Standardize input for lookup comparison (uppercase, no spaces/hyphens for key matching mostly?)
    # But getCanonicalName already handles aliases. 
    # If the canonical name itself is a combo key (e.g. "FULL-BACK-&-FULL-FRONT"),
    # then it should be in the combos dict.
    
    # Check direct canonical match against combo keys
    if canonical in combos:
        return list(combos[canonical])
    
    # Check normalized input against combo keys
    # (Just in case canonical resolution didn't catch a complex combo alias)
    # The configLoader's getCanonicalName should handle most aliases.
    
    # 3. Check for implicit "&" separation if not explicitly in registry
    # (Though ideally all supported combos should be in registry)
    if "&" in locationName:
        parts = locationName.split("&")
        result = [getCanonicalName(p.strip()) for p in parts]
        return result
        
    # 4. If not a generic combo, it's a single position
    return [canonical]

def getPositionCount(locationName):
    """Get the number of logo placements needed for a position."""
    return len(parseComboPosition(locationName))


