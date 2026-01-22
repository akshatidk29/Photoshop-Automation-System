import sys
from pathlib import Path

# Add project root to path if running directly
if __name__ == "__main__":
    sys.path.append(str(Path(__file__).resolve().parents[3]))

try:
    from model.inference.core.engine import InferenceEngine
except ImportError:
    # Fallback if running from different context
    from ..core.engine import InferenceEngine

# Default Model Path (Relative to this file -> model/inference/detectors -> model/runs/...)
DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "modelGarment" / "best.pt"

# Configuration for Visualization/Testing
PLACEMENT_CONFIG = {
    # Full body
    "FULL_FRONT": {"baseSize": 300, "align": "center"},
    "FULL_BACK": {"baseSize": 300, "align": "center"},
    
    # Chest
    "LEFT_CHEST": {"baseSize": 99, "align": "center"},
    "RIGHT_CHEST": {"baseSize": 99, "align": "center"},
    
    # Collar
    "LEFT_COLLAR": {"baseSize": 99, "align": "left"},
    "RIGHT_COLLAR": {"baseSize": 99, "align": "right"},
    
    # Bicep
    "LEFT_BICEP": {"baseSize": 99, "align": "left"},
    "RIGHT_BICEP": {"baseSize": 99, "align": "right"},
    
    # Sleeve
    "LEFT_SLEEVE": {"baseSize": 99, "align": "left"},
    "RIGHT_SLEEVE": {"baseSize": 99, "align": "right"},
    
    # Cuff
    "LEFT_CUFF": {"baseSize": 99, "align": "left"},
    "RIGHT_CUFF": {"baseSize": 99, "align": "right"},
    
    # Hip
    "LEFT_HIP": {"baseSize": 99, "align": "center"},
    "RIGHT_HIP": {"baseSize": 99, "align": "center"},
    
    # Thigh
    "LEFT_THIGH_HIGH": {"baseSize": 99, "align": "center"},
    "RIGHT_THIGH_HIGH": {"baseSize": 99, "align": "center"},
    
    # Pocket
    "ON_POCKET": {"baseSize": 99, "align": "center"},
    
    # Back Yoke
    "BACK_YOKE": {"baseSize": 99, "align": "center"},
}

class GarmentModelDetector(InferenceEngine):
    """
    Garment-specific detector for testing.
    """
    def __init__(self, modelPath=None):
        path = modelPath or DEFAULT_MODEL_PATH
        super().__init__(path, config=PLACEMENT_CONFIG)

# Global Settings for Easy Configuration
LOGO_SETTINGS = {
    # Default Base Size (User can update this variable to change width)
    "DEFAULT_BASE_SIZE": 99, # Example changed from 99
    
    # Specific Overrides per Class
    "OVERRIDES": {
        "FULL_FRONT": {"baseSize": 300},
        "FULL_BACK": {"baseSize": 300},
    }
}

if __name__ == "__main__":
    from pathlib import Path
    from model.inference.core.utils import loadLogo, drawDebugInfo
    from model.inference.core.compositor import LogoCompositor
    import cv2
    import sys
    
    # Setup test paths
    currentFile = Path(__file__)
    inferenceDir = currentFile.parent.parent # model/inference
    
    # Default Paths
    testImageDir = inferenceDir / "inputs" / "garment"
    outputDir = inferenceDir / "outputs" / "garment_test"
    logoPath = inferenceDir / "inputs" / "logo.png"
    
    # Allow command line args
    if len(sys.argv) > 1:
        testImageDir = Path(sys.argv[1])
        
    print("="*60)
    print("  Garment Detector Test (Modular)")
    print("="*60)
    
    outputDir.mkdir(parents=True, exist_ok=True)
    
    detector = GarmentModelDetector()
    compositor = LogoCompositor()
    
    # Load Logo
    logo = None
    if logoPath.exists():
        logo = loadLogo(logoPath)
        
    # Get Images (Exclude logo.png)
    extensions = ["*.jpg", "*.jpeg", "*.png"]
    images = []
    if testImageDir.is_file():
        images = [testImageDir]
    else:
        for ext in extensions:
            found = testImageDir.glob(ext)
            for f in found:
                if f.name.lower() == "logo.png":
                    continue
                images.append(f)
            
    print(f"[RunTest] Found {len(images)} images.")
    
    for imgFile in images:
        print(f"  -> Processing {imgFile.name}...")
        
        # 1. Detect
        regions = detector.detect(str(imgFile))
        
        # Load Image
        originalImg = cv2.imread(str(imgFile))
        if originalImg is None: continue
        
        # 2. Output A: Debug BBox
        bboxImg = drawDebugInfo(originalImg, regions)
        bboxPath = outputDir / f"bbox_{imgFile.name}"
        cv2.imwrite(str(bboxPath), bboxImg)
        
        # 3. Output B: Final Placed (Clean)
        finalImg = originalImg.copy()
        if logo is not None:
            for r in regions:
                try:
                    # Resolve config: Global override -> Class specific -> Global default
                    baseSize = LOGO_SETTINGS["DEFAULT_BASE_SIZE"]
                    if r.className in LOGO_SETTINGS["OVERRIDES"]:
                        baseSize = LOGO_SETTINGS["OVERRIDES"][r.className]["baseSize"]
                    elif r.className in PLACEMENT_CONFIG:
                        # Fallback to internal config if not in overrides? 
                        # Or user wants "easy to change config at top".
                        # Let's trust LOGO_SETTINGS as primary control.
                        pass
                        
                    # Alignment still from PLACEMENT_CONFIG or default
                    align = "center"
                    if r.className in PLACEMENT_CONFIG:
                         align = PLACEMENT_CONFIG[r.className].get("align", "center")
                    
                    finalImg = compositor.placeLogo(finalImg, logo, r, baseSize, align)
                except Exception as e:
                    print(f"     Failed to place logo on {r.className}: {e}")
        
        finalPath = outputDir / f"final_{imgFile.name}"
        cv2.imwrite(str(finalPath), finalImg)
        
        print(f"     Saved: {bboxPath.name} & {finalPath.name}")
        
    print(f"\n[Completed] Check {outputDir}")
