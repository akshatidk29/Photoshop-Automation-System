"""
OBB (Oriented Bounding Box) based Garment Detector for Logo Placement.

Uses YOLO OBB model to detect garment regions with rotated bounding boxes.
The OBB model directly provides oriented bounding boxes, eliminating the need
to compute them from segmentation masks.

Logo Placement Rules:
- One detection per class (highest confidence)
- Logo starts horizontal/front, rotates to match OBB angle
- Use OBB box as mask to filter unwanted logo parts
"""

from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import numpy as np
import cv2

try:
    from ultralytics import YOLO
except ImportError:
    raise ImportError("Please install ultralytics: pip install ultralytics")


# Default OBB model path
DEFAULT_OBB_MODEL = Path(__file__).parent.parent / "runs" / "obb" / "train2" / "weights" / "best.pt"


# Placement configuration for each region type
PLACEMENT_CONFIG = {
    # Full body regions - center aligned, large logo
    "FULL_FRONT": {"base_size": 300, "align": "center"},
    "FULL_BACK": {"base_size": 300, "align": "center"},
    
    # Chest regions - center aligned
    "LEFT_CHEST": {"base_size": 99, "align": "center"},
    "RIGHT_CHEST": {"base_size": 99, "align": "center"},
    
    # Collar regions - edge aligned
    "LEFT_COLLAR": {"base_size": 99, "align": "left"},
    "RIGHT_COLLAR": {"base_size": 99, "align": "right"},
    
    # Bicep regions - edge aligned
    "LEFT_BICEP": {"base_size": 99, "align": "left"},
    "RIGHT_BICEP": {"base_size": 99, "align": "right"},
    
    # Sleeve regions - edge aligned
    "LEFT_SLEEVE": {"base_size": 99, "align": "left"},
    "RIGHT_SLEEVE": {"base_size": 99, "align": "right"},
    
    # Cuff regions - edge aligned
    "LEFT_CUFF": {"base_size": 99, "align": "left"},
    "RIGHT_CUFF": {"base_size": 99, "align": "right"},
    
    # Hip regions - center aligned
    "LEFT_HIP": {"base_size": 99, "align": "center"},
    "RIGHT_HIP": {"base_size": 99, "align": "center"},
    
    # Thigh regions - center aligned
    "LEFT_THIGH_HIGH": {"base_size": 99, "align": "center"},
    "RIGHT_THIGH_HIGH": {"base_size": 99, "align": "center"},
    
    # Pocket - center aligned
    "ON_POCKET": {"base_size": 99, "align": "center"},
    
    # Back yoke - center aligned
    "BACK_YOKE": {"base_size": 99, "align": "center"},
}


@dataclass
class OBBRegion:
    """Detected region with oriented bounding box."""
    class_id: int
    class_name: str
    confidence: float
    center: Tuple[float, float]  # (cx, cy)
    size: Tuple[float, float]    # (width, height)
    angle: float                  # rotation angle in degrees (raw from OBB)
    box_points: np.ndarray       # 4 corner points of the OBB


@dataclass 
class PlacementResult:
    """Result of logo placement."""
    success: bool
    image: np.ndarray
    region: OBBRegion
    logo_size: Tuple[int, int]
    logo_position: Tuple[int, int]
    rotation_angle: float
    debug_info: dict = None


