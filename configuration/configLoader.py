"""
Configuration Loader Module
Loads and manages YAML configuration files for the automation system.
"""

import os
import yaml
import re
from pathlib import Path

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


def clearConfigCache():
    """Clear the configuration cache to force reload."""
    global _configCache
    _configCache = {}


# ============================================================================
# Position Registry (Master Configuration)
# ============================================================================

def getPositionRegistry():
    """Get the master position registry configuration."""
    return _loadYaml('positionRegistry.yaml')


def getCanonicalName(positionName):
    """
    Resolve any alias or variation to the canonical position name.
    
    Args:
        positionName: Any position string (e.g., "BAG-FRONT", "Front", "LC")
        
    Returns:
        Canonical name (e.g., "FRONT (ON BAG)", "FULL-FRONT", "LEFT-CHEST")
        Returns the input sanitized if no match found.
    """
    if not positionName:
        return ""
        
    registry = getPositionRegistry()
    positions = registry.get('positions', {})
    
    # Normalize input: UPPERCASE, replace spaces with hyphens, remove extra hyphens
    cleanInput = str(positionName).strip().upper().replace(" ", "-").replace("&", "-")
    cleanInput = "-".join(filter(None, cleanInput.split("-")))
    
    # 1. Check if it IS a canonical name (Exact Match)
    if cleanInput in positions:
        return cleanInput
        
    # 1b. Check against normalized keys (Handle spaces/parens in keys)
    # This handles "FRONT (ON BAG)" (key) vs "FRONT-(ON-BAG)" (input)
    for key in positions:
        normKey = str(key).strip().upper().replace(" ", "-").replace("&", "-")
        normKey = "-".join(filter(None, normKey.split("-")))
        if normKey == cleanInput:
            return key
        
    # 2. Check aliases
    # We build a reverse lookup map on the fly (or ideally cached)
    # For now, iterate (registry is small)
    for canonical, data in positions.items():
        aliases = data.get('aliases', [])
        # Check direct alias match
        for alias in aliases:
            # Normalize alias too just in case
            aliasNorm = str(alias).strip().upper().replace(" ", "-").replace("&", "-")
            aliasNorm = "-".join(filter(None, aliasNorm.split("-")))
            if aliasNorm == cleanInput:
                return canonical
                
    # 3. Check Combo Mappings
    combos = registry.get('comboMappings', {})
    if cleanInput in combos:
        return cleanInput
    
    # 3b. Check normalized Combo keys
    for key in combos:
        normKey = str(key).strip().upper().replace(" ", "-").replace("&", "-")
        normKey = "-".join(filter(None, normKey.split("-")))
        if normKey == cleanInput:
            return key
        
    # Return normalized input if unknown
    return cleanInput


def getPositionData(positionName):
    """
    Get the full metadata for a position.
    Resolves aliases first.
    """
    canonical = getCanonicalName(positionName)
    registry = getPositionRegistry()
    return registry.get('positions', {}).get(canonical, {})


def getObbClassName(positionName):
    """
    Get the OBB model class name for a position.
    
    Priority:
    1. Explicit 'obbClass' field in positionRegistry.yaml
    2. Normalized canonical name (replace hyphens/spaces with underscores)
    
    Args:
        positionName: Position name (any variation)
        
    Returns:
        OBB class name string (e.g., "FRONT", "LEFT_CHEST", "ON_POCKET")
    """
    canonical = getCanonicalName(positionName)
    data = getPositionData(positionName)
    
    # Check for explicit obbClass mapping
    if data and 'obbClass' in data:
        return data['obbClass']
    
    # Default: normalize canonical name to model format
    # Replace hyphens, spaces, parentheses with underscores
    obbClass = canonical.replace("-", "_").replace(" ", "_")
    obbClass = obbClass.replace("(", "").replace(")", "")
    return obbClass


