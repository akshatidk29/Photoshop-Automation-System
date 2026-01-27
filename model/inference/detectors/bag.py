import sys
from pathlib import Path

# Add project root to path if running directly
if __name__ == "__main__":
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from model.inference.core.engine import InferenceEngine
from model.inference.core.utils import loadLogo, drawDebugInfo
from model.inference.core.compositor import LogoCompositor
import cv2

# Global Settings
LOGO_SETTINGS = {
    "DEFAULT_BASE_SIZE": 150,
    "USE_BOX_WIDTH": True, 
    "OVERRIDES": {}
}

PLACEMENT_CONFIG = {
    "FRONT_ON_BAG": {"baseSize": 200, "align": "center"},
    "ON_POCKET_ON_BAG": {"baseSize": 200, "align": "center"},
    "FRONT_CENTER": {"baseSize": 200, "align": "center"},
}

# Default Model Path
DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "modelBag" / "best.pt"

class BagModelDetector(InferenceEngine):
    def __init__(self, modelPath=None):
        path = modelPath or DEFAULT_MODEL_PATH
        super().__init__(path, config=PLACEMENT_CONFIG)

if __name__ == "__main__":
    # Setup test paths
    currentFile = Path(__file__)
    inferenceDir = currentFile.parent.parent # model/inference
    
    # Default Paths
    testImageDir = inferenceDir / "inputs" / "bag"
    outputDir = inferenceDir / "outputs" / "bag_test"
    logoPath = inferenceDir / "inputs" / "logo.png"
    
    # Allow command line args
    if len(sys.argv) > 1:
        testImageDir = Path(sys.argv[1])
        
    print("="*60)
    print("  Bag Detector Test (Modular)")
    print("="*60)
    
    outputDir.mkdir(parents=True, exist_ok=True)
    
    detector = BagModelDetector()
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
                    # Resolve config
                    baseSize = LOGO_SETTINGS["DEFAULT_BASE_SIZE"]
                    if r.className in LOGO_SETTINGS["OVERRIDES"]:
                        baseSize = LOGO_SETTINGS["OVERRIDES"][r.className]["baseSize"]
                        
                    # Logic for Box Width vs Fixed Size
                    if LOGO_SETTINGS.get("USE_BOX_WIDTH", False):
                        obbW, obbH = r.size
                        baseSize = int(obbW)
                        
                    align = "center"
                    # No clipping for bag
                    finalImg = compositor.placeLogo(finalImg, logo, r, baseSize, align, useClipping=False)
                except Exception as e:
                    print(f"     Failed to place logo on {r.className}: {e}")
        
        finalPath = outputDir / f"final_{imgFile.name}"
        cv2.imwrite(str(finalPath), finalImg)
        
        print(f"     Saved: {bboxPath.name} & {finalPath.name}")
        
    print(f"\n[Completed] Check {outputDir}")
