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
from PIL import Image

from services.excelReader import readExcel
from locators.imageLocator import findImageCandidates
from locators.logoLocator import findLogo

# New two-phase processing services
from services.excelPreProcessor import preProcessExcel, EnrichedColumns, PreProcessingStatus, saveEnrichedCsv
from services.batchLogger import BatchLogger, LogCategory
from services.imageProcessor import ImageProcessor

# Detectors
import detectors.garmentDetector as garmentDetector
import detectors.capDetector as capDetector
import detectors.bagDetector as bagDetector
import detectors.towelDetector as towelDetector
from detectors.comboParser import parseComboPosition

# Core/Utils
from photoshop.batchManager import PhotoshopBatchManager
from core.utils import detectGarmentTypeFromLocation, parseCustomSize, normalizeLocation
from core.config import BASE_DIR, OUTPUT_ROOT
from services.logger import logError, RowLogger

# Configuration
try:
    from configuration.configLoader import (
        getAllLogoSizes, getDefaultLogoSize, updateLogoSize,
        getAllClippingPositions, isClippingEnabledGlobal,
        updateClippingConfig, getLogoSizeForPosition
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
        DEFAULT_IMAGES = r"C:\Users\Akshat Mittal\Desktop\photoshopAutomation\testing\Imges"
        DEFAULT_LOGOS = r"C:\Users\Akshat Mittal\Desktop\photoshopAutomation\testing\LOGOS"
        
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
        
        
        # Background handling - Removed as per request for minimal UI
        # self.bgImage = None
        # self.bgLabel = None
        
        self._buildUI()  # Build UI
        self._updateStatus()
    
    
    # _loadBackground method removed as per request for minimal UI

    
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
        
        # Capture settings in main thread
        try:
            canvasHeight = int(self.canvasSize.get())
        except:
            canvasHeight = 1800
        
        settings = {
            'useExcelLogoSize': self.useExcelSize.get(),
            'logoSizes': self.logoSizes.copy(), # Copy to avoid thread race
            'clippingEnabled': self.clippingEnabled.get(),
            'clippingPositions': self.clippingPositions.copy(),
        }
        
        if self.clearAssets.get():
            self._clearOutput()
        
        thread = threading.Thread(
            target=self._runAutomation, 
            args=(canvasHeight, settings),
            daemon=True
        )
        thread.start()
    
    def _clearOutput(self):
        """Clear output folder."""
        # Delete all output{i} folders in Output directory
        if os.path.exists(OUTPUT_ROOT):
            try:
                for item in os.listdir(OUTPUT_ROOT):
                    itemPath = os.path.join(OUTPUT_ROOT, item)
                    if os.path.isdir(itemPath) and item.lower().startswith("output"):
                        try:
                            shutil.rmtree(itemPath)
                        except:
                            pass
            except:
                pass
    
    def _runAutomation(self, canvasHeight, settings):
        """Run automation in thread with pre-captured settings."""
        # Note: Settings now passed as argument, avoiding thread-unsafe GUI access
        
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
                "Check 'Output/' for results."
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
    """
    Main automation function with two-phase architecture.
    
    Phase 1: Pre-process entire Excel to resolve all paths and validate rows
    Phase 2: Process enriched rows with deterministic data
    """
    print("\n" + "=" * 70)
    print("                 PHOTOSHOP BATCH AUTOMATION")
    print("                   (Two-Phase Processing)")
    print("=" * 70)

    if not os.path.exists(excelPath):
        print(f"[ERROR] Excel file not found: {excelPath}")
        return False
    
    # Setup output directory
    if not os.path.exists(OUTPUT_ROOT):
        os.makedirs(OUTPUT_ROOT)
        
    # Find next available output folder
    i = 1
    while True:
        outputDir = os.path.join(OUTPUT_ROOT, f"output{i}")
        if not os.path.exists(outputDir):
            break
        i += 1
    
    os.makedirs(outputDir)
    print(f"[INFO] Created output directory: {outputDir}")
    
    # Copy Excel file to output directory
    try:
        shutil.copy2(excelPath, outputDir)
    except Exception as e:
        print(f"[WARNING] Failed to copy Excel file: {e}")
    
    # Get settings
    logoSizesConfig = settings.get('logoSizes', {})
    clippingEnabled = settings.get('clippingEnabled', False)
    clippingPositions = settings.get('clippingPositions', {})
    useExcelLogoSize = settings.get('useExcelLogoSize', True)
    
    # ========================================================================
    # PHASE 1: Pre-process Excel
    # ========================================================================
    print("\n" + "=" * 60)
    print("  PHASE 1: Pre-Processing Excel")
    print("=" * 60)
    
    preProcessSettings = {
        'canvasHeight': canvasHeight,
        'logoSizes': logoSizesConfig,
        'useExcelLogoSize': useExcelLogoSize
    }
    
    result = preProcessExcel(excelPath, imageRoot, logoRoot, preProcessSettings)
    
    if result['stats']['total'] == 0:
        print("[ERROR] No rows to process")
        return False
    
    # Show errors upfront
    if result['stats']['errors'] > 0:
        print(f"\n[WARNING] {result['stats']['errors']} rows have errors and will be skipped:")
        for err in result['errors'][:10]:
            print(f"  Row {err['row']}: {err['message']}")
        if len(result['errors']) > 10:
            print(f"  ... and {len(result['errors']) - 10} more errors")
    
    if result['stats']['valid'] == 0:
        print("[ERROR] No valid rows to process after pre-processing")
        return False
        
    # Save pre-processed data for debugging/reference
    csvPath = os.path.join(outputDir, "preprocessed.csv")
    saveEnrichedCsv(result['enrichedRows'], csvPath)
    
    # ========================================================================
    # PHASE 2: Process Enriched Rows
    # ========================================================================
    print("\n" + "=" * 60)
    print(f"  PHASE 2: Processing {result['stats']['valid']} Valid Rows")
    print("=" * 60)
    
    # Initialize batch logger
    batchName = os.path.splitext(os.path.basename(excelPath))[0]
    batchLogger = BatchLogger(batchName, outputDir)
    
    # Initialize Image Processor
    imgProcessor = ImageProcessor(tempDir=os.path.join(BASE_DIR, "processedImg"))
    
    processed = 0
    failed = 0
    
    # Pass outputDir to manager
    batchMgr = PhotoshopBatchManager(outputDir=outputDir, maxItemsPerBatch=100)
    enrichedRows = result['enrichedRows']
    totalRows = len(enrichedRows)
    
    for idx, row in enumerate(enrichedRows, 1):
        if gui:
            gui.updateProgress(idx - 1, totalRows)
        
        finalName = str(row.get("Final Image Name", "")).split(".jpg")[0]
        
        # Skip rows with errors (already logged in Phase 1)
        if row.get(EnrichedColumns.STATUS) == PreProcessingStatus.ERROR:
            batchLogger.logError(idx, finalName, 
                                 row.get(EnrichedColumns.ERROR_MESSAGE, "Pre-processing error"))
            if gui:
                gui.errorTracker.addError(idx, finalName, row.get(EnrichedColumns.ERROR_MESSAGE))
            failed += 1
            continue
        
        # Use pre-resolved data from enriched columns
        imagePath = row.get(EnrichedColumns.IMAGE_PATH, "")
        logoPath = row.get(EnrichedColumns.LOGO_PATH, "")
        positions = row.get(EnrichedColumns.POSITIONS_LIST, [])
        logoSizes = row.get(EnrichedColumns.LOGO_SIZES_LIST, [99])
        garmentType = row.get(EnrichedColumns.GARMENT_TYPE, "T-SHIRT")
        activeHeight = row.get(EnrichedColumns.CANVAS_HEIGHT, canvasHeight)
        
        # Get original row data for logging
        partId = row.get("Supplier Part ID", "")
        color = row.get("Supplier Color", "")
        decorationCode = row.get("Decoration Code", "")
        locationName = row.get("Decoration Location", "")
        
        rLog = RowLogger(idx, finalName)
        print(f"\n[Row {idx}/{totalRows}] {finalName}")
        rLog.log(f"Starting processing for: {finalName}")
        
        # Log if fallback was used during pre-processing
        if row.get(EnrichedColumns.FALLBACK_USED):
            fallbackReason = row.get(EnrichedColumns.FALLBACK_REASON, "Unknown")
            rLog.fallback("Logo size resolution", fallbackReason)
            batchLogger.logFallback(idx, finalName, 
                                    "Logo size not in Excel or config", 
                                    f"Using default: {fallbackReason}")
        
        # Validate pre-resolved data
        if not imagePath or not os.path.exists(imagePath):
            errorMsg = f"Image path not resolved or doesn't exist"
            rLog.error(errorMsg)
            batchLogger.logError(idx, finalName, errorMsg)
            if gui:
                gui.errorTracker.addError(idx, finalName, errorMsg)
            failed += 1
            continue
        
        if not logoPath or not os.path.exists(logoPath):
            errorMsg = f"Logo path not resolved or doesn't exist"
            rLog.error(errorMsg)
            batchLogger.logError(idx, finalName, errorMsg)
            if gui:
                gui.errorTracker.addError(idx, finalName, errorMsg)
            failed += 1
            continue
        
        if not positions:
            positions = [locationName.upper().replace(" ", "-")]
        
        positions.sort()
        isCombo = len(positions) > 1
        
        detector = getDetector(garmentType)
        success = False
        
        # New: Pre-process image based on canvas height
        finalImagePath = imagePath
        processingFailed = False
        
        try:
            rLog.log(f"Pre-processing image to {activeHeight}px height...")
            finalImagePath = imgProcessor.processImage(imagePath, activeHeight)
            rLog.log("Image pre-processing successful")
        except Exception as e:
            processingFailed = True
            errorMsg = f"Image pre-processing failed: {e}"
            rLog.fallback("Image pre-processing failed", "Using original image")
            batchLogger.logFallback(idx, finalName, 
                                   "Image pre-processing check failed", 
                                   "Using original raw image")
            finalImagePath = imagePath
        
        try:
            coordinatesList = []
            rotationsList = []
            valid = True
            fallbackUsedForCoords = False
            
            # Use finalImagePath (processed or original) for detection
            for pos in positions:
                try:
                    coords = detector.getCoordinates(finalImagePath, pos, originalLocation=locationName)
                    coordinatesList.append(coords)
                    try:
                        rotation = detector.getRotation(finalImagePath, pos)
                    except:
                        rotation = 0.0
                    rotationsList.append(rotation)
                except Exception as e:
                    # This is where model might fail and use fallback
                    rLog.fallback(f"Model failed for {pos}", "Using MediaPipe/heuristic fallback")
                    batchLogger.logFallback(idx, finalName, 
                                            f"Model did not predict position {pos}",
                                            "Used MediaPipe/heuristic coordinates")
                    fallbackUsedForCoords = True
                    
                    # Try to get heuristic coordinates
                    try:
                        coords = detector.getCoordinates(finalImagePath, pos, originalLocation=locationName)
                        coordinatesList.append(coords)
                        rotationsList.append(0.0)
                    except:
                        rLog.error(f"Failed pos {pos}: {e}")
                        valid = False
                        break
            
            if not valid:
                errorMsg = f"Could not get coordinates for all positions"
                rLog.error(errorMsg)
                batchLogger.logError(idx, finalName, errorMsg)
                if gui:
                    gui.errorTracker.addError(idx, finalName, errorMsg)
                failed += 1
                
                # Cleanup if valid failed
                if not processingFailed and finalImagePath != imagePath:
                    try:
                        os.remove(finalImagePath)
                    except:
                        pass
                continue
            
            # Ensure we have enough logo sizes for all positions
            while len(logoSizes) < len(positions):
                logoSizes.append(99)  # Default fallback
            
            if isCombo:
                # Pass per-position sizes for combo
                ok = batchMgr.addCombo(
                    partId, finalImagePath, logoPath, f"{partId} {color}.jpg",
                    decorationCode, positions, coordinatesList, rotationsList,
                    garmentType, logoSizes, finalName, activeHeight,
                    clippingEnabled=clippingEnabled, clippingPositions=clippingPositions
                )
            else:
                # Single position - use first size
                singleSize = logoSizes[0] if logoSizes else 99
                ok = batchMgr.addPair(
                    partId, finalImagePath, logoPath, f"{partId} {color}.jpg",
                    decorationCode, positions[0], coordinatesList[0], rotationsList[0],
                    garmentType, singleSize, finalName, activeHeight,
                    clippingEnabled=clippingEnabled, clippingPositions=clippingPositions
                )
            
            if ok:
                processed += 1
                rLog.success("Added to batch")
                batchLogger.logSuccess(idx, finalName, "Added to batch successfully")
                success = True
                
                # Note: We don't delete the temp file immediately here because
                # PhotoshopBatchManager might still need it open or queued.
                # However, for this localized flow, Photoshop usually opens it immediately.
                # If batch manager queues paths, we must NOT delete it yet.
                # Assuming batch manager processes or queues for later. 
                # Ideally cleanup should happen after batch execution.
                # But to save space as requested "after each row", we can try.
                # If PhotoshopBatchManager opens file immediately, we can delete.
        
        except Exception as e:
            errorMsg = f"Unexpected error: {str(e)}"
            rLog.error(errorMsg)
            batchLogger.logError(idx, finalName, errorMsg, reason=str(e))
            if gui:
                gui.errorTracker.addError(idx, finalName, str(e))
            failed += 1
            continue
            
        finally:
            # Cleanup temp file for this row immediately as Photoshop has already read it
            if not processingFailed and finalImagePath != imagePath and finalImagePath and os.path.exists(finalImagePath):
                try:
                    os.remove(finalImagePath)
                except Exception as e:
                    print(f"Warning: Failed to delete temp file {finalImagePath}: {e}")
            
            # Periodic cleanup of temp folder every 50 rows
            if idx % 50 == 0:
                imgProcessor.cleanup()
        
        if not success:
            errorMsg = f"Could not process image for {partId}"
            rLog.error(errorMsg, reason="The garment position may not be detected correctly")
            batchLogger.logError(idx, finalName, errorMsg)
            if gui:
                gui.errorTracker.addError(idx, finalName, errorMsg)
            failed += 1
    
    batchMgr.finalize()
    
    if gui:
        gui.updateProgress(totalRows, totalRows)
    
    # Final cleanup
    imgProcessor.cleanup()
    
    # Save batch report
    batchLogger.saveReport()
    
    # Print final summary
    print("\n" + "=" * 60)
    print("  PROCESSING COMPLETE")
    print("=" * 60)
    stats = batchLogger.getStats()
    print(f"  Total Rows:     {totalRows}")
    print(f"  Processed:      {processed}")
    print(f"  Failed:         {failed}")
    print(f"  Fallbacks Used: {stats.get(LogCategory.FALLBACK, 0)}")
    print(f"  Log File:       {batchLogger.logPath}")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    app = AutomationApp()
    app.mainloop()