def getGarmentType(positionName, partId=None):
    """
    Determine garment type (T-SHIRT, CAP, BAG, BLANKET) from position.
    
    Args:
        positionName: Position name
        partId: Optional part ID for fallback heuristics
        
    Returns:
        Garment Type string
    """
    # 1. Try Registry Lookup
    data = getPositionData(positionName)
    if data and 'type' in data:
        return data['type']
        
    # 2. Fallback Heuristics (for completely unknown positions)
    posNorm = str(positionName).upper()
    partIdNorm = str(partId).upper() if partId else ""
    
    # Load detection rules from garmentTypes.yaml
    garmentTypesConfig = _loadYaml('garmentTypes.yaml')
    rules = garmentTypesConfig.get('detectionRules', {})
    
    # Check each garment type's rules (except T-SHIRT which is default)
    for gType in ['BAG', 'CAP', 'BLANKET']:
        typeRules = rules.get(gType, {})
        keywords = typeRules.get('keywords', [])
        prefixes = typeRules.get('prefixes', [])
        
        # Check keywords in position name
        for keyword in keywords:
            if keyword.upper() in posNorm:
                return gType
        
        # Check prefixes in part ID (only if partId provided)
        if partIdNorm:
            for prefix in prefixes:
                if partIdNorm.startswith(prefix.upper()):
                    return gType
        
    return "T-SHIRT"


def getGarmentTypeForPositions(positions, partId=None):
    """
    Determine garment type from a LIST of parsed canonical positions.
    Uses the first valid position's type from the registry.
    
    This is more reliable than checking the raw location string because:
    1. Positions are already parsed and canonical
    2. Each position has a defined type in positionRegistry.yaml
    3. Avoids false positives from Part ID heuristics
    
    Args:
        positions: List of canonical position names (e.g., ['RIGHT-CHEST', 'LEFT-CHEST'])
        partId: Optional part ID for fallback (only used if NO positions have types)
        
    Returns:
        Garment Type string
    """
    if not positions:
        return "T-SHIRT"
    
    registry = getPositionRegistry()
    positionsData = registry.get('positions', {})
    
    # Check each position for its type
    for pos in positions:
        if pos in positionsData:
            posData = positionsData[pos]
            if 'type' in posData:
                return posData['type']
    
    # If no position had a type, try the original getGarmentType with first position
    # This handles unknown positions with Part ID fallback
    return getGarmentType(positions[0], partId)


def getPositionBehavior(positionName):
    """
    Get behavior flags for a position.
    
    Returns dict: { 'rotation': '...', 'reference': '...', 'mirror': bool }
    """
    data = getPositionData(positionName)
    return data.get('behavior', {})


def getComboMappings():
    """Get the dictionary of combo position mappings."""
    registry = getPositionRegistry()
    return registry.get('comboMappings', {})


def isComboPosition(positionName):
    """Check if a position is a combo/dual position."""
    combos = getComboMappings()
    # Normalize input first
    cleanInput = str(positionName).strip().upper().replace(" ", "-").replace("&", "-")
    cleanInput = "-".join(filter(None, cleanInput.split("-")))
    return cleanInput in combos


def validatePosition(positionName):
    """
    Check if a position is valid (either canonical, alias, or combo).
    
    Returns:
        (isValid, canonicalName)
    """
    # Resolve name
    canonical = getCanonicalName(positionName)
    registry = getPositionRegistry()
    
    # Check if it exists in main positions OR combo mappings
    if canonical in registry.get('positions', {}) or canonical in registry.get('comboMappings', {}):
        return True, canonical
        
    return False, canonical


# ============================================================================
# Column Mapping Functions
# ============================================================================

def getColumnMapping():
    """Get the column mapping configuration."""
    return _loadYaml('columnMapping.yaml')


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


def normalizeRowData(row, dfColumns):
    """Convert a DataFrame row to a normalized dictionary."""
    mapping = getColumnMapping()
    columns = mapping.get('columns', {})
    normalized = {}
    
    for internalName, variations in columns.items():
        for variation in variations:
            if variation in dfColumns:
                value = row.get(variation)
                if value is not None:
                    # Handle NaN
                    if isinstance(value, float) and value != value:
                        sVal = ""
                    else:
                        sVal = str(value).strip()
                    normalized[internalName] = sVal
                break
    return normalized


# ============================================================================
# Color Alias Functions
# ============================================================================

def getColorAliasesConfig():
    """Get color alias configuration."""
    return _loadYaml('colorAliases.yaml')

def getColorAliases():
    """Get the dictionary of color aliases."""
    return getColorAliasesConfig().get('aliases', {})

