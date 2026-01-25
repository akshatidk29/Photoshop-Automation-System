import cv2
import numpy as np
import math
import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from pathlib import Path

CLASS_LABELS = {
    "0":  "FULL_BACK",
    "1":  "FULL_FRONT",

    "2":  "LEFT_BICEP",
    "3":  "RIGHT_BICEP",

    "4":  "LEFT_CHEST",
    "5":  "RIGHT_CHEST",

    "6":  "LEFT_COLLAR",
    "7":  "RIGHT_COLLAR",

    "8":  "LEFT_CUFF",
    "9":  "RIGHT_CUFF",

    "10": "LEFT_HIP",
    "11": "RIGHT_HIP",

    "12": "LEFT_SLEEVE",
    "13": "RIGHT_SLEEVE",

    "14": "LEFT_THIGH_HIGH",
    "15": "RIGHT_THIGH_HIGH",

    "16": "ON_POCKET",

    "17": "BACK_YOKE",

    # Cap-related
    "18": "CAP_BACK",
    "19": "CAP_SIDE",
    "20": "CAP_FRONT",
    "21": "LOWER_LEFT_CROWN",
    "22": "LOWER_RIGHT_CROWN",

    # Towel-related
    "23": "CORNER_ANGLED_TOWEL",
    "24": "FRONT_NAPKIN",

    # Bag-related
    "25": "FRONT_ON_BAG",
    "26": "ON_POCKET_ON_BAG",

    "27": "FRONT_CENTER"
}

