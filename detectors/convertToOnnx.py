"""
Model Conversion Script - Export YOLO models to ONNX format.

Run this script ONCE to convert all .pt models to ONNX format.
This will significantly speed up inference on CPU.

Usage:
    python detectors/convert_to_onnx.py
"""

import os
from pathlib import Path

def convert_models():
    """Convert all YOLO .pt models to ONNX format."""
    
    # Find all model directories
    weights_dir = Path(__file__).parent / "weights"
    
    if not weights_dir.exists():
        print(f"[ERROR] Weights directory not found: {weights_dir}")
        return
    
    print("=" * 60)
    print("       YOLO to ONNX Model Conversion")
    print("=" * 60)
    print()
    
    converted = 0
    skipped = 0
    failed = 0
    
    # Find all .pt files
    for model_dir in weights_dir.iterdir():
        if not model_dir.is_dir():
            continue
            
        pt_file = model_dir / "best.pt"
        onnx_file = model_dir / "best.onnx"
        
        if not pt_file.exists():
            print(f"[SKIP] No model found in: {model_dir.name}")
            continue
            
        if onnx_file.exists():
            print(f"[SKIP] ONNX already exists: {model_dir.name}/best.onnx")
            skipped += 1
            continue
        
        print(f"[CONVERTING] {model_dir.name}/best.pt -> best.onnx")
        
        try:
            from ultralytics import YOLO
            
            # Load the model
            model = YOLO(str(pt_file))
            
            # Export to ONNX
            # Using opset=12 for better compatibility
            # half=False for CPU compatibility
            model.export(
                format='onnx',
                opset=12,
                simplify=True,
                dynamic=False,
                half=False,
                imgsz=640
            )
            
            # Ultralytics exports to same directory with .onnx extension
            exported_path = pt_file.with_suffix('.onnx')
            if exported_path.exists():
                print(f"    ✓ Success: {model_dir.name}/best.onnx")
                converted += 1
            else:
                print(f"    ✗ Failed: Export completed but file not found")
                failed += 1
                
        except Exception as e:
            print(f"    ✗ Failed: {e}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"  Conversion Complete!")
    print(f"  Converted: {converted}")
    print(f"  Skipped (already exists): {skipped}")
    print(f"  Failed: {failed}")
    print("=" * 60)
    
    if converted > 0:
        print()
        print("  Your models are now optimized for faster CPU inference!")
        print("  The automation will automatically use ONNX models.")


if __name__ == "__main__":
    convert_models()