def expandColorVariants(colorName):
    """
    Generate a set of variant strings for a color name.
    Useful for flexible matching (e.g., "Navy" matches "nvy", "Dark Navy").
    
    Args:
        colorName: The base color string (e.g. "Navy")
        
    Returns:
        Set of lowercase normalized variant strings
    """
    if not colorName:
        return set()
        
    normalized = str(colorName).lower().strip()
    config = getColorAliasesConfig()
    aliases = config.get('aliases', {})
    
    variants = {normalized}
    
    # 1. Reverse lookup: If input is a short alias (e.g. "nvy"), find full names
    if normalized in aliases:
        for full in aliases[normalized]:
            variants.add(full.lower())
            
    # 2. Forward lookup: If input is a full name (e.g. "Navy"), find aliases
    # This requires scanning the alias dict
    for alias, fulls in aliases.items():
        if normalized in [f.lower() for f in fulls]:
            variants.add(alias)
            
    # 3. Handle compound parts (e.g. "darknavy" -> "dark", "navy")
    # This helps matching split variants
    
    return variants

# ============================================================================
# Logo Size Functions
# ============================================================================

def getPositionType(positionName):
    """
    Return 'front', 'back', 'dual', or 'side' for a position.
    Used by imageLocator.
    """
    # 1. Check if it's a combo (Dual/Multi)
    if isComboPosition(positionName):
        return 'dual'
    
    # 2. Check registry for explicit 'view' type
    data = getPositionData(positionName)
    if data and 'view' in data:
        return data['view']
        
    # 3. Default to 'front'
    return 'front'


def getLogoSizesConfig():
    return _loadYaml('logoSizes.yaml')

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


# ============================================================================
# Constants & Helpers
# ============================================================================

def getIgnoreWords():
    return _loadYaml('filenamePatterns.yaml').get('ignoreWords', [])

def getFrontIndicators():
    return _loadYaml('filenamePatterns.yaml').get('frontIndicators', [])

def getBackIndicators():
    return _loadYaml('filenamePatterns.yaml').get('backIndicators', [])

def getSideIndicators():
    return _loadYaml('filenamePatterns.yaml').get('sideIndicators', [])

def getAllowedExtensions():
    return ['.' + e.lstrip('.') for e in _loadYaml('filenamePatterns.yaml').get('allowedExtensions', ['jpg','png'])]


# ============================================================================
# GUI / Advanced Settings Helpers
# ============================================================================

def getAllLogoSizes():
    """Get all configured logo sizes for the GUI."""
    config = getLogoSizesConfig()
    return config.get('positions', {})

def getLogoSizeForPosition(position, configOverride=None):
    """
    Get the specific logo size for a position.
    
    Args:
        position: The position name
        configOverride: Optional dictionary to use instead of loading from file
                        (used by excelPreProcessor with GUI settings)
    """
    if configOverride is not None:
        # Use provided config
        canonical = getCanonicalName(position)
        
        # Handle both nested config (like YAML) and flat dict (like GUI state)
        if 'positions' in configOverride and isinstance(configOverride['positions'], dict):
             positions = configOverride['positions']
             defaultSize = configOverride.get('defaultSize', 99)
        else:
             # Assume it's the flat positions dictionary itself
             positions = configOverride
             defaultSize = 99
        
        # Try canonical
        if canonical in positions:
            # Handle string/int conversion safely
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

def updateLogoSize(positionName, newSize):
    """
    Update the logo size for a specific position in the config.
    """
    try:
        data = getLogoSizesConfig()
        canonical = getCanonicalName(positionName)
        
        if 'positions' not in data:
            data['positions'] = {}
            
        data['positions'][canonical] = int(newSize)
        return _saveYaml('logoSizes.yaml', data)
    except Exception as e:
        print(f"[Config] Failed to update logo size: {e}")
        return False

def getClippingConfig():
    """Get the clipping configuration."""
    return _loadYaml('clippingPositions.yaml')

def getAllClippingPositions():
    """Get list of positions enabled for clipping."""
    config = getClippingConfig()
    return config.get('positions', {})

def isClippingEnabledGlobal():
    """Check if clipping is enabled globally."""
    config = getClippingConfig()
    return config.get('clippingEnabled', False)

def updateClippingConfig(globalEnabled=None, positions=None):
    """
    Update clipping configuration.
    
    Args:
        globalEnabled: bool or None (if None, keeps existing)
        positions: dict of {positionName: bool} or None
    """
    try:
        data = getClippingConfig()
        
        if globalEnabled is not None:
            data['clippingEnabled'] = bool(globalEnabled)
            
        if positions:
            if 'positions' not in data:
                data['positions'] = {}
            
            # Update specific positions
            for pos, enabled in positions.items():
                # Store by canonical name
                canonical = getCanonicalName(pos)
                data['positions'][canonical] = bool(enabled)
                
        return _saveYaml('clippingPositions.yaml', data)
    except Exception as e:
        print(f"[Config] Failed to update clipping config: {e}")
        return False
