"""
Test script for OBB Garment Detector with clean logo clipping.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from inference.obb_garment_detector import OBBGarmentDetector, createClippedLogo, parseClippedLogoOffset
import cv2
import numpy as np


def place_clipped_logo(image, clipped_logo_path):
    """
    Place a pre-clipped logo onto the image using its embedded offset.
    
    Args:
        image: Base image (BGR).
        clipped_logo_path: Path to clipped logo with offset info in filename.
        
    Returns:
        Image with logo composited.
    """
    # Load clipped logo (BGRA)
    logo = cv2.imread(clipped_logo_path, cv2.IMREAD_UNCHANGED)
    if logo is None:
        print(f"[place_clipped_logo] Failed to load: {clipped_logo_path}")
        return image
    
    # Parse offset from filename
    offset_x, offset_y = parseClippedLogoOffset(clipped_logo_path)
    
    result = image.copy()
    lh, lw = logo.shape[:2]
    ih, iw = result.shape[:2]
    
    # Compute placement region
    x1 = max(0, offset_x)
    y1 = max(0, offset_y)
    x2 = min(iw, offset_x + lw)
    y2 = min(ih, offset_y + lh)
    
    lx1 = x1 - offset_x
    ly1 = y1 - offset_y
    lx2 = lx1 + (x2 - x1)
    ly2 = ly1 + (y2 - y1)
    
    if lx2 <= lx1 or ly2 <= ly1:
        return result
    
    # Composite using alpha
    roi = result[y1:y2, x1:x2].astype(np.float32)
    logo_crop = logo[ly1:ly2, lx1:lx2].astype(np.float32)
    
    alpha = logo_crop[:, :, 3] / 255.0
    
    for c in range(3):
        roi[:, :, c] = logo_crop[:, :, c] * alpha + roi[:, :, c] * (1 - alpha)
    
    result[y1:y2, x1:x2] = roi.astype(np.uint8)
    
    return result


def main():
    print("=" * 60)
    print("  OBB Garment Detector - Clean Logo Clipping Test")
    print("=" * 60)
    
    # Initialize detector
    print("\nInitializing OBB detector...")
    detector = OBBGarmentDetector()
    print("  ✓ Model loaded successfully")
    
    # Find test images
    test_dir = Path(__file__).parent
    test_images = list(test_dir.glob("test*.jpg")) + list(test_dir.glob("test*.png"))
    
    if not test_images:
        print("\n⚠ No test images found. Place test*.jpg files in the inference directory.")
        return
    
    print(f"\nFound {len(test_images)} test image(s)")
    
    # Find logo
    logo_path = test_dir / "outputs" / "logo.png"
    if not logo_path.exists():
        print(f"\n⚠ Logo not found at {logo_path}")
        return
    
    # Create output directory
    output_dir = test_dir / "outputs" / "obb_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each test image
    for img_path in test_images:
        print(f"\n{'=' * 60}")
        print(f"Testing: {img_path.name}")
        print("=" * 60)
        
        # Detect regions (one per class, best confidence)
        regions = detector.detect(str(img_path))
        print(f"\n  Detected {len(regions)} regions:")
        for r in regions:
            print(f"    - {r.class_name}: {r.confidence:.1%} at ({r.center[0]:.0f}, {r.center[1]:.0f}), angle={r.angle:.1f}°")
        
        # Load image
        image = cv2.imread(str(img_path))
        
        # Draw debug image
        debug_img = detector.draw_debug_info(image, regions)
        debug_path = output_dir / f"{img_path.stem}_obb_debug.jpg"
        cv2.imwrite(str(debug_path), debug_img)
        print(f"\n  ✓ Debug image saved: {debug_path.name}")
        
        # Place clipped logos (clean method)
        result_clipped = image.copy()
        temp_files = []
        
        for region in regions:
            try:
                # Create clipped logo for this region
                clipped_path = createClippedLogo(
                    str(img_path),
                    str(logo_path),
                    region.class_name,
                    rotation=None,  # Use OBB angle
                    scale_factor=0.8
                )
                
                if clipped_path:
                    temp_files.append(clipped_path)
                    result_clipped = place_clipped_logo(result_clipped, clipped_path)
                    print(f"  ✓ Placed CLIPPED logo on {region.class_name}")
                else:
                    print(f"  ✗ Failed to create clipped logo for {region.class_name}")
                    
            except Exception as e:
                print(f"  ✗ Error on {region.class_name}: {e}")
        
        # Save clipped result
        result_path = output_dir / f"{img_path.stem}_obb_result.jpg"
        cv2.imwrite(str(result_path), result_clipped)
        print(f"\n  ✓ Clean result saved: {result_path.name}")
        
        # Clean up temp files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
    
    print(f"\n{'=' * 60}")
    print(f"  Output directory: {output_dir}")
    print("  All logos are now CLIPPED to OBB bounds!")
    print("=" * 60)


if __name__ == "__main__":
    main()
