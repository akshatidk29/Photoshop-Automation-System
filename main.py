"""
Photoshop Automation - Main Entry Point
Beautiful, modern GUI using CustomTkinter for production-ready automation.
"""

import os
import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import time
import shutil

from services.excelReader import readExcel
from locators.imageLocator import findImageCandidates
from locators.logoLocator import findLogo

# Detectors
import detectors.garmentDetector as garmentDetector
import detectors.capDetector as capDetector
import detectors.bagDetector as bagDetector
import detectors.towelDetector as towelDetector
from detectors.comboParser import parseComboPosition

# Core/Utils
from photoshop.batchManager import PhotoshopBatchManager
from core.utils import detectGarmentTypeFromLocation, parseCustomSize, normalizeLocation
from core.config import BASE_DIR
from services.logger import logError, RowLogger

# Configuration
try:
    from configuration.configLoader import (
        getAllLogoSizes, getDefaultLogoSize, updateLogoSize,
        getAllClippingPositions, isClippingEnabledGlobal,
        updateClippingConfig
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False


# Set appearance and theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# Detector module map
DETECTOR_MODULES = {
    "T-SHIRT": garmentDetector,
    "CAP": capDetector,
    "BAG": bagDetector,
    "BLANKET": towelDetector
}


def getDetector(garmentType):
    """Retrieve the correct detector module."""
    return DETECTOR_MODULES.get(garmentType, garmentDetector)


class ErrorTracker:
    """Track errors during processing."""
    
    def __init__(self):
        self.failedRows = []
    
    def addError(self, rowIndex, finalName, errorMessage):
        self.failedRows.append({
            'row': rowIndex,
            'name': finalName,
            'error': errorMessage
        })
    
    def getCount(self):
        return len(self.failedRows)
    
    def saveReport(self, path):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("ERROR REPORT - PHOTOSHOP AUTOMATION\n")
                f.write("=" * 60 + "\n\n")
                if not self.failedRows:
                    f.write("No errors occurred.\n")
                else:
                    f.write(f"Total Errors: {len(self.failedRows)}\n\n")
                    for item in self.failedRows:
                        f.write(f"Row {item['row']}: {item['name']}\n")
                        f.write(f"  Error: {item['error']}\n\n")
            return True
        except:
            return False


class AutomationApp(ctk.CTk):
    """Modern GUI for Photoshop Automation."""
    
    def __init__(self):
        super().__init__()
        
        self.title("Photoshop Automation")
        self.geometry("900x850")
        self.minsize(800, 750)
        
        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 900) // 2
        y = (self.winfo_screenheight() - 850) // 2
        self.geometry(f"900x850+{x}+{y}")
        
        # Default paths
        DEFAULT_EXCEL = r"C:\Users\Akshat Mittal\Desktop\photoshopAutomation\Data\Sheet.xlsx"
        DEFAULT_IMAGES = r"C:\Users\Akshat Mittal\Desktop\photoshopAutomation\Data\Images"
        DEFAULT_LOGOS = r"C:\Users\Akshat Mittal\Desktop\photoshopAutomation\Data\Logos"
        
        self.excelPath = DEFAULT_EXCEL if os.path.exists(DEFAULT_EXCEL) else None
        self.imageRoot = DEFAULT_IMAGES if os.path.exists(DEFAULT_IMAGES) else None
        self.logoRoot = DEFAULT_LOGOS if os.path.exists(DEFAULT_LOGOS) else None
        
        self.processing = False
        self.startTime = None
        self.errorTracker = ErrorTracker()
        
        # Settings variables
        self.canvasSize = ctk.StringVar(value="1800")
        self.clearAssets = ctk.BooleanVar(value=False)
        self.clippingEnabled = ctk.BooleanVar(value=isClippingEnabledGlobal() if CONFIG_AVAILABLE else False)
        self.useExcelSize = ctk.BooleanVar(value=True)
        
        # Load config
        self.logoSizes = getAllLogoSizes() if CONFIG_AVAILABLE else {}
        self.clippingPositions = getAllClippingPositions() if CONFIG_AVAILABLE else {}
        
        self._buildUI()
        self._updateStatus()
    
    def _buildUI(self):
        """Build the UI."""
        # Main scrollable frame
        self.mainFrame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.mainFrame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # ===== HEADER =====
        headerFrame = ctk.CTkFrame(self.mainFrame, fg_color="transparent")
        headerFrame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            headerFrame,
            text="Photoshop Automation",
            font=ctk.CTkFont(size=32, weight="bold")
        ).pack()
        
        ctk.CTkLabel(
            headerFrame,
            text="Production-Ready Batch Processing System",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).pack(pady=(5, 0))
        
        # ===== FILE SELECTION =====
        filesFrame = ctk.CTkFrame(self.mainFrame)
        filesFrame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            filesFrame,
            text="📁  File Selection",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 10))
        
        # Excel
        self._createFileRow(filesFrame, "Excel Data File", "excel")
        # Images
        self._createFileRow(filesFrame, "Images Folder", "images")
        # Logos
        self._createFileRow(filesFrame, "Logos Folder", "logos")
        
        # ===== CANVAS SETTINGS =====
        canvasFrame = ctk.CTkFrame(self.mainFrame)
        canvasFrame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            canvasFrame,
            text="📐  Canvas Settings",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 10))
        
        canvasRow = ctk.CTkFrame(canvasFrame, fg_color="transparent")
        canvasRow.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkLabel(canvasRow, text="Canvas Height:").pack(side="left")
        
        ctk.CTkRadioButton(
            canvasRow, text="1800px (T-Shirts)", 
            variable=self.canvasSize, value="1800"
        ).pack(side="left", padx=(20, 10))
        
        ctk.CTkRadioButton(
            canvasRow, text="1200px (Square)",
            variable=self.canvasSize, value="1200"
        ).pack(side="left")
        
        # ===== LOGO SETTINGS =====
        logoFrame = ctk.CTkFrame(self.mainFrame)
        logoFrame.pack(fill="x", pady=10)
        
        logoHeader = ctk.CTkFrame(logoFrame, fg_color="transparent")
        logoHeader.pack(fill="x", padx=20, pady=(15, 10))
        
        ctk.CTkLabel(
            logoHeader,
            text="🎨  Logo Settings",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")
        
        ctk.CTkButton(
            logoHeader, text="Edit Sizes", width=100,
            command=self._openSizeEditor
        ).pack(side="right")
        
        logoOptions = ctk.CTkFrame(logoFrame, fg_color="transparent")
        logoOptions.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkCheckBox(
            logoOptions,
            text="Use custom logo size from Excel (if available)",
            variable=self.useExcelSize
        ).pack(anchor="w")
        
        # Preview of sizes
        sizePreview = ", ".join([f"{k}: {v}px" for k, v in list(self.logoSizes.items())[:4]])
        self.sizePreviewLabel = ctk.CTkLabel(
            logoOptions, 
            text=f"Current sizes: {sizePreview}...",
            text_color="gray"
        )
        self.sizePreviewLabel.pack(anchor="w", pady=(5, 0))
        
        # ===== CLIPPING SETTINGS =====
        clipFrame = ctk.CTkFrame(self.mainFrame)
        clipFrame.pack(fill="x", pady=10)
        
        clipHeader = ctk.CTkFrame(clipFrame, fg_color="transparent")
        clipHeader.pack(fill="x", padx=20, pady=(15, 10))
        
        ctk.CTkLabel(
            clipHeader,
            text="✂️  Logo Clipping",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")
        
        ctk.CTkSwitch(
            clipHeader, text="Enable",
            variable=self.clippingEnabled,
            command=self._onClippingToggle
        ).pack(side="right")
        
        clipOptions = ctk.CTkFrame(clipFrame, fg_color="transparent")
        clipOptions.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkButton(
            clipOptions, text="Configure Positions", width=150,
            fg_color="gray30", hover_color="gray40",
            command=self._openClippingEditor
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            clipOptions,
            text="Clips logo parts that extend beyond garment edges",
            text_color="gray"
        ).pack(anchor="w", pady=(5, 0))
        
        # ===== OPTIONS =====
        optFrame = ctk.CTkFrame(self.mainFrame)
        optFrame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            optFrame,
            text="⚙️  Options",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 10))
        
        optContent = ctk.CTkFrame(optFrame, fg_color="transparent")
        optContent.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkCheckBox(
            optContent,
            text="Clear previous output before processing",
            variable=self.clearAssets
        ).pack(anchor="w")
        
        # ===== PROGRESS =====
        progressFrame = ctk.CTkFrame(self.mainFrame)
        progressFrame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            progressFrame,
            text="📊  Progress",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 10))
        
        progressContent = ctk.CTkFrame(progressFrame, fg_color="transparent")
        progressContent.pack(fill="x", padx=20, pady=(0, 15))
        
        self.progressBar = ctk.CTkProgressBar(progressContent, height=20)
        self.progressBar.pack(fill="x")
        self.progressBar.set(0)
        
        self.progressLabel = ctk.CTkLabel(
            progressContent, text="Ready to process", text_color="gray"
        )
        self.progressLabel.pack(anchor="w", pady=(5, 0))
        
        self.timeLabel = ctk.CTkLabel(
            progressContent, text="", text_color="gray"
        )
        self.timeLabel.pack(anchor="w")
        
        # ===== START BUTTON =====
        self.startBtn = ctk.CTkButton(
            self.mainFrame,
            text="▶  START AUTOMATION",
            font=ctk.CTkFont(size=18, weight="bold"),
            height=60,
            fg_color="#28a745",
            hover_color="#218838",
            command=self._startAutomation
        )
        self.startBtn.pack(fill="x", pady=20)
    
    def _createFileRow(self, parent, label, fileType):
        """Create a file selection row."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(row, text=label, width=140, anchor="w").pack(side="left")
        
        # Status label
        statusLabel = ctk.CTkLabel(row, text="Not selected", text_color="orange", width=350, anchor="w")
        statusLabel.pack(side="left", padx=10)
        
        # Browse button
        def browse():
            if fileType == "excel":
                path = filedialog.askopenfilename(
                    title="Select Excel File",
                    filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")]
                )
                if path:
                    self.excelPath = path
                    statusLabel.configure(text=f"✓ {os.path.basename(path)}", text_color="#28a745")
            elif fileType == "images":
                path = filedialog.askdirectory(title="Select Images Folder")
                if path:
                    self.imageRoot = path
                    statusLabel.configure(text=f"✓ {os.path.basename(path)}", text_color="#28a745")
            elif fileType == "logos":
                path = filedialog.askdirectory(title="Select Logos Folder")
                if path:
                    self.logoRoot = path
                    statusLabel.configure(text=f"✓ {os.path.basename(path)}", text_color="#28a745")
            self._updateStatus()
        
        ctk.CTkButton(row, text="Browse", width=100, command=browse).pack(side="right")
        
        # Set initial status
        if fileType == "excel" and self.excelPath:
            statusLabel.configure(text=f"✓ {os.path.basename(self.excelPath)}", text_color="#28a745")
        elif fileType == "images" and self.imageRoot:
            statusLabel.configure(text=f"✓ {os.path.basename(self.imageRoot)}", text_color="#28a745")
        elif fileType == "logos" and self.logoRoot:
            statusLabel.configure(text=f"✓ {os.path.basename(self.logoRoot)}", text_color="#28a745")
    
    def _updateStatus(self):
        """Update start button state."""
        if self.excelPath and self.imageRoot and self.logoRoot:
            self.startBtn.configure(state="normal")
        else:
            self.startBtn.configure(state="disabled")
    
    def _openSizeEditor(self):
        """Open logo size editor dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Logo Sizes")
        dialog.geometry("500x600")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 500) // 2
        y = self.winfo_y() + (self.winfo_height() - 600) // 2
        dialog.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(
            dialog, text="Logo Sizes by Position",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=20)
        
        ctk.CTkLabel(
            dialog, text="Width in pixels (height by aspect ratio)",
            text_color="gray"
        ).pack()
        
        # Scrollable list
        scrollFrame = ctk.CTkScrollableFrame(dialog, height=400)
        scrollFrame.pack(fill="both", expand=True, padx=20, pady=10)
        
        entries = {}
        for pos, size in sorted(self.logoSizes.items()):
            row = ctk.CTkFrame(scrollFrame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            ctk.CTkLabel(row, text=pos, width=200, anchor="w").pack(side="left")
            
            entry = ctk.CTkEntry(row, width=80)
            entry.insert(0, str(size))
            entry.pack(side="right")
            
            ctk.CTkLabel(row, text="px").pack(side="right", padx=(0, 5))
            
            entries[pos] = entry
        
        def save():
            for pos, entry in entries.items():
                try:
                    self.logoSizes[pos] = int(entry.get())
                    if CONFIG_AVAILABLE:
                        updateLogoSize(pos, int(entry.get()))
                except:
                    pass
            preview = ", ".join([f"{k}: {v}px" for k, v in list(self.logoSizes.items())[:4]])
            self.sizePreviewLabel.configure(text=f"Current sizes: {preview}...")
            dialog.destroy()
        
        ctk.CTkButton(
            dialog, text="Save Changes", fg_color="#28a745",
            hover_color="#218838", command=save
        ).pack(pady=20)
    
    def _openClippingEditor(self):
        """Open clipping positions editor."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Clipping Positions")
        dialog.geometry("500x600")
        dialog.transient(self)
        dialog.grab_set()
        
        x = self.winfo_x() + (self.winfo_width() - 500) // 2
        y = self.winfo_y() + (self.winfo_height() - 600) // 2
        dialog.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(
            dialog, text="Clipping Positions",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=20)
        
        ctk.CTkLabel(
            dialog, text="Toggle positions for logo clipping",
            text_color="gray"
        ).pack()
        
        scrollFrame = ctk.CTkScrollableFrame(dialog, height=400)
        scrollFrame.pack(fill="both", expand=True, padx=20, pady=10)
        
        checkVars = {}
        for pos, enabled in sorted(self.clippingPositions.items()):
            var = ctk.BooleanVar(value=enabled)
            checkVars[pos] = var
            
            ctk.CTkCheckBox(scrollFrame, text=pos, variable=var).pack(anchor="w", pady=2)
        
        def save():
            for pos, var in checkVars.items():
                self.clippingPositions[pos] = var.get()
            if CONFIG_AVAILABLE:
                updateClippingConfig(self.clippingEnabled.get(), self.clippingPositions)
            dialog.destroy()
        
        ctk.CTkButton(
            dialog, text="Save Changes", fg_color="#28a745",
            hover_color="#218838", command=save
        ).pack(pady=20)
    
    def _onClippingToggle(self):
        """Handle clipping toggle."""
        if CONFIG_AVAILABLE:
            updateClippingConfig(self.clippingEnabled.get(), self.clippingPositions)
    
    def _startAutomation(self):
        """Start automation."""
        if self.processing:
            return
        
        self.processing = True
        self.startBtn.configure(text="⏳ PROCESSING...", state="disabled")
        self.startTime = time.time()
        self.errorTracker = ErrorTracker()
        
        if self.clearAssets.get():
            self._clearOutput()
        
        thread = threading.Thread(target=self._runAutomation, daemon=True)
        thread.start()
    
    def _clearOutput(self):
        """Clear output folder."""
        outputDir = os.path.join(BASE_DIR, "assets", "output")
        if os.path.exists(outputDir):
            try:
                shutil.rmtree(outputDir)
                os.makedirs(outputDir)
            except:
                pass
    
    def _runAutomation(self):
        """Run automation in thread."""
        try:
            canvasHeight = int(self.canvasSize.get())
        except:
            canvasHeight = 1800
        
        settings = {
            'useExcelLogoSize': self.useExcelSize.get(),
            'logoSizes': self.logoSizes,
            'clippingEnabled': self.clippingEnabled.get(),
            'clippingPositions': self.clippingPositions,
        }
        
        success = runAutomation(
            self.excelPath, self.imageRoot, self.logoRoot,
            canvasHeight, self, settings
        )
        
        self.processing = False
        self.after(0, lambda: self._showCompletion(success))
    
    def _showCompletion(self, success):
        """Show completion dialog."""
        errors = self.errorTracker.getCount()
        
        if success and errors == 0:
            messagebox.showinfo(
                "Success",
                "Automation completed successfully!\n\n"
                "Check 'assets/output/' for results."
            )
        elif success:
            if messagebox.askyesno(
                "Completed with Errors",
                f"Completed with {errors} errors.\n\nSave error report?"
            ):
                path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text", "*.txt")]
                )
                if path:
                    self.errorTracker.saveReport(path)
        else:
            messagebox.showerror("Error", "Automation failed. Check console.")
        
        self.destroy()
    
    def updateProgress(self, current, total):
        """Update progress bar."""
        if total == 0:
            return
        
        progress = current / total
        self.progressBar.set(progress)
        self.progressLabel.configure(text=f"Processing: {current}/{total} rows ({progress*100:.1f}%)")
        
        if current > 0 and self.startTime:
            elapsed = time.time() - self.startTime
            remaining = (elapsed / current) * (total - current)
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            self.timeLabel.configure(text=f"Estimated remaining: {mins}m {secs}s")
        
        self.update()


def runAutomation(excelPath, imageRoot, logoRoot, canvasHeight, gui, settings):
    """Main automation function."""
    print("\n" + "=" * 70)
    print("                 PHOTOSHOP BATCH AUTOMATION")
    print("=" * 70)

    if not os.path.exists(excelPath):
        return False
    
    rows = readExcel(excelPath)
    if not rows:
        return False
    
    print(f"\n[CONFIG] Total rows: {len(rows)}")
    
    processed = 0
    failed = 0
    
    batchMgr = PhotoshopBatchManager(maxItemsPerBatch=100)
    
    # Get settings
    logoSizesConfig = settings.get('logoSizes', {})
    clippingEnabled = settings.get('clippingEnabled', False)
    clippingPositions = settings.get('clippingPositions', {})
    useExcelLogoSize = settings.get('useExcelLogoSize', False)
    
    for idx, row in enumerate(rows, 1):
        if gui:
            gui.updateProgress(idx - 1, len(rows))
        
        productId = row.get("Product ID")
        supplierName = row.get("Supplier Name")
        partId = row.get("Supplier Part ID")
        color = row.get("Supplier Color")
        decorationCode = row.get("Decoration Code")
        locationName = row.get("Decoration Location") or ""
        customLogoSize = row.get("Custom Logo Size")
        finalName = str(row.get("Final Image Name")).split(".jpg")[0]
        
        rLog = RowLogger(idx, finalName)
        print(f"\n[Row {idx}/{len(rows)}] {finalName}")
        rLog.log(f"Starting processing for: {finalName}")
        
        try:
            # Step 1: Find product image
            candidates = findImageCandidates(imageRoot, supplierName, partId, color, locationName)
            if not candidates:
                errorMsg = f"Could not find product image for '{partId}' in color '{color}'"
                rLog.error(errorMsg, reason="Check that the image exists in the Images folder")
                if gui:
                    gui.errorTracker.addError(idx, finalName, errorMsg)
                failed += 1
                continue
            
            # Step 2: Find logo file
            logoPath = findLogo(logoRoot, decorationCode)
            if not logoPath:
                errorMsg = f"Could not find logo file '{decorationCode}'"
                rLog.error(errorMsg, reason="Check that the logo file exists in the Logos folder")
                if gui:
                    gui.errorTracker.addError(idx, finalName, errorMsg)
                failed += 1
                continue
            
            garmentType = detectGarmentTypeFromLocation(locationName)
            activeHeight = canvasHeight if garmentType == "T-SHIRT" else 1200
            
            positions = parseComboPosition(locationName)
            positions.sort()
            isCombo = len(positions) > 1
            
            detector = getDetector(garmentType)
            success = False
            
            # Build per-position logo sizes
            positionSizes = []
            for pos in positions:
                posNorm = normalizeLocation(pos)
                # Check Excel first
                if useExcelLogoSize and customLogoSize:
                    parsed = parseCustomSize(customLogoSize)
                    if parsed:
                        positionSizes.append(parsed[0])
                        continue
                # Fallback to config - look for position in logoSizesConfig
                size = logoSizesConfig.get(posNorm, 99)
                positionSizes.append(size)
            
            for imgPath in candidates:
                try:
                    coordinatesList = []
                    rotationsList = []
                    valid = True
                    
                    for pos in positions:
                        try:
                            coords = detector.getCoordinates(imgPath, pos, originalLocation=locationName)
                            coordinatesList.append(coords)
                            try:
                                rotation = detector.getRotation(imgPath, pos)
                            except:
                                rotation = 0.0
                            rotationsList.append(rotation)
                        except Exception as e:
                            rLog.error(f"Failed pos {pos}: {e}")
                            valid = False
                            break
                    
                    if not valid:
                        continue
                    
                    if isCombo:
                        # Pass per-position sizes for combo
                        ok = batchMgr.addCombo(
                            partId, imgPath, logoPath, f"{partId} {color}.jpg",
                            decorationCode, positions, coordinatesList, rotationsList,
                            garmentType, positionSizes, finalName, activeHeight,
                            clippingEnabled=clippingEnabled, clippingPositions=clippingPositions
                        )
                    else:
                        # Single position - use first size
                        singleSize = positionSizes[0] if positionSizes else 99
                        ok = batchMgr.addPair(
                            partId, imgPath, logoPath, f"{partId} {color}.jpg",
                            decorationCode, positions[0], coordinatesList[0], rotationsList[0],
                            garmentType, singleSize, finalName, activeHeight,
                            clippingEnabled=clippingEnabled, clippingPositions=clippingPositions
                        )
                    
                    if ok:
                        processed += 1
                        rLog.success("Added to batch")
                        success = True
                        break
                
                except Exception as e:
                    rLog.error(f"Candidate failed: {e}")
                    continue
            
            if not success:
                errorMsg = f"Could not process any images for {partId}"
                rLog.error(errorMsg, reason="The garment position may not be detected correctly")
                if gui:
                    gui.errorTracker.addError(idx, finalName, errorMsg)
                failed += 1
        
        except Exception as e:
            errorMsg = f"Unexpected error processing row {idx}"
            rLog.error(errorMsg, reason=str(e))
            if gui:
                gui.errorTracker.addError(idx, finalName, str(e))
            failed += 1
    
    batchMgr.finalize()
    
    if gui:
        gui.updateProgress(len(rows), len(rows))
    
    print(f"\n[RESULT] Processed: {processed}, Failed: {failed}")
    return True


if __name__ == "__main__":
    app = AutomationApp()
    app.mainloop()

