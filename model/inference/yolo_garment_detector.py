"""
YOLO-Based Garment Detector for Logo Placement

This module uses YOLO segmentation to detect garment regions and provides
oriented bounding rectangles for accurate logo placement.

Key features:
- Oriented bounding rectangle from segmentation mask
- Auto-alignment based on rectangle angle
- Logo scaling with aspect ratio preservation
- Mask-based overflow clipping
- Special handling for curved surfaces (biceps, sleeves, collars)
"""

import os
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from ultralytics import YOLO


# ============================================================================
# CONFIGURATION
# ============================================================================

# Class names from data.yaml (0-17 for garments)
CLASS_NAMES = {
    0: "FULL_BACK",
    1: "FULL_FRONT",
    2: "LEFT_BICEP",
    3: "RIGHT_BICEP",
    4: "LEFT_CHEST",
    5: "RIGHT_CHEST",
    6: "LEFT_COLLAR",
    7: "RIGHT_COLLAR",
    8: "LEFT_CUFF",
    9: "RIGHT_CUFF",
    10: "LEFT_HIP",
    11: "RIGHT_HIP",
    12: "LEFT_SLEEVE",
    13: "RIGHT_SLEEVE",
    14: "LEFT_THIGH_HIGH",
    15: "RIGHT_THIGH_HIGH",
    16: "ON_POCKET",
    17: "BACK_YOKE",
}

# Reverse mapping
CLASS_IDS = {v: k for k, v in CLASS_NAMES.items()}

# Placement configuration per class
PLACEMENT_CONFIG = {
    # FULL positions - larger logos, no edge clipping
    "FULL_FRONT": {"base_size": 300, "width_ratio": 0.8, "clip_edge": None},
    "FULL_BACK": {"base_size": 300, "width_ratio": 0.8, "clip_edge": None},
    "BACK_YOKE": {"base_size": 200, "width_ratio": 0.7, "clip_edge": None},
    
    # Chest positions - medium logos
    "LEFT_CHEST": {"base_size": 99, "width_ratio": 0.7, "clip_edge": None},
    "RIGHT_CHEST": {"base_size": 99, "width_ratio": 0.7, "clip_edge": None},
    
    # Bicep positions - clip far edge for curved surface
    "LEFT_BICEP": {"base_size": 99, "width_ratio": 0.6, "clip_edge": "right"},
    "RIGHT_BICEP": {"base_size": 99, "width_ratio": 0.6, "clip_edge": "left"},
    
    # Sleeve positions - clip far edge for curved surface
    "LEFT_SLEEVE": {"base_size": 99, "width_ratio": 0.6, "clip_edge": "right"},
    "RIGHT_SLEEVE": {"base_size": 99, "width_ratio": 0.6, "clip_edge": "left"},
    
    # Collar positions - smaller, clip far edge
    "LEFT_COLLAR": {"base_size": 66, "width_ratio": 0.5, "clip_edge": "right"},
    "RIGHT_COLLAR": {"base_size": 66, "width_ratio": 0.5, "clip_edge": "left"},
    
    # Cuff positions - small logos
    "LEFT_CUFF": {"base_size": 66, "width_ratio": 0.5, "clip_edge": None},
    "RIGHT_CUFF": {"base_size": 66, "width_ratio": 0.5, "clip_edge": None},
    
    # Hip positions
    "LEFT_HIP": {"base_size": 99, "width_ratio": 0.6, "clip_edge": None},
    "RIGHT_HIP": {"base_size": 99, "width_ratio": 0.6, "clip_edge": None},
    
    # Thigh positions
    "LEFT_THIGH_HIGH": {"base_size": 99, "width_ratio": 0.6, "clip_edge": None},
    "RIGHT_THIGH_HIGH": {"base_size": 99, "width_ratio": 0.6, "clip_edge": None},
    
    # Pocket
    "ON_POCKET": {"base_size": 66, "width_ratio": 0.7, "clip_edge": None},
}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class OrientedRect:
    """Represents an oriented bounding rectangle."""
    center: Tuple[float, float]  # (cx, cy)
    size: Tuple[float, float]    # (width, height)
    angle: float                  # Rotation angle in degrees
    
    @property
    def cx(self) -> float:
        return self.center[0]
    
    @property
    def cy(self) -> float:
        return self.center[1]
    
    @property
    def width(self) -> float:
        return self.size[0]
    
    @property
    def height(self) -> float:
        return self.size[1]


