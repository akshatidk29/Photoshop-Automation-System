"""
Image Locator Module
Finds product images with robust color matching and front/back selection.
Uses YAML configuration for flexible, user-editable matching rules.
"""

import os
import re
import json
import difflib
from services.logger import logError

# Import configuration loaders
try:
    from configuration.configLoader import (
        getColorAliases, expandColorVariants, getPositionType,
        getIgnoreWords, getFrontIndicators, getBackIndicators, 
        getSideIndicators, getAllowedExtensions
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

# Fallback constants if config not available
if not CONFIG_AVAILABLE:
    ALLOWED_EXTENSIONS = (".jpg",)
    IGNORE_WORDS = ["flat", "model", "form", "temp", "folded", "1200w", "copy"]
    FRONT_INDICATORS = ["front", "fullfront", "flatfront"]
    BACK_INDICATORS = ["back", "fullback", "flatback", "rear"]
    SIDE_INDICATORS = ["side", "straight"]
else:
    ALLOWED_EXTENSIONS = tuple(getAllowedExtensions())
    IGNORE_WORDS = getIgnoreWords()
    FRONT_INDICATORS = getFrontIndicators()
    BACK_INDICATORS = getBackIndicators()
    SIDE_INDICATORS = getSideIndicators()

# In-memory image index
_imageIndex = None
_indexRoot = None
_indexByBasename = {}
_indexEntries = []


def normalize(text: str) -> str:
    """Normalize text to lowercase alphanumeric only."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def cleanFilename(name: str) -> str:
    """Clean filename by removing ignore words."""
    base = normalize(name)
    for word in IGNORE_WORDS:
        base = base.replace(normalize(word), "")
    return base


def getColorVariants(color: str) -> set:
    """Generate all color name variants for matching."""
    if CONFIG_AVAILABLE:
        return expandColorVariants(color)
    
    # Fallback basic expansion
    base = normalize(color)
    variants = {base}
    # Basic hardcoded aliases
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


def resolvePositionType(location: str) -> str:
    """Determine if location requires front, back, dual, or side image."""
    if CONFIG_AVAILABLE:
        return getPositionType(location)
    
    # Fallback to basic detection
    if not location:
        return "front"
    loc = location.strip().lower()
    if "full-back" in loc and "full-front" in loc:
        return "dual"
    if "back" in loc:
        return "back"
    return "front"


def _ensureIndex(imageRoot):
    """Build or reuse in-memory index of image files."""
    global _imageIndex, _indexRoot, _indexByBasename, _indexEntries
    if _imageIndex is not None and _indexRoot == os.path.abspath(imageRoot):
        return

    _indexEntries = []
    _indexByBasename = {}
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
                key = f.lower()
                _indexByBasename.setdefault(key, []).append(full)
        _imageIndex = True
    except Exception as e:
        _imageIndex = None
        logError(f"Failed to build image index for {imageRoot}: {e}")


def loadSupplierMappings():
    """Load learned supplier to folder mappings."""
    mappingsPath = os.path.join("assets", "learned", "image_mappings.json")
    try:
        with open(mappingsPath, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def resolveSupplierFolder(imageRoot, supplierName):
    """Find supplier folder using mappings, normalization, or fuzzy match."""
    if not supplierName:
        return None

    # Direct path check
    direct = os.path.join(imageRoot, supplierName)
    if os.path.isdir(direct):
        return direct

    # Learned mappings
    mappings = loadSupplierMappings()
    mapped = mappings.get(supplierName) or mappings.get(supplierName.lower())
    if mapped:
        candidate = os.path.join(imageRoot, mapped)
        if os.path.isdir(candidate):
            return candidate

    # Normalized matching
    try:
        folders = [d for d in os.listdir(imageRoot) if os.path.isdir(os.path.join(imageRoot, d))]
    except Exception:
        folders = []

    norm = normalize(supplierName)
    
    # Exact normalized match
    for f in folders:
        if normalize(f) == norm:
            return os.path.join(imageRoot, f)

    # Substring match
    for f in folders:
        nf = normalize(f)
        if norm in nf or nf in norm:
            return os.path.join(imageRoot, f)

    # Fuzzy match as last resort
    choices = {f: difflib.SequenceMatcher(None, normalize(f), norm).ratio() for f in folders}
    if choices:
        best = max(choices.items(), key=lambda x: x[1])
        if best[1] >= 0.6:
            return os.path.join(imageRoot, best[0])

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


def classifyImage(imgPath):
    """Classify an image as front, back, or side based on filename."""
    lname = os.path.basename(imgPath).lower()
    
    # Check back indicators first (more specific)
    for indicator in BACK_INDICATORS:
        if indicator in lname:
            return "back"
    
    # Check front indicators
    for indicator in FRONT_INDICATORS:
        if indicator in lname:
            return "front"
    
    # Check side indicators
    for indicator in SIDE_INDICATORS:
        if indicator in lname:
            return "side"
    
    # Check parent folder name for back subfolder
    parentDir = os.path.basename(os.path.dirname(imgPath)).lower()
    if parentDir == "back":
        return "back"
    if parentDir == "front":
        return "front"
    
    # Default to front
    return "front"


def scoreImage(imgPath, color, positionType):
    """
    Score an image for matching quality.
    Higher score = better match.
    """
    name = os.path.splitext(os.path.basename(imgPath))[0]
    cleaned = cleanFilename(name)
    lname = os.path.basename(imgPath).lower()
    
    # Color matching score (0-1)
    colorVariants = getColorVariants(color)
    colorScore = 0.0
    for variant in colorVariants:
        if variant and variant in cleaned:
            colorScore = 1.0
            break
    if colorScore == 0:
        # Fuzzy match
        colorNorm = normalize(color)
        colorScore = difflib.SequenceMatcher(None, colorNorm, cleaned).ratio()
    
    # Position type matching score - CRITICAL for correct selection
    imageType = classifyImage(imgPath)
    positionScore = 0.0
    
    if positionType == "back":
        if imageType == "back":
            positionScore = 2.0  # Strong match
        elif imageType == "front":
            positionScore = -3.0  # HEAVILY penalize wrong type
        else:
            positionScore = -1.0  # Side is also wrong for back
    
    elif positionType == "front":
        if imageType == "front":
            positionScore = 2.0  # Strong match
        elif imageType == "back":
            positionScore = -3.0  # HEAVILY penalize wrong type
        else:
            positionScore = 0.0  # Side is acceptable for front
    
    elif positionType == "dual":
        # Dual positions prefer front, but back is also acceptable
        if imageType == "front":
            positionScore = 1.0
        elif imageType == "back":
            positionScore = 0.5
    
    # Penalize flat/model views
    if "flat" in lname:
        positionScore -= 0.8
    if "model" in lname:
        positionScore -= 0.3
    if "folded" in lname:
        positionScore -= 0.5
    
    return colorScore + positionScore


def findImage(imageRoot, supplierName, partId, color, decorationLocation):
    """Find single best matching image."""
    candidates = findImageCandidates(imageRoot, supplierName, partId, color, decorationLocation)
    return candidates[0] if candidates else None


def findImageCandidates(imageRoot, supplierName, partId, color, decorationLocation, maxCandidates=6):
    """
    Return ordered list of candidate image paths (best-first).
    Uses YAML configuration for robust matching.
    """
    positionType = resolvePositionType(decorationLocation)
    pattern = buildPattern(partId, color)

    supplierFolder = resolveSupplierFolder(imageRoot, supplierName)

    if not supplierFolder or not os.path.isdir(supplierFolder):
        logError(f"Supplier folder not found: {supplierName} (root={imageRoot})")
        return []

    # Try to find part folder (could be direct or nested)
    partFolder = os.path.join(supplierFolder, partId)
    if not os.path.isdir(partFolder):
        # Try case-insensitive match
        try:
            subfolders = os.listdir(supplierFolder)
            for sf in subfolders:
                if normalize(sf) == normalize(partId):
                    partFolder = os.path.join(supplierFolder, sf)
                    break
        except Exception:
            pass
    
    if not os.path.isdir(partFolder):
        logError(f"Part folder not found: {partId} under supplier {supplierName}")
        return []

    # Check for back subfolder if looking for back images
    searchFolder = partFolder
    if positionType == "back":
        backFolder = os.path.join(partFolder, "back")
        if os.path.isdir(backFolder):
            # First try back subfolder only
            allMatches = collectMatches(backFolder, pattern)
            if allMatches:
                searchFolder = backFolder
                print(f"[INFO] Using 'back' subfolder for back position")
            else:
                allMatches = collectMatches(partFolder, pattern)
        else:
            allMatches = collectMatches(partFolder, pattern)
    else:
        allMatches = collectMatches(partFolder, pattern)
    
    if not allMatches:
        logError(f"Image not found | PartID={partId}, Color={color}, Supplier={supplierName}")
        return []

    # Score and sort all matches
    scoredMatches = []
    for imgPath in allMatches:
        score = scoreImage(imgPath, color, positionType)
        imgType = classifyImage(imgPath)
        scoredMatches.append((score, imgPath, imgType))
    
    # Sort by score (highest first)
    scoredMatches.sort(key=lambda x: x[0], reverse=True)
    
    # Build final candidate list
    candidates = []
    seen = set()
    
    for score, imgPath, imgType in scoredMatches:
        if imgPath not in seen:
            seen.add(imgPath)
            candidates.append(imgPath)
            
            # Log the selection
            if len(candidates) == 1:
                print(f"[INFO] Best image match: {os.path.basename(imgPath)} (type={imgType}, score={score:.2f})")
        
        if len(candidates) >= maxCandidates:
            break

    # Safety check: for back positions, verify we have a back image
    if positionType == "back" and candidates:
        firstType = classifyImage(candidates[0])
        if firstType != "back":
            print(f"[WARNING] No back image found for back position, using: {os.path.basename(candidates[0])}")
    
    return candidates


def validateImageFolder(imageRoot):
    """
    Validate that the image folder exists and has proper structure.
    
    Args:
        imageRoot: Path to check
        
    Returns:
        Tuple of (isValid, message, details)
    """
    if not imageRoot:
        return False, "No image folder specified", {}
    
    if not os.path.exists(imageRoot):
        return False, f"Folder does not exist: {imageRoot}", {}
    
    if not os.path.isdir(imageRoot):
        return False, f"Path is not a folder: {imageRoot}", {}
    
    # Count supplier folders
    details = {
        'supplierFolders': 0,
        'totalImages': 0,
        'suppliers': []
    }
    
    try:
        for item in os.listdir(imageRoot):
            itemPath = os.path.join(imageRoot, item)
            if os.path.isdir(itemPath):
                details['supplierFolders'] += 1
                details['suppliers'].append(item)
                
                # Count images in this supplier folder
                for root, _, files in os.walk(itemPath):
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in ALLOWED_EXTENSIONS:
                            details['totalImages'] += 1
    except Exception as e:
        return False, f"Error reading folder: {e}", details
    
    if details['supplierFolders'] == 0:
        return False, "No supplier folders found", details
    
    if details['totalImages'] == 0:
        return False, "No image files found", details
    
    message = f"Found {details['supplierFolders']} suppliers with {details['totalImages']} images"
    return True, message, details
