"""
Photoshop Automation - Main Entry Point
Beautiful, modern GUI using CustomTkinter for production-ready automation.
COMPACT SINGLE-PAGE LAYOUT - Optimized spacing
"""

import os
import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import time
import shutil
from PIL import Image, ImageFilter, ImageEnhance

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
    """Modern GUI for Photoshop Automation - Compact Layout."""
    
    def __init__(self):
        super().__init__()
        
        self.title("Photoshop Automation Pro")
        self.geometry("1200x800")
        self.minsize(1100, 750)
        
        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 1200) // 2
        y = (self.winfo_screenheight() - 800) // 2
        self.geometry(f"1200x800+{x}+{y}")
        
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
        
        # Color scheme - Premium professional palette
        self.colors = {
            'bg_main': '#0f1419',
            'bg_card': '#1a1f26',
            'bg_card_hover': '#1f252e',
            'accent': '#3b82f6',
            'accent_hover': '#2563eb',
            'success': '#10b981',
            'success_hover': '#059669',
            'warning': '#f59e0b',
            'error': '#ef4444',
            'text_primary': '#e5e7eb',
            'text_secondary': '#9ca3af',
            'border': '#374151',
            'border_focus': '#60a5fa'
        }
        
        # Background handling
        self.bgImage = None
        self.bgLabel = None
        
        self._loadBackground()  # Load background FIRST
        self._buildUI()  # Then build UI on top
        self._updateStatus()
    
    def _loadBackground(self):
        """Load and set background image with fallback."""
        from tkinter import Canvas
        
        try: 
            possiblePaths = [
                "photoshopAutomation.png",  # Current directory
                os.path.join(os.getcwd(), "photoshopAutomation.png"),  # Current working directory
                os.path.join(BASE_DIR, "photoshopAutomation.png"),  # Base directory
                os.path.join(os.path.dirname(__file__), "photoshopAutomation.png"),  # Script directory
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "photoshopAutomation.png"),  # Absolute script dir
            ]
            
            bgPath = None
            print("\n[BACKGROUND] Searching for photoshopAutomation.png...")
            for path in possiblePaths:
                print(f"[BACKGROUND] Checking: {path}")
                if os.path.exists(path):
                    bgPath = path
                    print(f"[BACKGROUND] ✓ Found at: {bgPath}")
                    break
            
            if bgPath:
                print(f"[BACKGROUND] Loading image from: {bgPath}")
                # Load image
                img = Image.open(bgPath)
                print(f"[BACKGROUND] Image loaded: {img.size}")
                
                # Resize to window size
                img = img.resize((1200, 800), Image.Resampling.LANCZOS)
                
                # Apply blur for subtle background
                img = img.filter(ImageFilter.GaussianBlur(radius=10))
                
                # Darken significantly for readability
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(0.25)
                
                # Use CTkImage for the background
                self.bgImage = ctk.CTkImage(light_image=img, dark_image=img, size=(1200, 800))
                print("[BACKGROUND] CTkImage created successfully")
                
                # Create canvas for background
                if self.bgLabel is None:
                    # Use Canvas which is more reliable for background images
                    canvas = Canvas(self, width=1200, height=800, highlightthickness=0)
                    canvas.place(x=0, y=0)
                    
                    # Convert to PhotoImage for canvas
                    from PIL import ImageTk
                    photo = ImageTk.PhotoImage(img)
                    self.bgImage = photo  # Keep reference
                    canvas.create_image(0, 0, image=photo, anchor='nw')
                    self.bgLabel = canvas
                    print("[BACKGROUND] Canvas background created and placed")
                
                return
            else:
                print("[BACKGROUND] ✗ Image file not found in any location")
                print(f"[BACKGROUND] Current directory: {os.getcwd()}")
                print(f"[BACKGROUND] Script directory: {os.path.dirname(os.path.abspath(__file__))}")
                print(f"[BACKGROUND] BASE_DIR: {BASE_DIR}")
        except Exception as e:
            print(f"[BACKGROUND] Error loading image: {e}")
            import traceback
            traceback.print_exc()
        
        # Fallback: Create subtle gradient using canvas
        print("[BACKGROUND] Using fallback gradient background")
        try:
            # Create dark gradient background
            img = Image.new('RGB', (1200, 800), color='#0a0e12')
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            
            # Create subtle gradient effect
            for i in range(800):
                color_value = int(10 + (i / 800) * 15)  # 10 to 25
                color = f'#{color_value:02x}{color_value+2:02x}{color_value+5:02x}'
                draw.line([(0, i), (1200, i)], fill=color)
            
            # Create canvas for gradient
            if self.bgLabel is None:
                canvas = Canvas(self, width=1200, height=800, highlightthickness=0)
                canvas.place(x=0, y=0)
                
                from PIL import ImageTk
                photo = ImageTk.PhotoImage(img)
                self.bgImage = photo
                canvas.create_image(0, 0, image=photo, anchor='nw')
                self.bgLabel = canvas
                print("[BACKGROUND] Gradient canvas background applied")
        except Exception as e:
            print(f"[BACKGROUND] Gradient background failed: {e}")
    
    def _buildUI(self):
        """Build the premium UI - ultra compact."""
        # Main container
        mainContainer = ctk.CTkFrame(self, fg_color="transparent")
        mainContainer.place(x=0, y=0, relwidth=1, relheight=1)
        
        # Inner container with better padding
        innerContainer = ctk.CTkFrame(mainContainer, fg_color="transparent")
        innerContainer.pack(fill="both", expand=True, padx=25, pady=15)
        
        # ===== LEFT PANEL: Primary Controls =====
        leftPanel = ctk.CTkFrame(innerContainer, fg_color="transparent")
        leftPanel.pack(side="left", fill="both", expand=True, padx=(0, 15))
        
        # Header
        self._buildHeader(leftPanel)
        
        # File Selection Card
        self._buildFileSelection(leftPanel)
        
        # Settings Card
        self._buildSettings(leftPanel)
        
        # Progress & Start Button
        self._buildProgressSection(leftPanel)
        
        # ===== RIGHT PANEL: Advanced Configuration =====
        rightPanel = ctk.CTkFrame(innerContainer, width=360, fg_color="transparent")
        rightPanel.pack(side="right", fill="y")
        rightPanel.pack_propagate(False)
        
        self._buildAdvancedConfig(rightPanel)
    
    def _buildHeader(self, parent):
        """Build professional header."""
        headerFrame = ctk.CTkFrame(parent, fg_color="transparent")
        headerFrame.pack(fill="x", pady=(0, 12))
        
         
        
        # Separator line
        separator = ctk.CTkFrame(headerFrame, height=1, fg_color=self.colors['border'])
        separator.pack(fill="x", pady=(10, 0))
    
    def _buildFileSelection(self, parent):
        """Build file selection card."""
        # Card header
        headerLabel = ctk.CTkLabel(
            parent,
            text="Source Files",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        headerLabel.pack(anchor="w", pady=(0, 8))
        
        # Card body
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors['bg_card'],
            corner_radius=8,
            border_width=1,
            border_color=self.colors['border']
        )
        card.pack(fill="x", pady=(0, 10))
        
        cardContent = ctk.CTkFrame(card, fg_color="transparent")
        cardContent.pack(fill="both", expand=True, padx=20, pady=18)
        
        # Excel file
        self.excelStatusLabel = self._createFileRow(
            cardContent, "Excel Data", "excel"
        )
        
        # Images folder
        self.imagesStatusLabel = self._createFileRow(
            cardContent, "Product Images", "images"
        )
        
        # Logos folder
        self.logosStatusLabel = self._createFileRow(
            cardContent, "Logo Assets", "logos"
        )
    
    def _buildSettings(self, parent):
        """Build settings card."""
        # Card header
        headerLabel = ctk.CTkLabel(
            parent,
            text="Configuration",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        headerLabel.pack(anchor="w", pady=(0, 8))
        
        # Card body
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors['bg_card'],
            corner_radius=8,
            border_width=1,
            border_color=self.colors['border']
        )
        card.pack(fill="x", pady=(0, 10))
        
        cardContent = ctk.CTkFrame(card, fg_color="transparent")
        cardContent.pack(fill="both", expand=True, padx=20, pady=18)
        
        # Canvas Size Section
        canvasFrame = ctk.CTkFrame(cardContent, fg_color="transparent")
        canvasFrame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            canvasFrame,
            text="Canvas Height",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors['text_primary']
        ).pack(anchor="w", pady=(0, 6))
        
        radioFrame = ctk.CTkFrame(canvasFrame, fg_color="transparent")
        radioFrame.pack(fill="x")
        
        radio1 = ctk.CTkRadioButton(
            radioFrame,
            text="1800px (Apparel)",
            variable=self.canvasSize,
            value="1800",
            font=ctk.CTkFont(size=11),
            text_color=self.colors['text_secondary'],
            fg_color=self.colors['accent'],
            hover_color=self.colors['accent_hover']
        )
        radio1.pack(side="left", padx=(0, 20))
        
        radio2 = ctk.CTkRadioButton(
            radioFrame,
            text="1200px (Square)",
            variable=self.canvasSize,
            value="1200",
            font=ctk.CTkFont(size=11),
            text_color=self.colors['text_secondary'],
            fg_color=self.colors['accent'],
            hover_color=self.colors['accent_hover']
        )
        radio2.pack(side="left")
        
        # Separator
        sep = ctk.CTkFrame(cardContent, height=1, fg_color=self.colors['border'])
        sep.pack(fill="x", pady=10)
        
        # Options
        optionsFrame = ctk.CTkFrame(cardContent, fg_color="transparent")
        optionsFrame.pack(fill="x")
        
        ctk.CTkLabel(
            optionsFrame,
            text="Processing Options",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors['text_primary']
        ).pack(anchor="w", pady=(0, 6))
        
        ctk.CTkCheckBox(
            optionsFrame,
            text="Clear previous outputs before processing",
            variable=self.clearAssets,
            font=ctk.CTkFont(size=11),
            text_color=self.colors['text_secondary'],
            fg_color=self.colors['accent'],
            hover_color=self.colors['accent_hover'],
            checkmark_color=self.colors['bg_card']
        ).pack(anchor="w")
    
    def _buildProgressSection(self, parent):
        """Build progress section and start button."""
        # Progress Card header
        headerLabel = ctk.CTkLabel(
            parent,
            text="Status",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        )
        headerLabel.pack(anchor="w", pady=(0, 8))
        
        # Progress Card
        progressCard = ctk.CTkFrame(
            parent,
            fg_color=self.colors['bg_card'],
            corner_radius=8,
            border_width=1,
            border_color=self.colors['border']
        )
        progressCard.pack(fill="x", pady=(0, 12))
        
        progressContent = ctk.CTkFrame(progressCard, fg_color="transparent")
        progressContent.pack(fill="both", expand=True, padx=20, pady=18)
        
        # Progress bar
        self.progressBar = ctk.CTkProgressBar(
            progressContent,
            height=8,
            corner_radius=4,
            fg_color=self.colors['border'],
            progress_color=self.colors['accent']
        )
        self.progressBar.pack(fill="x", pady=(0, 8))
        self.progressBar.set(0)
        
        # Status text
        statusFrame = ctk.CTkFrame(progressContent, fg_color="transparent")
        statusFrame.pack(fill="x")
        
        self.progressLabel = ctk.CTkLabel(
            statusFrame,
            text="Ready to process",
            font=ctk.CTkFont(size=11),
            text_color=self.colors['text_secondary'],
            anchor="w"
        )
        self.progressLabel.pack(side="left")
        
        self.timeLabel = ctk.CTkLabel(
            statusFrame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=self.colors['text_secondary'],
            anchor="e"
        )
        self.timeLabel.pack(side="right")
        
        # Start Button - Prominent CTA
        self.startBtn = ctk.CTkButton(
            parent,
            text="START AUTOMATION",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            corner_radius=8,
            fg_color=self.colors['success'],
            hover_color=self.colors['success_hover'],
            text_color="white",
            command=self._startAutomation
        )
        self.startBtn.pack(fill="x")
    
    def _buildAdvancedConfig(self, parent):
        """Build advanced configuration panel."""
        # Section header
        headerFrame = ctk.CTkFrame(parent, fg_color="transparent")
        headerFrame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            headerFrame,
            text="Advanced Settings",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors['text_primary']
        ).pack(anchor="w")
        
        # Scrollable area for advanced settings
        scrollFrame = ctk.CTkScrollableFrame(
            parent,
            fg_color=self.colors['bg_card'],
            corner_radius=8,
            border_width=1,
            border_color=self.colors['border']
        )
        scrollFrame.pack(fill="both", expand=True)
        
        # Logo Settings
        self._buildLogoSettings(scrollFrame)
        
        # Clipping Settings
        self._buildClippingSettings(scrollFrame)
    
    def _buildLogoSettings(self, parent):
        """Build logo settings section."""
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", padx=16, pady=(16, 10))
        
        # Header with edit button
        headerRow = ctk.CTkFrame(section, fg_color="transparent")
        headerRow.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(
            headerRow,
            text="Logo Sizing",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors['text_primary']
        ).pack(side="left")
        
        editBtn = ctk.CTkButton(
            headerRow,
            text="Configure",
            width=85,
            height=26,
            corner_radius=6,
            font=ctk.CTkFont(size=10),
            fg_color=self.colors['bg_card_hover'],
            hover_color=self.colors['border'],
            command=self._openSizeEditor
        )
        editBtn.pack(side="right")
        
        # Use Excel size checkbox
        ctk.CTkCheckBox(
            section,
            text="Use custom logo size from Excel",
            variable=self.useExcelSize,
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_secondary'],
            fg_color=self.colors['accent'],
            hover_color=self.colors['accent_hover'],
            checkmark_color=self.colors['bg_card']
        ).pack(anchor="w", pady=(0, 6))
        
        # Size preview
        sizePreview = ", ".join([f"{k}: {v}px" for k, v in list(self.logoSizes.items())[:3]])
        self.sizePreviewLabel = ctk.CTkLabel(
            section,
            text=f"{sizePreview}..." if sizePreview else "No sizes configured",
            font=ctk.CTkFont(size=9),
            text_color=self.colors['text_secondary'],
            anchor="w",
            wraplength=300
        )
        self.sizePreviewLabel.pack(anchor="w")
        
        # Separator
        ctk.CTkFrame(parent, height=1, fg_color=self.colors['border']).pack(fill="x", padx=16, pady=10)
    
    def _buildClippingSettings(self, parent):
        """Build clipping settings section."""
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", padx=16, pady=(0, 16))
        
        # Header with toggle
        headerRow = ctk.CTkFrame(section, fg_color="transparent")
        headerRow.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(
            headerRow,
            text="Logo Clipping",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors['text_primary']
        ).pack(side="left")
        
        clipSwitch = ctk.CTkSwitch(
            headerRow,
            text="",
            width=40,
            height=20,
            variable=self.clippingEnabled,
            command=self._onClippingToggle,
            fg_color=self.colors['border'],
            progress_color=self.colors['accent'],
            button_color=self.colors['text_primary'],
            button_hover_color=self.colors['text_secondary']
        )
        clipSwitch.pack(side="right")
        
        # Description
        ctk.CTkLabel(
            section,
            text="Clips logo parts extending beyond garment edges",
            font=ctk.CTkFont(size=9),
            text_color=self.colors['text_secondary'],
            anchor="w",
            wraplength=300
        ).pack(anchor="w", pady=(0, 8))
        
        # Configure button
        configBtn = ctk.CTkButton(
            section,
            text="Configure Positions",
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(size=10),
            fg_color=self.colors['bg_card_hover'],
            hover_color=self.colors['border'],
            command=self._openClippingEditor
        )
        configBtn.pack(fill="x")
    
    def _createFileRow(self, parent, label, fileType):
        """Create a file selection row - compact version."""
        rowContainer = ctk.CTkFrame(parent, fg_color="transparent")
        rowContainer.pack(fill="x", pady=(0, 10))
        
        # Label
        ctk.CTkLabel(
            rowContainer,
            text=label,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors['text_primary'],
            anchor="w"
        ).pack(anchor="w", pady=(0, 4))
        
        # Status and browse row
        actionFrame = ctk.CTkFrame(rowContainer, fg_color="transparent")
        actionFrame.pack(fill="x")
        
        # Status indicator
        statusFrame = ctk.CTkFrame(
            actionFrame,
            fg_color=self.colors['bg_main'],
            corner_radius=6,
            height=36
        )
        statusFrame.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        statusLabel = ctk.CTkLabel(
            statusFrame,
            text="No file selected",
            font=ctk.CTkFont(size=11),
            text_color=self.colors['warning'],
            anchor="w"
        )
        statusLabel.pack(side="left", padx=12, fill="x", expand=True)
        
        # Browse button
        browseBtn = ctk.CTkButton(
            actionFrame,
            text="Browse",
            width=90,
            height=36,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=self.colors['accent'],
            hover_color=self.colors['accent_hover'],
            command=lambda: self._browseFile(fileType, statusLabel)
        )
        browseBtn.pack(side="right")
        
        # Set initial status if path exists
        if fileType == "excel" and self.excelPath:
            statusLabel.configure(
                text=f"✓  {os.path.basename(self.excelPath)}",
                text_color=self.colors['success']
            )
        elif fileType == "images" and self.imageRoot:
            statusLabel.configure(
                text=f"✓  {os.path.basename(self.imageRoot)}",
                text_color=self.colors['success']
            )
        elif fileType == "logos" and self.logoRoot:
            statusLabel.configure(
                text=f"✓  {os.path.basename(self.logoRoot)}",
                text_color=self.colors['success']
            )
        
        return statusLabel
    
    def _browseFile(self, fileType, statusLabel):
        """Handle file browsing with visual feedback."""
        if fileType == "excel":
            path = filedialog.askopenfilename(
                title="Select Excel File",
                filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
            )
            if path:
                self.excelPath = path
                statusLabel.configure(
                    text=f"✓  {os.path.basename(path)}",
                    text_color=self.colors['success']
                )
        elif fileType == "images":
            path = filedialog.askdirectory(title="Select Product Images Folder")
            if path:
                self.imageRoot = path
                statusLabel.configure(
                    text=f"✓  {os.path.basename(path)}",
                    text_color=self.colors['success']
                )
        elif fileType == "logos":
            path = filedialog.askdirectory(title="Select Logo Assets Folder")
            if path:
                self.logoRoot = path
                statusLabel.configure(
                    text=f"✓  {os.path.basename(path)}",
                    text_color=self.colors['success']
                )
        
        self._updateStatus()
    
    def _updateStatus(self):
        """Update start button state with visual feedback."""
        if self.excelPath and self.imageRoot and self.logoRoot:
            self.startBtn.configure(state="normal")
        else:
            self.startBtn.configure(state="disabled")
    
    def _openSizeEditor(self):
        """Open logo size editor dialog with improved design."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Logo Size Configuration")
        dialog.geometry("550x650")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 550) // 2
        y = self.winfo_y() + (self.winfo_height() - 650) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Configure dialog colors
        dialog.configure(fg_color=self.colors['bg_main'])
        
        # Header
        headerFrame = ctk.CTkFrame(dialog, fg_color="transparent")
        headerFrame.pack(fill="x", padx=30, pady=(30, 10))
        
        ctk.CTkLabel(
            headerFrame,
            text="Logo Size Configuration",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.colors['text_primary']
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            headerFrame,
            text="Set logo width in pixels for each decoration position",
            font=ctk.CTkFont(size=11),
            text_color=self.colors['text_secondary']
        ).pack(anchor="w", pady=(4, 0))
        
        # Scrollable content
        scrollFrame = ctk.CTkScrollableFrame(
            dialog,
            fg_color=self.colors['bg_card'],
            corner_radius=10,
            border_width=1,
            border_color=self.colors['border']
        )
        scrollFrame.pack(fill="both", expand=True, padx=30, pady=(10, 20))
        
        entries = {}
        for pos, size in sorted(self.logoSizes.items()):
            row = ctk.CTkFrame(scrollFrame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=5)
            
            ctk.CTkLabel(
                row,
                text=pos,
                font=ctk.CTkFont(size=10),
                text_color=self.colors['text_primary'],
                width=200,
                anchor="w"
            ).pack(side="left")
            
            entry = ctk.CTkEntry(
                row,
                width=70,
                height=28,
                corner_radius=6,
                fg_color=self.colors['bg_main'],
                border_color=self.colors['border'],
                text_color=self.colors['text_primary']
            )
            entry.insert(0, str(size))
            entry.pack(side="right", padx=(0, 5))
            
            ctk.CTkLabel(
                row,
                text="px",
                font=ctk.CTkFont(size=10),
                text_color=self.colors['text_secondary']
            ).pack(side="right")
            
            entries[pos] = entry
        
        def save():
            for pos, entry in entries.items():
                try:
                    self.logoSizes[pos] = int(entry.get())
                    if CONFIG_AVAILABLE:
                        updateLogoSize(pos, int(entry.get()))
                except:
                    pass
            preview = ", ".join([f"{k}: {v}px" for k, v in list(self.logoSizes.items())[:3]])
            self.sizePreviewLabel.configure(text=f"{preview}..." if preview else "No sizes configured")
            dialog.destroy()
        
        # Save button
        ctk.CTkButton(
            dialog,
            text="Save Changes",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.colors['success'],
            hover_color=self.colors['success_hover'],
            command=save
        ).pack(fill="x", padx=30, pady=(0, 30))
    
    def _openClippingEditor(self):
        """Open clipping positions editor with improved design."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Clipping Position Configuration")
        dialog.geometry("550x650")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center dialog
        x = self.winfo_x() + (self.winfo_width() - 550) // 2
        y = self.winfo_y() + (self.winfo_height() - 650) // 2
        dialog.geometry(f"+{x}+{y}")
        
        dialog.configure(fg_color=self.colors['bg_main'])
        
        # Header
        headerFrame = ctk.CTkFrame(dialog, fg_color="transparent")
        headerFrame.pack(fill="x", padx=30, pady=(30, 10))
        
        ctk.CTkLabel(
            headerFrame,
            text="Clipping Positions",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.colors['text_primary']
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            headerFrame,
            text="Enable or disable logo clipping for specific positions",
            font=ctk.CTkFont(size=11),
            text_color=self.colors['text_secondary']
        ).pack(anchor="w", pady=(4, 0))
        
        # Scrollable content
        scrollFrame = ctk.CTkScrollableFrame(
            dialog,
            fg_color=self.colors['bg_card'],
            corner_radius=10,
            border_width=1,
            border_color=self.colors['border']
        )
        scrollFrame.pack(fill="both", expand=True, padx=30, pady=(10, 20))
        
        checkVars = {}
        for pos, enabled in sorted(self.clippingPositions.items()):
            var = ctk.BooleanVar(value=enabled)
            checkVars[pos] = var
            
            ctk.CTkCheckBox(
                scrollFrame,
                text=pos,
                variable=var,
                font=ctk.CTkFont(size=10),
                text_color=self.colors['text_primary'],
                fg_color=self.colors['accent'],
                hover_color=self.colors['accent_hover'],
                checkmark_color=self.colors['bg_card']
            ).pack(anchor="w", padx=15, pady=3)
        
        def save():
            for pos, var in checkVars.items():
                self.clippingPositions[pos] = var.get()
            if CONFIG_AVAILABLE:
                updateClippingConfig(self.clippingEnabled.get(), self.clippingPositions)
            dialog.destroy()
        
        # Save button
        ctk.CTkButton(
            dialog,
            text="Save Changes",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.colors['success'],
            hover_color=self.colors['success_hover'],
            command=save
        ).pack(fill="x", padx=30, pady=(0, 30))
    
    def _onClippingToggle(self):
        """Handle clipping toggle with config update."""
        if CONFIG_AVAILABLE:
            updateClippingConfig(self.clippingEnabled.get(), self.clippingPositions)
    
    def _startAutomation(self):
        """Start automation with visual feedback."""
        if self.processing:
            return
        
        self.processing = True
        self.startBtn.configure(
            text="PROCESSING...",
            state="disabled",
            fg_color=self.colors['text_secondary']
        )
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
        """Show completion dialog with enhanced design."""
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
                    filetypes=[("Text Files", "*.txt")]
                )
                if path:
                    self.errorTracker.saveReport(path)
        else:
            messagebox.showerror("Error", "Automation failed. Check console.")
        
        self.destroy()
    
    def updateProgress(self, current, total):
        """Update progress bar with smooth animation."""
        if total == 0:
            return
        
        progress = current / total
        self.progressBar.set(progress)
        
        # Update status text
        self.progressLabel.configure(
            text=f"Processing {current} of {total} items ({progress*100:.0f}%)"
        )
        
        # Update time estimate
        if current > 0 and self.startTime:
            elapsed = time.time() - self.startTime
            remaining = (elapsed / current) * (total - current)
            
            if remaining < 60:
                timeText = f"{int(remaining)}s remaining"
            else:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                timeText = f"{mins}m {secs}s remaining"
            
            self.timeLabel.configure(text=timeText)
        
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
            
            garmentType = detectGarmentTypeFromLocation(locationName, partId)
            activeHeight = canvasHeight  # Always use user's GUI selection
            
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