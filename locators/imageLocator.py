import os
import re
import json
import difflib
from services.logger import logError

# Allowed image file extensions
ALLOWED_EXTENSIONS = (".jpg",)

# Location sets for front/back classification
FRONT_LOCATIONS = {
    "full-front", "left-bicep", "right-bicep", "left-chest", "right-chest",
    "left-collar", "right-collar", "left-cuff", "right-cuff",
    "left-hip", "right-hip", "left-sleeve", "right-sleeve",
    "left-thigh-high", "right-thigh-high", "on-pocket",
    "left-bicep-right-bicep",
    "left-chest-left-bicep-right-bicep",
    "left-chest-right-bicep",
    "left-chest-right-sleeve",
    "left-sleeve-right-sleeve",
    "right-chest-left-bicep",
    "right-chest-left-sleeve",
    "right-chest-lft-bicep-right-bicep"
}

BACK_LOCATIONS = {
    "full-back",
    "back-yoke"
}

BOTH_LOCATIONS = {
    "full-back & full-front"
}

# Words to ignore when matching filenames
IGNORE_FILENAME_WORDS = {
    "flat", "model", "side", "form", "front", "back", "rear",
    "cap", "hat", "main", "temp", "folded",
    "-1200w", "1030x1030", "front1", "front2", "front3",
    "back1", "back2", "back3", "back4",
    "psb", "ga", "inside", "interior", "sticker",
    "- copy", "modelfront", "modelback"
}

# Color abbreviation mappings
COLOR_ALIASES = {
    "gry": ["grey", "gray"],
    "blk": ["black"],
    "wht": ["white"],
    "bl": ["blue"],
    "rd": ["red"],
    "grn": ["green"],
    "nv": ["navy"],
    "nvy": ["navy"],
    "ht": ["heather"],
    "hthr": ["heather"],
    "ath": ["athletic"],
    "pk": ["pink"],
    "pr": ["purple"],
    "brn": ["brown"],
    "ylw": ["yellow"],
    "or": ["orange"],
    "char": ["charcoal"]
}

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
    for word in IGNORE_FILENAME_WORDS:
        base = base.replace(normalize(word), "")
    return base


def expandColorVariants(color: str):
    """Generate color name variants for matching."""
    base = normalize(color)
    variants = {base}

    for short, fulls in COLOR_ALIASES.items():
        for full in fulls:
            if full in base:
                variants.add(base.replace(full, short))
            if short in base:
                variants.add(base.replace(short, full))

    return variants


def resolveLocationType(location: str) -> str:
    """Determine if location is front, back, or side."""
    if not location:
        return "front"

    loc = location.strip().lower()
    for b in BACK_LOCATIONS:
        if b in loc:
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
                basename = f
                _indexEntries.append({'path': full, 'basename': basename, 'cleaned': cleaned})
                key = basename.lower()
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


def exactImageMatch(imageRoot, supplierName, partId, color):
    """Try exact match for image file."""
    if not supplierName or not partId or not color:
        return None
    target = f"{partId} {color}.jpg"
    supplierFolder = os.path.join(imageRoot, supplierName)

    # Quick direct path check
    direct = os.path.join(supplierFolder, target)
    if os.path.exists(direct):
        return direct

    # Use index if available
    try:
        _ensureIndex(imageRoot)
        paths = _indexByBasename.get(target.lower())
        if paths:
            for p in paths:
                if supplierFolder and os.path.commonpath([supplierFolder, p]) == supplierFolder:
                    return p
            return paths[0]
    except Exception:
        pass

    # Fallback to directory walk
    if os.path.isdir(supplierFolder):
        for root, _, files in os.walk(supplierFolder):
            if target in files:
                return os.path.join(root, target)

    partFolder = os.path.join(supplierFolder, partId)
    if os.path.isdir(partFolder):
        direct = os.path.join(partFolder, target)
        if os.path.exists(direct):
            return direct
        for root, _, files in os.walk(partFolder):
            if target in files:
                return os.path.join(root, target)

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


def findImage(imageRoot, supplierName, partId, color, decorationLocation):
    """Find single best matching image."""
    candidates = findImageCandidates(imageRoot, supplierName, partId, color, decorationLocation)
    return candidates[0] if candidates else None


def findImageCandidates(imageRoot, supplierName, partId, color, decorationLocation, maxCandidates=6):
    """Return ordered list of candidate image paths (best-first)."""
    locationType = resolveLocationType(decorationLocation)
    pattern = buildPattern(partId, color)

    supplierFolder = resolveSupplierFolder(imageRoot, supplierName)

    if not supplierFolder or not os.path.isdir(supplierFolder):
        logError(f"Supplier folder not found: {supplierName} (root={imageRoot})")
        return []

    partFolder = os.path.join(supplierFolder, partId)
    if not os.path.isdir(partFolder):
        logError(f"Part folder not found: {partId} under supplier {supplierName}")
        return []

    allMatches = collectMatches(partFolder, pattern)
    
    if not allMatches:
        logError(f"Image not found | PartID={partId}, Color={color}, Supplier={supplierName}")
        return []

    # Scoring function for color similarity and location boosts
    def score(imgPath):
        name = os.path.splitext(os.path.basename(imgPath))[0]
        cleaned = cleanFilename(name)
        c = normalize(color)
        if c and c in cleaned:
            base = 1.0
        else:
            base = difflib.SequenceMatcher(None, c, cleaned).ratio()

        lname = os.path.basename(imgPath).lower()
        if "front" in lname and "back" not in lname:
            base += 0.15
        if "back" in lname:
            base -= 0.15
        if "side" in lname:
            base -= 0.15
        if "flat" in lname:
            base -= 0.80
        return base

    front, back, side = [], [], []
    for img in allMatches:
        lname = img.lower()
        if "back" in lname:
            back.append(img)
        elif "side" in lname:
            side.append(img)
        elif "front" in lname:
            front.append(img)
        else:
            front.append(img)

    def orderedList(lst):
        return [i for _, i in sorted(((score(i), i) for i in lst), key=lambda x: x[0], reverse=True)]

    candidates = []
    if locationType == "front":
        candidates.extend(orderedList(front))
        candidates.extend(orderedList(side))
        candidates.extend(orderedList(back))
    elif locationType == "back":
        candidates.extend(orderedList(front))
        candidates.extend(orderedList(side))
        candidates.extend(orderedList(back))
    else:
        candidates.extend(orderedList(front))
        candidates.extend(orderedList(side))
        candidates.extend(orderedList(back))

    if not candidates:
        candidates = orderedList(allMatches)

    # Deduplicate and limit
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
        if len(out) >= maxCandidates:
            break

    return out


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

