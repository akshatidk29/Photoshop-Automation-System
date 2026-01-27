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
