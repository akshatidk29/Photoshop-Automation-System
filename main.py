import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import time

from services.excelReader import readExcel
from locators.imageLocator import findImageCandidates
from locators.logoLocator import findLogo

# Detectors
# Detectors (Import Modules directly)
import detectors.garmentDetector as garmentDetector
import detectors.capDetector as capDetector
import detectors.bagDetector as bagDetector
import detectors.towelDetector as towelDetector
from detectors.comboParser import parseComboPosition

# Core/Utils
from photoshop.batchManager import PhotoshopBatchManager
from core.utils import detectGarmentTypeFromLocation, parseCustomSize, normalizeLocation
from services.logger import logError, RowLogger

# MODULE MAP
DETECTOR_MODULES = {
    "T-SHIRT": garmentDetector,
    "CAP": capDetector,
    "BAG": bagDetector,
    "BLANKET": towelDetector
}

def getDetector(garmentType):
    """Retrieve the correct detector module."""
    # Default to garmentDetector if unknown type
    return DETECTOR_MODULES.get(garmentType, garmentDetector)

class AutomationGUI:
    """Main GUI for Photoshop automation."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Photoshop Automation")
        self.root.geometry("700x750")
        self.root.resizable(True, True)
        
        # Center window on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        self.excelPath = None
        self.imageRoot = None
        self.logoRoot = None
        self.processing = False
        self.totalRows = 0
        self.processedRows = 0
        self.startTime = None

        self.buildUi()

    def buildUi(self):
        """Build the user interface."""
        # Title
        titleLabel = tk.Label(
            self.root, 
            text="Photoshop Automation", 
            font=("Arial", 16, "bold"), 
            fg="#003366"
        )
        titleLabel.pack(pady=10)

        # Main Frame for inputs
        mainFrame = tk.Frame(self.root)
        mainFrame.pack(padx=20, pady=5, fill=tk.BOTH, expand=True)

        # Excel File input
        excelFrame = tk.LabelFrame(mainFrame, text="1. Excel File", font=("Arial", 10, "bold"), padx=8, pady=5, bg="#E3F2FD")
        excelFrame.pack(fill=tk.X, pady=3)
        
        self.excelLabel = tk.Label(excelFrame, text="No file selected", font=("Arial", 9), fg="red", bg="#E3F2FD")
        self.excelLabel.pack(anchor=tk.W, pady=2)
        tk.Button(excelFrame, text="Browse Excel File", command=self.selectExcel, bg="#4CAF50", fg="white", width=35, height=1).pack(pady=2)

        # Images Folder input
        imageFrame = tk.LabelFrame(mainFrame, text="2. Images Folder", font=("Arial", 10, "bold"), padx=8, pady=5, bg="#E3F2FD")
        imageFrame.pack(fill=tk.X, pady=3)
        
        self.imageLabel = tk.Label(imageFrame, text="No folder selected", font=("Arial", 9), fg="red", bg="#E3F2FD")
        self.imageLabel.pack(anchor=tk.W, pady=2)
        tk.Button(imageFrame, text="Browse Images Folder", command=self.selectImageFolder, bg="#2196F3", fg="white", width=35, height=1).pack(pady=2)

        # Logos Folder input
        logoFrame = tk.LabelFrame(mainFrame, text="3. Logos Folder", font=("Arial", 10, "bold"), padx=8, pady=5, bg="#E3F2FD")
        logoFrame.pack(fill=tk.X, pady=3)
        
        self.logoLabel = tk.Label(logoFrame, text="No folder selected", font=("Arial", 9), fg="red", bg="#E3F2FD")
        self.logoLabel.pack(anchor=tk.W, pady=2)
        tk.Button(logoFrame, text="Browse Logos Folder", command=self.selectLogoFolder, bg="#FF9800", fg="white", width=35, height=1).pack(pady=2)

        # Settings (Canvas Size)
        settingsFrame = tk.LabelFrame(mainFrame, text="4. Canvas Settings", font=("Arial", 10, "bold"), padx=8, pady=5, bg="#E3F2FD")
        settingsFrame.pack(fill=tk.X, pady=3)
        
        self.canvasSizeVar = tk.StringVar(value="1800")
        
        tk.Label(settingsFrame, text="Default Canvas Height for Garments (Width 1200):", bg="#E3F2FD", font=("Arial", 9)).pack(anchor=tk.W)
        
        tk.Radiobutton(settingsFrame, text="1800px (Standard T-Shirts)", variable=self.canvasSizeVar, value="1800", bg="#E3F2FD", font=("Arial", 9)).pack(anchor=tk.W, padx=10)
        tk.Radiobutton(settingsFrame, text="1200px (Square)", variable=self.canvasSizeVar, value="1200", bg="#E3F2FD", font=("Arial", 9)).pack(anchor=tk.W, padx=10)

        # Progress Section
        progressFrame = tk.LabelFrame(self.root, text="Progress", font=("Arial", 10, "bold"), padx=10, pady=8)
        progressFrame.pack(padx=20, pady=8, fill=tk.X)

        self.progressVar = tk.DoubleVar()
        self.progressBar = ttk.Progressbar(progressFrame, variable=self.progressVar, maximum=100, length=400, mode='determinate')
        self.progressBar.pack(fill=tk.X, pady=5)

        self.progressLabel = tk.Label(progressFrame, text="Ready to process", font=("Arial", 9), fg="#666")
        self.progressLabel.pack(anchor=tk.W, pady=2)

        self.timeLabel = tk.Label(progressFrame, text="Estimated time: --", font=("Arial", 9), fg="#666")
        self.timeLabel.pack(anchor=tk.W, pady=2)

        # Start Button
        self.startButton = tk.Button(
            self.root, 
            text="START AUTOMATION", 
            font=("Arial", 11, "bold"), 
            command=self.startAutomation, 
            state=tk.DISABLED, 
            bg="#1B5E20", 
            fg="white", 
            height=2,
            cursor="hand2"
        )
        self.startButton.pack(pady=8, padx=20, fill=tk.X)

    def selectExcel(self):
        """Handle Excel file selection."""
        path = filedialog.askopenfilename(
            title="Select Excel Data File",
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
        )
        if path:
            self.excelPath = path
            filename = os.path.basename(path)
            self.excelLabel.config(text=f"Selected: {filename}", fg="green")
            self.checkEnableStart()

    def selectImageFolder(self):
        """Handle image folder selection."""
        path = filedialog.askdirectory(title="Select Images Folder")
        if path:
            self.imageRoot = path
            foldername = os.path.basename(path) or path
            self.imageLabel.config(text=f"Selected: {foldername}", fg="green")
            self.checkEnableStart()

    def selectLogoFolder(self):
        """Handle logo folder selection."""
        path = filedialog.askdirectory(title="Select Logos Folder")
        if path:
            self.logoRoot = path
            foldername = os.path.basename(path) or path
            self.logoLabel.config(text=f"Selected: {foldername}", fg="green")
            self.checkEnableStart()

    def checkEnableStart(self):
        """Enable start button if all inputs are selected."""
        if self.excelPath and self.imageRoot and self.logoRoot:
            self.startButton.config(state=tk.NORMAL, cursor="hand2")
        else:
            self.startButton.config(state=tk.DISABLED, cursor="arrow")

    def startAutomation(self):
        """Start the automation process."""
        self.startButton.config(state=tk.DISABLED, text="PROCESSING...")
        self.processing = True
        self.startTime = time.time()
        self.root.update()
        
        thread = threading.Thread(target=self.runAutomationThread, daemon=True)
        thread.start()

    def runAutomationThread(self):
        """Run automation in background thread."""
        try:
            defaultCanvasHeight = int(self.canvasSizeVar.get())
        except ValueError:
            defaultCanvasHeight = 1800
            
        success = runAutomation(self.excelPath, self.imageRoot, self.logoRoot, defaultCanvasHeight, self)
        
        self.processing = False
        if success:
            messagebox.showinfo("Success", "Automation Completed Successfully!\n\nCheck 'assets/output/' folder for results.")
        else:
            messagebox.showerror("Error", "Automation failed. Check console for details.")
        
        self.root.destroy()

    def updateProgress(self, current, total):
        """Update progress bar and estimated time."""
        if total == 0:
            return
        
        self.totalRows = total
        self.processedRows = current
        percentage = (current / total) * 100
        self.progressVar.set(percentage)
        
        self.progressLabel.config(text=f"Processing: {current}/{total} rows ({percentage:.1f}%)")
        
        if current > 0 and self.startTime:
            elapsed = time.time() - self.startTime
            avgTimePerRow = elapsed / current
            remainingRows = total - current
            estimatedRemaining = avgTimePerRow * remainingRows
            
            minutes = int(estimatedRemaining // 60)
            seconds = int(estimatedRemaining % 60)
            self.timeLabel.config(text=f"Estimated time remaining: {minutes}m {seconds}s")
        
        self.root.update()


def runAutomation(excelPath, imageRoot, logoRoot, defaultCanvasHeight=1800, gui=None):
    """Main automation function."""
    print("\n" + "="*70)
    print("                 PHOTOSHOP BATCH AUTOMATION")
    print("="*70)

    # Validate inputs
    if not os.path.exists(excelPath):
        return False
        
    # Read Excel (Auto-Converts to CSV)
    rows = readExcel(excelPath)
    if not rows:
        return False
        
    print(f"\n[CONFIG] Total rows to process: {len(rows)}")
    
    processed = 0
    failed = 0
    
    batchMgr = PhotoshopBatchManager(maxItemsPerBatch=100)
    
    for idx, row in enumerate(rows, 1):
        if gui:
            gui.updateProgress(idx - 1, len(rows))
            
        # Get data
        productId = row.get("Product ID")
        supplierName = row.get("Supplier Name")
        partId = row.get("Supplier Part ID")
        color = row.get("Supplier Color")
        decorationCode = row.get("Decoration Code")
        locationName = row.get("Decoration Location") or ""
        customLogoSize = row.get("Custom Logo Size")
        finalName = str(row.get("Final Image Name")).split(".jpg")[0]
        
        # Init Row Logger
        rLog = RowLogger(idx, finalName)
        rLog.log(f"Processing row {idx}: {finalName}")
        rLog.log(f"Config: {partId}, {color}, {locationName}, {decorationCode}")
        
        try:
            # 1. Find Images
            candidates = findImageCandidates(imageRoot, supplierName, partId, color, locationName)
            if not candidates:
                rLog.error("No image candidates found.")
                failed += 1
                continue
                
            rLog.log(f"Found {len(candidates)} image candidates: {[os.path.basename(c) for c in candidates]}")

            # 2. Find Logo
            logoPath = findLogo(logoRoot, decorationCode)
            if not logoPath:
                rLog.error(f"Logo not found: {decorationCode}")
                failed += 1
                continue
            rLog.log(f"Found logo: {os.path.basename(logoPath)}")

            # 3. Detect Garment Type
            garmentType = detectGarmentTypeFromLocation(locationName)
            rLog.log(f"Detected Type: {garmentType}")
            
            # 4. Canvas settings
            if garmentType == "T-SHIRT":
                activeHeight = defaultCanvasHeight
            else:
                activeHeight = 1200 # Caps, Bags, Towels are square
                
            # 5. Parse Positions
            positions = parseComboPosition(locationName)
            positions.sort() 
            isCombo = len(positions) > 1
            
            if isCombo:
                rLog.log(f"Combo Position Detected: {positions}")
            else:
                rLog.log(f"Single Position: {positions[0]}")

            # 6. Process Candidates
            success = False

            # Note: parseCustomSize returns ONE size.
            userSize = parseCustomSize(customLogoSize)
            
            # Select Detector Module
            detector = getDetector(garmentType)
            
            for imgPath in candidates:
                rLog.log(f"Trying image: {os.path.basename(imgPath)}")
                
                try:
                    coordinatesList = []
                    valid = True
                    
                    # Compute coordinates for ALL positions on this image
                    for pos in positions:
                        try:
                            # Standard Call: (image, location, *optionalContext)
                            # Some detectors ignore originalLocation, which is fine.
                            coords = detector.getCoordinates(imgPath, pos, originalLocation=locationName)
                            coordinatesList.append(coords)
                            rLog.log(f"  Coords for {pos}: {coords}")
                        except Exception as e:
                            rLog.error(f"  Failed specific pos {pos}: {e}")
                            valid = False
                            break
                    
                    if not valid:
                        continue
                        
                    finalLogoDims = (99.0, 99.0)
                    if userSize:
                        finalLogoDims = userSize
                    else:
                        # Compute based on first position using Standard Interface
                        try:
                            finalLogoDims = detector.getLogoScale(imgPath, positions[0], (200, 100))
                        except:
                             finalLogoDims = (200, 100)
                    
                    # Add to Batch
                    if isCombo:
                        ok = batchMgr.addCombo(
                            partId, imgPath, logoPath, f"{partId} {color}.jpg",
                            decorationCode, positions, coordinatesList,
                            garmentType, finalLogoDims, finalName, activeHeight
                        )
                    else:
                        ok = batchMgr.addPair(
                            partId, imgPath, logoPath, f"{partId} {color}.jpg",
                            decorationCode, positions[0], coordinatesList[0],
                            garmentType, finalLogoDims, finalName, activeHeight
                        )
                        
                    if ok:
                        processed += 1
                        rLog.success(f"Added to batch (Combo={isCombo})")
                        success = True
                        break # Done with this row
                
                except Exception as e:
                    rLog.error(f"Candidate failed: {e}")
                    continue
            
            if not success:
                rLog.error("All candidates failed.")
                failed += 1
        
        except Exception as e:
            rLog.error(f"Global Row Error: {e}")
            failed += 1
            
    # Finalize
    batchMgr.finalize()
    
    print(f"\n[RESULT] Processed: {processed}, Failed: {failed}")
    return True


if __name__ == "__main__":
    root = tk.Tk()
    gui = AutomationGUI(root)
    root.mainloop()
