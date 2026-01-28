"""
Configuration Loader Module
Loads and manages YAML configuration files for the automation system.
"""

import os
import yaml
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
# Column Mapping Functions
# ============================================================================

def getColumnMapping():
    """Get the column mapping configuration."""
    return _loadYaml('columnMapping.yaml')


def findColumnName(dfColumns, internalName):
    """
    Find the actual Excel column name for an internal field name.
    
    Args:
        dfColumns: List of column names from the DataFrame
        internalName: Internal field name (e.g., 'productId')
    
    Returns:
        The matching column name from dfColumns, or None if not found
    """
    mapping = getColumnMapping()
    columns = mapping.get('columns', {})
    
    variations = columns.get(internalName, [])
    
    for variation in variations:
        if variation in dfColumns:
            return variation
    
    # Try case-insensitive match
    dfColumnsLower = {col.lower(): col for col in dfColumns}
    for variation in variations:
        if variation.lower() in dfColumnsLower:
            return dfColumnsLower[variation.lower()]
    
    return None


def normalizeRowData(row, dfColumns):
    """
    Convert a DataFrame row to a normalized dictionary with internal field names.
    
    Args:
        row: pandas Series (a row from DataFrame)
        dfColumns: List of column names from DataFrame
    
    Returns:
        Dictionary with internal field names as keys
    """
    mapping = getColumnMapping()
    columns = mapping.get('columns', {})
    
    normalized = {}
    
    for internalName, variations in columns.items():
        for variation in variations:
            if variation in dfColumns:
                value = row.get(variation)
                if value is not None:
                    normalized[internalName] = str(value).strip() if not isinstance(value, float) or not (value != value) else ""
                break
    
    return normalized


# ============================================================================
# Logo Size Functions
# ============================================================================

def getLogoSizesConfig():
    """Get the logo sizes configuration."""
    return _loadYaml('logoSizes.yaml')


def getDefaultLogoSize(position):
    """
    Get the default logo width for a position.
    
    Args:
        position: Position name (e.g., 'LEFT-CHEST')
    
    Returns:
        Width in pixels
    """
    config = getLogoSizesConfig()
    positions = config.get('positions', {})
    defaultSize = config.get('defaultSize', 99)
    
    # Normalize position name
    posNorm = str(position).strip().upper().replace(' ', '-').replace('_', '-')
    
    # Try exact match first
    if posNorm in positions:
        return positions[posNorm]
    
    # Try partial match
    for key, value in positions.items():
        keyNorm = key.upper().replace(' ', '-').replace('_', '-')
        if keyNorm in posNorm or posNorm in keyNorm:
            return value
    
    return defaultSize


def getAllLogoSizes():
    """Get all position sizes as a dictionary."""
    config = getLogoSizesConfig()
    return config.get('positions', {})


def updateLogoSize(position, size):
    """Update the logo size for a specific position."""
    config = getLogoSizesConfig()
    if 'positions' not in config:
        config['positions'] = {}
    config['positions'][position] = size
    return _saveYaml('logoSizes.yaml', config)


# ============================================================================
# Clipping Configuration Functions
# ============================================================================

def getClippingConfig():
    """Get the clipping configuration."""
    return _loadYaml('clippingPositions.yaml')


def isClippingEnabledGlobal():
    """Check if clipping is enabled globally."""
    config = getClippingConfig()
    return config.get('clippingEnabled', False)


def isClippingEnabledForPosition(position):
    """
    Check if clipping is enabled for a specific position.
    
    Args:
        position: Position name
    
    Returns:
        True if clipping should be applied
    """
    config = getClippingConfig()
    
    # Check global toggle first
    if not config.get('clippingEnabled', False):
        return False
    
    positions = config.get('positions', {})
    defaultClipping = config.get('defaultClipping', False)
    
    # Normalize position name
    posNorm = str(position).strip().upper().replace(' ', '-').replace('_', '-')
    
    # Try exact match first
    if posNorm in positions:
        return positions[posNorm]
    
    # Try partial match
    for key, value in positions.items():
        keyNorm = key.upper().replace(' ', '-').replace('_', '-')
        if keyNorm in posNorm or posNorm in keyNorm:
            return value
    
    return defaultClipping


def getAllClippingPositions():
    """Get all clipping position settings."""
    config = getClippingConfig()
    return config.get('positions', {})


def updateClippingGlobal(enabled):
    """Update the global clipping toggle."""
    config = getClippingConfig()
    config['clippingEnabled'] = enabled
    return _saveYaml('clippingPositions.yaml', config)


def updateClippingPosition(position, enabled):
    """Update clipping setting for a specific position."""
    config = getClippingConfig()
    if 'positions' not in config:
        config['positions'] = {}
    config['positions'][position] = enabled
    return _saveYaml('clippingPositions.yaml', config)


def updateClippingConfig(globalEnabled, positionsDict):
    """Update entire clipping configuration at once."""
    config = getClippingConfig()
    config['clippingEnabled'] = globalEnabled
    config['positions'] = positionsDict
    return _saveYaml('clippingPositions.yaml', config)


# ============================================================================
# Color Aliases Functions
# ============================================================================

def getColorAliases():
    """Get color alias configuration as a dictionary."""
    config = _loadYaml('colorAliases.yaml')
    return config.get('aliases', {})


def getCompoundColorParts():
    """Get compound color parts for splitting joined colors."""
    config = _loadYaml('colorAliases.yaml')
    return config.get('compoundParts', [])


