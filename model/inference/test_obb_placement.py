"""
Test script for OBB Garment Detector.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from inference.obb_garment_detector import OBBGarmentDetector
import cv2


def main():
    print("=" * 60)
    print("  OBB Garment Detector - Logo Placement Test")
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
        print(f"Testing: {img_path}")
        print("=" * 60)
        
        # Detect regions (one per class, best confidence)
        regions = detector.detect(str(img_path))
        print(f"\n  Detected {len(regions)} regions:")
        for r in regions:
            print(f"    - {r.class_name}: {r.confidence:.1%} at ({r.center[0]:.0f}, {r.center[1]:.0f}), angle={r.angle:.1f}°")
        
        # Load image
        image = cv2.imread(str(img_path))
        logo = detector.load_logo(str(logo_path))
        
        # Draw debug image
        debug_img = detector.draw_debug_info(image, regions)
        debug_path = output_dir / f"{img_path.stem}_obb_debug.jpg"
        cv2.imwrite(str(debug_path), debug_img)
        print(f"\n  ✓ Debug image saved: {debug_path}")
        
        # Place logos
        result_img = image.copy()
        for region in regions:
            try:
                placement = detector.place_logo(result_img, logo, region)
                result_img = placement.image
                print(f"  ✓ Placed logo on {region.class_name} (align: {placement.debug_info['align']})")
            except Exception as e:
                print(f"  ✗ Error on {region.class_name}: {e}")
        
        # Save result
        result_path = output_dir / f"{img_path.stem}_obb_result.jpg"
        cv2.imwrite(str(result_path), result_img)
        print(f"\n  ✓ Result saved: {result_path}")
    
    print(f"\n{'=' * 60}")
    print(f"  Output directory: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
