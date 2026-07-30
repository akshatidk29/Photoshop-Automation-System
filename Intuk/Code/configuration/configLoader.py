"""Loads and manages YAML configuration files."""

import re
import yaml
from pathlib import Path
from itertools import product as iterProduct

# Configuration directory path
CONFIG_DIR = Path(__file__).parent

# Cache for loaded configurations
_configCache = {}


def _loadYaml(filename):
    """Load a YAML file from the configuration directory."""
    filepath = CONFIG_DIR / filename
    
    if filename in _configCache:
        return _configCache[filename]
    
    if not filepath.exists():
        print(f"[Config] Warning: {filename} not found, using defaults")
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
            _configCache[filename] = data
            return data
    except Exception as e:
        print(f"[Config] Error loading {filename}: {e}")
        return {}



# Position Registry

def getPositionRegistry():
    """Get the master position registry configuration."""
    return _loadYaml('positions/positionRegistry.yaml')


def getCanonicalName(positionName):
    """Resolve any alias/variation to canonical position name."""
    if not positionName:
        return ""
        
    registry = getPositionRegistry()
    positions = registry.get('positions', {})
    
    # Normalize input
    cleanInput = str(positionName).strip().upper().replace(" ", "-").replace("&", "-")
    cleanInput = "-".join(filter(None, cleanInput.split("-")))
    
    # Check if it IS a canonical name
    if cleanInput in positions:
        return cleanInput
        
    # Check against normalized keys (Handle spaces/parens in keys)
    for key in positions:
        normKey = str(key).strip().upper().replace(" ", "-").replace("&", "-")
        normKey = "-".join(filter(None, normKey.split("-")))
        if normKey == cleanInput:
            return key
        
    # Check aliases
    for canonical, data in positions.items():
        aliases = data.get('aliases', [])

        for alias in aliases:
 
            aliasNorm = str(alias).strip().upper().replace(" ", "-").replace("&", "-")
            aliasNorm = "-".join(filter(None, aliasNorm.split("-")))
            if aliasNorm == cleanInput:
                return canonical
        
    # normalized input if unknown
    return cleanInput


def getPositionData(positionName):
    """
    Get the full metadata for a position.
    """
    canonical = getCanonicalName(positionName)
    registry = getPositionRegistry()
    return registry.get('positions', {}).get(canonical, {})


def getObbClassName(positionName):

    # Get the OBB model class name for a position.
    canonical = getCanonicalName(positionName)
    data = getPositionData(positionName)
    
    # Check for explicit obbClass mapping
    if data and 'obbClass' in data:
        return data['obbClass']
    
    # normalize canonical name to model format
    obbClass = canonical.replace("-", "_").replace(" ", "_")
    obbClass = obbClass.replace("(", "").replace(")", "")
    return obbClass


class PositionNotFoundError(Exception):
    """Raised when a position is not found in the registry."""
    pass


def getGarmentType(positionName, partId=None):
    """Determine garment type from position. Raises PositionNotFoundError if not found."""

    data = getPositionData(positionName)
    if data and 'type' in data:
        return data['type']
    
    # Position not found in registry
    raise PositionNotFoundError(
        f"Position '{positionName}' not found in positionRegistry.yaml. "
        f"Please add this position to the registry or check for typos."
    )


def getGarmentTypeForPositions(positions, partId=None):
    """Determine garment type from list of positions. Uses first valid position's type."""
    if not positions:
        raise PositionNotFoundError("No positions provided to determine garment type.")
    
    registry = getPositionRegistry()
    positionsData = registry.get('positions', {})
    
    # Check each position for its type
    for pos in positions:
        if pos in positionsData:
            posData = positionsData[pos]
            if 'type' in posData:
                return posData['type']
    
    # No position had a type defined - raise error
    raise PositionNotFoundError(
        f"None of the positions {positions} have a 'type' defined in positionRegistry.yaml. "
        f"Please add the 'type' field to these positions in the registry."
    )


def getRotationThreshold():
    """Get rotation threshold in degrees from settings."""
    registry = getPositionRegistry()
    return registry.get('settings', {}).get('rotation_threshold', 15)


def validatePosition(positionName):
    """
    Check if a position is valid (either canonical, alias, or combo).
    Returns:
        (isValid, canonicalName)
    """

    canonical = getCanonicalName(positionName)
    registry = getPositionRegistry()
    
    # Check if it exists in main positions OR combo mappings
    if canonical in registry.get('positions', {}):
        return True, canonical
        
    return False, canonical


# Column Mapping Functions

def getColumnMapping():
    """Get the column mapping configuration."""
    return _loadYaml('excel/columnMapping.yaml')


