"""Loads and manages YAML configuration files."""

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
                
    # Check Combo Mappings
    combos = registry.get('comboMappings', {})
    if cleanInput in combos:
        return cleanInput
    
    # Check normalized Combo keys
    for key in combos:
        normKey = str(key).strip().upper().replace(" ", "-").replace("&", "-")
        normKey = "-".join(filter(None, normKey.split("-")))
        if normKey == cleanInput:
            return key
        
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


def getPositionBehavior(positionName):
    """
    Get behavior flags for a position.
    Returns dict: { 'rotation': '...', 'reference': '...', 'mirror': bool }
    """
    data = getPositionData(positionName)
    return data.get('behavior', {})


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

def expandColorVariants(colorName):
    """
    Generate a set of variant strings for a color name.
    """
    if not colorName:
        return set()
        
    normalized = str(colorName).lower().strip()
    config = getColorAliasesConfig()
    aliases = config.get('aliases', {})
    
    variants = {normalized}
    
    # Reverse lookup
    if normalized in aliases:
        for full in aliases[normalized]:
            variants.add(full.lower())
            
    # Forward lookup
    for alias, fulls in aliases.items():
        if normalized in [f.lower() for f in fulls]:
            variants.add(alias)
            
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

def getIgnoreWords():
    return _loadYaml('images/filenamePatterns.yaml').get('ignoreWords', [])

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
        return _saveYaml('positions/logoSizes.yaml', data)
    except Exception as e:
        print(f"[Config] Failed to update logo size: {e}")
        return False

def getClippingConfig():
    """Get the clipping configuration."""
    return _loadYaml('positions/clippingPositions.yaml')

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
                
        return _saveYaml('positions/clippingPositions.yaml', data)
    
    except Exception as e:
        print(f"[Config] Failed to update clipping config: {e}")
        return False