def expandColorVariants(color):
    """
    Generate all color name variants for matching.
    Uses YAML configuration for comprehensive matching.
    
    Args:
        color: The color string to expand
        
    Returns:
        Set of all possible variants of this color
    """
    import re
    aliases = getColorAliases()
    
    # Normalize input
    colorNorm = re.sub(r'[^a-z0-9]', '', str(color).lower())
    variants = {colorNorm}
    
    # Add all alias expansions (bidirectional)
    for abbrev, fulls in aliases.items():
        abbrevNorm = re.sub(r'[^a-z0-9]', '', abbrev.lower())
        
        # If color contains the abbreviation, add full versions
        if abbrevNorm in colorNorm:
            for full in fulls:
                fullNorm = re.sub(r'[^a-z0-9]', '', full.lower())
                variants.add(colorNorm.replace(abbrevNorm, fullNorm))
        
        # If color contains any full version, add abbreviation
        for full in fulls:
            fullNorm = re.sub(r'[^a-z0-9]', '', full.lower())
            if fullNorm in colorNorm:
                variants.add(colorNorm.replace(fullNorm, abbrevNorm))
    
    return variants


# ============================================================================
# Position Type Functions
# ============================================================================

def getPositionTypesConfig():
    """Get position types configuration."""
    return _loadYaml('positionTypes.yaml')


def getPositionType(position):
    """
    Return 'front', 'back', 'dual', or 'side' for a position.
    
    Args:
        position: Position name (e.g., 'LEFT-CHEST', 'FULL-BACK')
        
    Returns:
        String: 'front', 'back', 'dual', or 'side'
    """
    config = getPositionTypesConfig()
    
    # Normalize position name
    posNorm = str(position).strip().upper().replace(' ', '-').replace('_', '-')
    
    # Check back positions
    backPositions = config.get('backPositions', [])
    for bp in backPositions:
        bpNorm = bp.upper().replace(' ', '-').replace('_', '-')
        if bpNorm == posNorm or bpNorm in posNorm:
            return 'back'
    
    # Check dual positions
    dualPositions = config.get('dualPositions', [])
    for dp in dualPositions:
        dpNorm = dp.upper().replace(' ', '-').replace('_', '-').replace('&', '-')
        if dpNorm == posNorm or dpNorm in posNorm:
            return 'dual'
    
    # Check side positions
    sidePositions = config.get('sidePositions', [])
    for sp in sidePositions:
        spNorm = sp.upper().replace(' ', '-').replace('_', '-')
        if spNorm == posNorm or spNorm in posNorm:
            return 'side'
    
    # Default to front
    return 'front'


def getFrontPositions():
    """Get list of front-facing positions."""
    config = getPositionTypesConfig()
    return config.get('frontPositions', [])


def getBackPositions():
    """Get list of back-facing positions."""
    config = getPositionTypesConfig()
    return config.get('backPositions', [])


def getDualPositions():
    """Get list of dual-image positions."""
    config = getPositionTypesConfig()
    return config.get('dualPositions', [])


# ============================================================================
# Garment Type Functions
# ============================================================================

def getGarmentTypesConfig():
    """Get garment types configuration."""
    return _loadYaml('garmentTypes.yaml')


def detectGarmentType(position, partId=None):
    """
    Detect garment type from position keywords or part ID prefix.
    
    Args:
        position: Position/location name
        partId: Optional part ID to check prefix
        
    Returns:
        String: 'T-SHIRT', 'CAP', 'BAG', or 'BLANKET'
    """
    config = getGarmentTypesConfig()
    rules = config.get('detectionRules', {})
    
    posNorm = str(position).upper() if position else ''
    partIdNorm = str(partId).upper() if partId else ''
    
    # Check each garment type (except T-SHIRT which is default)
    for gType in ['CAP', 'BAG', 'BLANKET']:
        rule = rules.get(gType, {})
        
        # Check keywords in position
        for keyword in rule.get('keywords', []):
            if keyword.upper() in posNorm:
                return gType
        
        # Check part ID prefix
        for prefix in rule.get('prefixes', []):
            if partIdNorm.startswith(prefix.upper()):
                return gType
    
    # Default to T-SHIRT
    return 'T-SHIRT'


def getTypeAliases():
    """Get garment type aliases."""
    config = getGarmentTypesConfig()
    return config.get('typeAliases', {})


# ============================================================================
# Filename Pattern Functions
# ============================================================================

def getFilenamePatternsConfig():
    """Get filename patterns configuration."""
    return _loadYaml('filenamePatterns.yaml')


def getIgnoreWords():
    """Get list of words to ignore in filenames."""
    config = getFilenamePatternsConfig()
    return [w.lower() for w in config.get('ignoreWords', [])]


def getFrontIndicators():
    """Get list of front image indicators."""
    config = getFilenamePatternsConfig()
    return [w.lower() for w in config.get('frontIndicators', [])]


def getBackIndicators():
    """Get list of back image indicators."""
    config = getFilenamePatternsConfig()
    return [w.lower() for w in config.get('backIndicators', [])]


def getSideIndicators():
    """Get list of side image indicators."""
    config = getFilenamePatternsConfig()
    return [w.lower() for w in config.get('sideIndicators', [])]


def getAllowedExtensions():
    """Get list of allowed image file extensions."""
    config = getFilenamePatternsConfig()
    exts = config.get('allowedExtensions', ['jpg', 'jpeg', 'png'])
    return ['.' + e.lower().lstrip('.') for e in exts]


def getViewPriority():
    """Get view type priority for image selection."""
    config = getFilenamePatternsConfig()
    return config.get('viewPriority', {'front': 1, 'back': 2, 'side': 3})

