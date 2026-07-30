"""
Image Locator Module

Finds product images based on part ID, color, and view type.
Unified findImage() function handles all use cases.
"""

import os
import re
from services.batchLogger import logError

# Handle configLoader import
try:
    from configuration.configLoader import (
        expandColorVariants, getPositionType,
        getFrontIndicators, getBackIndicators,
        getSideIndicators, getAllowedExtensions,
        getCompoundParts
    )
    CONFIG_AVAILABLE = True
except ImportError as e:
    print(f"Warning: configLoader import failed: {e}")
    CONFIG_AVAILABLE = False

# Handle comboParser import (optional/heavy dependency)
try:
    from detectors.comboParser import parseComboPosition
except ImportError:
    # Dummy function if parser unavailable
    def parseComboPosition(filename): return None

# Fallback constants if config not available
if not CONFIG_AVAILABLE:
    ALLOWED_EXTENSIONS = (".jpg",)
    FRONT_INDICATORS = ["front", "fullfront", "flatfront"]
    BACK_INDICATORS = ["back", "fullback", "flatback", "rear", "side", "straight", "left", "right"]
else:
    ALLOWED_EXTENSIONS = tuple(getAllowedExtensions())
    FRONT_INDICATORS = getFrontIndicators()
    BACK_INDICATORS = getBackIndicators() + getSideIndicators()

# Pre-compute sorted view indicators (longest-first) at module level
ALL_VIEW_INDICATORS = sorted(
    [ind.lower() for ind in (FRONT_INDICATORS + BACK_INDICATORS)],
    key=len, reverse=True
)

# Cached color token regex for residual matching (compiled once)
_colorTokenRegex = None

# Pre-compiled regexes for residual cleanup
_DIGIT_RE = re.compile(r'\d+')
_ISOLATED_LETTER_RE = re.compile(r'(?<![a-z])[a-z](?![a-z])')

def _getColorTokenRegex():
    """Get cached compiled regex matching any known color token."""
    global _colorTokenRegex
    if _colorTokenRegex is None:
        if CONFIG_AVAILABLE:
            tokens = getCompoundParts()
        else:
            tokens = ['grey', 'gray', 'steel', 'blue', 'red', 'green',
                      'white', 'black', 'navy', 'khaki', 'brown',
                      'heather', 'charcoal', 'orange', 'purple', 'pink', 'yellow']
        # Escape tokens and join into alternation regex, longest first
        escaped = [re.escape(t) for t in tokens]
        _colorTokenRegex = re.compile('|'.join(escaped))
    return _colorTokenRegex


def _isExactColorMatch(variant, cleaned, partId=""):
    """
    Check if a color variant is the ONLY color in the filename.

    Algorithm:
      1. Find variant in cleaned filename (must be present).
      2. Remove it and the partId prefix.
      3. Strip all view indicators (front, back, side, ...).
      4. Strip numeric segments and short alpha-only part-ID fragments.
      5. If any known color token remains in the residual → extra color present → reject.
    """
    if variant not in cleaned:
        return False

    # Step 1: Remove the matched variant (first occurrence only)
    residual = cleaned.replace(variant, "", 1)

    # Step 1b: Remove partId prefix (prevents ST941's 'st' from matching 'steel' alias)
    if partId:
        normPart = normalize(partId)
        residual = residual.replace(normPart, "", 1)

    # Step 2: Remove view indicators (pre-sorted at module level)
    for ind in ALL_VIEW_INDICATORS:
        residual = residual.replace(ind, "")

    # Step 3: Remove digit sequences (numeric part IDs like "7525395", "850")
    residual = _DIGIT_RE.sub('', residual)

    # Step 4: Remove isolated single non-color letters (part-ID prefix/suffix like "l", "f")
    residual = _ISOLATED_LETTER_RE.sub('', residual)

    # Step 5: Check if any known color token is still present (single regex search)
    if residual and _getColorTokenRegex().search(residual):
        return False  # extra color found — not an exact match

    return True

# In-memory image index
_imageIndex = None
_indexRoot = None
_indexEntries = []


