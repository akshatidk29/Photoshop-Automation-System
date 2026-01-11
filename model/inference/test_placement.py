"""
Test Script for YOLO-Based Logo Placement

Run this script to test the new placement system on test images.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import cv2
import numpy as np
from yolo_garment_detector import YOLOGarmentDetector, CLASS_NAMES


def draw_debug_info(image, region, placement_result):
    """Draw debug visualization on image."""
    debug_img = image.copy()
    
    # Draw mask polygon
    cv2.polylines(debug_img, [region.mask_polygon], True, (0, 255, 0), 2)
    
    # Draw oriented rectangle
    rect = region.oriented_rect
    box = cv2.boxPoints((rect.center, rect.size, rect.angle))
    box = np.intp(box)
    cv2.drawContours(debug_img, [box], 0, (0, 0, 255), 2)
    
    # Draw center point
    cx, cy = int(rect.cx), int(rect.cy)
    cv2.circle(debug_img, (cx, cy), 8, (255, 0, 255), -1)
    
    # Draw rotation direction
    angle_rad = np.deg2rad(rect.angle)
    dx = int(np.cos(angle_rad) * 50)
    dy = int(np.sin(angle_rad) * 50)
    cv2.line(debug_img, (cx, cy), (cx + dx, cy + dy), (255, 255, 0), 3)
    
    # Add text label
    label = f"{region.class_name} ({region.confidence:.0%})"
    label2 = f"Angle: {rect.angle:.1f}°"
    cv2.putText(debug_img, label, (cx - 50, cy - 20), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(debug_img, label2, (cx - 50, cy), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
    
    return debug_img


def test_single_image(detector, image_path, logo_path, output_dir):
    """Test logo placement on a single image."""
    print(f"\n{'='*60}")
    print(f"Testing: {image_path}")
    print(f"{'='*60}")
    
    image_name = Path(image_path).stem
    
    # Place logos on all detected regions
    try:
        result_img, placements = detector.place_all_logos(
            image_path=image_path,
            logo_path=logo_path,
            conf_threshold=0.3
        )
        
        # Load original for debug overlay
        original = cv2.imread(str(image_path))
        debug_img = original.copy()
        
        print(f"\nDetected {len(placements)} region(s):")
        
        for p in placements:
            status = "✓" if p.success else "✗"
            clip_info = f" (clipped {p.clipped_edge})" if p.clipped_edge else ""
            print(f"  {status} {p.region.class_name}:")
            print(f"      Confidence: {p.region.confidence:.0%}")
            print(f"      Logo size: {p.logo_size[0]}x{p.logo_size[1]}")
            print(f"      Position: {p.logo_position}")
            print(f"      Rotation: {p.rotation_angle:.1f}°{clip_info}")
            
            if p.success:
                # Add to debug image
                debug_img = draw_debug_info(debug_img, p.region, p)
        
        # Save outputs
        result_path = output_dir / f"{image_name}_result.jpg"
        debug_path = output_dir / f"{image_name}_debug.jpg"
        
        cv2.imwrite(str(result_path), result_img)
        cv2.imwrite(str(debug_path), debug_img)
        
        print(f"\n  Saved: {result_path.name}")
        print(f"  Debug: {debug_path.name}")
        
        return True
        
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_specific_class(detector, image_path, logo_path, class_name, output_dir):
    """Test logo placement on a specific class only."""
    print(f"\n{'='*60}")
    print(f"Testing {class_name} on: {image_path}")
    print(f"{'='*60}")
    
    image_name = Path(image_path).stem
    
    try:
        result_img, placements = detector.place_all_logos(
            image_path=image_path,
            logo_path=logo_path,
            target_classes=[class_name],
            conf_threshold=0.2  # Lower threshold for specific class
        )
        
        if not placements:
            print(f"  No {class_name} detected!")
            return False
        
        for p in placements:
            if p.success:
                print(f"  ✓ Placed on {class_name}")
                print(f"      Size: {p.logo_size}")
                print(f"      Angle: {p.rotation_angle:.1f}°")
                print(f"      Clipped: {p.clipped_edge or 'No'}")
        
        # Save
        result_path = output_dir / f"{image_name}_{class_name}.jpg"
        cv2.imwrite(str(result_path), result_img)
        print(f"  Saved: {result_path.name}")
        
        return True
        
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("  YOLO Garment Detector - Logo Placement Test")
    print("="*60)
    
    # Setup paths
    base_dir = Path(__file__).parent
    output_dir = base_dir / "outputs" / "test_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logo_path = base_dir / "outputs" / "logo.png"
    
    # Check logo exists
    if not logo_path.exists():
        print(f"\nERROR: Logo not found at {logo_path}")
        print("Please ensure logo.png is in the outputs folder.")
        return
    
    # Initialize detector
    print("\nInitializing YOLO detector...")
    try:
        detector = YOLOGarmentDetector()
        print("  ✓ Model loaded successfully")
    except Exception as e:
        print(f"  ✗ Failed to load model: {e}")
        return
    
    # Test images
    test_images = [
        base_dir / "test.jpg",
        base_dir / "test1.jpg",
        base_dir / "test2.jpg",
        base_dir / "test3.jpg",
        base_dir / "test4.jpg",
        base_dir / "test5.jpg",
        base_dir / "test6.jpg",
        base_dir / "test7.jpg",
    ]
    
    # Filter to existing images
    test_images = [p for p in test_images if p.exists()]
    
    if not test_images:
        print("\nNo test images found in inference directory!")
        return
    
    print(f"\nFound {len(test_images)} test image(s)")
    
    # Process each image
    results = []
    for img_path in test_images:
        success = test_single_image(detector, str(img_path), str(logo_path), output_dir)
        results.append((img_path.name, success))
    
    # Summary
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {name}")
    
    passed = sum(1 for _, s in results if s)
    print(f"\n  Total: {passed}/{len(results)} passed")
    print(f"\n  Output directory: {output_dir}")


if __name__ == "__main__":
    main()
