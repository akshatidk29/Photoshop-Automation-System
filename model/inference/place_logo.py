"""
Simple Logo Placement Script
Places logos on segmented garment regions.
"""

import json
import cv2
import numpy as np
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================
CONFIG = {
    'base_dir': Path("/DATA/idk/photoshopAutomation/model/inference"),
    'image_name': "test3.jpg",
    'logo_name': "outputs/logo.png",
    'output_name': "outputs/logo_placed.jpg",
    'debug_output': "outputs/logo_placed_debug.jpg",
    
    'min_confidence': 0.3,
    'target_classes': None,  # None = all classes, or list like [1, 2, 3]
    'logo_scale': 0.8,  # Logo width = 80% of segment's widest span
}


def load_logo(logo_path):
    """Load logo with alpha channel."""
    logo = cv2.imread(str(logo_path), cv2.IMREAD_UNCHANGED)
    if logo is None:
        raise FileNotFoundError(f"Cannot load logo: {logo_path}")
    
    # Ensure 4 channels (BGRA)
    if len(logo.shape) == 2:
        logo = cv2.cvtColor(logo, cv2.COLOR_GRAY2BGRA)
    elif logo.shape[2] == 3:
        # Add alpha channel
        b, g, r = cv2.split(logo)
        # Make white/near-white transparent
        gray = cv2.cvtColor(logo, cv2.COLOR_BGR2GRAY)
        _, alpha = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
        logo = cv2.merge([b, g, r, alpha])
    
    return logo


def find_widest_span(mask, y_start, y_end):
    """Find the widest horizontal span inside the mask."""
    max_width = 0
    best_row = 0
    best_left = 0
    best_right = 0
    
    for row in range(y_start, y_end):
        cols = np.where(mask[row] > 0)[0]
        if len(cols) > 0:
            left, right = cols[0], cols[-1]
            width = right - left
            if width > max_width:
                max_width = width
                best_row = row
                best_left = left
                best_right = right
    
    return best_row, best_left, best_right, max_width


def get_span_at_row(mask, row):
    """Return left/right column indices where mask is present at a given row."""
    if row < 0 or row >= mask.shape[0]:
        return None
    cols = np.where(mask[row] > 0)[0]
    if len(cols) == 0:
        return None
    return int(cols[0]), int(cols[-1])


def rotate_image(img, angle, center):
    """Rotate image around a center point."""
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Calculate new bounding box
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    
    # Adjust matrix
    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2
    
    rotated = cv2.warpAffine(img, M, (new_w, new_h), 
                             borderMode=cv2.BORDER_CONSTANT, 
                             borderValue=(0, 0, 0, 0) if img.shape[2] == 4 else (0, 0, 0))
    return rotated

# ============================================================================
# GEOMETRY HELPERS
# ============================================================================

def compute_pca_axis(points):
    """Return principal axis direction (unit vector) and centroid."""
    pts = points.astype(np.float32)
    mean = pts.mean(axis=0)
    cov = np.cov((pts - mean).T)
    eigvals, eigvecs = np.linalg.eig(cov)
    axis = eigvecs[:, np.argmax(eigvals)]
    axis = axis / np.linalg.norm(axis)
    return mean, axis


def classify_region(mask_pts):
    """
    Decide region type purely from geometry.
    Returns: 'chest', 'sleeve', 'collar'
    """
    rect = cv2.minAreaRect(mask_pts.astype(np.float32))
    (_, (w, h), _) = rect
    area = cv2.contourArea(mask_pts)

    aspect = max(w, h) / (min(w, h) + 1e-6)

    if aspect < 1.4:
        return 'chest'
    elif aspect > 2.2:
        return 'sleeve'
    else:
        return 'collar'


def rotate_with_canvas(img, angle_deg):
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)

    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)

    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2

    return cv2.warpAffine(
        img, M, (new_w, new_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0)
    )


def cylindrical_warp(logo):
    """
    Approximate cylindrical wrap:
    compress edges, preserve center.
    """
    h, w = logo.shape[:2]
    map_x = np.zeros((h, w), np.float32)
    map_y = np.zeros((h, w), np.float32)

    cx = w / 2
    for y in range(h):
        for x in range(w):
            dx = (x - cx) / cx
            warp = np.cos(dx * np.pi / 2)
            map_x[y, x] = cx + dx * cx * warp
            map_y[y, x] = y

    return cv2.remap(
        logo, map_x, map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0)
    )


