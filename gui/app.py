"""Photoshop Automation - Modern GUI using CustomTkinter."""

import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import time
import shutil

from core.config import OUTPUT_ROOT

# Configuration
try:
    from configuration.configLoader import (
        getAllLogoSizes, updateLogoSize,
        getAllClippingPositions, isClippingEnabledGlobal,
        updateClippingConfig
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False


# Set appearance and theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


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
    
    def __init__(self, automationCallback=None):
        super().__init__()
        
        self.automationCallback = automationCallback
        
        self.title("Photoshop Automation")
        self.geometry("1100x720")
        self.minsize(1000, 680)
        
        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 1100) // 2
        y = (self.winfo_screenheight() - 720) // 2
        self.geometry(f"1100x720+{x}+{y}")
        
        # Default paths
        DEFAULT_EXCEL = r"C:\Users\Akshat Mittal\Desktop\photoshopAutomation\Data\\test.xlsx"
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
        
        # Clean color palette
        self.colors = {
            'bg': '#111318',
            'surface': '#1a1d24',
            'surface_light': '#22262f',
            'border': '#2d323c',
            'border_light': '#3d424f',
            'primary': '#4f8cff',
            'primary_hover': '#3d7ae8',
            'success': '#34d399',
            'success_hover': '#2cb880',
            'warning': '#fbbf24',
            'error': '#f87171',
            'text': '#f1f5f9',
            'text_dim': '#94a3b8',
            'text_muted': '#64748b',
        }
        
        self.configure(fg_color=self.colors['bg'])
        self._buildUI()
        self._updateStatus()
    
    def _buildUI(self):
        """Build the UI layout."""
        # Main container
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=32, pady=24)
        
        # Header
        self._buildHeader(main)
        
        # Content area - two columns
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(fill="both", expand=True, pady=(20, 0))
        
        # Left column - Main controls
        left = ctk.CTkFrame(content, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        
        self._buildSourceFiles(left)
        self._buildConfiguration(left)
        self._buildActions(left)
        
        # Right column - Advanced settings
        right = ctk.CTkFrame(content, width=400, fg_color="transparent")
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        
        self._buildAdvancedPanel(right)
    
    def _buildHeader(self, parent):
        """Build the header section."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x")
        
        # Title
        ctk.CTkLabel(
            header,
            text="Photoshop Automation",
            font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold"),
            text_color=self.colors['text']
        ).pack(side="left")
        
    def _buildSourceFiles(self, parent):
        """Build source files section."""
        # Section label
        ctk.CTkLabel(
            parent,
            text="SOURCE FILES",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w", pady=(0, 8))
        
        # Card
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors['surface'],
            corner_radius=12,
            border_width=1,
            border_color=self.colors['border']
        )
        card.pack(fill="x", pady=(0, 20))
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        
        # File rows
        self.excelStatus = self._createFileRow(inner, "Excel Data File", "excel", 0)
        self.imagesStatus = self._createFileRow(inner, "Product Images Folder", "images", 1)
        self.logosStatus = self._createFileRow(inner, "Logo Assets Folder", "logos", 2)
    
    def _createFileRow(self, parent, label, fileType, index):
        """Create a file selection row."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0 if index == 0 else 12, 0))
        
        # Left side - label and status
        leftSide = ctk.CTkFrame(row, fg_color="transparent")
        leftSide.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(
            leftSide,
            text=label,
            font=ctk.CTkFont(size=14),
            text_color=self.colors['text'],
            anchor="w"
        ).pack(anchor="w")
        
        # Status indicator
        statusFrame = ctk.CTkFrame(leftSide, fg_color="transparent")
        statusFrame.pack(anchor="w", pady=(4, 0))
        
        # Dot indicator
        dot = ctk.CTkFrame(statusFrame, width=8, height=8, corner_radius=4)
        dot.pack(side="left")
        
        statusLabel = ctk.CTkLabel(
            statusFrame,
            text="Not selected",
            font=ctk.CTkFont(size=11),
            text_color=self.colors['text_muted'],
            anchor="w"
        )
        statusLabel.pack(side="left", padx=(8, 0))
        
        # Set initial state
        path = None
        if fileType == "excel":
            path = self.excelPath
        elif fileType == "images":
            path = self.imageRoot
        elif fileType == "logos":
            path = self.logoRoot
        
        if path:
            dot.configure(fg_color=self.colors['success'])
            statusLabel.configure(
                text=os.path.basename(path),
                text_color=self.colors['text_dim']
            )
        else:
            dot.configure(fg_color=self.colors['warning'])
        
        # Browse button
        ctk.CTkButton(
            row,
            text="Browse",
            width=80,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=12),
            fg_color=self.colors['surface_light'],
            hover_color=self.colors['border'],
            text_color=self.colors['text'],
            command=lambda: self._browseFile(fileType, dot, statusLabel)
        ).pack(side="right")
        
        return (dot, statusLabel)
    
    def _buildConfiguration(self, parent):
        """Build configuration section."""
        # Section label
        ctk.CTkLabel(
            parent,
            text="CONFIGURATION",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w", pady=(0, 8))
        
        # Card
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors['surface'],
            corner_radius=12,
            border_width=1,
            border_color=self.colors['border']
        )
        card.pack(fill="x", pady=(0, 20))
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        
        # Canvas size
        sizeFrame = ctk.CTkFrame(inner, fg_color="transparent")
        sizeFrame.pack(fill="x")
        
        ctk.CTkLabel(
            sizeFrame,
            text="Canvas Height",
            font=ctk.CTkFont(size=15),
            text_color=self.colors['text']
        ).pack(anchor="w")
        
        radioFrame = ctk.CTkFrame(sizeFrame, fg_color="transparent")
        radioFrame.pack(anchor="w", pady=(8, 0))
        
        ctk.CTkRadioButton(
            radioFrame,
            text="1800px  Apparel",
            variable=self.canvasSize,
            value="1800",
            font=ctk.CTkFont(size=13),
            text_color=self.colors['text_dim'],
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            border_color=self.colors['border_light']
        ).pack(side="left", padx=(0, 24))
        
        ctk.CTkRadioButton(
            radioFrame,
            text="1200px  Square",
            variable=self.canvasSize,
            value="1200",
            font=ctk.CTkFont(size=13),
            text_color=self.colors['text_dim'],
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            border_color=self.colors['border_light']
        ).pack(side="left")
        
        # Divider
        ctk.CTkFrame(inner, height=1, fg_color=self.colors['border']).pack(fill="x", pady=16)
        
        # Clear outputs option
        ctk.CTkCheckBox(
            inner,
            text="Clear previous outputs before processing",
            variable=self.clearAssets,
            font=ctk.CTkFont(size=14),
            text_color=self.colors['text_dim'],
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            border_color=self.colors['border_light'],
            checkmark_color=self.colors['bg']
        ).pack(anchor="w")
    
    def _buildActions(self, parent):
        """Build actions section."""
        # Progress section
        progressFrame = ctk.CTkFrame(
            parent,
            fg_color=self.colors['surface'],
            corner_radius=12,
            border_width=1,
            border_color=self.colors['border']
        )
        progressFrame.pack(fill="x", pady=(0, 16))
        
        progressInner = ctk.CTkFrame(progressFrame, fg_color="transparent")
        progressInner.pack(fill="x", padx=20, pady=16)
        
        # Progress bar
        self.progressBar = ctk.CTkProgressBar(
            progressInner,
            height=6,
            corner_radius=3,
            fg_color=self.colors['border'],
            progress_color=self.colors['primary']
        )
        self.progressBar.pack(fill="x")
        self.progressBar.set(0)
        
        # Status row
        statusRow = ctk.CTkFrame(progressInner, fg_color="transparent")
        statusRow.pack(fill="x", pady=(10, 0))
        
        self.progressLabel = ctk.CTkLabel(
            statusRow,
            text="Ready",
            font=ctk.CTkFont(size=14),
            text_color=self.colors['text_dim']
        )
        self.progressLabel.pack(side="left")
        
        self.timeLabel = ctk.CTkLabel(
            statusRow,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=self.colors['text_muted']
        )
        self.timeLabel.pack(side="right")
        
        # Start button
        self.startBtn = ctk.CTkButton(
            parent,
            text="Start Processing",
            height=48,
            corner_radius=10,
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color=self.colors['success'],
            hover_color=self.colors['success_hover'],
            text_color="#111318",
            command=self._startAutomation
        )
        self.startBtn.pack(fill="x")
    
    def _buildAdvancedPanel(self, parent):
        """Build advanced settings panel."""
        # Section label
        ctk.CTkLabel(
            parent,
            text="ADVANCED",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w", pady=(0, 8))
        
        # Scrollable card
        scroll = ctk.CTkScrollableFrame(
            parent,
            fg_color=self.colors['surface'],
            corner_radius=12,
            border_width=1,
            border_color=self.colors['border']
        )
        scroll.pack(fill="both", expand=True)
        
        # Clipping section (above)
        self._buildClippingSection(scroll)
        
        # Divider
        ctk.CTkFrame(scroll, height=1, fg_color=self.colors['border']).pack(fill="x", padx=16, pady=12)
        
        # Logo sizing section (below with inline scroll)
        self._buildLogoSection(scroll)
    
    def _buildLogoSection(self, parent):
        """Build logo sizing section."""
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", padx=16, pady=(0, 16))
        
        # Header row
        headerRow = ctk.CTkFrame(section, fg_color="transparent")
        headerRow.pack(fill="x")
        
        ctk.CTkLabel(
            headerRow,
            text="Logo Sizing",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.colors['text']
        ).pack(side="left")
        
        ctk.CTkButton(
            headerRow,
            text="Edit All",
            width=60,
            height=26,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            fg_color=self.colors['surface_light'],
            hover_color=self.colors['border'],
            text_color=self.colors['text_dim'],
            command=self._openSizeEditor
        ).pack(side="right")
        
        # Use Excel checkbox
        ctk.CTkCheckBox(
            section,
            text="Use size from Excel column",
            variable=self.useExcelSize,
            font=ctk.CTkFont(size=13),
            text_color=self.colors['text_dim'],
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            border_color=self.colors['border_light'],
            checkmark_color=self.colors['bg']
        ).pack(anchor="w", pady=(12, 0))
        
        # Inline scrollable size list
        self.sizeListFrame = ctk.CTkScrollableFrame(
            section,
            height=180,
            fg_color=self.colors['bg'],
            corner_radius=8,
            border_width=1,
            border_color=self.colors['border']
        )
        self.sizeListFrame.pack(fill="x", pady=(12, 0))
        
        self._populateSizeList()
    
    def _populateSizeList(self):
        """Populate the inline size list."""
        # Clear existing
        for widget in self.sizeListFrame.winfo_children():
            widget.destroy()
        
        for pos, size in sorted(self.logoSizes.items()):
            row = ctk.CTkFrame(self.sizeListFrame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=4)
            
            ctk.CTkLabel(
                row,
                text=pos,
                font=ctk.CTkFont(size=12),
                text_color=self.colors['text_dim'],
                anchor="w"
            ).pack(side="left", fill="x", expand=True)
            
            ctk.CTkLabel(
                row,
                text=f"{size} px",
                font=ctk.CTkFont(size=12),
                text_color=self.colors['text_muted']
            ).pack(side="right")
    
    def _buildClippingSection(self, parent):
        """Build clipping section."""
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", padx=16, pady=(16, 0))
        
        # Header row
        headerRow = ctk.CTkFrame(section, fg_color="transparent")
        headerRow.pack(fill="x")
        
        ctk.CTkLabel(
            headerRow,
            text="Logo Clipping",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors['text']
        ).pack(side="left")
        
        ctk.CTkSwitch(
            headerRow,
            text="",
            width=40,
            height=20,
            variable=self.clippingEnabled,
            command=self._onClippingToggle,
            fg_color=self.colors['border'],
            progress_color=self.colors['primary'],
            button_color=self.colors['text'],
            button_hover_color=self.colors['text_dim']
        ).pack(side="right")
        
        # Description
        ctk.CTkLabel(
            section,
            text="Clips logo parts extending beyond garment edges",
            font=ctk.CTkFont(size=13),
            text_color=self.colors['text_muted'],
            wraplength=320
        ).pack(anchor="w", pady=(8, 0))
        
        # Configure button
        ctk.CTkButton(
            section,
            text="Configure Positions",
            height=34,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            fg_color=self.colors['surface_light'],
            hover_color=self.colors['border'],
            text_color=self.colors['text_dim'],
            command=self._openClippingEditor
        ).pack(fill="x", pady=(12, 0))
    
    def _browseFile(self, fileType, dot, statusLabel):
        """Handle file browsing."""
        if fileType == "excel":
            path = filedialog.askopenfilename(
                title="Select Excel File",
                filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
            )
            if path:
                self.excelPath = path
        elif fileType == "images":
            path = filedialog.askdirectory(title="Select Product Images Folder")
            if path:
                self.imageRoot = path
        elif fileType == "logos":
            path = filedialog.askdirectory(title="Select Logo Assets Folder")
            if path:
                self.logoRoot = path
        else:
            path = None
        
        if path:
            dot.configure(fg_color=self.colors['success'])
            statusLabel.configure(
                text=os.path.basename(path),
                text_color=self.colors['text_dim']
            )
        
        self._updateStatus()
    
    def _updateStatus(self):
        """Update start button state."""
        if self.excelPath and self.imageRoot and self.logoRoot:
            self.startBtn.configure(state="normal")
        else:
            self.startBtn.configure(state="disabled")
    
    def _openSizeEditor(self):
        """Open logo size editor dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Logo Sizes")
        dialog.geometry("480x580")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=self.colors['bg'])
        
        # Center dialog
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 480) // 2
        y = self.winfo_y() + (self.winfo_height() - 580) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Header
        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(24, 16))
        
        ctk.CTkLabel(
            header,
            text="Logo Size Configuration",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            header,
            text="Set logo width in pixels for each position",
            font=ctk.CTkFont(size=13),
            text_color=self.colors['text_muted']
        ).pack(anchor="w", pady=(4, 0))
        
        # Content
        scroll = ctk.CTkScrollableFrame(
            dialog,
            fg_color=self.colors['surface'],
            corner_radius=10,
            border_width=1,
            border_color=self.colors['border']
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        
        entries = {}
        for i, (pos, size) in enumerate(sorted(self.logoSizes.items())):
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=(12 if i == 0 else 6, 6 if i == len(self.logoSizes)-1 else 0))
            
            ctk.CTkLabel(
                row,
                text=pos,
                font=ctk.CTkFont(size=11),
                text_color=self.colors['text_dim'],
                anchor="w"
            ).pack(side="left", fill="x", expand=True)
            
            entry = ctk.CTkEntry(
                row,
                width=60,
                height=28,
                corner_radius=6,
                fg_color=self.colors['bg'],
                border_color=self.colors['border'],
                text_color=self.colors['text']
            )
            entry.insert(0, str(size))
            entry.pack(side="right")
            
            ctk.CTkLabel(
                row,
                text="px",
                font=ctk.CTkFont(size=10),
                text_color=self.colors['text_muted']
            ).pack(side="right", padx=(0, 8))
            
            entries[pos] = entry
        
        def save():
            for pos, entry in entries.items():
                try:
                    self.logoSizes[pos] = int(entry.get())
                    if CONFIG_AVAILABLE:
                        updateLogoSize(pos, int(entry.get()))
                except:
                    pass
            self._populateSizeList()
            dialog.destroy()
        
        ctk.CTkButton(
            dialog,
            text="Save",
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            command=save
        ).pack(fill="x", padx=24, pady=(0, 24))
    
    def _openClippingEditor(self):
        """Open clipping positions editor."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Clipping Positions")
        dialog.geometry("480x580")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=self.colors['bg'])
        
        # Center dialog
        x = self.winfo_x() + (self.winfo_width() - 480) // 2
        y = self.winfo_y() + (self.winfo_height() - 580) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Header
        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(24, 16))
        
        ctk.CTkLabel(
            header,
            text="Clipping Positions",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            header,
            text="Enable clipping for specific positions",
            font=ctk.CTkFont(size=12),
            text_color=self.colors['text_muted']
        ).pack(anchor="w", pady=(4, 0))
        
        # Content
        scroll = ctk.CTkScrollableFrame(
            dialog,
            fg_color=self.colors['surface'],
            corner_radius=10,
            border_width=1,
            border_color=self.colors['border']
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        
        checkVars = {}
        for i, (pos, enabled) in enumerate(sorted(self.clippingPositions.items())):
            var = ctk.BooleanVar(value=enabled)
            checkVars[pos] = var
            
            ctk.CTkCheckBox(
                scroll,
                text=pos,
                variable=var,
                font=ctk.CTkFont(size=11),
                text_color=self.colors['text_dim'],
                fg_color=self.colors['primary'],
                hover_color=self.colors['primary_hover'],
                border_color=self.colors['border_light'],
                checkmark_color=self.colors['bg']
            ).pack(anchor="w", padx=12, pady=(12 if i == 0 else 4, 4))
        
        def save():
            for pos, var in checkVars.items():
                self.clippingPositions[pos] = var.get()
            if CONFIG_AVAILABLE:
                updateClippingConfig(self.clippingEnabled.get(), self.clippingPositions)
            dialog.destroy()
        
        ctk.CTkButton(
            dialog,
            text="Save",
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            command=save
        ).pack(fill="x", padx=24, pady=(0, 24))
    
    def _onClippingToggle(self):
        """Handle clipping toggle."""
        if CONFIG_AVAILABLE:
            updateClippingConfig(self.clippingEnabled.get(), self.clippingPositions)
    
    def _startAutomation(self):
        """Start automation."""
        if self.processing:
            return
        
        if not self.automationCallback:
            messagebox.showerror("Error", "No automation callback configured")
            return
        
        self.processing = True
        self.startBtn.configure(
            text="Processing...",
            state="disabled",
            fg_color=self.colors['text_muted']
        )
        self.progressLabel.configure(text="Starting...")
        self.startTime = time.time()
        self.errorTracker = ErrorTracker()
        
        try:
            canvasHeight = int(self.canvasSize.get())
        except:
            canvasHeight = 1800
        
        settings = {
            'useExcelLogoSize': self.useExcelSize.get(),
            'logoSizes': self.logoSizes.copy(),
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
        """Run automation in thread."""
        success = self.automationCallback(
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
                "Complete",
                "Processing completed successfully.\n\nOutput saved to 'Output/' folder."
            )
        elif success:
            if messagebox.askyesno(
                "Complete with Errors",
                f"Processing completed with {errors} errors.\n\nSave error report?"
            ):
                path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text Files", "*.txt")]
                )
                if path:
                    self.errorTracker.saveReport(path)
        else:
            messagebox.showerror("Error", "Processing failed. Check console for details.")
        
        self.destroy()
    
    def updateProgress(self, current, total):
        """Update progress bar."""
        if total == 0:
            return
        
        progress = current / total
        self.progressBar.set(progress)
        
        self.progressLabel.configure(
            text=f"Processing {current} of {total}"
        )
        
        if current > 0 and self.startTime:
            elapsed = time.time() - self.startTime
            remaining = (elapsed / current) * (total - current)
            
            if remaining < 60:
                timeText = f"{int(remaining)}s left"
            else:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                timeText = f"{mins}m {secs}s left"
            
            self.timeLabel.configure(text=timeText)
        
        self.update()
