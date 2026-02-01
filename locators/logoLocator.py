"""
Logo Locator Module
Finds logo files by decoration code with robust matching.
Supports multiple formats and handles various naming conventions.
"""

import os
import re
import difflib
from services.logger import logError


# Supported logo file extensions (in order of preference)
SUPPORTED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".ai")


def normalize(text: str) -> str:
    """Normalize text to lowercase alphanumeric only."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def findLogo(logoRoot, decorationCode):
    """
    Find logo file by decoration code with robust matching.
    
    Searches for logo files matching the decoration code with various strategies:
    1. Direct file lookup (exact name)
    2. Subfolder with same name as code
    3. Case-insensitive search
    4. Partial/fuzzy matching
    
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
    codeNorm = normalize(decorationCode)
    
    # Strategy 1: Direct file lookup (fastest)
    for ext in SUPPORTED_EXTENSIONS:
        directPath = os.path.join(logoRoot, f"{decorationCode}{ext}")
        if os.path.exists(directPath):
            return directPath
    
    # Strategy 2: Check for subfolder with code name (e.g., Logos/AIRTEL/AIRTEL.pdf)
    codeFolder = os.path.join(logoRoot, decorationCode)
    if os.path.isdir(codeFolder):
        for ext in SUPPORTED_EXTENSIONS:
            subPath = os.path.join(codeFolder, f"{decorationCode}{ext}")
            if os.path.exists(subPath):
                return subPath
        # Also check any file in the subfolder
        try:
            for f in os.listdir(codeFolder):
                name, ext = os.path.splitext(f)
                if ext.lower() in SUPPORTED_EXTENSIONS:
                    return os.path.join(codeFolder, f)
        except Exception:
            pass
    
    # Strategy 2b: Case-insensitive subfolder check
    try:
        for item in os.listdir(logoRoot):
            itemPath = os.path.join(logoRoot, item)
            if os.path.isdir(itemPath) and normalize(item) == codeNorm:
                # Found matching folder, look for logo inside
                for ext in SUPPORTED_EXTENSIONS:
                    subPath = os.path.join(itemPath, f"{decorationCode}{ext}")
                    if os.path.exists(subPath):
                        return subPath
                # Any file in folder
                for f in os.listdir(itemPath):
                    name, ext = os.path.splitext(f)
                    if ext.lower() in SUPPORTED_EXTENSIONS:
                        return os.path.join(itemPath, f)
    except Exception:
        pass
    
    # Strategy 3: Walk directories and find exact match
    for root, dirs, files in os.walk(logoRoot):
        for ext in SUPPORTED_EXTENSIONS:
            targetName = f"{decorationCode}{ext}"
            if targetName in files:
                return os.path.join(root, targetName)
    
    # Strategy 4: Case-insensitive filename search
    decorationCodeLower = decorationCode.lower()
    for root, _, files in os.walk(logoRoot):
        for f in files:
            name, ext = os.path.splitext(f)
            if ext.lower() in SUPPORTED_EXTENSIONS and name.lower() == decorationCodeLower:
                return os.path.join(root, f)
    
    # Strategy 5: Normalized match (removes special characters)
    for root, _, files in os.walk(logoRoot):
        for f in files:
            name, ext = os.path.splitext(f)
            if ext.lower() in SUPPORTED_EXTENSIONS and normalize(name) == codeNorm:
                return os.path.join(root, f)
    
    # Strategy 6: Partial match (code is contained in filename)
    bestMatch = None
    bestScore = 0
    
    for root, _, files in os.walk(logoRoot):
        for f in files:
            name, ext = os.path.splitext(f)
            if ext.lower() in SUPPORTED_EXTENSIONS:
                nameNorm = normalize(name)
                
                # Exact substring match
                if codeNorm in nameNorm:
                    fullPath = os.path.join(root, f)
                    # Prefer shorter filenames (more likely exact match)
                    score = 1.0 - (len(nameNorm) - len(codeNorm)) / max(len(nameNorm), 1)
                    if score > bestScore:
                        bestScore = score
                        bestMatch = fullPath
    
    if bestMatch and bestScore > 0.5:
        print(f"[INFO] Logo partial match: {os.path.basename(bestMatch)} for code '{decorationCode}'")
        return bestMatch
    
    # Strategy 7: Fuzzy match as last resort
    bestFuzzyMatch = None
    bestFuzzyScore = 0
    
    for root, _, files in os.walk(logoRoot):
        for f in files:
            name, ext = os.path.splitext(f)
            if ext.lower() in SUPPORTED_EXTENSIONS:
                nameNorm = normalize(name)
                score = difflib.SequenceMatcher(None, codeNorm, nameNorm).ratio()
                if score > bestFuzzyScore and score >= 0.7:
                    bestFuzzyScore = score
                    bestFuzzyMatch = os.path.join(root, f)
    
    if bestFuzzyMatch:
        print(f"[INFO] Logo fuzzy match: {os.path.basename(bestFuzzyMatch)} for code '{decorationCode}' (score={bestFuzzyScore:.2f})")
        return bestFuzzyMatch
    
    logError(f"Logo not found: {decorationCode} (searched {logoRoot})")
    return None
