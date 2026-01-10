import filecmp
from pathlib import Path
import shutil

# =======================
# CONFIG
# =======================
ANNOTATIONS_ROOT = Path("Annotations")
ANNOT_CATEGORIZED = ANNOTATIONS_ROOT / "categorized"

IMAGES_CATEGORIZED = Path("categorized")   # OUTSIDE Annotations

CATEGORIES = ["garment", "towel", "cap", "bag"]
IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".bmp"]

# =======================
# SCRIPT
# =======================

def sync_and_check():
    if not ANNOTATIONS_ROOT.exists():
        raise RuntimeError("Annotations root folder not found")

    if not ANNOT_CATEGORIZED.exists():
        raise RuntimeError("Annotations/categorized folder not found")

    if not IMAGES_CATEGORIZED.exists():
        raise RuntimeError("categorized (images) folder not found")

    replaced = 0
    checked = 0
    skipped = 0

    categorized_annotation_files = set()

    print("\n========== PART 1: ANNOTATION SYNC ==========")

    for category in CATEGORIES:
        cat_ann_dir = ANNOT_CATEGORIZED / category

        if not cat_ann_dir.exists():
            print(f"⚠ Missing annotation category folder: {category}")
            continue

        print(f"\n🔍 Checking annotations: {category}")

        for ann_file in cat_ann_dir.glob("*.txt"):
            categorized_annotation_files.add(ann_file.name)
            root_ann = ANNOTATIONS_ROOT / ann_file.name
            checked += 1

            if not root_ann.exists():
                print(f"  ⏭ Root annotation missing: {ann_file.name}")
                skipped += 1
                continue

            if not filecmp.cmp(root_ann, ann_file, shallow=False):
                shutil.copy2(root_ann, ann_file)
                print(f"  🔁 Replaced annotation: {ann_file.name}")
                replaced += 1
            else:
                print(f"  ✅ Annotation OK: {ann_file.name}")

    # Root-only annotations
    root_annotations = {f.name for f in ANNOTATIONS_ROOT.glob("*.txt")}
    missing_in_categories = root_annotations - categorized_annotation_files

    print("\n📌 Root annotations missing from ALL categories:")
    if missing_in_categories:
        for f in sorted(missing_in_categories):
            print(f"  • {f}")
    else:
        print("  ✅ None")

    print("\n========== PART 2: IMAGE ↔ ANNOTATION CHECK ==========")

    for category in CATEGORIES:
        img_dir = IMAGES_CATEGORIZED / category
        ann_dir = ANNOT_CATEGORIZED / category

        if not img_dir.exists():
            print(f"\n⚠ Missing image category folder: {category}")
            continue

        if not ann_dir.exists():
            print(f"\n⚠ Missing annotation category folder: {category}")
            continue

        print(f"\n🔍 Checking images vs annotations: {category}")

        images = {
            f.stem: f
            for f in img_dir.iterdir()
            if f.suffix.lower() in IMAGE_EXTS
        }

        annotations = {
            f.stem: f
            for f in ann_dir.glob("*.txt")
        }

        # Images without annotations
        missing_ann = images.keys() - annotations.keys()
        for name in sorted(missing_ann):
            print(f"  ❌ Image has NO annotation: {images[name].name}")

        # Annotations without images
        missing_img = annotations.keys() - images.keys()
        for name in sorted(missing_img):
            print(f"  ❌ Annotation has NO image: {annotations[name].name}")

        if not missing_ann and not missing_img:
            print("  ✅ All images and annotations are paired correctly")

    print("\n========== SUMMARY ==========")
    print(f"Checked annotations : {checked}")
    print(f"Replaced annotations: {replaced}")
    print(f"Skipped             : {skipped}")
    print("================================\n")


if __name__ == "__main__":
    sync_and_check()
