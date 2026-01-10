# Galaxy Morphology Classification - Beginner-Friendly Guide

A simple, easy-to-follow project for classifying galaxy images into 10 categories using ResNet-50.
 

## 📋 What You'll Build

**Input**: Galaxy images (256×256 pixels)

**Output**: One of 10 galaxy types:
1. Spiral
2. Barred Spiral
3. Elliptical
4. Lenticular
5. Irregular
6. Merging
7. Edge-on (no bulge)
8. Edge-on (with bulge)
9. Ring
10. Peculiar

**Dataset**:
- Training: 14,188 images
- Validation: 3,548 images

---

## 🚀 Quick Start (5 Steps)

### Step 1: Install Python Libraries

```bash
# Install just what you need (works on 4GB RAM!)
pip install torch torchvision pillow numpy pandas matplotlib scikit-learn tqdm
```

### Step 2: Organize Your Data

Put your images in this structure:

```
galaxy_project/
├── train/
│   ├── spiral/
│   │   ├── img1.jpg
│   │   ├── img2.jpg
│   │   └── ...
│   ├── barred_spiral/
│   ├── elliptical/
│   └── ... (all 10 classes)
│
└── val/
    ├── spiral/
    ├── barred_spiral/
    └── ... (all 10 classes)
```

### Step 3: Copy This Training Code

Save as `train.py`:

```python
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
import time

# IMPORTANT: Settings for 4GB RAM
BATCH_SIZE = 8          # Small batch = less memory
NUM_WORKERS = 0         # Avoid multiprocessing overhead
IMAGE_SIZE = 128        # Smaller images = less memory (instead of 224)
EPOCHS = 20

# Check if GPU available
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# Simple data preprocessing
train_transform = transforms.Compose([
    transforms.Resize(IMAGE_SIZE),
    transforms.RandomHorizontalFlip(),      # Flip image left-right
    transforms.RandomRotation(30),          # Rotate up to 30 degrees
    transforms.ToTensor(),                  # Convert to numbers
    transforms.Normalize([0.485, 0.456, 0.406],  # ImageNet mean
                        [0.229, 0.224, 0.225])   # ImageNet std
])

val_transform = transforms.Compose([
    transforms.Resize(IMAGE_SIZE),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                        [0.229, 0.224, 0.225])
])

# Load data
print("Loading data...")
train_data = datasets.ImageFolder('train/', transform=train_transform)
val_data = datasets.ImageFolder('val/', transform=val_transform)

train_loader = DataLoader(train_data, batch_size=BATCH_SIZE, 
                          shuffle=True, num_workers=NUM_WORKERS)
val_loader = DataLoader(val_data, batch_size=BATCH_SIZE, 
                        shuffle=False, num_workers=NUM_WORKERS)

print(f"Train images: {len(train_data)}")
print(f"Val images: {len(val_data)}")
print(f"Classes: {train_data.classes}")

# Create ResNet-50 model
print("\nCreating model...")
model = models.resnet50(pretrained=True)  # Download pre-trained weights

# Freeze early layers to save memory
for param in model.parameters():
    param.requires_grad = False

# Only train the last layer
model.fc = nn.Linear(model.fc.in_features, 10)  # 10 galaxy classes
model = model.to(device)

# Training settings
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.fc.parameters(), lr=0.001)

# Training function
def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        running_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()
    
    accuracy = 100. * correct / total
    avg_loss = running_loss / len(loader)
    return avg_loss, accuracy

# Validation function
def validate(model, loader, criterion, device):
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            
            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
    
    accuracy = 100. * correct / total
    avg_loss = running_loss / len(loader)
    return avg_loss, accuracy

# Training loop
print("\nStarting training...")
best_val_acc = 0.0

for epoch in range(EPOCHS):
    start_time = time.time()
    
    train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)
    val_loss, val_acc = validate(model, val_loader, criterion, device)
    
    epoch_time = time.time() - start_time
    
    print(f"Epoch {epoch+1}/{EPOCHS} ({epoch_time:.1f}s)")
    print(f"  Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.2f}%")
    print(f"  Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.2f}%")
    
    # Save best model
    if val_acc > best_val_acc:
        best_val_acc = val_acc
        torch.save(model.state_dict(), 'best_model.pth')
        print(f"  ✓ Saved best model (Val Acc: {val_acc:.2f}%)")
    print()

print(f"Training complete! Best validation accuracy: {best_val_acc:.2f}%")
```