def normalize(text: str) -> str:
    """Normalize text to lowercase alphanumeric only."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def isFlatGarmentImage(imagePath: str) -> bool:
    if not imagePath:
        return False
    filename = os.path.basename(imagePath).lower()
    return "flat" in filename


def cleanFilename(name: str) -> str:
    """Clean filename by removing ignore words."""
    return normalize(name)


def getColorVariants(color: str) -> set:
    """Generate all color name variants for matching."""
    if CONFIG_AVAILABLE:
        return expandColorVariants(color)
    
    base = normalize(color)
    variants = {base}
    basicAliases = {
        "blk": ["black"], "wht": ["white"], "gry": ["grey", "gray"],
        "nvy": ["navy"], "rd": ["red"], "grn": ["green"]
    }
    for short, fulls in basicAliases.items():
        for full in fulls:
            if full in base:
                variants.add(base.replace(full, short))
            if short in base:
                variants.add(base.replace(short, full))
    return variants


def _ensureIndex(imageRoot):
    """Build or reuse in-memory index of image files."""
    global _imageIndex, _indexRoot, _indexEntries
    if _imageIndex is not None and _indexRoot == os.path.abspath(imageRoot):
        return

    _indexEntries = []
    rootAbs = os.path.abspath(imageRoot)
    _indexRoot = rootAbs

    try:
        for r, _, files in os.walk(rootAbs):
            for f in files:
                name, ext = os.path.splitext(f)
                if ext.lower() not in ALLOWED_EXTENSIONS:
                    continue
                full = os.path.join(r, f)
                cleaned = cleanFilename(name)
                _indexEntries.append({'path': full, 'basename': f, 'cleaned': cleaned})
        _imageIndex = True
    except Exception as e:
        _imageIndex = None
        logError(f"Failed to build image index for {imageRoot}: {e}")


def resolveSupplierFolder(imageRoot, supplierName):
    """Find supplier folder using direct match or normalized match."""
    if not supplierName:
        return None

    # Direct path check
    direct = os.path.join(imageRoot, supplierName)
    if os.path.isdir(direct):
        return direct

    # Normalized match (case-insensitive, alphanumeric only)
    try:
        folders = [d for d in os.listdir(imageRoot) if os.path.isdir(os.path.join(imageRoot, d))]
    except Exception:
        return None

    norm = normalize(supplierName)
    for f in folders:
        if normalize(f) == norm:
            return os.path.join(imageRoot, f)
    
    return None


def resolvePartFolder(supplierFolder, partId):
    """Find part folder within supplier folder."""
    if not supplierFolder or not os.path.isdir(supplierFolder):
        return None
    
    partFolder = os.path.join(supplierFolder, partId)
    if os.path.isdir(partFolder):
        return partFolder
    
    # Case-insensitive match
    try:
        subfolders = os.listdir(supplierFolder)
        for sf in subfolders:
            if normalize(sf) == normalize(partId):
                return os.path.join(supplierFolder, sf)
    except Exception:
        pass
    
    return None


def buildPattern(partId, color):
    """Build regex pattern for matching image files."""
    part = normalize(partId)
    ext = "|".join(e[1:] for e in ALLOWED_EXTENSIONS)
    return re.compile(rf".*{part}.*\.({ext})$", re.I)


def collectMatches(root, pattern):
    """Collect matching files using index or filesystem walk."""
    matches = []
    try:
        _ensureIndex(root)
        rootAbs = os.path.abspath(root)
        for e in _indexEntries:
            try:
                if os.path.commonpath([rootAbs, os.path.abspath(e['path'])]) != rootAbs:
                    continue
            except Exception:
                continue
            nameExt = e['cleaned'] + os.path.splitext(e['basename'])[1].lower()
            if pattern.search(nameExt):
                matches.append(e['path'])
        return matches
    except Exception:
        matches = []
        for r, _, files in os.walk(root):
            for f in files:
                name, ext = os.path.splitext(f)
                if ext.lower() not in ALLOWED_EXTENSIONS:
                    continue
                cleaned = cleanFilename(name) + ext.lower()
                if pattern.search(cleaned):
                    matches.append(os.path.join(r, f))
        return matches


def hasIndicator(imgPath, indicators):
    """
    Check if image filename contains any of the given indicators.
    
    Args:
        imgPath: Path to the image file
        indicators: List of indicator strings to check for
        
    Returns:
        True if any indicator is found in the filename
    """
    basename = os.path.basename(imgPath)
    name = os.path.splitext(basename)[0].lower()
    tokens = set(re.split(r'[^a-z0-9]+', name))
    
    for indicator in indicators:
        ind = indicator.lower()
        if ind in tokens:
            return True
        for token in tokens:
            if token.endswith(ind) and token != ind:
                return True
            idx = token.find(ind)
            if idx != -1 and idx + len(ind) < len(token):
                suffix = token[idx + len(ind):]
                if suffix.isdigit():
                    return True
    return False


def scoreImage(imgPath, color, viewType, colorVariants=None, partId=""):
    """
    Score an image for matching quality.
    
    viewType:
        'front' - must be front image
        'back' - must be back/side image
        'any' - no view filtering, just color match
    
    colorVariants: Pre-computed set of color variants (optional, computed if not provided)
    partId: Product part ID, used to strip from filename before color-collision check
    """
    name = os.path.splitext(os.path.basename(imgPath))[0]
    cleaned = cleanFilename(name)
    lname = os.path.basename(imgPath).lower()
    
    # Color matching - REQUIRED (exact boundary-aware match)
    if colorVariants is None:
        colorVariants = getColorVariants(color)
    colorMatched = any(variant and _isExactColorMatch(variant, cleaned, partId) for variant in colorVariants)
    
    if not colorMatched:
        return -100.0
    
    colorScore = 1.0
    
    # View type scoring - Direct indicator check
    positionScore = 0.0
    
    if viewType == "none":
        # No view filtering - any image is fine
        positionScore = 1.0
    elif viewType == "front":
        # Check if image has any FRONT indicators
        if hasIndicator(imgPath, FRONT_INDICATORS):
            positionScore = 2.0
        elif hasIndicator(imgPath, BACK_INDICATORS):
            positionScore = -100.0  # Back indicator = reject
        else:
            positionScore = 1.0  # No Indicator

    elif viewType == "back":
        # Check if image has any BACK indicators
        if hasIndicator(imgPath, BACK_INDICATORS):
            positionScore = 2.0
        else:
            positionScore = -100.0  # No back indicator = reject
    
    # Penalize flat views
    if "flat" in lname:
        positionScore -= 0.5
    
    return colorScore + positionScore


# UNIFIED IMAGE FINDER

def findImage(imageRoot: str, supplierName: str, partId: str, color: str, 
              viewType: str = "none") -> str:
    """
    Find a single best-match image.
    
    Args:
        imageRoot: Root directory for images
        supplierName: Supplier name for folder resolution  
        partId: Product part ID
        color: Product color
        viewType: 'front', 'back', or 'none' (no view filtering)
        
    Returns:
        Path to best matching image, or empty string if not found
    """
    candidates = findImageCandidates(imageRoot, supplierName, partId, color, viewType)
    return candidates[0] if candidates else ""


def findImageCandidates(imageRoot: str, supplierName: str, partId: str, color: str, 
                        viewType: str = "none", maxCandidates: int = 6) -> list:
    """
    Find image candidates matching criteria.
    
    Args:
        imageRoot: Root directory for images
        supplierName: Supplier name for folder resolution
        partId: Product part ID
        color: Product color
        viewType: 'front', 'back', or 'none' (no view filtering for BAG, TOWEL, etc.)
        maxCandidates: Maximum candidates to return
        
    Returns:
        List of matching image paths, best-first
    """
    pattern = buildPattern(partId, color)
    
    supplierFolder = resolveSupplierFolder(imageRoot, supplierName)
    if not supplierFolder:
        logError(f"Supplier folder not found: {supplierName} (root={imageRoot})")
        return []
    
    partFolder = resolvePartFolder(supplierFolder, partId)
    if not partFolder:
        logError(f"Part folder not found: {partId} under supplier {supplierName}")
        return []
    
    allMatches = collectMatches(partFolder, pattern)
    if not allMatches:
        logError(f"Image not found | PartID={partId}, Color={color}, Supplier={supplierName}")
        return []
    
    # Pre-compute color variants once for all candidates
    colorVariants = getColorVariants(color)
    
    # Score and filter matches
    scoredMatches = []
    for imgPath in allMatches:
        score = scoreImage(imgPath, color, viewType, colorVariants=colorVariants, partId=partId)
        if score > 0:
            scoredMatches.append((score, imgPath))
    
    if not scoredMatches:
        logError(f"No {viewType} image found with matching color '{color}' | PartID={partId}, Supplier={supplierName}")
        return []
    
    scoredMatches.sort(key=lambda x: x[0], reverse=True)
    
    candidates = []
    seen = set()
    
    for score, imgPath in scoredMatches:
        if imgPath not in seen:
            seen.add(imgPath)
            candidates.append(imgPath)
            
            if len(candidates) == 1:
                print(f"[INFO] Best image match: {os.path.basename(imgPath)} (view={viewType}, score={score:.2f})")
        
        if len(candidates) >= maxCandidates:
            break
    

    return candidates
