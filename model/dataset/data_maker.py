import os
import shutil
import random

# ===================== CONFIG =====================
IMAGES_TRAIN_DIR = "model\\dataset\\images\\train"
LABELS_TRAIN_DIR = "model\\dataset\\labels\\train"

IMAGES_VAL_DIR   = "model\\dataset\\images\\val"
LABELS_VAL_DIR   = "model\\dataset\\labels\\val"
TRAIN_RATIO = 0.8  # 80% train, 20% val
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
# =================================================

# Create val directories
os.makedirs(IMAGES_VAL_DIR, exist_ok=True)
os.makedirs(LABELS_VAL_DIR, exist_ok=True)

# -------------------------------------------------
# STEP 1: Collect valid image-label pairs
# -------------------------------------------------
pairs = []

for file in os.listdir(IMAGES_TRAIN_DIR):
    name, ext = os.path.splitext(file)
    if ext.lower() in IMAGE_EXTS:
        img_path = os.path.join(IMAGES_TRAIN_DIR, file)
        lbl_path = os.path.join(LABELS_TRAIN_DIR, name + ".txt")

        if os.path.exists(lbl_path):
            pairs.append((img_path, lbl_path))

print(f"📦 Found {len(pairs)} image-label pairs")

# -------------------------------------------------
# STEP 2: Shuffle & split
# -------------------------------------------------
random.shuffle(pairs)

split_idx = int(len(pairs) * TRAIN_RATIO)
val_pairs = pairs[split_idx:]   # move these to val
train_pairs = pairs[:split_idx]

# -------------------------------------------------
# STEP 3: COPY val files (train stays as-is)
# -------------------------------------------------
for img, lbl in val_pairs:
    shutil.copy2(img, os.path.join(IMAGES_VAL_DIR, os.path.basename(img)))
    shutil.copy2(lbl, os.path.join(LABELS_VAL_DIR, os.path.basename(lbl)))

print(f"✅ Train samples: {len(train_pairs)} (kept in images/train)")
print(f"✅ Val samples:   {len(val_pairs)} (copied to images/val)")
