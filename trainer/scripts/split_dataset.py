# split_dataset.py
import os, random, shutil

images = "dataset/images/"
labels = "dataset/labels/"

train_ratio = 0.8
files = os.listdir(images)
random.shuffle(files)

split = int(len(files) * train_ratio)
train, val = files[:split], files[split:]

for f in train:
    shutil.move(f"{images}/{f}", "dataset/images/train/")
    shutil.move(f"{labels}/{f.replace('.jpg','.txt')}", "dataset/labels/train/")

for f in val:
    shutil.move(f"{images}/{f}", "dataset/images/val/")
    shutil.move(f"{labels}/{f.replace('.jpg','.txt')}", "dataset/labels/val/")
