import os
import shutil
import re
from collections import defaultdict
from pathlib import Path

# Configuration
SOURCE_DIR = r"C:\Users\Akshat Mittal\Desktop\photoshopAutomation\Data_\Images"
DEST_DIR = r"C:\Users\Akshat Mittal\Desktop\photoshopAutomation\Data_1"

# View keywords to strip from filename to isolate color
VIEW_KEYWORDS = [
    "ModelFront", "ModelBack", "ModelSide", 
    "Front", "Back", "Side", 
    "FlatFront", "FlatBack",
    "1200W", "032017"
]

def clean_color_name(filename_stem, code):
    """
    Extracts color from filename by removing code and view keywords.
    """
    name = filename_stem
    if name.lower().startswith(code.lower()):
        name = name[len(code):]
        
    for key in VIEW_KEYWORDS:
        pattern = re.compile(re.escape(key), re.IGNORECASE)
        name = pattern.sub("", name)
        
    name = re.sub(r'\d+$', '', name)
    name = name.replace("-", " ").replace("_", " ")
    name = re.sub(r'\s+', ' ', name).strip()
    return name if name else "Unknown"

def get_letter_suffix(index):
    """
    Returns 'a', 'b', ..., 'z', 'aa', 'ab', etc. for a 0-based index.
    """
    if index < 26:
        return chr(97 + index)
    else:
        # Fallback for > 26: aa, ab... 
        # index 26 -> aa (0, 0) ? No, let's keep it simple.
        # z1, z2, z3 might be easier to read or just aa, ab.
        # The previous logic used 'z{n}', let's stick to that for simplicity unless specified
        return f"z{index-25}"

def main():
    print(f"Scanning {SOURCE_DIR}...")
    
    # Structure: groups[code][color] = [file_path, ...]
    groups = defaultdict(lambda: defaultdict(list))
    files_found = 0
    
    for root, dirs, files in os.walk(SOURCE_DIR):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')):
                full_path = Path(root) / file
                code = full_path.parent.name
                
                if full_path.parent.absolute() == Path(SOURCE_DIR).absolute():
                    continue
                    
                color = clean_color_name(full_path.stem, code)
                groups[code][color].append(full_path)
                files_found += 1

    print(f"Found {files_found} images.")

    # Clean Destination Directory
    if os.path.exists(DEST_DIR):
        print(f"Cleaning existing directory {DEST_DIR}...")
        shutil.rmtree(DEST_DIR)
    os.makedirs(DEST_DIR)

    print("Grouping and Copying to new structure...")
    
    mapping_lines = []
    
    # Sort Codes
    sorted_codes = sorted(groups.keys())
    
    for i, code in enumerate(sorted_codes, 1):
        # Create Folder for Code (e.g. "1")
        folder_name = str(i)
        folder_path = os.path.join(DEST_DIR, folder_name)
        os.makedirs(folder_path)
        
        mapping_lines.append(f"Folder {folder_name}: Code='{code}'")
        
        # Sort Colors for this Code
        sorted_colors = sorted(groups[code].keys())
        
        for j, color in enumerate(sorted_colors):
            letter = get_letter_suffix(j)
            variant_id = f"{i}{letter}"
            
            mapping_lines.append(f"  - {variant_id}: Color='{color}'")
            
            for src_file in groups[code][color]:
                # Rename: 1a_OriginalName.jpg
                new_filename = f"{variant_id}_{src_file.name}"
                dest_path = os.path.join(folder_path, new_filename)
                
                try:
                    shutil.copy2(src_file, dest_path)
                except Exception as e:
                    print(f"Error copying {src_file}: {e}")

    # Save Mapping
    with open(os.path.join(DEST_DIR, "mapping.txt"), "w") as f:
        f.write("\n".join(mapping_lines))
        
    print(f"Done! Images organized in {DEST_DIR}")

if __name__ == "__main__":
    main()