def findColumnName(dfColumns, internalName):
    """
    Find the actual Excel column name for an internal field name.
    """
    import re
    
    def cleanName(name):
        if name is None: return ''
        s = re.sub(r'_x[0-9a-fA-F]{4}_', '', str(name))
        s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
        return s.strip()
    
    cleanToOriginal = {cleanName(col): col for col in dfColumns}
    cleanedColumns = list(cleanToOriginal.keys())
    
    mapping = getColumnMapping()
    columns = mapping.get('columns', {})
    variations = columns.get(internalName, [])
    
    for variation in variations:
        cleanVar = cleanName(variation)
        if cleanVar in cleanedColumns:
            return cleanToOriginal[cleanVar]
            
    cleanedColumnsLower = {col.lower(): col for col in cleanedColumns}
    for variation in variations:
        cleanVarLower = cleanName(variation).lower()
        if cleanVarLower in cleanedColumnsLower:
            return cleanToOriginal[cleanedColumnsLower[cleanVarLower]]
            
    return None



# Color Alias Functions

def getColorAliasesConfig():
    """Get color alias configuration."""
    return _loadYaml('colors/colorAliases.yaml')


def getCompoundParts():
    """
    Get comprehensive list of known color tokens for boundary-aware matching.
    Includes all alias keys and full names from colorAliases.yaml.
    Filters out single-letter aliases to prevent false positives (e.g. 'b' matching 'Back').
    """
    config = getColorAliasesConfig()
    
    # Start with explicit compound parts if any
    parts = set(p.lower() for p in config.get('compoundParts', []))
    
    # Add all keys (abbreviations) and values (full names) from aliases map
    aliases = config.get('aliases', {})
    for abbrev, fulls in aliases.items():
        if len(abbrev) > 1:  # specific check to avoid single chars
            parts.add(abbrev.lower())
        
        if isinstance(fulls, list):
            for full in fulls:
                # Add individual words from full name
                # e.g. "dark heather" -> "dark", "heather"
                for word in full.split():
                    w = word.lower().strip()
                    if len(w) > 1:
                        parts.add(w)
    
    # Return sorted by length (descending) so longest matches match first
    return sorted(list(parts), key=len, reverse=True)


# Cached reverse alias map: full name -> set of abbreviations
_reverseAliasMap = None

def _getReverseAliasMap(aliases):
    """Build and cache reverse lookup: full_name -> {abbreviations}."""
    global _reverseAliasMap
    if _reverseAliasMap is not None:
        return _reverseAliasMap
    
    _reverseAliasMap = {}
    for abbrev, fulls in aliases.items():
        if not isinstance(fulls, list):
            continue
        for full in fulls:
            if not isinstance(full, str):
                continue
            for key in (full.lower().replace(" ", ""), full.lower()):
                if key not in _reverseAliasMap:
                    _reverseAliasMap[key] = set()
                _reverseAliasMap[key].add(abbrev)
    return _reverseAliasMap


def _expandSingleColor(colorWord, aliases):
    """
    Expand a single color word to all its variants.
    Returns set of variants for one word (e.g., "grey" -> {"grey", "gray", "gry", "gy"})
    """
    colorWord = colorWord.lower().strip()
    if not colorWord:
        return set()
    
    variants = {colorWord}
    
    # Check if this word IS an abbreviation - add full names
    if colorWord in aliases:
        fullList = aliases[colorWord]
        if isinstance(fullList, list):
            for full in fullList:
                if isinstance(full, str):
                    variants.add(full.lower().replace(" ", ""))
    
    # Reverse lookup: check if this word is a full name -> get abbreviations (O(1) dict lookup)
    reverseMap = _getReverseAliasMap(aliases)
    if colorWord in reverseMap:
        variants.update(reverseMap[colorWord])
    
    return variants


