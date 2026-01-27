"""
Logo Locator Module
Finds logo files by decoration code with support for multiple formats.
"""

import os
from services.logger import logError


# Supported logo file extensions (in order of preference)
SUPPORTED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".ai")


def findLogo(logoRoot, decorationCode):
    """
    Find logo file by decoration code.
    
    Searches for logo files matching the decoration code with various extensions.
    Case-insensitive matching is used as fallback.
    
    Args:
        logoRoot: Root directory to search for logos
        decorationCode: The decoration/logo code to find
        
    Returns:
        Full path to logo file, or None if not found
    """
    if not decorationCode:
        return None
    
    if not logoRoot or not os.path.exists(logoRoot):
        logError(f"Logo root folder does not exist: {logoRoot}")
        return None
    
    decorationCode = str(decorationCode).strip()
    
    # Strategy 1: Direct file lookup (fastest)
    for ext in SUPPORTED_EXTENSIONS:
        directPath = os.path.join(logoRoot, f"{decorationCode}{ext}")
        if os.path.exists(directPath):
            return directPath
    
    # Strategy 2: Walk directories and find exact match
    for root, _, files in os.walk(logoRoot):
        for ext in SUPPORTED_EXTENSIONS:
            targetName = f"{decorationCode}{ext}"
            if targetName in files:
                return os.path.join(root, targetName)
    
    # Strategy 3: Case-insensitive search
    decorationCodeLower = decorationCode.lower()
    for root, _, files in os.walk(logoRoot):
        for f in files:
            name, ext = os.path.splitext(f)
            if ext.lower() in SUPPORTED_EXTENSIONS and name.lower() == decorationCodeLower:
                return os.path.join(root, f)
    
    # Strategy 4: Partial match (code might be part of filename)
    for root, _, files in os.walk(logoRoot):
        for f in files:
            name, ext = os.path.splitext(f)
            if ext.lower() in SUPPORTED_EXTENSIONS:
                if decorationCodeLower in name.lower():
                    return os.path.join(root, f)
    
    logError(f"Logo not found: {decorationCode} (searched {logoRoot})")
    return None


def validateLogoFolder(logoRoot):
    """
    Validate that the logo folder exists and contains logo files.
    
    Args:
        logoRoot: Path to check
        
    Returns:
        Tuple of (isValid, message)
    """
    if not logoRoot:
        return False, "No logo folder specified"
    
    if not os.path.exists(logoRoot):
        return False, f"Folder does not exist: {logoRoot}"
    
    if not os.path.isdir(logoRoot):
        return False, f"Path is not a folder: {logoRoot}"
    
    # Count logo files
    logoCount = 0
    for root, _, files in os.walk(logoRoot):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                logoCount += 1
    
    if logoCount == 0:
        return False, f"No logo files found in {logoRoot}"
    
    return True, f"Found {logoCount} logo files"
