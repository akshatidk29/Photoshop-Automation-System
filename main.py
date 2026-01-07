import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import time

from services.excelReader import readExcel
from locators.imageLocator import findImage, findImageCandidates
from locators.logoLocator import findLogo
from detectors.garmentDetector import getGarmentCoordinates, GARMENT_MAPPING
from detectors.capDetector import getCapCoordinates, CAP_MAPPING
from detectors.towelDetector import getTowelCoordinates, TOWEL_MAPPING
from detectors.bagDetector import getBagCoordinates, BAG_MAPPING
from detectors.baseDetector import getLocationCoordinates
from photoshop.batchManager import PhotoshopBatchManager
from core.utils import detectGarmentTypeFromLocation, computeLogoSize, parseCustomSize
from services.logger import logError


# Combined mapping for all garment types
ALL_MAPPINGS = {**GARMENT_MAPPING, **CAP_MAPPING, **TOWEL_MAPPING, **BAG_MAPPING}


def getLocationCoordinatesForType(imagePath, locationName):
    """Get coordinates using the appropriate detector based on garment type."""
    return getLocationCoordinates(imagePath, locationName, ALL_MAPPINGS)


class AutomationGUI:
    """Main GUI for Photoshop automation."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Photoshop Automation")
        self.root.geometry("700x560")
        self.root.resizable(False, False)
        
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
        success = runAutomation(self.excelPath, self.imageRoot, self.logoRoot, self)
        
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


def runAutomation(excelPath, imageRoot, logoRoot, gui=None):
    """Main automation function."""
    print("\n" + "="*70)
    print("                 PHOTOSHOP BATCH AUTOMATION")
    print("="*70)

    # Validation
    if not os.path.exists(excelPath):
        print(f"[ERROR] Excel file not found: {excelPath}")
        if gui:
            messagebox.showerror("Error", f"Excel file not found:\n{excelPath}")
        return False

    if not os.path.isdir(imageRoot):
        print(f"[ERROR] Image folder not found: {imageRoot}")
        if gui:
            messagebox.showerror("Error", f"Image folder not found:\n{imageRoot}")
        return False

    if not os.path.isdir(logoRoot):
        print(f"[ERROR] Logo folder not found: {logoRoot}")
        if gui:
            messagebox.showerror("Error", f"Logo folder not found:\n{logoRoot}")
        return False

    # Load Excel
    rows = readExcel(excelPath)
    if not rows:
        print("[ERROR] No valid rows found in Excel.")
        if gui:
            messagebox.showerror("Error", "No valid rows found in Excel file.")
        return False

    # Print configuration
    print(f"\n[CONFIG] Excel: {os.path.basename(excelPath)}")
    print(f"[CONFIG] Images: {imageRoot}")
    print(f"[CONFIG] Logos: {logoRoot}")
    print(f"[CONFIG] Total rows to process: {len(rows)}")
    print("-"*70)

    processed = 0
    failed = 0
    
    try:
        batchMgr = PhotoshopBatchManager(maxItemsPerBatch=200)
    except Exception as e:
        print("BATCH ERROR:", str(e))

    # Process each row
    try:
        for idx, row in enumerate(rows, 1):
            if gui:
                gui.updateProgress(idx - 1, len(rows))
            
            productId = row.get("Product ID")
            supplierName = row.get("Supplier Name")
            partId = row.get("Supplier Part ID")
            color = row.get("Supplier Color")
            decorationCode = row.get("Decoration Code")
            locationName = row.get("Decoration Location")
            customLogoSize = row.get("Custom Logo Size")
            finalName = str(row.get("Final Image Name")).split(".jpg")[0]

            try:
                # Find image candidates and logo
                candidates = findImageCandidates(imageRoot, supplierName, partId, color, locationName)
                if not candidates:
                    print(f"[{idx:3d}/{len(rows)}] [SKIP] Image not found for '{finalName}'")
                    failed += 1
                    continue

                logoPath = findLogo(logoRoot, decorationCode)
                if not logoPath:
                    print(f"[{idx:3d}/{len(rows)}] [SKIP] Logo not found for '{decorationCode}'")
                    failed += 1
                    continue

                # Determine garment type
                garmentType = detectGarmentTypeFromLocation(locationName)

                # Resolve logo size
                parsed = parseCustomSize(customLogoSize)
                if parsed:
                    logoDims = (float(parsed[0]), float(parsed[1]))
                else:
                    print("Using computed logo size")
                    try:
                        logoDims = computeLogoSize(garmentType, logoPath, locationName)
                    except Exception:
                        logoDims = (99.0, 99.0)

                # Try candidates sequentially
                success = False
                firstError = None
                targetName = f"{partId} {color}.jpg"

                for imagePath in candidates:
                    try:
                        coords = getLocationCoordinatesForType(imagePath, locationName)
                        ok = batchMgr.addPair(
                            partId,
                            imagePath,
                            logoPath,
                            targetName,
                            decorationCode,
                            locationName,
                            coords,
                            garmentType,
                            logoDims,
                            finalName,
                        )

                        if ok:
                            processed += 1
                            print(f"[{idx:3d}/{len(rows)}] [OK] {finalName}")
                            success = True
                            break
                        else:
                            continue

                    except Exception as e:
                        if firstError is None:
                            firstError = e
                        continue

                if not success:
                    failed += 1
                    errMsg = str(firstError) if firstError else "No candidate produced a valid result"
                    logError(f"Row failed: {errMsg}")
                    print(f"[{idx:3d}/{len(rows)}] [FAIL] {finalName}")

            except Exception as e:
                logError(f"Error in row {idx - 1} : {finalName}: {e}")
                failed += 1
                print(f"[{idx:3d}/{len(rows)}] [ERROR] {finalName}")
                print(f"          Exception: {str(e)[:60]}")
                continue
            
    except Exception as e:
        print("FOR LOOP ERROR:", str(e))

    # Finalize remaining batches
    batchMgr.finalize()

    if gui:
        gui.updateProgress(len(rows), len(rows))
        gui.timeLabel.config(text="Completed!")

    # Print results
    print("-"*70)
    print(f"\n[RESULT] Total Processed: {processed}/{len(rows)}")
    print(f"[RESULT] Failed/Skipped: {failed}/{len(rows)}")
    print("\n[OUTPUT] Files saved to:")
    print(f"         PSD Files: assets/output/photoshop/")
    print(f"         JPG Files: assets/output/For Printing/")
    print("\n" + "="*70 + "\n")
    
    return True


if __name__ == "__main__":
    root = tk.Tk()
    gui = AutomationGUI(root)
    root.mainloop()