# Pre-compiled regex for CamelCase splitting
_CAMEL_CASE_RE = re.compile(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+')

def _splitCamelCase(text):
    """
    Split a CamelCase or PascalCase string into words.
    E.g., "SmokeGreyWhite" -> ["Smoke", "Grey", "White"]
    """
    words = _CAMEL_CASE_RE.findall(text)
    return words if words else [text]


# Cache for expandColorVariants results
_colorVariantCache = {}

def expandColorVariants(colorName):
    """
    Generate a set of variant strings for a color name. Results are cached.
    
    Handles:
    1. Colors with "/" treated as word separator (e.g., "Black/ White" -> "blackwhite")
       Sequence order is preserved: "blackwhite" matches, "whiteblack" does NOT
    2. Compound colors (e.g., "Shadow Grey" or "ShadowGrey") - expands each word and combines
    3. CamelCase colors (e.g., "SmokeGreyWhite") - splits and expands
    4. Abbreviations in either direction (e.g., "gry" <-> "grey") while preserving order
    5. Exact matching - no optional word dropping
    
    Example: "Steel Grey" could match:
    - "steelgrey", "steelgray", "stlgrey", "stlgray", "stgrey", etc.
    - But NOT "greysteel", "graysteel", etc. (wrong order)
    """
    if not colorName:
        return set()
    
    # Check cache first
    cacheKey = str(colorName).strip()
    if cacheKey in _colorVariantCache:
        return _colorVariantCache[cacheKey]
    
    config = getColorAliasesConfig()
    aliases = config.get('aliases', {})
    
    variants = set()
    
    # Treat "/" as a word separator (like a space), NOT as OR
    # "Black/ White" -> single compound color "Black White" -> "blackwhite"
    normalizedColor = str(colorName).replace("/", " ").strip()
    # Clean up extra spaces from "Black/ White" -> "Black  White" -> "Black White"  
    normalizedColor = re.sub(r'\s+', ' ', normalizedColor)
    
    # Add the fully normalized version (no spaces, no separators, lowercase)
    fullNormalized = normalizedColor.lower().replace(" ", "").replace("-", "")
    variants.add(fullNormalized)
    
    # Also add the lowercase with spaces version
    variants.add(normalizedColor.lower())
    
    # Check if the FULL normalized color is an alias key (for complex patterns)
    if fullNormalized in aliases:
        fullList = aliases[fullNormalized]
        if isinstance(fullList, list):
            for full in fullList:
                if isinstance(full, str):
                    variants.add(full.lower().replace(" ", ""))
    
    # Split into words: spaces and "-" are word boundaries
    words = re.split(r'[\s\-]+', normalizedColor)
    words = [w.strip() for w in words if w.strip()]
    
    # If single word with no spaces, try CamelCase split
    if len(words) == 1 and len(words[0]) > 3:
        camelWords = _splitCamelCase(words[0])
        if len(camelWords) > 1:
            words = camelWords
    
    def generateOrderedCombinations(wordList):
        """Generate all combinations of word variants, preserving original word order."""
        if not wordList:
            return set()
        
        wordVariantLists = []
        for word in wordList:
            wordVariants = _expandSingleColor(word.lower(), aliases)
            if not wordVariants:
                wordVariants = {word.lower()}
            wordVariantLists.append(wordVariants)
        
        result = set()
        for combo in iterProduct(*wordVariantLists):
            # Words are concatenated in their ORIGINAL order
            result.add("".join(combo))
        return result
    
    if len(words) == 1:
        # Single word - just expand it
        wordVariants = _expandSingleColor(words[0], aliases)
        variants.update(wordVariants)
    else:
        # Multiple words - expand each and create ordered combinations
        variants.update(generateOrderedCombinations(words))
    
    # Filter out empty strings
    variants = {v for v in variants if v}
    
    # Cache the result
    _colorVariantCache[cacheKey] = variants
    
    return variants

# Logo Size Functions

def getPositionType(positionName):
    """
    Return 'front', 'back' or 'side' for a position.
    """

    data = getPositionData(positionName)
    if data and 'view' in data:
        return data['view']
        
    return 'front'


def isBackPosition(positionName):
    """
    Check if a position requires a back view.
    
    Args:
        positionName: Single position name (e.g., 'FULL-BACK', 'LEFT-CHEST')
        
    Returns:
        True if position requires back view, False otherwise
    """
    return getPositionType(positionName) == 'back'


def hasAnyBackPosition(positions):
    """
    Check if any position in the list requires a back view.
    
    Args:
        positions: List of position names
        
    Returns:
        True if at least one position requires back view, False otherwise
    """
    if not positions:
        return False
    
    for pos in positions:
        if isBackPosition(pos):
            return True
    
    return False


def isCapDualViewPosition(positionName):
    """
    Check if a CAP position requires dual-view (CAP-BACK or CAP-SIDE).
    
    Args:
        positionName: Single position name
        
    """
    posType = getPositionType(positionName)
    
    return posType in ('back', 'side')
    

def hasCapDualViewPosition(positions):
    """
    Check if any CAP position in the list requires dual-view.
    
    Args:
        positions: List of position names
        
    Returns:
        True if at least one CAP position requires dual-view, False otherwise
    """
    if not positions:
        return False
    
    for pos in positions:
        if isCapDualViewPosition(pos):
            return True
    
    return False


def getPositionViewType(positionName):
    """
    Get the view type for a position (front, back, or side).
    Also returns the garment type.
    
    Args:
        positionName: Position name
        
    Returns:
        tuple: (viewType, garmentType) e.g., ('front', 'CAP') or ('back', 'T-SHIRT')
    """
    data = getPositionData(positionName)
    if data:
        viewType = data.get('view', 'front')
        garmentType = data.get('type', 'T-SHIRT')
        return (viewType, garmentType)
    
    return ('front', 'T-SHIRT')


def getLogoSizesConfig():
    return _loadYaml('positions/logoSizes.yaml')

def getDefaultLogoSize(position):
    config = getLogoSizesConfig()
    # Normalize position first used canonical name
    canonical = getCanonicalName(position)
    
    positions = config.get('positions', {})
    defaultSize = config.get('defaultSize', 99)
    
    # Try canonical
    if canonical in positions:
        return positions[canonical]
        
    # Try finding loop
    for key, val in positions.items():
        # Check if key is alias of our position
        if getCanonicalName(key) == canonical:
            return val
            
    return defaultSize


# Constants & Helpers

def getFrontIndicators():
    return _loadYaml('images/filenamePatterns.yaml').get('frontIndicators', [])

def getBackIndicators():
    return _loadYaml('images/filenamePatterns.yaml').get('backIndicators', [])

def getSideIndicators():
    return _loadYaml('images/filenamePatterns.yaml').get('sideIndicators', [])

def getAllowedExtensions():
    return ['.' + e.lstrip('.') for e in _loadYaml('images/filenamePatterns.yaml').get('allowedExtensions', ['jpg','png'])]


# GUI / Advanced Settings Helpers

def getAllLogoSizes():
    """Get all configured logo sizes for the GUI."""
    config = getLogoSizesConfig()
    return config.get('positions', {})

def getLogoSizeForPosition(position, configOverride=None):
    """
    Get the specific logo size for a position.
    """
    if configOverride is not None:
        # Use provided config
        canonical = getCanonicalName(position)
        
        # Handle both nested config (like YAML) and flat dict (like GUI state)
        if 'positions' in configOverride and isinstance(configOverride['positions'], dict):
             positions = configOverride['positions']
             defaultSize = configOverride.get('defaultSize', 99)
        else:
             positions = configOverride
             defaultSize = 99
        
        # Try canonical
        if canonical in positions:
            try:
                return int(positions[canonical])
            except:
                return defaultSize
            
        # Try finding alias/match
        for key, val in positions.items():
            if getCanonicalName(key) == canonical:
                try:
                    return int(val)
                except:
                    return defaultSize
                
        return defaultSize
        
    return getDefaultLogoSize(position)


def getClippingConfig():
    """Get the clipping configuration."""
    return _loadYaml('positions/clippingPositions.yaml')

def getAllClippingPositions():
    """Get list of positions enabled for clipping."""
    config = getClippingConfig()
    return config.get('positions', {})


# IMAGE LAYOUT SETTINGS

def getLayoutSettings():
    """Get all image layout settings."""
    return _loadYaml('images/layoutSettings.yaml')


def getDualViewSettings(imageType='tshirt'):
    """
    Returns: dict with canvas dimensions, scale percentages, and edge margin settings
    """
    settings = getLayoutSettings()
    dualSettings = settings.get('dualView', {})
    return dualSettings.get(imageType, {})


def getBackgroundRemovalSettings():
    settings = getLayoutSettings()
    return settings.get('backgroundRemoval', {
        'alphaMatting': True,
        'alphaMattingForegroundThreshold': 240,
        'alphaMattingBackgroundThreshold': 20,
        'alphaMattingErodeSize': 10
    })


def getOutputSettings():
    """Get output settings (jpeg quality, etc)."""
    settings = getLayoutSettings()
    return settings.get('output', {'jpegQuality': 95})

def isClippingEnabledGlobal():
    """Check if clipping is enabled globally."""
    config = getClippingConfig()
    return config.get('clippingEnabled', False)


def _saveYaml(filename, data):
    """Save data to a YAML file in the configuration directory."""
    filepath = CONFIG_DIR / filename
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        _configCache[filename] = data
        return True
    except Exception as e:
        print(f"[Config] Error saving {filename}: {e}")
        return False


def updateLogoSize(positionName, newSize):
    """Update the logo size for a specific position in the config."""
    try:
        data = getLogoSizesConfig()
        canonical = getCanonicalName(positionName)
        if 'positions' not in data:
            data['positions'] = {}
        data['positions'][canonical] = int(newSize)
        return _saveYaml('positions/logoSizes.yaml', data)
    except Exception as e:
        print(f"[Config] Failed to update logo size: {e}")
        return False


def updateClippingConfig(globalEnabled=None, positions=None):
    """Update clipping configuration."""
    try:
        data = getClippingConfig()
        if globalEnabled is not None:
            data['clippingEnabled'] = bool(globalEnabled)
        if positions:
            if 'positions' not in data:
                data['positions'] = {}
            for pos, enabled in positions.items():
                canonical = getCanonicalName(pos)
                data['positions'][canonical] = bool(enabled)
        return _saveYaml('positions/clippingPositions.yaml', data)
    except Exception as e:
        print(f"[Config] Failed to update clipping config: {e}")
        return False
