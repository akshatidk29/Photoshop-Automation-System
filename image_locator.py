import os
import re
import json
import difflib
from logger import log_error

# ==================================================
# CONFIG
# ==================================================
ALLOWED_EXTENSIONS = (".jpg",)# ".jpeg", ".png", ".webp", ".tiff")

# ==================================================
# LOCATION RULE MAP
# ==================================================
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

# ==================================================
# WORDS TO IGNORE FROM IMAGE FILENAMES
# ==================================================
IGNORE_FILENAME_WORDS = {
    "flat", "model", "side", "form", "front", "back", "rear",
    "cap", "hat", "main", "temp", "folded",
    "-1200w", "1030x1030", "front1", "front2", "front3",
    "back1", "back2", "back3", "back4",
    "psb", "ga", "inside", "interior", "sticker",
    "- copy", "modelfront", "modelback"
}

# ==================================================
# COLOR NORMALIZATION MAP
# ==================================================
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

# ==================================================
# HELPERS
# ==================================================
def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())

def clean_filename(name: str) -> str:
    base = normalize(name)
    for word in IGNORE_FILENAME_WORDS:
        base = base.replace(normalize(word), "")
    return base

def expand_color_variants(color: str):
    base = normalize(color)
    variants = {base}

    for short, fulls in COLOR_ALIASES.items():
        for full in fulls:
            if full in base:
                variants.add(base.replace(full, short))
            if short in base:
                variants.add(base.replace(short, full))

    return variants

def resolve_location_type(location: str) -> str:
    if not location:
        return "front"

    loc = location.strip().lower()
    # explicit side mention -> side
    # if "side" in loc:
    #     return "side"
    # if any back-location token appears, treat as back
    for b in BACK_LOCATIONS:
        if b in loc:
            return "back"
    # default to front (also covers previous 'both' cases)
    return "front"

# ==================================================
# EXACT MATCH (SAFE)
# ==================================================
def exact_image_match(image_root, supplier_name, part_id, color):
    # Preserve original exact-match behavior (do not change logic)
    if not supplier_name or not part_id or not color:
        return None
    target = f"{part_id} {color}.jpg"
    supplier_folder = os.path.join(image_root, supplier_name)

    # Quick direct path check (fast)
    direct = os.path.join(supplier_folder, target)
    if os.path.exists(direct):
        return direct

    # Use index if available: look for exact basename match
    try:
        _ensure_index(image_root)
        paths = _index_by_basename.get(target.lower())
        if paths:
            # prefer supplier folder occurrence
            for p in paths:
                if supplier_folder and os.path.commonpath([supplier_folder, p]) == supplier_folder:
                    return p
            return paths[0]
    except Exception:
        pass

    # Fallback to previous directory walks (rare)
    if os.path.isdir(supplier_folder):
        for root, _, files in os.walk(supplier_folder):
            if target in files:
                return os.path.join(root, target)

    part_folder = os.path.join(supplier_folder, part_id)
    if os.path.isdir(part_folder):
        direct = os.path.join(part_folder, target)
        if os.path.exists(direct):
            return direct
        for root, _, files in os.walk(part_folder):
            if target in files:
                return os.path.join(root, target)

    return None


