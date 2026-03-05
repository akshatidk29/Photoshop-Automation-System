"""Logo Locator - Finds PDF logo files by decoration code."""

import os
import re
from services.batchLogger import logError


def normalize(text: str) -> str:
    """Normalize text to lowercase alphanumeric only."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def findLogo(logoRoot, decorationCode):
    """
    Find PDF logo file by decoration code.
    Args:
        logoRoot: Root directory for logo files
        decorationCode: Logo/decoration code to search for
    """
    if not decorationCode:
        logError(f"No decoration code provided")
        return None
    
    if not logoRoot or not os.path.exists(logoRoot):
        logError(f"Logo root folder does not exist: {logoRoot}")
        return None
    
    decorationCode = str(decorationCode).strip()
    codeNorm = normalize(decorationCode)
    
    # Strategy 1: Direct file - LOGO_ROOT/CODE.pdf
    directPath = os.path.join(logoRoot, f"{decorationCode}.pdf")
    if os.path.exists(directPath):
        return directPath
    
    # Strategy 2: Subfolder - LOGO_ROOT/CODE/CODE.pdf or any PDF in subfolder
    codeFolder = os.path.join(logoRoot, decorationCode)
    if os.path.isdir(codeFolder):
        subPath = os.path.join(codeFolder, f"{decorationCode}.pdf")
        if os.path.exists(subPath):
            return subPath
        # Any PDF in the subfolder
        try:
            for f in os.listdir(codeFolder):
                if f.lower().endswith('.pdf'):
                    return os.path.join(codeFolder, f)
        except Exception:
            pass
    
    # Strategy 3: Case-insensitive direct match
    try:
        for f in os.listdir(logoRoot):
            if f.lower().endswith('.pdf'):
                name = os.path.splitext(f)[0]
                if normalize(name) == codeNorm:
                    return os.path.join(logoRoot, f)
    except Exception:
        pass
    
    # Strategy 4: Case-insensitive subfolder match
    try:
        for item in os.listdir(logoRoot):
            itemPath = os.path.join(logoRoot, item)
            if os.path.isdir(itemPath) and normalize(item) == codeNorm:
                # Look for PDF in matching folder
                for f in os.listdir(itemPath):
                    if f.lower().endswith('.pdf'):
                        return os.path.join(itemPath, f)
    except Exception:
        pass
    
    # Strategy 5: Walk all subdirectories for exact match
    for root, _, files in os.walk(logoRoot):
        for f in files:
            if f.lower().endswith('.pdf'):
                name = os.path.splitext(f)[0]
                if normalize(name) == codeNorm:
                    return os.path.join(root, f)
    
    # Not found - log error
    logError(f"PDF logo not found for decoration code: '{decorationCode}' (searched in {logoRoot})")
    return None


def findMultipleLogos(logoRoot, decorationCodes, positions=None):
    """
    Find multiple PDF logo files for multiple positions.
    
    Args:
        logoRoot: Root directory for logo files
        decorationCodes: List of decoration codes
        positions: List of position names for context
    
    Returns:
        List of logo paths. None for any logo not found.
    """
    if not decorationCodes:
        return []
    
    targetCount = len(positions) if positions else len(decorationCodes)
    
    if not positions:
        positions = [f"Position{i+1}" for i in range(targetCount)]
    
    # Resolve each logo
    resolvedLogos = []
    for code in decorationCodes:
        logoPath = findLogo(logoRoot, code)
        resolvedLogos.append(logoPath)
    
    # Filter valid logos
    validLogos = [logo for logo in resolvedLogos if logo]
    
    if not validLogos:
        print(f"[ERROR] No PDF logos found for codes: {decorationCodes}")
        return [None] * targetCount
    
    # Map logos to positions (cycle if fewer logos than positions)
    result = []
    for idx in range(targetCount):
        logoIdx = idx % len(validLogos)
        result.append(validLogos[logoIdx])
    
    return result
