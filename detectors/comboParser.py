"""
Combo Position Parser
Parses position names from Excel into individual position components.
Uses positionRegistry.yaml for configuration.
"""

import re
from configuration.configLoader import (
    getCanonicalName,
    getComboMappings,
    isComboPosition as isComboPositionCheck,
    getPositionRegistry
)

def _getComboMappings():
    """Get combo position mappings."""
    return getComboMappings()

def isComboPosition(locationName):
    """Check if a position is a combo position (requires multiple logos)."""
    return isComboPositionCheck(locationName)


def _getAllKnownPositionPatterns():
    """
    Get all known position names and their aliases for pattern matching.
    Returns a dict: {normalized_pattern: canonical_name}
    Patterns are sorted by length (longest first) to match greedily.
    """
    registry = getPositionRegistry()
    positions = registry.get('positions', {})
    
    patterns = {}
    for canonical, data in positions.items():
        # Add canonical name
        norm = canonical.upper().replace("-", " ").replace("_", " ")
        patterns[norm] = canonical
        
        # Add aliases
        for alias in data.get('aliases', []):
            norm = str(alias).upper().replace("-", " ").replace("_", " ")
            patterns[norm] = canonical
    
    return patterns


def _tryExtractMultiplePositions(locationName):
    """
    Try to extract multiple known positions from a combined string.
    E.g., "Right Chest Left Chest" -> ["RIGHT-CHEST", "LEFT-CHEST"]
    
    Uses an interval scheduling algorithm to maximize the number of
    non-overlapping position matches found in the input string.
    
    Returns list of canonical positions if found, else None.
    """
    # Normalize input: uppercase, convert separators to spaces
    text = str(locationName).upper().replace("-", " ").replace("_", " ").replace("&", " ")
    text = " ".join(text.split())  # Normalize whitespace
    
    patterns = _getAllKnownPositionPatterns()
    if not patterns:
        return None
    
    # Find ALL possible matches with their start/end positions
    allMatches = []  # List of (startIdx, endIdx, canonical, pattern)
    
    for pattern, canonical in patterns.items():
        # Use word boundary matching via regex
        escapedPattern = re.escape(pattern)
        # Match at word boundaries
        regex = r'(?:^|(?<=\s))(' + escapedPattern + r')(?=\s|$)'
        
        for match in re.finditer(regex, text):
            startIdx = match.start(1)
            endIdx = match.end(1)
            allMatches.append((startIdx, endIdx, canonical, pattern))
    
    if not allMatches:
        return None
    
    # Use interval scheduling algorithm to maximize number of non-overlapping matches
    # Sort by END position (greedy interval scheduling for maximum count)
    allMatches.sort(key=lambda x: x[1])
    
    selectedMatches = []
    lastEnd = -1
    
    for startIdx, endIdx, canonical, pattern in allMatches:
        # If this interval doesn't overlap with the last selected one
        if startIdx >= lastEnd:
            selectedMatches.append((startIdx, canonical))
            lastEnd = endIdx
    
    # Sort by position in original string to preserve input order
    selectedMatches.sort(key=lambda x: x[0])
    
    # Extract canonical names, removing duplicates while preserving order
    found = []
    seen = set()
    for _, canonical in selectedMatches:
        if canonical not in seen:
            found.append(canonical)
            seen.add(canonical)
    
    # Only return if we found at least 2 positions (otherwise it's a single position)
    if len(found) >= 2:
        return found
    
    return None


def parseComboPosition(locationName):
    """
    Parse a combo position into list of individual positions.
    Returns list of canonical position names.
    Single positions return [canonicalName].
    Combo positions return [pos1, pos2, ...].
    
    Handles:
    - "&" separated positions (e.g., "Left Chest & Right Bicep")
    - Space/hyphen separated known positions (e.g., "Right Chest Left Chest")
    - Explicit combos from registry as fallback
    """
    if not locationName or not str(locationName).strip():
        return []
    
    # 1. Check for implicit "&" separation first (explicit intent)
    if "&" in locationName:
        parts = locationName.split("&")
        result = [getCanonicalName(p.strip()) for p in parts if p.strip()]
        if len(result) >= 2:
            return result
    
    # 2. Try to extract multiple known positions from the ORIGINAL string
    # This must happen BEFORE getCanonicalName() which might merge positions
    # Handles: "Right Chest Left Chest", "LEFT-CHEST-RIGHT-BICEP", "LFT-CHEST-RGT-BICEP"
    extracted = _tryExtractMultiplePositions(locationName)
    if extracted:
        return extracted
    
    # 3. Get canonical form for single position fallback
    canonical = getCanonicalName(locationName)
    
    # 4. Check if canonical form is a known combo in the registry (legacy support)
    combos = getComboMappings()
    if canonical in combos:
        return list(combos[canonical])
    
    # 5. If nothing else worked, it's a single position
    return [canonical]
    return [canonical]

def getPositionCount(locationName):
    """Get the number of logo placements needed for a position."""
    return len(parseComboPosition(locationName))