class OBBGarmentDetector:
    """
    Detector using YOLO OBB model for garment region detection.
    
    Uses oriented bounding boxes directly from the model for logo placement.
    """
    
    def __init__(self, model_path: str = None, config: dict = None):
        """
        Initialize the OBB detector.
        
        Args:
            model_path: Path to the YOLO OBB model weights.
            config: Optional placement configuration override.
        """
        if model_path is None:
            model_path = str(DEFAULT_OBB_MODEL)
        
        self.model = YOLO(model_path)
        self.config = config or PLACEMENT_CONFIG
        
        # Get class names from model
        self.class_names = self.model.names
    
    def detect(self, image_path: str) -> List[OBBRegion]:
        """
        Detect garment regions using OBB model.
        Returns only the best detection (highest confidence) per class.
        
        Args:
            image_path: Path to the image.
            
        Returns:
            List of detected OBB regions (one per class).
        """
        # Run detection with no confidence filter (conf > 0)
        results = self.model(image_path, conf=0.01, verbose=False)
        
        # Collect all detections grouped by class
        detections_by_class: Dict[str, OBBRegion] = {}
        
        for r in results:
            if r.obb is None:
                continue
                
            boxes = r.obb
            
            for i in range(len(boxes)):
                try:
                    cls_id = int(boxes.cls[i].item())
                    conf = float(boxes.conf[i].item())
                    class_name = self.class_names.get(cls_id, f"class_{cls_id}")
                    
                    # Get the 4 corner points of the OBB
                    xyxyxyxy = boxes.xyxyxyxy[i].cpu().numpy().reshape(4, 2)
                    
                    # Compute center, size, angle from the 4 points (no normalization)
                    center, size, angle = self._compute_obb_params(xyxyxyxy)
                    
                    region = OBBRegion(
                        class_id=cls_id,
                        class_name=class_name,
                        confidence=conf,
                        center=center,
                        size=size,
                        angle=angle,
                        box_points=xyxyxyxy.astype(np.int32)
                    )
                    
                    # Keep only best confidence per class
                    if class_name not in detections_by_class or conf > detections_by_class[class_name].confidence:
                        detections_by_class[class_name] = region
                    
                except Exception as e:
                    print(f"Error processing OBB detection {i}: {e}")
                    continue
        
        return list(detections_by_class.values())
    
    def _compute_obb_params(self, points: np.ndarray) -> Tuple[Tuple[float, float], Tuple[float, float], float]:
        """
        Compute center, size, and angle from 4 corner points.
        No normalization - returns raw angle from OBB.
        
        Args:
            points: 4 corner points (4, 2).
            
        Returns:
            (center, size, angle) tuple.
        """
        # Center is the mean of all points
        center = (points[:, 0].mean(), points[:, 1].mean())
        
        # Compute edge lengths
        edge1 = np.linalg.norm(points[1] - points[0])
        edge2 = np.linalg.norm(points[2] - points[1])
        
        # Width is the longer edge, height is the shorter
        if edge1 >= edge2:
            width, height = edge1, edge2
            dx = points[1][0] - points[0][0]
            dy = points[1][1] - points[0][1]
        else:
            width, height = edge2, edge1
            dx = points[2][0] - points[1][0]
            dy = points[2][1] - points[1][1]
        
        # Calculate raw angle
        angle = np.degrees(np.arctan2(dy, dx))
        
        # Keep logo readable: ensure angle is in [-90, 90] range
        # This prevents upside-down logos while preserving OBB direction
        while angle > 90:
            angle -= 180
        while angle < -90:
            angle += 180
        
        return center, (width, height), angle
    
    def load_logo(self, logo_path: str) -> np.ndarray:
        """
        Load logo with alpha channel.
        Removes white background if logo doesn't have alpha channel.
        """
        logo = cv2.imread(str(logo_path), cv2.IMREAD_UNCHANGED)
        if logo is None:
            raise FileNotFoundError(f"Cannot load logo: {logo_path}")
        
        # Ensure 4 channels (BGRA)
        if len(logo.shape) == 2:
            # Grayscale - convert to BGRA
            logo = cv2.cvtColor(logo, cv2.COLOR_GRAY2BGRA)
        elif logo.shape[2] == 3:
            # BGR - create alpha from white background
            # White pixels become transparent
            b, g, r = cv2.split(logo)
            # Detect near-white pixels (background)
            white_mask = (b > 240) & (g > 240) & (r > 240)
            # Create alpha: 0 for white, 255 for non-white
            alpha = np.where(white_mask, 0, 255).astype(np.uint8)
            logo = cv2.merge([b, g, r, alpha])
        # If already 4 channels (BGRA), keep as is
        
        return logo
    
    def rotate_logo(self, logo: np.ndarray, angle: float) -> np.ndarray:
        """
        Rotate logo by given angle, preserving alpha channel.
        Logo starts horizontal/front, rotates to match OBB angle.
        """
        h, w = logo.shape[:2]
        center = (w / 2, h / 2)
        
        # Get rotation matrix
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Compute new bounding box size
        cos = abs(M[0, 0])
        sin = abs(M[0, 1])
        new_w = int(h * sin + w * cos)
        new_h = int(h * cos + w * sin)
        
        # Adjust rotation matrix for new size
        M[0, 2] += (new_w - w) / 2
        M[1, 2] += (new_h - h) / 2
        
        # Rotate with transparent background
        rotated = cv2.warpAffine(
            logo, M, (new_w, new_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0)
        )
        
        return rotated
    
    def create_obb_mask(self, image_shape: Tuple[int, int], box_points: np.ndarray) -> np.ndarray:
        """Create a mask from OBB corner points."""
        mask = np.zeros(image_shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [box_points], 255)
        return mask
    
    def place_logo(
        self,
        image: np.ndarray,
        logo: np.ndarray,
        region: OBBRegion
    ) -> PlacementResult:
        """
        Place logo on the detected OBB region.
        
        Logo starts horizontal/front and rotates to match OBB angle.
        No flipping - direct rotation only.
        
        Args:
            image: Background image (BGR).
            logo: BGRA logo image.
            region: Detected OBB region.
            
        Returns:
            PlacementResult with the composited image.
        """
        config = self.config.get(region.class_name, {"base_size": 99, "align": "center"})
        
        base_size = config["base_size"]
        align = config["align"]
        
        # 1. Resize logo to base_size
        logo_h, logo_w = logo.shape[:2]
        aspect_ratio = logo_h / logo_w if logo_w > 0 else 1.0
        target_w = base_size
        target_h = int(base_size * aspect_ratio)
        
        logo_resized = cv2.resize(logo, (target_w, target_h), interpolation=cv2.INTER_AREA)
        
        # 2. Apply rotation - logo starts horizontal, rotate to match OBB angle
        # Negate angle because OBB angle is counterclockwise but rotation is clockwise
        rotation_angle = -region.angle
        logo_rotated = self.rotate_logo(logo_resized, rotation_angle)
        
        # 3. Compute position based on alignment
        lh, lw = logo_rotated.shape[:2]
        cx, cy = region.center
        obb_w, obb_h = region.size
        
        if align == "left":
            # Align logo to left edge of OBB
            angle_rad = np.radians(region.angle)
            offset_x = (obb_w / 2 - lw / 2) * np.cos(angle_rad)
            offset_y = (obb_w / 2 - lw / 2) * np.sin(angle_rad)
            px = int(cx - offset_x - lw / 2)
            py = int(cy - offset_y - lh / 2)
        elif align == "right":
            # Align logo to right edge of OBB
            angle_rad = np.radians(region.angle)
            offset_x = (obb_w / 2 - lw / 2) * np.cos(angle_rad)
            offset_y = (obb_w / 2 - lw / 2) * np.sin(angle_rad)
            px = int(cx + offset_x - lw / 2)
            py = int(cy + offset_y - lh / 2)
        else:
            # Center align
            px = int(cx - lw / 2)
            py = int(cy - lh / 2)
        
        # 4. Create mask from OBB
        mask = self.create_obb_mask(image.shape, region.box_points)
        
        # 5. Composite with mask clipping (no blur)
        result = self._apply_mask_clipping(image, logo_rotated, (px, py), mask)
        
        return PlacementResult(
            success=True,
            image=result,
            region=region,
            logo_size=(lw, lh),
            logo_position=(px, py),
            rotation_angle=rotation_angle,
            debug_info={
                "base_size": base_size,
                "align": align,
                "obb_size": region.size,
            }
        )
    
    def _apply_mask_clipping(
        self,
        image: np.ndarray,
        logo: np.ndarray,
        position: Tuple[int, int],
        mask: np.ndarray
    ) -> np.ndarray:
        """Apply logo to image, clipping to mask bounds. No blur effect."""
        result = image.copy()
        px, py = position
        lh, lw = logo.shape[:2]
        ih, iw = image.shape[:2]
        
        # Compute valid regions
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
        
        # Logo alpha combined with mask (no blur)
        alpha = logo_crop[:, :, 3] / 255.0
        alpha = alpha * mask_crop  # Multiply by OBB mask
        
        # Composite
        for c in range(3):
            roi[:, :, c] = (
                logo_crop[:, :, c] * alpha + 
                roi[:, :, c] * (1 - alpha)
            )
        
        result[y1:y2, x1:x2] = roi.astype(np.uint8)
        return result
    
    def place_all_logos(
        self,
        image_path: str,
        logo_path: str,
        target_classes: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[PlacementResult]]:
        """
        Detect regions and place logos on all detected areas.
        Only one detection per class (highest confidence).
        
        Args:
            image_path: Path to input image.
            logo_path: Path to logo image.
            target_classes: Optional list of classes to target.
            
        Returns:
            (result_image, list of PlacementResults)
        """
        # Load images
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Cannot load image: {image_path}")
        
        logo = self.load_logo(logo_path)
        
        # Detect regions (one per class, best confidence)
        regions = self.detect(image_path)
        
        # Filter by target classes if specified
        if target_classes:
            regions = [r for r in regions if r.class_name in target_classes]
        
        # Place logos
        result_image = image.copy()
        results = []
        
        for region in regions:
            try:
                placement = self.place_logo(result_image, logo, region)
                result_image = placement.image
                results.append(placement)
            except Exception as e:
                print(f"Error placing logo on {region.class_name}: {e}")
                continue
        
        return result_image, results
    
    def draw_debug_info(
        self,
        image: np.ndarray,
        regions: List[OBBRegion]
    ) -> np.ndarray:
        """Draw debug visualization with OBB boxes and labels."""
        debug_img = image.copy()
        
        for region in regions:
            # Draw OBB
            pts = region.box_points.reshape((-1, 1, 2))
            cv2.polylines(debug_img, [pts], True, (0, 0, 255), 2)
            
            # Draw center point
            cx, cy = int(region.center[0]), int(region.center[1])
            cv2.circle(debug_img, (cx, cy), 5, (255, 0, 255), -1)
            
            # Draw label
            label = f"{region.class_name} ({region.confidence:.0%})"
            cv2.putText(debug_img, label, (cx - 50, cy - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            
            # Draw angle
            angle_text = f"Angle: {region.angle:.1f}"
            cv2.putText(debug_img, angle_text, (cx - 50, cy + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        
        return debug_img
