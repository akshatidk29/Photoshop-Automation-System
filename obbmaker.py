import cv2
import numpy as np
import math
import os
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
    "20": "CAP_FRONT_SIDE",

    # Crown-related
    "21": "LOWER_LEFT_CROWN",
    "22": "LOWER_RIGHT_CROWN",

    # Other items / products
    "23": "CORNER_ANGLED_TOWEL",
    "24": "FRONT_CENTER",

    # Bag-related
    "25": "FRONT_ON_BAG",
    "26": "ON_POCKET_ON_BAG"
}

MIN_AREA = 200             # ignore tiny boxes
IMAGES_FOLDER = "path/to/images"      # <-- SET YOUR IMAGES FOLDER
LABELS_FOLDER = "annotations"      # <-- SET YOUR LABELS FOLDER
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
        self.drawing_start = None
        self.selected_box_idx = None
        self.drag_start = None
        self.resize_edge = None  # Which edge is being resized
        self.auto_save = tk.BooleanVar(value=True)
        
        self.obb_list = []  # List of (corners, class_id) tuples
        self.box_graphics = []
        
        self.setup_ui()
        
        # Keyboard shortcuts
        self.root.bind('<Left>', lambda e: self.prev_image())
        self.root.bind('<Right>', lambda e: self.next_image())
        self.root.bind('<Delete>', lambda e: self.delete_selected())
        self.root.bind('<Control-s>', lambda e: self.save_annotations())
        self.root.bind('<Control-z>', lambda e: self.undo_last())
        
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
        
        # Auto-save checkbox
        tk.Checkbutton(toolbar, text="Auto-save", variable=self.auto_save,
                      bg='#2d2d2d', fg='white', selectcolor='#1a1a1a',
                      font=('Arial', 10), activebackground='#2d2d2d').pack(side=tk.RIGHT, padx=20)
        
    def create_left_sidebar(self, parent):
        left_frame = tk.Frame(parent, width=280, bg='#252525')
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
        
        # Image info bar
        info_bar = tk.Frame(center_frame, bg='#2d2d2d', height=40)
        info_bar.pack(fill=tk.X, pady=(0, 5))
        
        self.image_info_label = tk.Label(info_bar, text="No image loaded", 
                                         bg='#2d2d2d', fg='white', font=('Arial', 11, 'bold'))
        self.image_info_label.pack(side=tk.LEFT, padx=15, pady=8)
        
        # Canvas
        self.canvas = tk.Canvas(center_frame, bg='#2d2d2d', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        
        # Help overlay
        help_frame = tk.Frame(center_frame, bg='#1a1a1a')
        help_frame.pack(fill=tk.X, pady=(5, 0))
        
        help_text = "💡 Drag: Create box | Click+Drag: Move | Drag edges: Resize | Drag corners: Rotate | Double-click: Delete | ⬅➡: Navigate"
        tk.Label(help_frame, text=help_text, bg='#1a1a1a', fg='#888888', 
                font=('Arial', 9, 'italic')).pack(pady=5)
        
    def create_right_sidebar(self, parent):
        right_frame = tk.Frame(parent, width=350, bg='#252525')
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_frame.pack_propagate(False)
        
        # Current box info
        info_frame = tk.LabelFrame(right_frame, text="📊 Current Selection", bg='#252525',
                                   fg='white', font=('Arial', 11, 'bold'), bd=2)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.info_text = tk.Text(info_frame, height=12, bg='#1a1a1a', fg='#00ff88',
                                font=('Courier', 9), relief=tk.FLAT, wrap=tk.WORD)
        self.info_text.pack(fill=tk.X, padx=8, pady=8)
        self.update_info_display()
        
        # Quick actions
        action_frame = tk.LabelFrame(right_frame, text="⚡ Quick Actions", bg='#252525',
                                     fg='white', font=('Arial', 11, 'bold'), bd=2)
        action_frame.pack(fill=tk.X, padx=10, pady=10)
        
        btn_config = {'font': ('Arial', 10, 'bold'), 'relief': tk.FLAT, 'pady': 10, 'cursor': 'hand2'}
        
        tk.Button(action_frame, text="💾 Save (Ctrl+S)", command=self.save_annotations,
                 bg='#28a745', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=3)
        
        tk.Button(action_frame, text="🗑 Delete (Del)", command=self.delete_selected,
                 bg='#dc3545', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=3)
        
        tk.Button(action_frame, text="↶ Undo (Ctrl+Z)", command=self.undo_last,
                 bg='#ffc107', fg='black', **btn_config).pack(fill=tk.X, padx=8, pady=3)
        
        tk.Button(action_frame, text="🧹 Clear All", command=self.clear_all,
                 bg='#6c757d', fg='white', **btn_config).pack(fill=tk.X, padx=8, pady=3)
        
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
            
    def load_image_list(self):
        """Load all images from the selected folder and all subdirectories"""
        if not self.images_folder or not os.path.exists(self.images_folder):
            messagebox.showerror("Error", "Invalid images folder!")
            return
        
        # Supported formats
        extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        self.image_files = []
        # Use ** for recursive search through all subdirectories
        for ext in extensions:
            self.image_files.extend(Path(self.images_folder).rglob(f"*{ext}"))
            self.image_files.extend(Path(self.images_folder).rglob(f"*{ext.upper()}"))
        
        self.image_files = sorted(self.image_files)
        
        if not self.image_files:
            messagebox.showwarning("No Images", "No images found in the selected folder and its subdirectories!")
            return
        
        # Populate listbox
        self.image_listbox.delete(0, tk.END)
        for img_file in self.image_files:
            # Check if already annotated
            label_file = Path(self.labels_folder) / f"{img_file.stem}.txt"
            status = "✅" if label_file.exists() else "○"
            self.image_listbox.insert(tk.END, f"{status} {img_file.name}")
        
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
                label_file = Path(self.labels_folder) / f"{img_file.stem}.txt"
                status = "✓" if label_file.exists() else "○"
                self.image_listbox.insert(tk.END, f"{status} {img_file.name}")
        
    def on_image_select(self, event):
        """Handle image selection from list"""
        selection = self.image_listbox.curselection()
        if selection:
            # Get the actual index from the displayed name
            selected_name = self.image_listbox.get(selection[0])[2:]  # Remove status symbol
            for idx, img_file in enumerate(self.image_files):
                if img_file.name == selected_name:
                    self.load_image(idx)
                    break
        
    def load_image(self, idx):
        """Load image at given index"""
        if idx < 0 or idx >= len(self.image_files):
            return
        
        # Auto-save current annotations
        if self.auto_save.get() and self.obb_list and self.image_path:
            self.save_annotations(silent=True)
        
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
        """Load existing annotations for current image"""
        self.obb_list.clear()
        self.selected_box_idx = None
        
        if not self.labels_folder:
            return
        
        label_file = Path(self.labels_folder) / f"{Path(self.image_path).stem}.txt"
        
        if label_file.exists():
            # Prompt user about existing annotations
            response = messagebox.askyesnocancel(
                "Existing Annotations Found",
                f"Annotations already exist for this image.\n\n"
                f"Yes: Load existing annotations\n"
                f"No: Start fresh (will overwrite on save)\n"
                f"Cancel: Go back",
                icon='warning'
            )
            
            if response is None:  # Cancel
                # Go back to previous image
                if self.current_image_idx > 0:
                    self.current_image_idx -= 1
                return
            elif response:  # Yes - load existing
                try:
                    with open(label_file, 'r') as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) == 9:  # class_id + 8 coordinates
                                class_id = parts[0]
                                coords = [float(x) for x in parts[1:]]
                                # Denormalize
                                corners = [
                                    (coords[0] * self.W, coords[1] * self.H),
                                    (coords[2] * self.W, coords[3] * self.H),
                                    (coords[4] * self.W, coords[5] * self.H),
                                    (coords[6] * self.W, coords[7] * self.H)
                                ]
                                self.obb_list.append((corners, class_id))
                    self.status_var.set(f"Loaded {len(self.obb_list)} existing annotations")
                except Exception as e:
                    self.status_var.set(f"Error loading annotations: {str(e)}")
            # else: No - start fresh (obb_list already cleared)
        
    def prev_image(self):
        """Navigate to previous image"""
        if self.image_files and self.current_image_idx > 0:
            self.load_image(self.current_image_idx - 1)
        
    def next_image(self):
        """Navigate to next image"""
        if self.image_files and self.current_image_idx < len(self.image_files) - 1:
            self.load_image(self.current_image_idx + 1)
        
    def update_progress(self):
        """Update progress label"""
        if self.image_files:
            total = len(self.image_files)
            current = self.current_image_idx + 1
            
            # Count annotated
            annotated = sum(1 for f in self.image_files 
                          if (Path(self.labels_folder) / f"{f.stem}.txt").exists())
            
            self.progress_label.config(
                text=f"Image {current}/{total} | Annotated: {annotated}/{total} ({annotated*100//total}%)"
            )
            
            # Update session stats
            total_boxes = sum(1 for f in self.image_files 
                            if (Path(self.labels_folder) / f"{f.stem}.txt").exists())
            self.stats_label.config(text=f"📊 Session: {annotated} images | ~{total_boxes}+ boxes")
        
    def display_image(self):
        if self.original_img is None:
            return
        
        self.canvas.update()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        scale_w = (canvas_width - 100) / self.W
        scale_h = (canvas_height - 100) / self.H
        self.scale = min(scale_w, scale_h, 1.0)
        
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
    
    def on_mouse_down(self, event):
        if self.original_img is None:
            return
        
        clicked_box = self.get_box_at_point(event.x, event.y)
        clicked_handle = self.get_rotation_handle_at_point(event.x, event.y)
        clicked_edge = self.get_resize_edge_at_point(event.x, event.y)
        
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
            self.mode = 'drawing'
            self.drawing_start = (event.x, event.y)
            self.selected_box_idx = None
            self.status_var.set("✏ Drawing new box...")
    
    def on_mouse_drag(self, event):
        # Update coordinates display
        img_x, img_y = self.canvas_to_image(event.x, event.y)
        self.coords_var.set(f"X: {int(img_x)} Y: {int(img_y)}")
        
        if self.mode == 'drawing' and self.drawing_start:
            self.canvas.delete('temp')
            x1, y1 = self.drawing_start
            x2, y2 = event.x, event.y
            self.canvas.create_rectangle(x1, y1, x2, y2, outline='#00ff00', 
                                        width=3, tags='temp', dash=(5, 5))
            
        elif self.mode == 'moving' and self.selected_box_idx is not None:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            self.drag_start = (event.x, event.y)
            
            corners, class_id = self.obb_list[self.selected_box_idx]
            dx_img, dy_img = dx / self.scale, dy / self.scale
            new_corners = [(x + dx_img, y + dy_img) for x, y in corners]
            self.obb_list[self.selected_box_idx] = (new_corners, class_id)
            
            self.redraw_box(self.selected_box_idx)
            self.update_info_display()
            
        elif self.mode == 'resizing' and self.selected_box_idx is not None:
            # Resize the edge
            corners, class_id = self.obb_list[self.selected_box_idx]
            
            # Get mouse movement in image coordinates
            curr_x, curr_y = self.canvas_to_image(event.x, event.y)
            old_x, old_y = self.canvas_to_image(self.drag_start[0], self.drag_start[1])
            dx = curr_x - old_x
            dy = curr_y - old_y
            
            # Move the two corners of the selected edge
            edge_idx = self.resize_edge
            new_corners = list(corners)
            
            # Calculate which corners to move based on edge index
            corner1_idx = edge_idx
            corner2_idx = (edge_idx + 1) % 4
            
            # Move both corners of this edge
            new_corners[corner1_idx] = (corners[corner1_idx][0] + dx, corners[corner1_idx][1] + dy)
            new_corners[corner2_idx] = (corners[corner2_idx][0] + dx, corners[corner2_idx][1] + dy)
            
            self.obb_list[self.selected_box_idx] = (new_corners, class_id)
            self.drag_start = (event.x, event.y)
            
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
            
            self.redraw_box(self.selected_box_idx)
            self.update_info_display()
    
    def on_mouse_up(self, event):
        if self.mode == 'drawing' and self.drawing_start:
            x1, y1 = self.drawing_start
            x2, y2 = event.x, event.y
            
            if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:
                img_x1, img_y1 = self.canvas_to_image(x1, y1)
                img_x2, img_y2 = self.canvas_to_image(x2, y2)
                
                corners = [
                    (img_x1, img_y1),
                    (img_x2, img_y1),
                    (img_x2, img_y2),
                    (img_x1, img_y2)
                ]
                
                width = abs(img_x2 - img_x1)
                height = abs(img_y2 - img_y1)
                if width * height >= MIN_AREA:
                    # Show class selection dialog
                    result = self.show_class_selection_dialog()
                    
                    if result['confirmed']:
                        self.obb_list.append((corners, result['class_id']))
                        self.redraw_all_boxes()
                        self.update_annotations_list()
                        class_name = CLASS_LABELS.get(result['class_id'], result['class_id'])
                        self.status_var.set(f"✓ Box #{len(self.obb_list)} created ({class_name})! Total: {len(self.obb_list)}")
                    else:
                        self.status_var.set("Box creation cancelled")
                else:
                    self.status_var.set(f"⚠ Box too small (min {MIN_AREA}px²)")
            
            self.canvas.delete('temp')
            
        elif self.mode in ['moving', 'rotating', 'resizing']:
            self.status_var.set(f"✓ Box #{self.selected_box_idx + 1} updated")
        
        self.mode = None
        self.drawing_start = None
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
        for idx, (corners, class_id) in enumerate(self.obb_list):
            if self.point_in_polygon(img_x, img_y, corners):
                return idx
        return None
    
    def get_rotation_handle_at_point(self, cx, cy):
        for idx, (corners, class_id) in enumerate(self.obb_list):
            for corner_x, corner_y in corners:
                handle_cx, handle_cy = self.image_to_canvas(corner_x, corner_y)
                dist = math.sqrt((cx - handle_cx)**2 + (cy - handle_cy)**2)
                if dist < 8:
                    return idx
        return None
    
    def get_resize_edge_at_point(self, cx, cy):
        """Check if point is near an edge of any box. Returns (box_idx, edge_idx)"""
        threshold = 8  # Distance threshold for edge detection
        
        for idx, (corners, class_id) in enumerate(self.obb_list):
            canvas_corners = [self.image_to_canvas(x, y) for x, y in corners]
            
            # Check each edge
            for i in range(4):
                p1 = canvas_corners[i]
                p2 = canvas_corners[(i + 1) % 4]
                
                # Calculate distance from point to line segment
                dist = self.point_to_segment_distance(cx, cy, p1[0], p1[1], p2[0], p2[1])
                
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
        width = 3 if selected else 2
        self.canvas.create_polygon(points, outline=color, fill='', width=width,
                                   tags=('box', f'box_{idx}'))
        
        for x, y in canvas_corners:
            handle_color = '#ffff00' if selected else '#ff8800'
            self.canvas.create_oval(x-6, y-6, x+6, y+6, fill=handle_color,
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
        label_file = Path(self.labels_folder) / f"{Path(self.image_path).stem}.txt"
        status_icon = "✓" if label_file.exists() else "○"
        
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
            self.redraw_all_boxes()
            self.update_annotations_list()
            self.update_info_display()
            self.status_var.set(f"🗑 Box deleted. Remaining: {len(self.obb_list)}")
    
    def undo_last(self):
        if self.obb_list:
            self.obb_list.pop()
            self.selected_box_idx = None
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
                self.redraw_all_boxes()
                self.update_annotations_list()
                self.update_info_display()
                self.status_var.set("🧹 All boxes cleared")
        else:
            self.status_var.set("No boxes to clear")
    
    def save_annotations(self, silent=False):
        if not self.obb_list:
            if not silent:
                self.status_var.set("⚠ No annotations to save")
            return
        
        if not self.image_path or not self.labels_folder:
            if not silent:
                messagebox.showerror("Error", "No image or labels folder!")
            return
        
        # Create labels folder if needed
        Path(self.labels_folder).mkdir(parents=True, exist_ok=True)
        
        out_txt = Path(self.labels_folder) / f"{Path(self.image_path).stem}.txt"
        
        try:
            with open(out_txt, "w") as f:
                for corners, class_id in self.obb_list:
                    norm_corners = [(x/self.W, y/self.H) for x, y in corners]
                    line = class_id
                    for x, y in norm_corners:
                        line += f" {x:.6f} {y:.6f}"
                    f.write(line + "\n")
            
            if not silent:
                messagebox.showinfo("Success", f"Saved {len(self.obb_list)} annotations!")
            
            self.status_var.set(f"💾 Saved {len(self.obb_list)} annotations → {out_txt.name}")
            
            # Update image list status
            self.filter_image_list()
            self.update_progress()
            
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to save: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = OBBAnnotator(root)
    root.mainloop()