def load_supplier_mappings():
    """Load learned supplier -> folder mappings from assets/learned/image_mappings.json"""
    mappings_path = os.path.join("assets", "learned", "image_mappings.json")
    try:
        with open(mappings_path, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


# -----------------------
# In-memory index (build once per image_root)
# -----------------------
_image_index = None
_index_root = None
_index_by_basename = {}
_index_entries = []

def _ensure_index(image_root):
    """Build or reuse an in-memory index of image files under image_root.

    Index structure:
      - _index_entries: list of {'path','basename','cleaned'}
      - _index_by_basename: map lowercase basename -> [paths]
    """
    global _image_index, _index_root, _index_by_basename, _index_entries
    if _image_index is not None and _index_root == os.path.abspath(image_root):
        return

    _index_entries = []
    _index_by_basename = {}
    root_abs = os.path.abspath(image_root)
    _index_root = root_abs

    try:
        for r, _, files in os.walk(root_abs):
            for f in files:
                name, ext = os.path.splitext(f)
                if ext.lower() not in ALLOWED_EXTENSIONS:
                    continue
                full = os.path.join(r, f)
                cleaned = clean_filename(name)
                basename = f
                _index_entries.append({'path': full, 'basename': basename, 'cleaned': cleaned})
                key = basename.lower()
                _index_by_basename.setdefault(key, []).append(full)
        _image_index = True
    except Exception as e:
        # if index build fails, keep index None so callers fallback to os.walk
        _image_index = None
        log_error(f"Failed to build image index for {image_root}: {e}")


def resolve_supplier_folder(image_root, supplier_name):
    """Try to find the supplier folder on disk using mappings, normalization or fuzzy match."""
    if not supplier_name:
        return None

    # direct path
    direct = os.path.join(image_root, supplier_name)
    if os.path.isdir(direct):
        return direct

    # learned mappings
    mappings = load_supplier_mappings()
    mapped = mappings.get(supplier_name) or mappings.get(supplier_name.lower())
    if mapped:
        candidate = os.path.join(image_root, mapped)
        if os.path.isdir(candidate):
            return candidate

    # try normalized exact or substring match against folders in image_root
    try:
        folders = [d for d in os.listdir(image_root) if os.path.isdir(os.path.join(image_root, d))]
    except Exception:
        folders = []

    norm = normalize(supplier_name)
    # exact normalized match
    for f in folders:
        if normalize(f) == norm:
            return os.path.join(image_root, f)

    # substring match (supplier short vs long)
    for f in folders:
        nf = normalize(f)
        if norm in nf or nf in norm:
            return os.path.join(image_root, f)

    # fuzzy match as last resort
    choices = {f: difflib.SequenceMatcher(None, normalize(f), norm).ratio() for f in folders}
    if choices:
        best = max(choices.items(), key=lambda x: x[1])
        if best[1] >= 0.6:
            return os.path.join(image_root, best[0])

    return None

# ==================================================
# REGEX SEARCH
# ==================================================
def build_pattern(part_id, color):
    # Match files that contain the part id; color matching is done later via scoring
    part = normalize(part_id)
    ext = "|".join(e[1:] for e in ALLOWED_EXTENSIONS)
    return re.compile(rf".*{part}.*\.({ext})$", re.I)

def collect_matches(root, pattern):
    # Use pre-built index when available (faster). Pattern is regex compiled from part id.
    matches = []
    try:
        _ensure_index(root)
        root_abs = os.path.abspath(root)
        for e in _index_entries:
            # restrict to the requested root subtree
            try:
                if os.path.commonpath([root_abs, os.path.abspath(e['path'])]) != root_abs:
                    continue
            except Exception:
                continue
            # match against cleaned name + extension
            name_ext = e['cleaned'] + os.path.splitext(e['basename'])[1].lower()
            if pattern.search(name_ext):
                matches.append(e['path'])
        return matches
    except Exception:
        # fallback to filesystem walk
        matches = []
        for r, _, files in os.walk(root):
            for f in files:
                name, ext = os.path.splitext(f)
                if ext.lower() not in ALLOWED_EXTENSIONS:
                    continue

                cleaned = clean_filename(name) + ext.lower()
                if pattern.search(cleaned):
                    matches.append(os.path.join(r, f))
        return matches

# ==================================================
# MAIN IMAGE FINDER (GLOBAL ISSUE FIXED)
# ==================================================
def find_image(image_root, supplier_name, part_id, color, decoration_location):
    # Keep compatibility: return top candidate (or None)
    candidates = find_image_candidates(image_root, supplier_name, part_id, color, decoration_location)
    return candidates[0] if candidates else None


def find_image_candidates(image_root, supplier_name, part_id, color, decoration_location, max_candidates=6):
    """Return ordered list of candidate image paths (best-first).

    Caller should try candidates sequentially and only log row-level errors after
    exhausting the list — this allows falling back to the next image when the
    first causes processing errors.
    """
    # STEP 1 — EXACT MATCH (preserve original behavior)
    # exact = exact_image_match(image_root, supplier_name, part_id, color)
    # if exact:
    #     return [exact]

    location_type = resolve_location_type(decoration_location)
    pattern = build_pattern(part_id, color)

    supplier_folder = resolve_supplier_folder(image_root, supplier_name)

    # STRICT PATH: only search under supplier/part_id per agreed structure
    if not supplier_folder or not os.path.isdir(supplier_folder):
        log_error(f"Supplier folder not found: {supplier_name} (root={image_root})")
        return []

    part_folder = os.path.join(supplier_folder, part_id)
    if not os.path.isdir(part_folder):
        log_error(f"Part folder not found: {part_id} under supplier {supplier_name}")
        return []

    all_matches = collect_matches(part_folder, pattern)
    
    if not all_matches:
        log_error(f"Image not found | PartID={part_id}, Color={color}, Supplier={supplier_name}")
        return []

    # scoring by color similarity with small location boosts/penalties
    def score(img_path):
        name = os.path.splitext(os.path.basename(img_path))[0]
        cleaned = clean_filename(name)
        c = normalize(color)
        if c and c in cleaned:
            base = 1.0
        else:
            base = difflib.SequenceMatcher(None, c, cleaned).ratio()

        # lname = img_path.lower()
        lname = os.path.basename(img_path).lower()
        # print("NAME.......................----------------",lname)
        # boost explicit fronts, deboost sides
        if "front" in lname and "back" not in lname:
            base += 0.15
        if "back" in lname:
            base -= 0.15
        if "side" in lname:
            base -= 0.15
        if "flat" in lname:
            base -=0.80
        return base

    front, back, side = [], [], []
    for img in all_matches:
        lname = img.lower()
        if "back" in lname:
            back.append(img)
        elif "side" in lname:
            side.append(img)
        elif "front" in lname:
            front.append(img)
        else:
            # default unclear names to front
            front.append(img)

    def ordered_list(lst):
        return [i for _, i in sorted(((score(i), i) for i in lst), key=lambda x: x[0], reverse=True)]

    candidates = []
    # Respect decoration location: prefer requested type first
    if location_type == "front":
        candidates.extend(ordered_list(front))
        candidates.extend(ordered_list(side))
        candidates.extend(ordered_list(back))
    elif location_type == "back":
        candidates.extend(ordered_list(front))
        candidates.extend(ordered_list(side))
        candidates.extend(ordered_list(back))
    else:  # side
        candidates.extend(ordered_list(front))
        candidates.extend(ordered_list(side))
        candidates.extend(ordered_list(back))

    # final fallback: all matches ordered by score
    if not candidates:
        candidates = ordered_list(all_matches)

    # unique preserve order and limit
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
        if len(out) >= max_candidates:
            break

    return out

# ==================================================
# LOGO FINDER
# ==================================================
def find_logo(logo_root, decoration_code):
    if not decoration_code:
        return None

    for root, _, files in os.walk(logo_root):
        for ext in ( ".pdf",):
            name = f"{decoration_code}{ext}"
            if name in files:
                return os.path.join(root, name)

    log_error(f"Logo not found: {decoration_code}")
    return None




# import os
# import re
# from logger import log_error

# # ==================================================
# # CONFIG
# # ==================================================
# ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".tiff")

# # ==================================================
# # LOCATION RULE MAP
# # ==================================================
# FRONT_LOCATIONS = {
#     "full-front", "left-bicep", "right-bicep", "left-chest", "right-chest",
#     "left-collar", "right-collar", "left-cuff", "right-cuff",
#     "left-hip", "right-hip", "left-sleeve", "right-sleeve",
#     "left-thigh-high", "right-thigh-high", "on-pocket",
#     "left-bicep-right-bicep",
#     "left-chest-left-bicep-right-bicep",
#     "left-chest-right-bicep",
#     "left-chest-right-sleeve",
#     "left-sleeve-right-sleeve",
#     "right-chest-left-bicep",
#     "right-chest-left-sleeve",
#     "right-chest-lft-bicep-right-bicep"
# }

# BACK_LOCATIONS = {
#     "full-back",
#     "back-yoke"
# }

# BOTH_LOCATIONS = {
#     "full-back & full-front"
# }

# # ==================================================
# # WORDS TO IGNORE FROM IMAGE FILENAMES
# # ==================================================
# IGNORE_FILENAME_WORDS = {
#     "flat", "model", "side", "form", "front", "back", "rear",
#     "cap", "hat", "main", "temp", "folded",
#     "-1200w", "1030x1030", "front1", "front2", "front3",
#     "back1", "back2", "back3", "back4",
#     "psb", "ga", "inside", "interior", "sticker","- Copy","ModelFront","ModelBack"
# }

# # ==================================================
# # COLOR NORMALIZATION MAP (FULL)
# # ==================================================
# COLOR_ALIASES = {
#     "sfty": ["safety"],
#     "gry": ["grey", "gray"],
#     "ht": ["heather"],
#     "hthr": ["heather"],
#     "ret": ["retro"],
#     "grn": ["green"],
#     "ath": ["athletic"],
#     "blk": ["black"],
#     "bk": ["black"],
#     "clsc": ["classic"],
#     "bl": ["blue"],
#     "yllw": ["yellow"],
#     "vtg": ["vintage"],
#     "fr": ["frost"],
#     "mil": ["military"],
#     "pr": ["purple"],
#     "prpl": ["purple"],
#     "rd": ["red"],
#     "ry": ["royal"],
#     "nv": ["navy"],
#     "nvy": ["navy"],
#     "flnt": ["flint"],
#     "mar": ["maroon"],
#     "turq": ["turquoise"],
#     "mari": ["maritime"],
#     "fsch": ["fuchsia"],
#     "brt": ["bright"],
#     "crnation": ["carnation"],
#     "pk": ["pink"],
#     "brn": ["brown"],
#     "euclptus": ["eucalyptus"],
#     "dsrt": ["desert"],
#     "oat": ["oatmeal"],
#     "lvndr": ["lavender"],
#     "dp": ["deep"],
#     "or": ["orange"],
#     "rs": ["raspberry"],
#     "eggplnt": ["eggplant"],
#     "char": ["charcoal"],
#     "wtrmln": ["watermelon"],
#     "dsty": ["dusty"],
#     "euclps": ["eucalyptus"],
#     "tr": ["true"],
#     "dk": ["dark"],
#     "lt": ["light"],
#     "wstria": ["wisteria"],
#     "nstlga": ["nostalgia"],
#     "rse": ["rose"],
#     "wht": ["white"],
#     "bffl": ["buffalo"],
#     "ck": ["check"],
#     "sil": ["silver"],
#     "gdna": ["gardenia"],
#     "grvl": ["grevel"],
#     "md": ["medium"],
#     "irs": ["irish"],
#     "ivr": ["ivory"]
# }

# # ==================================================
# # HELPERS
# # ==================================================
# def normalize(text: str) -> str:
#     return re.sub(r"[^a-z0-9]", "", text.lower())

# def clean_filename(name: str) -> str:
#     base = normalize(name)
#     for word in IGNORE_FILENAME_WORDS:
#         base = base.replace(normalize(word), "")
#     return base

# def expand_color_variants(color: str):
#     base = normalize(color)
#     variants = {base}

#     for short, fulls in COLOR_ALIASES.items():
#         for full in fulls:
#             if full in base:
#                 variants.add(base.replace(full, short))
#             if short in base:
#                 variants.add(base.replace(short, full))

#     return variants

# def resolve_location_type(location: str):
#     if not location:
#         return "front"

#     loc = location.strip().lower()

#     if loc in BOTH_LOCATIONS:
#         return "both"
#     if loc in BACK_LOCATIONS:
#         return "back"
#     return "front"

# # ==================================================
# # OLD EXACT MATCH (UNCHANGED LOGIC)
# # ==================================================
# def exact_image_match(image_root, supplier_name, part_id, color):
#     target = f"{part_id} {color}.jpg"

#     if not supplier_name:
#         return None

#     supplier_folder = os.path.join(image_root, supplier_name)
#     if not os.path.exists(supplier_folder):
#         return None

#     # Direct
#     direct = os.path.join(supplier_folder, target)
#     if os.path.exists(direct):
#         return direct

#     # Walk supplier
#     for root, _, files in os.walk(supplier_folder):
#         if target in files:
#             return os.path.join(root, target)

#     # Supplier / PartID
#     part_folder = os.path.join(supplier_folder, part_id)
#     if os.path.exists(part_folder):
#         direct = os.path.join(part_folder, target)
#         if os.path.exists(direct):
#             return direct

#         for root, _, files in os.walk(part_folder):
#             if target in files:
#                 return os.path.join(root, target)

#     return None

# # ==================================================
# # REGEX MATCH
# # ==================================================
# def build_pattern(part_id, color):
#     part = normalize(part_id)
#     color_variants = expand_color_variants(color)

#     color_regex = "|".join(color_variants)
#     ext = "|".join(e[1:] for e in ALLOWED_EXTENSIONS)

#     return re.compile(rf".*{part}.*({color_regex}).*\.({ext})$", re.I)

# def collect_matches(root, pattern):
#     matches = []
#     for r, _, files in os.walk(root):
#         for f in files:
#             name, ext = os.path.splitext(f)

#             # skip non-image files early
#             if ext.lower() not in ALLOWED_EXTENSIONS:
#                 continue

#             # clean only the filename (keep extension for regex)
#             cleaned_name = clean_filename(name) + ext.lower()

#             # use search instead of match (more flexible)
#             if pattern.search(cleaned_name):
#                 matches.append(os.path.join(r, f))

#     return matches


# # ==================================================
# # MAIN IMAGE FINDER (BUG FIXED)
# # ==================================================
# def find_image(
#     image_root,
#     supplier_name,
#     supplier_part_id,
#     supplier_color,
#     decoration_location
# ):
#     # STEP 0 — EXACT MATCH FIRST
#     exact = exact_image_match(
#         image_root,
#         supplier_name,
#         supplier_part_id,
#         supplier_color
#     )
#     if exact:
#         return exact

#     location_type = resolve_location_type(decoration_location)
#     pattern = build_pattern(supplier_part_id, supplier_color)

#     supplier_folder = os.path.join(image_root, supplier_name)
#     roots = [supplier_folder] if os.path.exists(supplier_folder) else [image_root]

#     all_matches = []
#     for root in roots:
#         all_matches.extend(collect_matches(root, pattern))

#     if not all_matches:
#         log_error(
#             f"Image not found | PartID={supplier_part_id}, "
#             f"Color={supplier_color}, Supplier={supplier_name}"
#         )
#         return None

#     # ==================================================
#     # 🔥 STRICT LOCATION ENFORCEMENT (FIX)
#     # ==================================================
#     front_images = []
#     back_images = []
#     both_images = []

#     for img in all_matches:
#         fname = img.lower()
#         if "front" in fname and "back" in fname:
#             both_images.append(img)
#         elif "back" in fname:
#             back_images.append(img)
#         else:
#             front_images.append(img)

#     if location_type == "front" and front_images:
#         return front_images[0]

#     if location_type == "back" and back_images:
#         return back_images[0]

#     if location_type == "both" and both_images:
#         return both_images[0]

#     # HARD FALLBACK (ONLY IF REQUIRED TYPE MISSING)
#     if location_type == "front" and back_images:
#         return back_images[0]

#     if location_type == "back" and front_images:
#         return front_images[0]

#     return all_matches[0]

# # ==================================================
# # LOGO FINDER
# # ==================================================
# def find_logo(logo_root, decoration_code):
#     for ext in (".pdf", ".png", ".jpg", ".jpeg"):
#         name = f"{decoration_code}{ext}"
#         for root, _, files in os.walk(logo_root):
#             if name in files:
#                 return os.path.join(root, name)

#     log_error(f"Logo not found: {decoration_code}")
#     return None
