import os
import shutil
import random

# ===================== CONFIG =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "images")
LABELS_DIR = os.path.join(BASE_DIR, "labels")

IMAGES_TRAIN_DIR = os.path.join(IMAGES_DIR, "train")
LABELS_TRAIN_DIR = os.path.join(LABELS_DIR, "train")

IMAGES_VAL_DIR   = os.path.join(IMAGES_DIR, "val")
LABELS_VAL_DIR   = os.path.join(LABELS_DIR, "val")

TRAIN_RATIO = 0.8  # 80% train, 20% val
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
# =================================================

def get_all_pairs():
    """Collects all image-label pairs from both train and val directories."""
    all_pairs = []
    
    # Check both train and val folders for existing data
    for folder in ["train", "val"]:
        img_folder = os.path.join(IMAGES_DIR, folder)
        lbl_folder = os.path.join(LABELS_DIR, folder)
        
        if not os.path.exists(img_folder):
            continue
            
        for file in os.listdir(img_folder):
            name, ext = os.path.splitext(file)
            if ext.lower() in IMAGE_EXTS:
                img_path = os.path.join(img_folder, file)
                lbl_path = os.path.join(lbl_folder, name + ".txt")

                if os.path.exists(lbl_path):
                    all_pairs.append((img_path, lbl_path))
                else:
                    print(f"⚠️ Warning: No label found for {file}")
                    
    return all_pairs

def main():
    # Ensure directories exist
    os.makedirs(IMAGES_TRAIN_DIR, exist_ok=True)
    os.makedirs(LABELS_TRAIN_DIR, exist_ok=True)
    os.makedirs(IMAGES_VAL_DIR, exist_ok=True)
    os.makedirs(LABELS_VAL_DIR, exist_ok=True)

    # 1. Collect all pairs
    pairs = get_all_pairs()
    print(f"📦 Total unique image-label pairs found: {len(pairs)}")

    if not pairs:
        print("❌ No pairs found. Check your images/ and labels/ directories.")
        return

    # 2. Shuffle & Split
    random.shuffle(pairs)
    split_idx = int(len(pairs) * TRAIN_RATIO)
    train_pairs = pairs[:split_idx]
    val_pairs = pairs[split_idx:]

    # 3. Move files to their new homes
    def move_pairs(pair_list, target_img_dir, target_lbl_dir, label):
        count = 0
        for img_src, lbl_src in pair_list:
            img_dst = os.path.join(target_img_dir, os.path.basename(img_src))
            lbl_dst = os.path.join(target_lbl_dir, os.path.basename(lbl_src))
            
            # Use shutil.move only if source and destination are different
            if os.path.abspath(img_src) != os.path.abspath(img_dst):
                shutil.move(img_src, img_dst)
            if os.path.abspath(lbl_src) != os.path.abspath(lbl_dst):
                shutil.move(lbl_src, lbl_dst)
            count += 1
        print(f"✅ {label} samples: {count}")

    move_pairs(train_pairs, IMAGES_TRAIN_DIR, LABELS_TRAIN_DIR, "Train")
    move_pairs(val_pairs, IMAGES_VAL_DIR, LABELS_VAL_DIR, "Val")

    print("\n✨ Dataset reorganization complete. No data leakage between train and val.")

if __name__ == "__main__":
    main()