### Step 4: Run Training

```bash
# Train the model (takes 1-2 hours on CPU, 15-20 min on GPU)
python train.py
```

You'll see output like:
```
Using device: cpu
Loading data...
Train images: 14188
Val images: 3548
Classes: ['spiral', 'barred_spiral', 'elliptical', ...]

Creating model...
Starting training...

Epoch 1/20 (145.2s)
  Train Loss: 1.2345 | Train Acc: 65.32%
  Val Loss: 0.9876 | Val Acc: 70.12%
  ✓ Saved best model (Val Acc: 70.12%)

Epoch 2/20 (142.8s)
  Train Loss: 0.8765 | Train Acc: 72.45%
  Val Loss: 0.8123 | Val Acc: 74.56%
  ✓ Saved best model (Val Acc: 74.56%)
...
```

### Step 5: Test Your Model

Save as `predict.py`:

```python
import torch
from torchvision import transforms, models
from PIL import Image
import torch.nn as nn

# Load class names (should match your folder names)
class_names = ['spiral', 'barred_spiral', 'elliptical', 'lenticular', 
               'irregular', 'merging', 'edge_on_no_bulge', 
               'edge_on_bulge', 'ring', 'peculiar']

# Load model
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = models.resnet50(pretrained=False)
model.fc = nn.Linear(model.fc.in_features, 10)
model.load_state_dict(torch.load('best_model.pth', map_location=device))
model = model.to(device)
model.eval()

# Image preprocessing
transform = transforms.Compose([
    transforms.Resize(128),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                        [0.229, 0.224, 0.225])
])

# Predict function
def predict_image(image_path):
    image = Image.open(image_path).convert('RGB')
    image_tensor = transform(image).unsqueeze(0).to(device)
    
    with torch.no_grad():
        output = model(image_tensor)
        probabilities = torch.nn.functional.softmax(output[0], dim=0)
        confidence, predicted = torch.max(probabilities, 0)
    
    predicted_class = class_names[predicted.item()]
    confidence_pct = confidence.item() * 100
    
    print(f"\nPrediction: {predicted_class}")
    print(f"Confidence: {confidence_pct:.2f}%")
    print(f"\nTop 3 predictions:")
    
    top3_prob, top3_idx = torch.topk(probabilities, 3)
    for i in range(3):
        print(f"  {i+1}. {class_names[top3_idx[i]]}: {top3_prob[i]*100:.2f}%")

# Test on a single image
predict_image('val/spiral/example.jpg')
```

Run it:
```bash
python predict.py
```

Output:
```
Prediction: spiral
Confidence: 87.34%

Top 3 predictions:
  1. spiral: 87.34%
  2. barred_spiral: 8.21%
  3. lenticular: 2.45%
```

---

## 📊 Evaluate Your Model

Save as `evaluate.py`:

```python
import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import torch.nn as nn

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Load validation data
val_transform = transforms.Compose([
    transforms.Resize(128),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                        [0.229, 0.224, 0.225])
])

val_data = datasets.ImageFolder('val/', transform=val_transform)
val_loader = DataLoader(val_data, batch_size=8, shuffle=False)

# Load model
model = models.resnet50(pretrained=False)
model.fc = nn.Linear(model.fc.in_features, 10)
model.load_state_dict(torch.load('best_model.pth', map_location=device))
model = model.to(device)
model.eval()

# Get predictions
all_preds = []
all_labels = []

print("Evaluating model...")
with torch.no_grad():
    for images, labels in val_loader:
        images = images.to(device)
        outputs = model(images)
        _, predicted = outputs.max(1)
        
        all_preds.extend(predicted.cpu().numpy())
        all_labels.extend(labels.numpy())

# Print detailed metrics
print("\nClassification Report:")
print(classification_report(all_labels, all_preds, 
                          target_names=val_data.classes,
                          digits=3))

# Create confusion matrix
cm = confusion_matrix(all_labels, all_preds)

# Plot confusion matrix
plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=val_data.classes,
            yticklabels=val_data.classes)
plt.title('Confusion Matrix')
plt.ylabel('True Label')
plt.xlabel('Predicted Label')
plt.tight_layout()
plt.savefig('confusion_matrix.png', dpi=150)
print("\nConfusion matrix saved as 'confusion_matrix.png'")

# Calculate per-class accuracy
class_correct = cm.diagonal()
class_total = cm.sum(axis=1)
class_accuracy = class_correct / class_total

print("\nPer-Class Accuracy:")
for i, class_name in enumerate(val_data.classes):
    print(f"  {class_name:20s}: {class_accuracy[i]*100:.2f}%")
```

