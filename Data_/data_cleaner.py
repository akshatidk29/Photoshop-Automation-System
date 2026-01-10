import filecmp
from pathlib import Path
import shutil

# =======================
# CONFIG
# =======================
ANNOTATIONS_ROOT = Path("Annotations")
CATEGORIZED_DIR = ANNOTATIONS_ROOT / "categorized"

CATEGORIES = ["garment", "towel", "cap", "bag"]

# =======================
# SCRIPT
# =======================

def sync_category_annotations():
    if not ANNOTATIONS_ROOT.exists():
        raise RuntimeError("Annotations root folder not found")

    if not CATEGORIZED_DIR.exists():
        raise RuntimeError("categorized folder not found inside Annotations")

    replaced = 0
    checked = 0
    skipped = 0

    # Track files present in categories
    categorized_files = set()

    for category in CATEGORIES:
        category_dir = CATEGORIZED_DIR / category

        if not category_dir.exists():
            print(f"⚠ Skipping missing category folder: {category}")
            continue

        print(f"\n🔍 Checking category: {category}")

        for cat_file in category_dir.glob("*.txt"):
            categorized_files.add(cat_file.name)
            root_file = ANNOTATIONS_ROOT / cat_file.name
            checked += 1

            # Root annotation must exist
            if not root_file.exists():
                print(f"  ⏭ Root annotation missing, skipped: {cat_file.name}")
                skipped += 1
                continue

            # Compare file content
            same = filecmp.cmp(root_file, cat_file, shallow=False)

            if not same:
                shutil.copy2(root_file, cat_file)
                print(f"  🔁 Replaced: {cat_file.name}")
                replaced += 1
            else:
                print(f"  ✅ Same: {cat_file.name}")

    # =======================
    # FIND ROOT-ONLY FILES
    # =======================
    root_files = {f.name for f in ANNOTATIONS_ROOT.glob("*.txt")}
    missing_in_categories = root_files - categorized_files

    print("\n=======================")
    print("✔ Sync complete")
    print(f"Checked  : {checked}")
    print(f"Replaced : {replaced}")
    print(f"Skipped  : {skipped}")

    if missing_in_categories:
        print("\n📌 Present in root but missing from ALL categories:")
        for name in sorted(missing_in_categories):
            print(f"  • {name}")
    else:
        print("\n✅ All root annotations are present in at least one category")

    print("=======================\n")


if __name__ == "__main__":
    sync_category_annotations()