def apply_photometric_blend(roi, logo_rgb, alpha):
    """
    Make logo look printed (not sticker).
    """
    gray = cv2.cvtColor(roi.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    gray = gray.astype(np.float32) / 255.0
    shade = 0.7 + 0.3 * gray

    for c in range(3):
        logo_rgb[:, :, c] *= shade

    return logo_rgb, alpha * 0.95


# ============================================================================
# NEW LOGO PLACEMENT
# ============================================================================

def place_logo_on_segment(img, logo, mask_pts, config):
    result = img.copy()

    # Build filled mask
    mask = np.zeros(img.shape[:2], np.uint8)
    cv2.fillPoly(mask, [mask_pts], 255)

    region_type = classify_region(mask_pts)

    rect = cv2.minAreaRect(mask_pts.astype(np.float32))
    (cx, cy), (w, h), angle = rect

    # Normalize OpenCV angle
    if angle < -45:
        angle += 90

    # Target logo size
    target_width = int(min(w, h) * config['logo_scale'])
    scale = target_width / logo.shape[1]
    if scale < 0.05:
        return result, False, None

    logo_resized = cv2.resize(
        logo,
        (int(logo.shape[1] * scale), int(logo.shape[0] * scale)),
        interpolation=cv2.INTER_AREA
    )

    # =============================
    # REGION-SPECIFIC TRANSFORMS
    # =============================

    if region_type == 'chest':
        logo_proj = rotate_with_canvas(logo_resized, -angle)

    elif region_type == 'sleeve':
        mean, axis = compute_pca_axis(mask_pts)
        theta = np.degrees(np.arctan2(axis[1], axis[0]))
        logo_rot = rotate_with_canvas(logo_resized, -theta)
        logo_proj = cylindrical_warp(logo_rot)

    else:  # collar
        logo_rot = rotate_with_canvas(logo_resized, -angle)
        logo_proj = logo_rot[:, :int(logo_rot.shape[1] * 0.7)]

    # =============================
    # PLACE ON IMAGE
    # =============================

    ph, pw = logo_proj.shape[:2]
    px = int(cx - pw / 2)
    py = int(cy - ph / 2)

    x1 = max(0, px)
    y1 = max(0, py)
    x2 = min(img.shape[1], px + pw)
    y2 = min(img.shape[0], py + ph)

    lx1 = x1 - px
    ly1 = y1 - py
    lx2 = lx1 + (x2 - x1)
    ly2 = ly1 + (y2 - y1)

    if lx2 <= lx1 or ly2 <= ly1:
        return result, False, None

    roi = result[y1:y2, x1:x2].astype(np.float32)
    logo_crop = logo_proj[ly1:ly2, lx1:lx2].astype(np.float32)
    mask_crop = mask[y1:y2, x1:x2].astype(np.float32) / 255.0

    alpha = logo_crop[:, :, 3] / 255.0
    alpha *= mask_crop
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)

    logo_rgb = logo_crop[:, :, :3]
    logo_rgb, alpha = apply_photometric_blend(roi, logo_rgb, alpha)

    for c in range(3):
        roi[:, :, c] = logo_rgb[:, :, c] * alpha + roi[:, :, c] * (1 - alpha)

    result[y1:y2, x1:x2] = roi.astype(np.uint8)

    # Compute aspect ratio for debug (from OBB)
    aspect_ratio = max(w, h) / (min(w, h) + 1e-6)

    info = {
        'region': region_type,
        'angle': angle,
        'center': (int(cx), int(cy)),
        'logo_size': (pw, ph),
        'aspect_ratio': aspect_ratio,
    }

    # Backward compatibility
    info['use_tilt'] = (region_type != 'chest')

    # Pseudo alignment line (for debug drawing only)
    dx = int(np.cos(np.deg2rad(angle)) * 50)
    dy = int(np.sin(np.deg2rad(angle)) * 50)
    info['alignment_line'] = (
        (int(cx - dx), int(cy - dy)),
        (int(cx + dx), int(cy + dy)),
    )

    return result, True, info



def main():
    config = CONFIG
    base_dir = config['base_dir']
    
    # Load files
    img = cv2.imread(str(base_dir / config['image_name']))
    if img is None:
        raise FileNotFoundError(f"Cannot load image")
    
    logo = load_logo(base_dir / config['logo_name'])
    
    with open(base_dir / "outputs/bboxes.json") as f:
        all_detections = json.load(f)
    
    detections = all_detections[0]['detections']
    
    print(f"Image: {img.shape[1]}x{img.shape[0]}")
    print(f"Logo: {logo.shape[1]}x{logo.shape[0]}")
    print(f"Detections: {len(detections)}")
    
    # Filter detections
    filtered = []
    for det in detections:
        if det['conf'] < config['min_confidence']:
            continue
        if config['target_classes'] is not None:
            if det['cls'] not in config['target_classes']:
                continue
        if 'mask_xy' not in det or not det['mask_xy'] or len(det['mask_xy']) < 3:
            continue
        filtered.append(det)
    
    print(f"Processing: {len(filtered)} detections (conf >= {config['min_confidence']:.0%})")
    
    # Process each detection
    result = img.copy()
    debug_img = img.copy()
    
    for det in filtered:
        cls = det['cls']
        conf = det['conf']
        mask_pts = np.array(det['mask_xy'], dtype=np.int32)
        
        result, success, info = place_logo_on_segment(result, logo, mask_pts, config)
        
        if success:
            method = "TILTED" if info['use_tilt'] else "HORIZONTAL"
            print(f"  Class {cls} ({conf:.0%}): {method}, angle={info['angle']:.1f}°, aspect={info['aspect_ratio']:.2f}")
            
            # Draw on debug
            cv2.polylines(debug_img, [mask_pts], True, (0, 255, 0), 2)
            # Draw alignment line
            p1, p2 = info['alignment_line']
            color = (0, 0, 255) if info['use_tilt'] else (255, 0, 0)  # Red for tilt, Blue for horizontal
            cv2.line(debug_img, p1, p2, color, 2)
            cv2.circle(debug_img, p1, 5, (255, 0, 255), -1)
            cv2.circle(debug_img, p2, 5, (255, 0, 255), -1)
        else:
            print(f"  Class {cls} ({conf:.0%}): FAILED")
    
    # Save outputs
    cv2.imwrite(str(base_dir / config['output_name']), result)
    cv2.imwrite(str(base_dir / config['debug_output']), debug_img)
    
    print(f"\nSaved: {config['output_name']}")
    print(f"Debug: {config['debug_output']}")


if __name__ == "__main__":
    main()