MIN_AREA = 200             # ignore tiny boxes
IMAGES_FOLDER = "_Images"      # <-- SET YOUR IMAGES FOLDER
LABELS_FOLDER = "_Annotations"      # <-- SET YOUR LABELS FOLDER
# ==================================================
class OBBAnnotator:
    def __init__(self, root):
        self.root = root
        self.root.title("OBB Annotation Tool - Professional Edition")
        self.root.geometry("1800x1000")
        self.root.configure(bg='#1a1a1a')
        
        # Folder paths
        self.images_folder = IMAGES_FOLDER
        self.labels_folder = LABELS_FOLDER
        
        # Image management
        self.image_files = []
        self.current_image_idx = 0
        self.image_path = None
        self.original_img = None
        self.photo = None
        
        self.scale = 1.0
        self.H = 0
        self.W = 0
        self.image_offset_x = 0
        self.image_offset_y = 0
        
        # State
        self.mode = None
        self.drawing_points = []  # NEW: Store points being drawn
        self.selected_box_idx = None
        self.drag_start = None
        self.resize_edge = None  # Which edge is being resized
        self.auto_save = tk.BooleanVar(value=True)
        
        self.obb_list = []  # List of (corners, class_id) tuples
        self.box_graphics = []
        
        # Global clipboard for copy-paste
        self.clipboard_annotations = None  # Will store: {'boxes': [...], 'source_W': ..., 'source_H': ...}
        
        # Track if current annotations are saved
        self.annotations_modified = False
        
        # Track where current annotations were loaded from (for auto-save)
        self.annotation_source_path = None
        
        # Box creation mode
        self.box_creation_mode = tk.StringVar(value="99x66")
        self.base_scale = 1.0   # fit-to-canvas scale
        self.zoom_factor = 1.0 # user zoom (1.0 = no zoom)
        
        # Custom box drawing state
        self.custom_box_start = None
        
        self.setup_ui()
        
        # Keyboard shortcuts
        self.root.bind('<Left>', lambda e: self.prev_image())
        self.root.bind('<Right>', lambda e: self.next_image())
        self.root.bind('<Delete>', lambda e: self.delete_selected())
        self.root.bind('<Escape>', lambda e: self.cancel_drawing())
        
        # Intercept window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_ui(self):
        # Top toolbar
        self.create_toolbar()
        
        # Main container
        main_container = tk.Frame(self.root, bg='#1a1a1a')
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left sidebar - Image list
        self.create_left_sidebar(main_container)
        
        # Center - Canvas
        self.create_canvas_area(main_container)
        
        # Right sidebar - Controls
        self.create_right_sidebar(main_container)
        
        # Bottom status bar
        self.create_status_bar()
        
    def create_toolbar(self):
        toolbar = tk.Frame(self.root, bg='#2d2d2d', height=60, relief=tk.RAISED, bd=2)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # Title
        title = tk.Label(toolbar, text="🎯 OBB Annotator Pro", font=('Arial', 16, 'bold'),
                        bg='#2d2d2d', fg='#00ff88')
        title.pack(side=tk.LEFT, padx=20, pady=10)
        
        # Folder buttons
        btn_frame = tk.Frame(toolbar, bg='#2d2d2d')
        btn_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Button(btn_frame, text="📁 Select Images Folder", command=self.select_images_folder,
                 bg='#4a90e2', fg='white', font=('Arial', 10, 'bold'),
                 relief=tk.FLAT, padx=15, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="📂 Select Labels Folder", command=self.select_labels_folder,
                 bg='#e24a90', fg='white', font=('Arial', 10, 'bold'),
                 relief=tk.FLAT, padx=15, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        # Auto-save checkbox (kept for compatibility but not used for manual save)
        tk.Checkbutton(toolbar, text="Auto-save", variable=self.auto_save,
                      bg='#2d2d2d', fg='white', selectcolor='#1a1a1a',
                      font=('Arial', 10), activebackground='#2d2d2d').pack(side=tk.RIGHT, padx=20)
        
    def create_left_sidebar(self, parent):
        left_frame = tk.Frame(parent, width=320, bg='#252525')
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.pack_propagate(False)
        
        # Header
        header = tk.Label(left_frame, text="📂 Image List", font=('Arial', 13, 'bold'),
                         bg='#252525', fg='white', pady=10)
        header.pack(fill=tk.X)
        
        # Progress info
        self.progress_label = tk.Label(left_frame, text="No images loaded", 
                                       bg='#252525', fg='#888888', font=('Arial', 9))
        self.progress_label.pack(fill=tk.X, padx=10, pady=5)
        
        # Search box
        search_frame = tk.Frame(left_frame, bg='#252525')
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(search_frame, text="🔍", bg='#252525', fg='white').pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_image_list)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, 
                               bg='#1a1a1a', fg='white', relief=tk.FLAT, font=('Arial', 9))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Image listbox
        list_frame = tk.Frame(left_frame, bg='#252525')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.image_listbox = tk.Listbox(list_frame, bg='#1a1a1a', fg='white',
                                       font=('Courier', 9), selectmode=tk.SINGLE,
                                       yscrollcommand=scrollbar.set, relief=tk.FLAT,
                                       selectbackground='#4a90e2', activestyle='none')
        self.image_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.image_listbox.yview)
        self.image_listbox.bind('<<ListboxSelect>>', self.on_image_select)
        
        # Navigation buttons
        nav_frame = tk.Frame(left_frame, bg='#252525')
        nav_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(nav_frame, text="⬅ Previous", command=self.prev_image,
                 bg='#666666', fg='white', font=('Arial', 9, 'bold'),
                 relief=tk.FLAT, pady=8, cursor='hand2').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        tk.Button(nav_frame, text="Next ➡", command=self.next_image,
                 bg='#666666', fg='white', font=('Arial', 9, 'bold'),
                 relief=tk.FLAT, pady=8, cursor='hand2').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
    def create_canvas_area(self, parent):
        center_frame = tk.Frame(parent, bg='#1a1a1a')
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ─── Image info bar ─────────────────────────────────────────────
        info_bar = tk.Frame(center_frame, bg='#2d2d2d', height=40)
        info_bar.pack(fill=tk.X, pady=(0, 5))

        self.image_info_label = tk.Label(
            info_bar,
            text="No image loaded",
            bg='#2d2d2d',
            fg='white',
            font=('Arial', 11, 'bold')
        )
        self.image_info_label.pack(side=tk.LEFT, padx=15, pady=8)

        # ─── Canvas + Scrollbars container ──────────────────────────────
        canvas_frame = tk.Frame(center_frame, bg='#1a1a1a')
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        self.v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        self.h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)

        # Canvas
        self.canvas = tk.Canvas(
            canvas_frame,
            bg='#2d2d2d',
            highlightthickness=0,
            cursor='crosshair',
            yscrollcommand=self.v_scroll.set,
            xscrollcommand=self.h_scroll.set
        )

        # Attach scrollbars to canvas
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)

        # Layout
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ─── Mouse bindings ─────────────────────────────────────────────
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        # Scroll / Zoom
        self.canvas.bind("<MouseWheel>", self.on_zoom)   # Windows
        self.canvas.bind("<Button-4>", self.on_zoom)     # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_zoom)     # Linux scroll down

        # ─── Help overlay ───────────────────────────────────────────────
        help_frame = tk.Frame(center_frame, bg='#1a1a1a')
        help_frame.pack(fill=tk.X, pady=(5, 0))

        help_text = (
            "💡 Scroll: Move | Shift+Scroll: Horizontal | Ctrl+Scroll: Zoom | "
            "Click: Create | Drag: Move | Edges: Resize | Corners: Rotate | "
            "Double-click: Delete | ESC: Cancel | ⬅➡: Navigate"
        )

        tk.Label(
            help_frame,
            text=help_text,
            bg='#1a1a1a',
            fg='#888888',
            font=('Arial', 9, 'italic')
        ).pack(pady=5)

        
    def create_right_sidebar(self, parent):
        right_frame = tk.Frame(parent, width=350, bg='#252525')
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_frame.pack_propagate(False)
        
        # Box creation mode selector
        mode_frame = tk.LabelFrame(right_frame, text="📐 Box Creation Mode", bg='#252525',
                                   fg='white', font=('Arial', 11, 'bold'), bd=2)
        mode_frame.pack(fill=tk.X, padx=10, pady=10)
        
        modes = [
            ("99 × 66", "99x66"),
            ("66 × 66", "66x66"),
            ("180 × 120", "180x120"),
            ("300 × 200", "300x200"),
            ("Custom (Click & Drag)", "custom")
        ]
        
        for text, value in modes:
            tk.Radiobutton(mode_frame, text=text, variable=self.box_creation_mode,
                          value=value, bg='#252525', fg='white', selectcolor='#1a1a1a',
                          font=('Arial', 10), activebackground='#252525',
                          cursor='hand2').pack(anchor='w', padx=15, pady=3)
        
        # Current box info
        info_frame = tk.LabelFrame(right_frame, text="📊 Current Selection", bg='#252525',
                                   fg='white', font=('Arial', 11, 'bold'), bd=2)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.info_text = tk.Text(info_frame, height=6, bg='#1a1a1a', fg='#00ff88',
                                font=('Courier', 9), relief=tk.FLAT, wrap=tk.WORD)
        self.info_text.pack(fill=tk.X, padx=8, pady=8)
        self.update_info_display()
        
        # Quick actions
        action_frame = tk.LabelFrame(right_frame, text="⚡ Quick Actions", bg='#252525',
                                     fg='white', font=('Arial', 11, 'bold'), bd=2)
        action_frame.pack(fill=tk.X, padx=10, pady=10)
        
        btn_config = {'font': ('Arial', 9, 'bold'), 'relief': tk.FLAT, 'pady': 5, 'cursor': 'hand2'}
        
        # Copy/Paste buttons
        tk.Button(action_frame, text="📋 Copy", command=self.copy_current_annotations,
                 bg='#6f42c1', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=1)
        
        tk.Button(action_frame, text="📥 Paste", command=self.paste_annotations,
                 bg='#20c997', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=1)
        
        tk.Button(action_frame, text="📋 Copy Previous", command=self.copy_from_previous,
                 bg='#17a2b8', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=1)
        
        # Duplicate button
        tk.Button(action_frame, text="📑 Duplicate", command=self.duplicate_selected,
                 bg='#fd7e14', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=1)
        
        # Category buttons (Add to garment / towel / cap / bag)
        tk.Button(action_frame, text="➕ Garment", command=self.add_to_garment,
                bg='#8e44ad', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=1)

        tk.Button(action_frame, text="➕ Towel", command=self.add_to_towel,
                bg='#f39c12', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=1)

        tk.Button(action_frame, text="➕ Cap", command=self.add_to_cap,
                bg='#3498db', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=1)

        tk.Button(action_frame, text="➕ Bag", command=self.add_to_bag,
                bg='#27ae60', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=1)

        tk.Button(action_frame, text="🗑 Delete", command=self.delete_selected,
                 bg='#dc3545', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=1)
        
        tk.Button(action_frame, text="🧹 Clear All", command=self.clear_all,
                 bg='#6c757d', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=1)
        
        # Annotations list
        list_frame = tk.LabelFrame(right_frame, text="📋 Annotations (0)", bg='#252525',
                                  fg='white', font=('Arial', 11, 'bold'), bd=2)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.list_frame = list_frame
        
        list_scroll = ttk.Scrollbar(list_frame)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4))
        
        self.annotations_listbox = tk.Listbox(list_frame, bg='#1a1a1a', fg='white',
                                             font=('Courier', 9), selectmode=tk.SINGLE,
                                             yscrollcommand=list_scroll.set, relief=tk.FLAT,
                                             selectbackground='#4a90e2', activestyle='none')
        self.annotations_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        list_scroll.config(command=self.annotations_listbox.yview)
        self.annotations_listbox.bind('<<ListboxSelect>>', self.on_list_select)
        
        # Stats
        stats_frame = tk.Frame(right_frame, bg='#252525')
        stats_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.stats_label = tk.Label(stats_frame, text="📊 Session: 0 images | 0 boxes", 
                                    bg='#252525', fg='#888888', font=('Arial', 9))
        self.stats_label.pack()
    def format_image_list_item(self, img_name, max_len=38):
        """Ensure status icon is always visible by truncating long names"""
        if len(img_name) > max_len:
            return img_name[:max_len - 3] + "..."
        return img_name

    def create_status_bar(self):
        status_frame = tk.Frame(self.root, bg='#2d2d2d', height=30)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_var = tk.StringVar(value="Ready. Select folders to begin.")
        status_label = tk.Label(status_frame, textvariable=self.status_var, bd=1,
                              anchor=tk.W, bg='#2d2d2d', fg='#00ff88', font=('Arial', 10), padx=15)
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Coordinates display
        self.coords_var = tk.StringVar(value="")
        coords_label = tk.Label(status_frame, textvariable=self.coords_var,
                               bg='#2d2d2d', fg='#ffaa00', font=('Courier', 9), padx=15)
        coords_label.pack(side=tk.RIGHT)
        
    def select_images_folder(self):
        folder = filedialog.askdirectory(title="Select Images Folder")
        if folder:
            self.images_folder = folder
            self.load_image_list()
            
    def select_labels_folder(self):
        folder = filedialog.askdirectory(title="Select Labels Output Folder")
        if folder:
            self.labels_folder = folder
            # Create folder if it doesn't exist
            Path(self.labels_folder).mkdir(parents=True, exist_ok=True)
            self.status_var.set(f"Labels will be saved to: {self.labels_folder}")
    
    def show_class_selection_dialog(self):
        """Show dialog to select class for the newly drawn box"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Class")
        dialog.configure(bg='#2b2b2b')
        dialog.transient(self.root)
        dialog.grab_set()
        
        selected_class = tk.StringVar(value=list(CLASS_LABELS.keys())[0])
        
        # Title
        tk.Label(dialog, text="Select Class for Box", font=('Arial', 14, 'bold'),
                bg='#2b2b2b', fg='white', pady=15).pack()
        
        # Class selection frame with grid layout
        classes_frame = tk.Frame(dialog, bg='#1a1a1a', bd=2, relief=tk.SUNKEN)
        classes_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Calculate grid dimensions (aim for 6 items per column)
        items_per_column = 6
        total_items = len(CLASS_LABELS)
        num_columns = (total_items + items_per_column - 1) // items_per_column
        
        # Add radio buttons in grid layout
        class_items = list(CLASS_LABELS.items())
        for idx, (class_id, class_name) in enumerate(class_items):
            col = idx // items_per_column
            row = idx % items_per_column
            
            rb = tk.Radiobutton(
                classes_frame,
                text=f"{class_id}: {class_name}",
                variable=selected_class,
                value=class_id,
                bg='#1a1a1a',
                fg='white',
                selectcolor='#2b2b2b',
                activebackground='#1a1a1a',
                activeforeground='white',
                font=('Arial', 10),
                pady=4,
                padx=10,
                anchor='w',
                cursor='hand2'
            )
            rb.grid(row=row, column=col, sticky='w', padx=5, pady=2)
        
        # Buttons frame
        btn_frame = tk.Frame(dialog, bg='#2b2b2b')
        btn_frame.pack(fill=tk.X, padx=20, pady=15)
        
        result = {'confirmed': False, 'class_id': None}
        
        def confirm():
            result['confirmed'] = True
            result['class_id'] = selected_class.get()
            dialog.destroy()
        
        def cancel():
            result['confirmed'] = False
            dialog.destroy()
        
        tk.Button(btn_frame, text="✓ Confirm", command=confirm,
                 bg='#28a745', fg='white', font=('Arial', 11, 'bold'),
                 relief=tk.FLAT, padx=30, pady=10, cursor='hand2').pack(side=tk.LEFT, expand=True, padx=5)
        
        tk.Button(btn_frame, text="✗ Cancel", command=cancel,
                 bg='#dc3545', fg='white', font=('Arial', 11, 'bold'),
                 relief=tk.FLAT, padx=30, pady=10, cursor='hand2').pack(side=tk.RIGHT, expand=True, padx=5)
        
        # Keyboard shortcuts
        dialog.bind('<Return>', lambda e: confirm())
        dialog.bind('<Escape>', lambda e: cancel())
        
        # Update and center the dialog after packing all widgets
        dialog.update_idletasks()
        
        # Get screen dimensions
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        
        # Get dialog dimensions
        dialog_width = dialog.winfo_reqwidth() + 100  # Add padding for multiple columns
        dialog_height = dialog.winfo_reqheight()
        
        # Ensure good proportions
        dialog_width = max(dialog_width, 900)  # Wider for multiple columns
        
        # Make sure dialog fits on screen
        if dialog_height > screen_height - 100:
            dialog_height = screen_height - 100
        
        # Center on parent window
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog_width) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog_height) // 2
        
        # Make sure dialog is on screen
        x = max(0, min(x, screen_width - dialog_width))
        y = max(0, min(y, screen_height - dialog_height))
        
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        # Wait for dialog to close
        self.root.wait_window(dialog)
        
        return result
    
    def copy_current_annotations(self):
        """Copy annotations from the current image to clipboard"""
        if self.original_img is None:
            messagebox.showinfo("Info", "No image loaded")
            return
        
        if not self.obb_list:
            messagebox.showinfo("Info", "No annotations to copy from current image")
            return
        
        # Store current annotations in clipboard with current image dimensions
        self.clipboard_annotations = {
            'boxes': [(list(corners), class_id) for corners, class_id in self.obb_list],
            'source_W': self.W,
            'source_H': self.H
        }
        
        self.status_var.set(f"✓ Copied {len(self.obb_list)} annotations to clipboard")
    
    def paste_annotations(self):
        """Paste copied annotations to current image"""
        if self.clipboard_annotations is None:
            messagebox.showinfo("Info", "No annotations copied. Use 'Copy From File' first.")
            return
        
        if self.original_img is None:
            messagebox.showerror("Error", "No image loaded")
            return
        
        # Get clipboard data
        source_boxes = self.clipboard_annotations['boxes']
        source_W = self.clipboard_annotations['source_W']
        source_H = self.clipboard_annotations['source_H']
        
        # Calculate scale factors
        sx = self.W / source_W
        sy = self.H / source_H
        
        # Clear current annotations
        self.obb_list.clear()
        self.selected_box_idx = None
        
        # Scale and add boxes
        for corners, class_id in source_boxes:
            scaled_corners = [(x * sx, y * sy) for x, y in corners]
            self.obb_list.append((scaled_corners, class_id))
        
        # Mark as modified
        self.annotations_modified = True
        
        # Update UI
        self.redraw_all_boxes()
        self.update_annotations_list()
        self.update_info_display()
        self.status_var.set(f"✓ Pasted {len(self.obb_list)} annotations")
    
    def duplicate_selected(self):
        """Duplicate the selected box (or last box if none selected) with a small offset"""
        # If nothing selected, select the last box
        if self.selected_box_idx is None or self.selected_box_idx >= len(self.obb_list):
            if not self.obb_list:
                messagebox.showinfo("Info", "No boxes to duplicate")
                return
            # Auto-select last box
            self.selected_box_idx = len(self.obb_list) - 1
        
        corners, class_id = self.obb_list[self.selected_box_idx]
        
        # Offset by 10 pixels
        offset_corners = [(x + 10, y + 10) for x, y in corners]
        
        # Add new box
        self.obb_list.append((offset_corners, class_id))
        
        # Mark as modified
        self.annotations_modified = True
        
        # Select the new box
        self.selected_box_idx = len(self.obb_list) - 1
        
        # Update UI
        self.redraw_all_boxes()
        self.update_annotations_list()
        self.update_info_display()
        self.status_var.set(f"✓ Box duplicated! Total: {len(self.obb_list)}")
    
    def copy_from_previous(self):
        """Copy annotations from the previous image and scale to current image size"""

        if self.current_image_idx <= 0:
            messagebox.showinfo("Info", "This is the first image. Nothing to copy.")
            return

        prev_image_path = self.image_files[self.current_image_idx - 1]
        prev_img = cv2.imread(str(prev_image_path))
        if prev_img is None:
            messagebox.showerror("Error", "Failed to load previous image.")
            return

        prev_H, prev_W = prev_img.shape[:2]
        stem = prev_image_path.stem

        # 🔍 Find annotation file (main or categorized)
        label_file = Path(self.labels_folder) / f"{stem}.txt"

        if not label_file.exists():
            categorized_dir = Path(self.labels_folder) / "categorized"
            if categorized_dir.exists():
                for category_folder in categorized_dir.iterdir():
                    if category_folder.is_dir():
                        candidate = category_folder / f"{stem}.txt"
                        if candidate.exists():
                            label_file = candidate
                            break

        if not label_file.exists():
            messagebox.showinfo("Info", "Previous image has no annotations.")
            return

        # 🧹 Clear current annotations
        self.obb_list.clear()
        self.selected_box_idx = None

        try:
            with open(label_file, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) != 9:
                        continue

                    class_id = parts[0]
                    coords = list(map(float, parts[1:]))

                    # Denormalize using previous image size
                    prev_corners = [
                        (coords[0] * prev_W, coords[1] * prev_H),
                        (coords[2] * prev_W, coords[3] * prev_H),
                        (coords[4] * prev_W, coords[5] * prev_H),
                        (coords[6] * prev_W, coords[7] * prev_H),
                    ]

                    # Scale to current image
                    sx = self.W / prev_W
                    sy = self.H / prev_H
                    curr_corners = [(x * sx, y * sy) for x, y in prev_corners]

                    self.obb_list.append((curr_corners, class_id))

            self.annotations_modified = True

            self.redraw_all_boxes()
            self.update_annotations_list()
            self.update_info_display()
            self.status_var.set(f"✓ Copied {len(self.obb_list)} boxes from previous image")

        except Exception as e:
            messagebox.showerror("Error", f"Copy failed:\n{e}")
    def on_zoom(self, event):
        if self.original_img is None:
            return

        # Check CTRL key
        if not (event.state & 0x0004):
            # Normal scroll (no zoom)
            if event.delta:
                self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return

        # CTRL + Scroll → Zoom
        zoom = 1.1 if event.delta > 0 else 0.9
        new_zoom = self.zoom_factor * zoom

        if not (0.2 <= new_zoom <= 5.0):
            return

        self.zoom_factor = new_zoom

        # Re-render image (center-based zoom)
        self.display_image()

        self.status_var.set(f"🔍 Zoom: {self.zoom_factor:.2f}x")



    def check_annotation_exists(self, stem):
        """Check if annotation exists for given stem in main or any category folder"""
        if not self.labels_folder:
            return False
        
        # Check main labels folder
        main_label = Path(self.labels_folder) / f"{stem}.txt"
        if main_label.exists():
            return True
        
        # Check categorized folders
        categorized_dir = Path(self.labels_folder) / "categorized"
        if categorized_dir.exists():
            for category_folder in categorized_dir.iterdir():
                if category_folder.is_dir():
                    category_label = category_folder / f"{stem}.txt"
                    if category_label.exists():
                        return True
        
        return False
    
    def auto_save_to_original_location(self):
        """Auto-save annotations back to their original source location"""
        if not self.annotation_source_path:
            return False
        
        try:
            # Write annotations to the same file they were loaded from
            ok, err = self._write_annotations_to_path(self.annotation_source_path)
            if ok:
                self.annotations_modified = False
                self.status_var.set(f"✓ Auto-saved to {self.annotation_source_path.parent.name}")
                return True
            else:
                self.status_var.set(f"Error auto-saving: {err}")
                return False
        except Exception as e:
            self.status_var.set(f"Error auto-saving: {e}")
            return False
    
    def check_if_saved_anywhere(self):
        """Check if current image has annotations saved in main or any categorized folder"""
        if not self.image_path:
            return False
        
        stem = Path(self.image_path).stem
        return self.check_annotation_exists(stem)
    
    def prompt_category_selection(self):
        """Show modal dialog forcing user to select a category"""
        dialog = tk.Toplevel(self.root)
        dialog.title("⚠ Save Required")
        dialog.configure(bg='#2b2b2b')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Make dialog modal - user cannot dismiss it
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Warning message
        tk.Label(dialog, text="⚠ Unsaved Annotations Detected", 
                font=('Arial', 16, 'bold'), bg='#2b2b2b', fg='#ff6b6b', pady=20).pack()
        
        tk.Label(dialog, text="You must save annotations to a category before continuing.",
                font=('Arial', 12), bg='#2b2b2b', fg='white', pady=10).pack()
        
        tk.Label(dialog, text=f"Current image: {Path(self.image_path).name}",
                font=('Arial', 10), bg='#2b2b2b', fg='#888888', pady=5).pack()
        
        tk.Label(dialog, text=f"Annotations: {len(self.obb_list)} boxes",
                font=('Arial', 10), bg='#2b2b2b', fg='#888888', pady=5).pack()
        
        # Category buttons
        btn_frame = tk.Frame(dialog, bg='#2b2b2b')
        btn_frame.pack(fill=tk.X, padx=30, pady=30)
        
        result = {'category': None}
        
        def select_category(cat):
            result['category'] = cat
            dialog.destroy()
        
        categories = [
            ("➕ Add to garment", "garment", '#8e44ad'),
            ("➕ Add to towel", "towel", '#f39c12'),
            ("➕ Add to cap", "cap", '#3498db'),
            ("➕ Add to bag", "bag", '#27ae60')
        ]
        
        for text, cat, color in categories:
            tk.Button(btn_frame, text=text, command=lambda c=cat: select_category(c),
                     bg=color, fg='white', font=('Arial', 12, 'bold'),
                     relief=tk.FLAT, pady=15, cursor='hand2').pack(fill=tk.X, pady=5)
        
        # Center dialog
        dialog.update_idletasks()
        dialog_width = 500
        dialog_height = dialog.winfo_reqheight()
        
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog_width) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog_height) // 2
        
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        # Wait for selection
        self.root.wait_window(dialog)
        
        return result['category']
    
    def check_and_save_before_navigation(self):
        """Check if annotations need to be saved before navigation"""
        # If no annotations, just proceed
        if not self.obb_list:
            return True
        
        # If annotations not modified, proceed
        if not self.annotations_modified:
            return True
        
        # If annotations were loaded from a file and modified, auto-save back to that location
        if self.annotation_source_path:
            return self.auto_save_to_original_location()
        
        # If annotations are new (never saved before), prompt for category
        if not self.check_if_saved_anywhere():
            category = self.prompt_category_selection()
            if category:
                self.save_to_category(category)
                self.annotations_modified = False
                return True
            else:
                # User didn't select (shouldn't happen with modal dialog)
                return False
        
        return True
        
    def prev_image(self):
        """Navigate to previous image"""
        if not self.check_and_save_before_navigation():
            return
        
        if self.image_files and self.current_image_idx > 0:
            self.load_image(self.current_image_idx - 1)
        
    def next_image(self):
        """Navigate to next image"""
        if not self.check_and_save_before_navigation():
            return
        
        if self.image_files and self.current_image_idx < len(self.image_files) - 1:
            self.load_image(self.current_image_idx + 1)
    
    def on_image_select(self, event):
        """Handle image selection from list"""
        # First, capture the selection before any dialogs might clear it
        selection = self.image_listbox.curselection()
        if not selection:
            return
        
        # Store the selected listbox index and get the display name
        listbox_idx = selection[0]
        selected_display = self.image_listbox.get(listbox_idx)[2:]  # Remove status symbol (e.g., "✓ " or "○ ")
        
        # Find the matching image file index BEFORE navigation check
        # This handles both filtered and unfiltered lists, and truncated names
        target_idx = None
        search_term = self.search_var.get().lower()
        
        if not search_term:
            # No filter active - listbox index matches image_files index directly
            target_idx = listbox_idx
        else:
            # Filter is active - need to find the actual index by matching names
            filtered_idx = 0
            for idx, img_file in enumerate(self.image_files):
                if search_term in img_file.name.lower():
                    if filtered_idx == listbox_idx:
                        target_idx = idx
                        break
                    filtered_idx += 1
        
        # Fallback: match by name (handles truncated names with startswith)
        if target_idx is None:
            for idx, img_file in enumerate(self.image_files):
                display_name = self.format_image_list_item(img_file.name)
                if display_name == selected_display or img_file.name == selected_display:
                    target_idx = idx
                    break
        
        if target_idx is None:
            return
        
        # Don't reload if already on the same image
        if target_idx == self.current_image_idx:
            return
        
        # Now do the navigation check (which may show dialogs)
        if not self.check_and_save_before_navigation():
            # Reset selection to current image
            self.image_listbox.selection_clear(0, tk.END)
            self.image_listbox.selection_set(self.current_image_idx)
            return
        
        # Load the target image
        self.load_image(target_idx)
    
    def on_closing(self):
        """Handle window close event"""
        if self.obb_list and self.annotations_modified:
            # If loaded from existing file, auto-save
            if self.annotation_source_path:
                self.auto_save_to_original_location()
            # If new annotations, prompt for category
            elif not self.check_if_saved_anywhere():
                category = self.prompt_category_selection()
                if category:
                    self.save_to_category(category)
        
        self.root.destroy()
        
    def update_progress(self):
        """Update progress label"""
        if self.image_files:
            total = len(self.image_files)
            current = self.current_image_idx + 1
            
            # Count annotated (check both main and category folders)
            annotated = sum(1 for f in self.image_files 
                          if self.check_annotation_exists(f.stem))
            
            self.progress_label.config(
                text=f"Image {current}/{total} | Annotated: {annotated}/{total} ({annotated*100//total}%)"
            )
            
            # Update session stats
            self.stats_label.config(text=f"📊 Session: {annotated} images | ~{annotated}+ boxes")
        
    def display_image(self):
        if self.original_img is None:
            return
        
        self.canvas.update()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        scale_w = (canvas_width - 100) / self.W
        scale_h = (canvas_height - 100) / self.H
        self.base_scale = min(scale_w, scale_h, 1.0)
        self.scale = self.base_scale * self.zoom_factor

        
        new_w = int(self.W * self.scale)
        new_h = int(self.H * self.scale)
        
        self.image_offset_x = (canvas_width - new_w) // 2
        self.image_offset_y = (canvas_height - new_h) // 2
        
        img_rgb = cv2.cvtColor(self.original_img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        pil_img = Image.fromarray(img_resized)
        self.photo = ImageTk.PhotoImage(pil_img)
        
        self.canvas.delete("all")
        self.canvas.create_image(self.image_offset_x, self.image_offset_y, 
                                anchor=tk.NW, image=self.photo, tags='image')
        self.canvas.config(
                scrollregion=(
                    self.image_offset_x,
                    self.image_offset_y,
                    self.image_offset_x + new_w,
                    self.image_offset_y + new_h
                )
            )

        self.redraw_all_boxes()
        self.update_info_display()
        
    def canvas_to_image(self, cx, cy):
        x = (cx - self.image_offset_x) / self.scale
        y = (cy - self.image_offset_y) / self.scale
        return x, y
    
    def image_to_canvas(self, x, y):
        cx = x * self.scale + self.image_offset_x
        cy = y * self.scale + self.image_offset_y
        return cx, cy
    
    def cancel_drawing(self):
        """Cancel current drawing operation"""
        if self.mode == 'drawing_custom':
            self.custom_box_start = None
            self.canvas.delete('temp')
            self.mode = None
            self.status_var.set("Drawing cancelled")
    
    def create_preset_box(self, center_x, center_y, width, height):
        """Create a preset-sized box centered at the given point"""
        half_w = width / 2
        half_h = height / 2
        
        corners = [
            (center_x - half_w, center_y - half_h),  # Top-left
            (center_x + half_w, center_y - half_h),  # Top-right
            (center_x + half_w, center_y + half_h),  # Bottom-right
            (center_x - half_w, center_y + half_h),  # Bottom-left
        ]
        
        return corners
    
    def on_mouse_down(self, event):
        if self.original_img is None:
            return
        
        img_x, img_y = self.canvas_to_image(event.x, event.y)
        
        # Check for existing interactions first
        clicked_handle = self.get_rotation_handle_at_point(event.x, event.y)
        clicked_edge = self.get_resize_edge_at_point(event.x, event.y)
        clicked_box = self.get_box_at_point(event.x, event.y)

        
        if clicked_handle is not None:
            self.mode = 'rotating'
            self.selected_box_idx = clicked_handle
            self.drag_start = (event.x, event.y)
            self.highlight_box(self.selected_box_idx)
            self.status_var.set(f"🔄 Rotating box #{self.selected_box_idx + 1}")
        elif clicked_edge is not None:
            self.mode = 'resizing'
            self.selected_box_idx = clicked_edge[0]
            self.resize_edge = clicked_edge[1]
            self.drag_start = (event.x, event.y)
            self.highlight_box(self.selected_box_idx)
            self.status_var.set(f"↔️ Resizing box #{self.selected_box_idx + 1}")
        elif clicked_box is not None:
            self.mode = 'moving'
            self.selected_box_idx = clicked_box
            self.drag_start = (event.x, event.y)
            self.highlight_box(self.selected_box_idx)
            self.status_var.set(f"📦 Moving box #{self.selected_box_idx + 1}")
        else:
            # Create new box based on mode
            mode = self.box_creation_mode.get()
            
            if mode == "custom":
                # Start custom box drawing
                self.mode = 'drawing_custom'
                self.custom_box_start = (img_x, img_y)
                self.selected_box_idx = None
                self.status_var.set("Click and drag to create custom box")
            else:
                # Create preset box
                if mode == "99x66":
                    width, height = 99, 66
                elif mode == "66x66":
                    width, height = 66, 66
                elif mode == "180x120":
                    width, height = 180, 120
                elif mode == "300x200":
                    width, height = 300, 200
                else:
                    return
                
                # Create box centered at click
                corners = self.create_preset_box(img_x, img_y, width, height)
                
                # Show class selection dialog
                result = self.show_class_selection_dialog()
                
                if result['confirmed']:
                    self.obb_list.append((corners, result['class_id']))
                    self.annotations_modified = True
                    self.redraw_all_boxes()
                    self.update_annotations_list()
                    class_name = CLASS_LABELS.get(result['class_id'], result['class_id'])
                    self.status_var.set(f"✓ Box #{len(self.obb_list)} created ({class_name})! Total: {len(self.obb_list)}")
                else:
                    self.status_var.set("Box creation cancelled")
    
    def on_mouse_drag(self, event):
        # Update coordinates display
        img_x, img_y = self.canvas_to_image(event.x, event.y)
        self.coords_var.set(f"X: {int(img_x)} Y: {int(img_y)}")
        
        if self.mode == 'drawing_custom' and self.custom_box_start:
            # Draw preview rectangle
            self.canvas.delete('temp')
            
            start_x, start_y = self.custom_box_start
            canvas_start = self.image_to_canvas(start_x, start_y)
            
            self.canvas.create_rectangle(
                canvas_start[0], canvas_start[1], event.x, event.y,
                outline='#00ff00', width=2, tags='temp'
            )
            return
            
        if self.mode == 'moving' and self.selected_box_idx is not None:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            self.drag_start = (event.x, event.y)
            
            corners, class_id = self.obb_list[self.selected_box_idx]
            dx_img, dy_img = dx / self.scale, dy / self.scale
            new_corners = [(x + dx_img, y + dy_img) for x, y in corners]
            self.obb_list[self.selected_box_idx] = (new_corners, class_id)
            
            self.annotations_modified = True
            self.redraw_box(self.selected_box_idx)
            self.update_info_display()
            
        elif self.mode == 'resizing' and self.selected_box_idx is not None:
            # Resize while maintaining aspect ratio
            corners, class_id = self.obb_list[self.selected_box_idx]
            
            # Calculate center of the box
            cx = sum(x for x, y in corners) / 4
            cy = sum(y for x, y in corners) / 4
            
            # Get current mouse position in image coordinates
            curr_x, curr_y = self.canvas_to_image(event.x, event.y)
            
            # Calculate vector from center to mouse
            dx_from_center = curr_x - cx
            dy_from_center = curr_y - cy
            
            # Calculate current distance from center (diagonal)
            current_dist = math.sqrt(dx_from_center**2 + dy_from_center**2)
            
            # Calculate original distance from center to any corner
            orig_dx = corners[0][0] - cx
            orig_dy = corners[0][1] - cy
            orig_dist = math.sqrt(orig_dx**2 + orig_dy**2)
            
            # Calculate scale factor
            if orig_dist > 0:
                scale_factor = current_dist / orig_dist
            else:
                scale_factor = 1.0
            
            # Apply scale to all corners while maintaining aspect ratio
            new_corners = []
            for x, y in corners:
                # Vector from center to corner
                vx = x - cx
                vy = y - cy
                # Scale the vector
                new_x = cx + vx * scale_factor
                new_y = cy + vy * scale_factor
                new_corners.append((new_x, new_y))
            
            self.obb_list[self.selected_box_idx] = (new_corners, class_id)
            self.drag_start = (event.x, event.y)
            
            self.annotations_modified = True
            self.redraw_box(self.selected_box_idx)
            self.update_info_display()
            
        elif self.mode == 'rotating' and self.selected_box_idx is not None:
            corners, class_id = self.obb_list[self.selected_box_idx]
            
            cx = sum(x for x, y in corners) / 4
            cy = sum(y for x, y in corners) / 4
            cx_canvas, cy_canvas = self.image_to_canvas(cx, cy)
            
            old_x, old_y = self.drag_start
            old_angle = math.atan2(old_y - cy_canvas, old_x - cx_canvas)
            new_angle = math.atan2(event.y - cy_canvas, event.x - cx_canvas)
            angle_diff = new_angle - old_angle
            
            cos_a = math.cos(angle_diff)
            sin_a = math.sin(angle_diff)
            
            new_corners = []
            for x, y in corners:
                tx = x - cx
                ty = y - cy
                rx = tx * cos_a - ty * sin_a
                ry = tx * sin_a + ty * cos_a
                new_corners.append((rx + cx, ry + cy))
            
            self.obb_list[self.selected_box_idx] = (new_corners, class_id)
            self.drag_start = (event.x, event.y)
            
            self.annotations_modified = True
            self.redraw_box(self.selected_box_idx)
            self.update_info_display()
    
    def on_mouse_up(self, event):
        if self.mode == 'drawing_custom' and self.custom_box_start:
            # Complete custom box
            img_x, img_y = self.canvas_to_image(event.x, event.y)
            start_x, start_y = self.custom_box_start
            
            # Calculate box dimensions
            min_x = min(start_x, img_x)
            max_x = max(start_x, img_x)
            min_y = min(start_y, img_y)
            max_y = max(start_y, img_y)
            
            width = max_x - min_x
            height = max_y - min_y
            
            # Check minimum area
            if width * height < MIN_AREA:
                self.status_var.set(f"⚠ Box too small (min {MIN_AREA}px²)")
                self.canvas.delete('temp')
                self.custom_box_start = None
                self.mode = None
                return
            
            # Create corners (axis-aligned)
            corners = [
                (min_x, min_y),  # Top-left
                (max_x, min_y),  # Top-right
                (max_x, max_y),  # Bottom-right
                (min_x, max_y),  # Bottom-left
            ]
            
            # Show class selection dialog
            result = self.show_class_selection_dialog()
            
            if result['confirmed']:
                self.obb_list.append((corners, result['class_id']))
                self.annotations_modified = True
                self.redraw_all_boxes()
                self.update_annotations_list()
                class_name = CLASS_LABELS.get(result['class_id'], result['class_id'])
                self.status_var.set(f"✓ Box #{len(self.obb_list)} created ({class_name})! Total: {len(self.obb_list)}")
            else:
                self.status_var.set("Box creation cancelled")
            
            # Clean up
            self.canvas.delete('temp')
            self.custom_box_start = None
            self.mode = None
            return
            
        if self.mode in ['moving', 'rotating', 'resizing']:
            self.status_var.set(f"✓ Box #{self.selected_box_idx + 1} updated")
        
        self.mode = None
        self.resize_edge = None
    
    def on_mouse_move(self, event):
        if self.mode is None and self.original_img is not None:
            # Update cursor and coordinates
            img_x, img_y = self.canvas_to_image(event.x, event.y)
            self.coords_var.set(f"X: {int(img_x)} Y: {int(img_y)}")
            
            if self.get_rotation_handle_at_point(event.x, event.y) is not None:
                self.canvas.config(cursor='exchange')
            elif self.get_resize_edge_at_point(event.x, event.y) is not None:
                self.canvas.config(cursor='sb_h_double_arrow')  # Resize cursor
            elif self.get_box_at_point(event.x, event.y) is not None:
                self.canvas.config(cursor='fleur')
            else:
                self.canvas.config(cursor='crosshair')
    
    def on_double_click(self, event):
        clicked_box = self.get_box_at_point(event.x, event.y)
        if clicked_box is not None:
            self.delete_box(clicked_box)
    
    def on_list_select(self, event):
        selection = self.annotations_listbox.curselection()
        if selection:
            self.selected_box_idx = selection[0]
            self.highlight_box(self.selected_box_idx)
            self.update_info_display()
    
    def get_box_at_point(self, cx, cy):
        img_x, img_y = self.canvas_to_image(cx, cy)
        for idx in reversed(range(len(self.obb_list))):
            corners, class_id = self.obb_list[idx]
            if self.point_in_polygon(img_x, img_y, corners):
                return idx
        return None
    
    def get_rotation_handle_at_point(self, cx, cy):
        ROTATE_DETECT_RADIUS = max(6, int(6 * self.scale))
        for idx in reversed(range(len(self.obb_list))):
            corners, class_id = self.obb_list[idx]
            for corner_x, corner_y in corners:
                handle_cx, handle_cy = self.image_to_canvas(corner_x, corner_y)
                dist = math.sqrt((cx - handle_cx)**2 + (cy - handle_cy)**2)
                if dist < ROTATE_DETECT_RADIUS:
                    return idx
        return None
    
    def get_resize_edge_at_point(self, cx, cy):
        threshold = max(6, int(6 * self.scale))

        for idx in reversed(range(len(self.obb_list))):
            corners, class_id = self.obb_list[idx]
            canvas_corners = [self.image_to_canvas(x, y) for x, y in corners]

            for i in range(4):
                p1 = canvas_corners[i]
                p2 = canvas_corners[(i + 1) % 4]

                dist = self.point_to_segment_distance(
                    cx, cy, p1[0], p1[1], p2[0], p2[1]
                )

                if dist < threshold:
                    return (idx, i)

        return None

    
    def point_to_segment_distance(self, px, py, x1, y1, x2, y2):
        """Calculate distance from point to line segment"""
        # Vector from point 1 to point 2
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            # Point 1 and 2 are the same
            return math.sqrt((px - x1)**2 + (py - y1)**2)
        
        # Parameter t of the closest point on the line segment
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx**2 + dy**2)))
        
        # Closest point on segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        # Distance
        return math.sqrt((px - closest_x)**2 + (py - closest_y)**2)
    
    def point_in_polygon(self, x, y, polygon):
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside
    
    def redraw_all_boxes(self):
        self.canvas.delete('box')
        self.canvas.delete('handle')
        self.canvas.delete('label')
        self.box_graphics.clear()
        
        for idx, (corners, class_id) in enumerate(self.obb_list):
            self.draw_box(idx, corners, class_id, selected=(idx == self.selected_box_idx))
    
    def redraw_box(self, idx):
        if idx < len(self.obb_list):
            corners, class_id = self.obb_list[idx]
            self.draw_box(idx, corners, class_id, selected=True, clear_old=True)
    
    def draw_box(self, idx, corners, class_id, selected=False, clear_old=False):
        if clear_old:
            self.canvas.delete(f'box_{idx}')
            self.canvas.delete(f'handle_{idx}')
            self.canvas.delete(f'label_{idx}')
        
        canvas_corners = [self.image_to_canvas(x, y) for x, y in corners]
        points = []
        for x, y in canvas_corners:
            points.extend([x, y])
        
        color = '#00ffff' if selected else '#ff0000'
        width = 2 if selected else 1
        self.canvas.create_polygon(points, outline=color, fill='', width=width,
                                   tags=('box', f'box_{idx}'))
        HANDLE_RADIUS = 2
        for x, y in canvas_corners:
            handle_color = '#ffff00' if selected else '#ff8800'
            self.canvas.create_oval(x-HANDLE_RADIUS, y-HANDLE_RADIUS, x+HANDLE_RADIUS, y+HANDLE_RADIUS, fill=handle_color,
                                   outline='black', width=2, tags=('handle', f'handle_{idx}'))
        
        cx = sum(x for x, y in canvas_corners) / 4
        cy = sum(y for x, y in canvas_corners) / 4
        
        # Show box number and class
        class_name = CLASS_LABELS.get(class_id, class_id)
        label_text = f"#{idx+1}: {class_name}"
        self.canvas.create_text(cx, cy - 15, text=label_text, fill='#00ff00',
                               font=('Arial', 10, 'bold'), tags=('label', f'label_{idx}'))
    
    def highlight_box(self, idx):
        self.redraw_all_boxes()
        self.update_info_display()
    
    def update_info_display(self):
        self.info_text.delete('1.0', tk.END)
        
        if self.original_img is None:
            self.info_text.insert('1.0', "No image loaded")
            return
        
        # Show current image info with annotation status
        img_name = Path(self.image_path).name
        stem = Path(self.image_path).stem
        status_icon = "✓" if self.check_annotation_exists(stem) else "○"
        
        header = f"📄 {img_name} {status_icon}\n{'═' * 35}\n\n"
        
        if self.selected_box_idx is not None and self.selected_box_idx < len(self.obb_list):
            corners, class_id = self.obb_list[self.selected_box_idx]
            norm_corners = [(x/self.W, y/self.H) for x, y in corners]
            
            class_name = CLASS_LABELS.get(class_id, class_id)
            
            info = header
            info += f"═══ BOX #{self.selected_box_idx + 1} ═══\n\n"
            info += f"Class: {class_name} (ID: {class_id})\n\n"
            info += "8-Point Format:\n"
            info += f"{class_id}"
            for x, y in norm_corners:
                info += f" {x:.6f} {y:.6f}"
            info += "\n\n"
            info += "Corners (pixels):\n"
            for i, (x, y) in enumerate(corners, 1):
                info += f"  P{i}: ({x:.1f}, {y:.1f})\n"
            
            self.info_text.insert('1.0', info)
        else:
            info = header
            info += f"Total Boxes: {len(self.obb_list)}\n\n"
            info += "Click a box to see details"
            self.info_text.insert('1.0', info)
    
    def update_annotations_list(self):
        self.annotations_listbox.delete(0, tk.END)
        
        for idx, (corners, class_id) in enumerate(self.obb_list):
            xs = [x for x, y in corners]
            ys = [y for x, y in corners]
            cx = sum(xs) / 4
            cy = sum(ys) / 4
            
            class_name = CLASS_LABELS.get(class_id, class_id)
            self.annotations_listbox.insert(tk.END, f"#{idx+1}: {class_name}")
        
        self.update_list_title()
    
    def update_list_title(self):
        self.list_frame.config(text=f"📋 Annotations ({len(self.obb_list)})")
    
    def delete_selected(self):
        if self.selected_box_idx is not None and self.selected_box_idx < len(self.obb_list):
            self.delete_box(self.selected_box_idx)
    
    def delete_box(self, idx):
        if 0 <= idx < len(self.obb_list):
            self.obb_list.pop(idx)
            self.selected_box_idx = None
            self.annotations_modified = True
            self.redraw_all_boxes()
            self.update_annotations_list()
            self.update_info_display()
            self.status_var.set(f"🗑 Box deleted. Remaining: {len(self.obb_list)}")
    
    def undo_last(self):
        if self.obb_list:
            self.obb_list.pop()
            self.selected_box_idx = None
            self.annotations_modified = True
            self.redraw_all_boxes()
            self.update_annotations_list()
            self.update_info_display()
            self.status_var.set(f"↶ Undo complete. Remaining: {len(self.obb_list)}")
        else:
            self.status_var.set("Nothing to undo")
    
    def clear_all(self):
        if self.obb_list:
            if messagebox.askyesno("Confirm", f"Delete all {len(self.obb_list)} boxes?"):
                self.obb_list.clear()
                self.selected_box_idx = None
                self.annotations_modified = True
                if self.annotation_source_path:
                    self.auto_save_to_original_location()
                self.redraw_all_boxes()
                self.update_annotations_list()
                self.update_info_display()
                self.status_var.set("🧹 All boxes cleared")
        else:
            self.status_var.set("No boxes to clear")
    
    def _ensure_dir(self, path: Path):
        """Create directory if it doesn't exist (Path object)."""
        path.mkdir(parents=True, exist_ok=True)

    def _write_annotations_to_path(self, out_txt: Path):
        """Write current self.obb_list (normalized) to out_txt"""
        try:
            self._ensure_dir(out_txt.parent)
            with open(out_txt, "w") as f:
                for corners, class_id in self.obb_list:
                    norm_corners = [(x / self.W, y / self.H) for x, y in corners]
                    line = class_id
                    for x, y in norm_corners:
                        line += f" {x:.6f} {y:.6f}"
                    f.write(line + "\n")
            return True, None
        except Exception as e:
            return False, str(e)

    def save_to_category(self, category_name: str):
        """
        Generic: copy image + annotation into categorized/<category_name>/ 
        under images_folder and labels_folder respectively.
        """
        # Preconditions
        if not self.image_path:
            messagebox.showerror("Error", "No image loaded to save.")
            return

        if not self.labels_folder or not self.images_folder:
            messagebox.showerror("Error", "Select both Images and Labels folders first.")
            return

        try:
            src_image = Path(self.image_path)
            src_ann = Path(self.labels_folder) / f"{src_image.stem}.txt"

            # destination directories
            dest_ann_dir = Path(self.labels_folder) / "categorized" / category_name
            dest_img_dir = Path(self.images_folder) / "categorized" / category_name

            self._ensure_dir(dest_ann_dir)
            self._ensure_dir(dest_img_dir)

            # 1) Ensure annotation exists in labels_folder by saving current in-memory
            #    or copying existing file if present.
            if src_ann.exists():
                # copy existing annotation
                shutil.copy2(src_ann, dest_ann_dir / src_ann.name)
                ann_copied = True
                ann_msg = f"Copied annotation from {src_ann}."
            else:
                # write in-memory annotations (if any) to destination
                if self.obb_list:
                    out_ann_path = dest_ann_dir / f"{src_image.stem}.txt"
                    ok, err = self._write_annotations_to_path(out_ann_path)
                    if not ok:
                        raise RuntimeError(f"Failed to write annotation: {err}")
                    ann_copied = True
                    ann_msg = "Wrote annotation from memory."
                else:
                    ann_copied = False
                    ann_msg = "No annotation available to save."

            # 2) Copy image file
            if src_image.exists():
                shutil.copy2(src_image, dest_img_dir / src_image.name)
                img_msg = f"Copied image to {dest_img_dir}."
            else:
                img_msg = "Image file not found to copy."

            # 3) Clear modified flag and update source path
            self.annotations_modified = False
            
            # Update source path so future modifications auto-save to this location
            self.annotation_source_path = dest_ann_dir / f"{src_image.stem}.txt"

            # 4) Update the listbox to show checkmark immediately
            self.image_listbox.delete(self.current_image_idx)
            status = "✓"
            display_name = self.format_image_list_item(src_image.name)
            self.image_listbox.insert(self.current_image_idx, f"✓ {display_name}")
            self.image_listbox.config(xscrollcommand=None)
            self.image_listbox.selection_set(self.current_image_idx)
            
            # Update progress display
            self.update_progress()
            
            self.status_var.set(f"✓ Saved to {category_name}: {src_image.name}")

        except Exception as e:
            self.status_var.set(f"Error saving to {category_name}: {e}")
            messagebox.showerror("Error", f"Failed to save to {category_name}:\n{e}")

    # convenience wrappers for buttons
    def add_to_garment(self):
        self.save_to_category("garment")

    def add_to_towel(self):
        self.save_to_category("towel")

    def add_to_cap(self):
        self.save_to_category("cap")

    def add_to_bag(self):
        self.save_to_category("bag")

    def load_image_list(self):
        """Load all images from the selected folder and all subdirectories"""
        if not self.images_folder or not os.path.exists(self.images_folder):
            messagebox.showerror("Error", "Invalid images folder!")
            return
        
        # Supported formats
        extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        found_files = set()
        # Use ** for recursive search through all subdirectories
        for ext in extensions:
            found_files.update(Path(self.images_folder).rglob(f"*{ext}"))
            found_files.update(Path(self.images_folder).rglob(f"*{ext.upper()}"))
        
        # Sort by path to maintain directory structure, not by annotation status
        self.image_files = sorted(list(found_files), key=lambda p: str(p))
        
        if not self.image_files:
            messagebox.showwarning("No Images", "No images found in the selected folder and its subdirectories!")
            return
        
        # Populate listbox
        self.image_listbox.delete(0, tk.END)
        for img_file in self.image_files:
            # Check if already annotated (check both main and category folders)
            status = "✓" if self.check_annotation_exists(img_file.stem) else "○"
            display_name = self.format_image_list_item(img_file.name)
            self.image_listbox.insert(tk.END, f"{status} {display_name}")
            self.image_listbox.config(xscrollcommand=None)


        
        self.current_image_idx = 0
        self.load_image(0)
        self.update_progress()
        self.status_var.set(f"Loaded {len(self.image_files)} images from folder (including subdirectories)")
        
    def filter_image_list(self, *args):
        """Filter image list based on search"""
        search_term = self.search_var.get().lower()
        self.image_listbox.delete(0, tk.END)
        
        for idx, img_file in enumerate(self.image_files):
            if search_term in img_file.name.lower():
                # Check if already annotated (check both main and category folders)
                status = "✓" if self.check_annotation_exists(img_file.stem) else "○"
                display_name = self.format_image_list_item(img_file.name)
                self.image_listbox.insert(tk.END, f"{status} {display_name}")
                self.image_listbox.config(xscrollcommand=None)


        
    def load_image(self, idx):
        """Load image at given index"""
        if idx < 0 or idx >= len(self.image_files):
            return
        
        self.current_image_idx = idx
        self.image_path = str(self.image_files[idx])
        self.original_img = cv2.imread(self.image_path)
        
        if self.original_img is None:
            messagebox.showerror("Error", f"Failed to load: {self.image_path}")
            return
        
        self.H, self.W = self.original_img.shape[:2]
        
        # Load existing annotations if available
        self.load_existing_annotations()
        
        # Display
        self.display_image()
        self.update_progress()
        self.update_list_title()
        
        # Update UI
        img_name = Path(self.image_path).name
        self.image_info_label.config(text=f"📄 {img_name} | {self.W}x{self.H}px | Scale: {self.scale:.1%}")
        self.image_listbox.selection_clear(0, tk.END)
        self.image_listbox.selection_set(idx)
        self.image_listbox.see(idx)
        
    def load_existing_annotations(self):
        """Auto-load existing annotations for current image (check main and category folders)"""
        self.obb_list.clear()
        self.selected_box_idx = None
        self.annotations_modified = False
        self.annotation_source_path = None  # Reset source path

        if not self.labels_folder:
            return

        stem = Path(self.image_path).stem
        
        # Try main labels folder first
        label_file = Path(self.labels_folder) / f"{stem}.txt"
        
        # If not in main folder, check categorized folders
        if not label_file.exists():
            categorized_dir = Path(self.labels_folder) / "categorized"
            if categorized_dir.exists():
                for category_folder in categorized_dir.iterdir():
                    if category_folder.is_dir():
                        category_label = category_folder / f"{stem}.txt"
                        if category_label.exists():
                            label_file = category_label
                            break

        if not label_file.exists():
            return

        try:
            with open(label_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 9:  # class_id + 8 normalized coords
                        class_id = parts[0]
                        coords = [float(x) for x in parts[1:]]

                        # Denormalize back to pixel coordinates
                        corners = [
                            (coords[0] * self.W, coords[1] * self.H),
                            (coords[2] * self.W, coords[3] * self.H),
                            (coords[4] * self.W, coords[5] * self.H),
                            (coords[6] * self.W, coords[7] * self.H),
                        ]

                        self.obb_list.append((corners, class_id))

            # Store the source path for auto-save later
            self.annotation_source_path = label_file
            
            self.status_var.set(f"Loaded {len(self.obb_list)} existing annotations")

        except Exception as e:
            self.status_var.set(f"Error loading annotations: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = OBBAnnotator(root)
    root.mainloop()