Run it:
```bash
python evaluate.py
```

---

## 💡 Tips for 4GB RAM

**If you run out of memory:**

1. **Reduce batch size** in `train.py`:
   ```python
   BATCH_SIZE = 4  # or even 2
   ```

2. **Use smaller images**:
   ```python
   IMAGE_SIZE = 96  # instead of 128
   ```

3. **Free up memory** (add to `train.py`):
   ```python
   import gc
   torch.cuda.empty_cache()  # After each epoch
   gc.collect()
   ```

4. **Use CPU instead of GPU** if GPU runs out of memory:
   ```python
   device = torch.device('cpu')  # Force CPU
   ```

5. **Train only the last layer** (already done in the code above):
   ```python
   for param in model.parameters():
       param.requires_grad = False  # Freeze all layers
   
   model.fc = nn.Linear(model.fc.in_features, 10)  # Only train this
   ```

---

## 📁 Simple Project Structure

```
galaxy_project/
├── train/              # Training images (organized by class)
├── val/                # Validation images (organized by class)
├── train.py            # Training script
├── predict.py          # Single image prediction
├── evaluate.py         # Evaluation metrics
├── best_model.pth      # Saved model (created during training)
└── confusion_matrix.png # Evaluation plot
```

---

## 🎯 Expected Results

With this simple setup, you should get:

- **Accuracy**: 70-75% (not bad for a first try!)
- **Training time**: 
  - CPU (4GB RAM): ~2 hours
  - GPU (even entry-level): ~20 minutes

**Good classes** (easier to classify):
- Elliptical: ~80% accuracy
- Spiral: ~75% accuracy

**Challenging classes** (harder to classify):
- Edge-on (with/without bulge): ~60% accuracy
- Irregular vs Peculiar: ~65% accuracy

---

## 🔧 Common Issues & Solutions

### Issue 1: "CUDA out of memory"
**Solution**: Reduce batch size to 4 or 2

### Issue 2: "RuntimeError: DataLoader worker"
**Solution**: Set `NUM_WORKERS = 0` in train.py

### Issue 3: Training is very slow
**Solution**: Use a smaller image size (96 instead of 128)

### Issue 4: Accuracy not improving
**Solution**: 
- Train for more epochs (30-40)
- Check that your data folders are organized correctly
- Make sure images are in the right classes

### Issue 5: "FileNotFoundError"
**Solution**: Make sure your folder structure matches:
```
train/
  spiral/
  barred_spiral/
  ... (all 10 classes)
val/
  spiral/
  barred_spiral/
  ... (all 10 classes)
```

---

## 🚀 Next Steps (After You Get This Working)

1. **Try more epochs**: Change `EPOCHS = 40` in train.py
2. **Fine-tune more layers**: Unfreeze the last few layers
3. **Add more augmentations**: Color changes, slight zoom
4. **Try a different model**: EfficientNet-B0 (smaller and faster)
5. **Create an ensemble**: Train 3 models and average predictions

---

## 📚 What You Learned

✅ How to organize image datasets
✅ How to use pre-trained models (transfer learning)
✅ How to train a deep learning model
✅ How to evaluate model performance
✅ How to make predictions on new images
✅ How to work with limited hardware (4GB RAM)

---

## 🤝 Getting Help

**If you're stuck:**

1. Check that Python is installed: `python --version`
2. Check that PyTorch is installed: `python -c "import torch; print(torch.__version__)"`
3. Verify your data structure matches the examples above
4. Start with a very small test: 10 images per class in `train/` and `val/`

**Error messages**: Copy the full error and search online, or ask for help with the specific error text.

---
 