@dataclass 
class DetectedRegion:
    """Represents a detected garment region."""
    class_id: int
    class_name: str
    confidence: float
    mask_polygon: np.ndarray      # Polygon points (N, 2)
    oriented_rect: OrientedRect
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2


@dataclass
class PlacementResult:
    """Result of logo placement."""
    success: bool
    image: Optional[np.ndarray]
    region: Optional[DetectedRegion]
    logo_size: Tuple[int, int]
    logo_position: Tuple[int, int]
    rotation_angle: float
    clipped_edge: Optional[str]
    debug_info: Dict[str, Any]


# ============================================================================
# CORE DETECTOR CLASS
# ============================================================================

class YOLOGarmentDetector:
    """YOLO-based garment region detection and logo placement."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the detector with a YOLO segmentation model.
        
        Args:
            model_path: Path to the YOLO model weights. If None, uses default.
        """
        if model_path is None:
            # Default to trained model
            base = Path(__file__).parent.parent
            model_path = str(base / "runs" / "segment" / "train2" / "weights" / "best.pt")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        self.model = YOLO(model_path)
        self.class_names = CLASS_NAMES
        self.config = PLACEMENT_CONFIG
        
    def detect(self, image_path: str, conf_threshold: float = 0.3) -> List[DetectedRegion]:
        """
        Run YOLO segmentation and return detected regions.
        
        Args:
            image_path: Path to the image file.
            conf_threshold: Minimum confidence threshold.
            
        Returns:
            List of DetectedRegion objects.
        """
        results = self.model.predict(
            source=image_path,
            conf=conf_threshold,
            iou=0.5,
            save=False,
            verbose=False
        )
        
        regions = []
        
        for r in results:
            if r.boxes is None or r.masks is None:
                continue
                
            for i in range(len(r.boxes)):
                try:
                    # Get class and confidence
                    cls_id = int(r.boxes.cls[i].item())
                    conf = float(r.boxes.conf[i].item())
                    
                    if conf < conf_threshold:
                        continue
                    
                    # Get class name
                    class_name = self.class_names.get(cls_id, f"CLASS_{cls_id}")
                    
                    # Get bounding box
                    bbox = r.boxes.xyxy[i].cpu().numpy().astype(int)
                    bbox = tuple(bbox)
                    
                    # Get mask polygon
                    if hasattr(r.masks, 'xy') and r.masks.xy is not None:
                        mask_pts = np.array(r.masks.xy[i], dtype=np.int32)
                    else:
                        # Fallback to bbox as polygon
                        x1, y1, x2, y2 = bbox
                        mask_pts = np.array([
                            [x1, y1], [x2, y1], [x2, y2], [x1, y2]
                        ], dtype=np.int32)
                    
                    # Compute oriented rectangle (strategy depends on region type)
                    oriented_rect = self._get_oriented_rectangle(mask_pts, class_name)
                    
                    regions.append(DetectedRegion(
                        class_id=cls_id,
                        class_name=class_name,
                        confidence=conf,
                        mask_polygon=mask_pts,
                        oriented_rect=oriented_rect,
                        bbox=bbox
                    ))
                    
                except Exception as e:
                    print(f"Error processing detection {i}: {e}")
                    continue
        
        return regions
    
    def _get_oriented_rectangle(self, mask_polygon: np.ndarray, class_name: str = "") -> OrientedRect:
        """
        Compute the bounding rectangle for logo placement.
        
        For rotated regions (collars, biceps, sleeves):
        - Find the maximum diameter line within the segmented area
        - Use that line's angle as the rectangle width axis
        - Build a bounding rectangle aligned with that direction
        
        For other regions: Use standard minAreaRect.
        
        Args:
            mask_polygon: Polygon points (N, 2).
            class_name: Name of the region class.
            
        Returns:
            OrientedRect with center, size, and angle.
        """
        if len(mask_polygon) < 3:
            return OrientedRect(center=(0, 0), size=(0, 0), angle=0)
        
        pts = mask_polygon.astype(np.float32)
        
        # Check if this is a rotated region (collars, biceps, sleeves)
        rotated_regions = ["BICEP", "SLEEVE", "COLLAR", "CUFF"]
        use_diameter = any(region in class_name.upper() for region in rotated_regions)
        
        if use_diameter:
            # For rotated regions: find the maximum diameter (longest chord)
            # This gives us the DIRECTION only
            hull = cv2.convexHull(pts)
            hull_pts = hull.reshape(-1, 2)
            
            # Find the two points with maximum distance (diameter)
            max_dist = 0
            p1, p2 = hull_pts[0], hull_pts[1]
            
            for i in range(len(hull_pts)):
                for j in range(i + 1, len(hull_pts)):
                    dist = np.linalg.norm(hull_pts[i] - hull_pts[j])
                    if dist > max_dist:
                        max_dist = dist
                        p1, p2 = hull_pts[i], hull_pts[j]
            
            # The diameter line angle becomes our direction
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            angle = np.degrees(np.arctan2(dy, dx))
            
            # Center is the CENTROID of the segmented area, not the diameter midpoint
            center = (pts[:, 0].mean(), pts[:, 1].mean())
            
            # Compute direction vectors
            direction = np.array([dx, dy]) / max_dist if max_dist > 0 else np.array([1, 0])
            perpendicular = np.array([-direction[1], direction[0]])
            
            # Project all points onto both axes (from centroid)
            centered_pts = pts - np.array(center)
            
            # Width: extent along the diameter direction
            dir_proj = np.dot(centered_pts, direction)
            width = dir_proj.max() - dir_proj.min()
            
            # Height: extent perpendicular to diameter direction
            perp_proj = np.dot(centered_pts, perpendicular)
            height = perp_proj.max() - perp_proj.min()
            
        else:
            # For other regions: use standard minAreaRect
            rect = cv2.minAreaRect(pts)
            center, size, angle = rect
            width, height = size
            
            # Ensure width is the longer dimension
            if height > width:
                width, height = height, width
                angle = angle + 90
            
            # Normalize angle to [-45, 45] range for non-rotated regions only
            # This keeps logos readable while preserving orientation
            while angle > 45:
                angle -= 90
            while angle < -45:
                angle += 90
        
        # For rotated regions (diameter-based), angle is used as-is
        # This lets the rectangle follow the natural collar/bicep/sleeve direction
        
        return OrientedRect(
            center=center,
            size=(width, height),
            angle=angle
        )
    
    def load_logo(self, logo_path: str) -> np.ndarray:
        """
        Load logo with alpha channel.
        
        Args:
            logo_path: Path to logo image (PNG with transparency).
            
        Returns:
            BGRA image as numpy array.
        """
        logo = cv2.imread(str(logo_path), cv2.IMREAD_UNCHANGED)
        if logo is None:
            raise FileNotFoundError(f"Cannot load logo: {logo_path}")
        
        # Ensure 4 channels (BGRA)
        if len(logo.shape) == 2:
            logo = cv2.cvtColor(logo, cv2.COLOR_GRAY2BGRA)
        elif logo.shape[2] == 3:
            # Add alpha channel - make white/near-white transparent
            b, g, r = cv2.split(logo)
            gray = cv2.cvtColor(logo, cv2.COLOR_BGR2GRAY)
            _, alpha = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
            logo = cv2.merge([b, g, r, alpha])
        
        return logo
    
    def compute_logo_size(
        self, 
        logo: np.ndarray, 
        region: DetectedRegion
    ) -> Tuple[int, int]:
        """
        Compute the target logo size based on fixed base sizes.
        Logo size is NOT reduced dynamically - always use base_size.
        
        Args:
            logo: BGRA logo image.
            region: Detected region for placement.
            
        Returns:
            (target_width, target_height)
        """
        config = self.config.get(region.class_name, {
            "base_size": 99, "width_ratio": 0.6, "clip_edge": None
        })
        
        base_size = config["base_size"]
        logo_h, logo_w = logo.shape[:2]
        aspect_ratio = logo_h / logo_w if logo_w > 0 else 1.0
        
        # Fixed size based on base_size (no dynamic reduction)
        target_w = base_size
        target_h = int(base_size * aspect_ratio)
        
        return target_w, target_h
    
    def rotate_logo(
        self, 
        logo: np.ndarray, 
        angle: float
    ) -> np.ndarray:
        """
        Rotate logo by specified angle with transparent padding.
        
        Args:
            logo: BGRA logo image.
            angle: Rotation angle in degrees.
            
        Returns:
            Rotated BGRA image.
        """
        if abs(angle) < 0.5:
            return logo.copy()
        
        h, w = logo.shape[:2]
        center = (w // 2, h // 2)
        
        # Rotation matrix
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Compute new bounding box
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int(h * sin + w * cos)
        new_h = int(h * cos + w * sin)
        
        # Adjust matrix for new center
        M[0, 2] += (new_w - w) / 2
        M[1, 2] += (new_h - h) / 2
        
        # Rotate with transparent border
        rotated = cv2.warpAffine(
            logo, M, (new_w, new_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0)
        )
        
        return rotated
    
    def clip_logo_edge(
        self, 
        logo: np.ndarray, 
        edge: str,
        clip_ratio: float = 0.3
    ) -> np.ndarray:
        """
        Clip/fade one edge of the logo for curved surface effect.
        
        Args:
            logo: BGRA logo image.
            edge: "left" or "right" edge to clip.
            clip_ratio: Portion of logo to fade (0.3 = 30% from edge).
            
        Returns:
            Logo with faded edge.
        """
        result = logo.copy()
        h, w = result.shape[:2]
        
        clip_width = int(w * clip_ratio)
        if clip_width < 1:
            return result
        
        # Create gradient mask for smooth fade
        if edge == "right":
            # Fade the right edge
            start_x = w - clip_width
            for x in range(start_x, w):
                alpha_factor = 1.0 - ((x - start_x) / clip_width)
                result[:, x, 3] = (result[:, x, 3] * alpha_factor).astype(np.uint8)
        elif edge == "left":
            # Fade the left edge
            for x in range(clip_width):
                alpha_factor = x / clip_width
                result[:, x, 3] = (result[:, x, 3] * alpha_factor).astype(np.uint8)
        
        return result
    
    def apply_mask_clipping(
        self,
        image: np.ndarray,
        logo: np.ndarray,
        position: Tuple[int, int],
        mask: np.ndarray
    ) -> np.ndarray:
        """
        Clip logo to only show within the garment mask.
        
        Args:
            image: Background image (BGR).
            logo: BGRA logo with alpha.
            position: (x, y) top-left position for logo.
            mask: Binary mask of garment region.
            
        Returns:
            Image with logo composited and clipped to mask.
        """
        result = image.copy()
        px, py = position
        lh, lw = logo.shape[:2]
        ih, iw = image.shape[:2]
        
        # Compute valid overlap region
        x1 = max(0, px)
        y1 = max(0, py)
        x2 = min(iw, px + lw)
        y2 = min(ih, py + lh)
        
        # Logo crop coordinates
        lx1 = x1 - px
        ly1 = y1 - py
        lx2 = lx1 + (x2 - x1)
        ly2 = ly1 + (y2 - y1)
        
        if lx2 <= lx1 or ly2 <= ly1:
            return result
        
        # Get regions
        roi = result[y1:y2, x1:x2].astype(np.float32)
        logo_crop = logo[ly1:ly2, lx1:lx2].astype(np.float32)
        mask_crop = mask[y1:y2, x1:x2].astype(np.float32) / 255.0
        
        # Logo alpha combined with mask
        alpha = logo_crop[:, :, 3] / 255.0
        alpha = alpha * mask_crop  # Multiply by garment mask
        
        # Feather edges slightly for smoother blend
        alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
        
        # Composite
        for c in range(3):
            roi[:, :, c] = (
                logo_crop[:, :, c] * alpha + 
                roi[:, :, c] * (1 - alpha)
            )
        
        result[y1:y2, x1:x2] = roi.astype(np.uint8)
        return result
    
    def place_logo(
        self,
        image: np.ndarray,
        logo: np.ndarray,
        region: DetectedRegion
    ) -> PlacementResult:
        """
        Place logo on the detected region.
        
        Args:
            image: Background image (BGR).
            logo: BGRA logo image.
            region: Detected region for placement.
            
        Returns:
            PlacementResult with the composited image.
        """
        config = self.config.get(region.class_name, {
            "base_size": 99, "width_ratio": 0.6, "clip_edge": None
        })
        
        # 1. Compute target size (fixed base_size, no dynamic reduction)
        target_w, target_h = self.compute_logo_size(logo, region)
        
        # 2. Resize logo (maintain aspect ratio)
        logo_h, logo_w = logo.shape[:2]
        scale = target_w / logo_w
        new_w = int(logo_w * scale)
        new_h = int(logo_h * scale)
        
        logo_resized = cv2.resize(logo, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # 3. Apply rotation to match region orientation
        rotation_angle = region.oriented_rect.angle
        
        # Rule-based orientation fix:
        # - LEFT_COLLAR needs 180° flip to keep logo upright
        # - All BICEP and SLEEVE regions need 180° flip for consistent orientation
        flip_regions = ["LEFT_COLLAR", "LEFT_BICEP", "LEFT_SLEEVE", "RIGHT_BICEP", "RIGHT_SLEEVE"]
        if region.class_name in flip_regions:
            rotation_angle = rotation_angle + 180
        
        logo_rotated = self.rotate_logo(logo_resized, -rotation_angle)
        
        # 4. Apply edge clipping for curved surfaces (biceps, sleeves, collars)
        # This is decorative effect, not size reduction
        clip_edge = config.get("clip_edge")
        if clip_edge:
            logo_rotated = self.clip_logo_edge(logo_rotated, clip_edge, clip_ratio=0.25)
        
        # 5. Create mask from polygon
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [region.mask_polygon], 255)
        
        # 6. Compute position (center logo on region center)
        lh, lw = logo_rotated.shape[:2]
        cx, cy = region.oriented_rect.center
        px = int(cx - lw / 2)
        py = int(cy - lh / 2)
        
        # 7. Composite with mask clipping (removes parts outside garment)
        result = self.apply_mask_clipping(image, logo_rotated, (px, py), mask)
        
        return PlacementResult(
            success=True,
            image=result,
            region=region,
            logo_size=(new_w, new_h),
            logo_position=(px, py),
            rotation_angle=rotation_angle,
            clipped_edge=clip_edge,
            debug_info={
                "base_size": config["base_size"],
                "rect_size": region.oriented_rect.size,
            }
        )
    
    def place_all_logos(
        self,
        image_path: str,
        logo_path: str,
        target_classes: Optional[List[str]] = None,
        conf_threshold: float = 0.3
    ) -> Tuple[np.ndarray, List[PlacementResult]]:
        """
        Detect all regions and place logos on them.
        
        Args:
            image_path: Path to the garment image.
            logo_path: Path to the logo image.
            target_classes: Optional list of class names to process.
            conf_threshold: Minimum detection confidence.
            
        Returns:
            (result_image, list of PlacementResult)
        """
        # Load image and logo
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Cannot load image: {image_path}")
        
        logo = self.load_logo(logo_path)
        
        # Detect regions
        regions = self.detect(image_path, conf_threshold)
        
        # Filter by target classes if specified
        if target_classes:
            regions = [r for r in regions if r.class_name in target_classes]
        
        # Place logo on each region
        result = image.copy()
        placements = []
        
        for region in regions:
            try:
                placement = self.place_logo(result, logo, region)
                if placement.success and placement.image is not None:
                    result = placement.image
                    placements.append(placement)
            except Exception as e:
                print(f"Error placing logo on {region.class_name}: {e}")
                placements.append(PlacementResult(
                    success=False,
                    image=None,
                    region=region,
                    logo_size=(0, 0),
                    logo_position=(0, 0),
                    rotation_angle=0,
                    clipped_edge=None,
                    debug_info={"error": str(e)}
                ))
        
        return result, placements


# ============================================================================
# CONVENIENCE FUNCTIONS (for integration with main.py later)
# ============================================================================

def get_coordinates(image_path: str, location_name: str, **kwargs) -> Tuple[int, int]:
    """
    Standard interface matching garmentDetector.py.
    Returns (x, y) coordinates for logo placement.
    """
    detector = YOLOGarmentDetector()
    
    # Map location name to class
    location_upper = location_name.upper().replace("-", "_").replace(" ", "_")
    
    regions = detector.detect(image_path)
    
    for region in regions:
        if region.class_name == location_upper:
            cx, cy = region.oriented_rect.center
            return int(cx), int(cy)
    
    # Fallback to image center if not found
    img = cv2.imread(image_path)
    if img is not None:
        return img.shape[1] // 2, img.shape[0] // 2
    return 0, 0


def get_logo_scale(
    image_path: str, 
    location_name: str, 
    base_size: Tuple[int, int] = (200, 100)
) -> Tuple[int, int]:
    """
    Standard interface matching garmentDetector.py.
    Returns (width, height) for logo sizing.
    """
    location_upper = location_name.upper().replace("-", "_").replace(" ", "_")
    config = PLACEMENT_CONFIG.get(location_upper, {"base_size": 99})
    
    base_w = config["base_size"]
    aspect_ratio = base_size[1] / base_size[0] if base_size[0] > 0 else 0.5
    
    return base_w, int(base_w * aspect_ratio)


def get_rotation(image_path: str, location_name: str) -> float:
    """
    Standard interface matching garmentDetector.py.
    Returns rotation angle in degrees.
    """
    detector = YOLOGarmentDetector()
    
    location_upper = location_name.upper().replace("-", "_").replace(" ", "_")
    
    regions = detector.detect(image_path)
    
    for region in regions:
        if region.class_name == location_upper:
            return region.oriented_rect.angle
    
    return 0.0
