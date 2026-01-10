import cv2
import numpy as np
import math
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from pathlib import Path

CLASS_LABELS = {
    "0": "FULL_BACK", "1": "FULL_FRONT", "2": "LEFT_BICEP", "3": "RIGHT_BICEP",
    "4": "LEFT_CHEST", "5": "RIGHT_CHEST", "6": "LEFT_COLLAR", "7": "RIGHT_COLLAR",
    "8": "LEFT_CUFF", "9": "RIGHT_CUFF", "10": "LEFT_HIP", "11": "RIGHT_HIP",
    "12": "LEFT_SLEEVE", "13": "RIGHT_SLEEVE", "14": "LEFT_THIGH_HIGH", "15": "RIGHT_THIGH_HIGH",
    "16": "ON_POCKET", "17": "BACK_YOKE", "18": "CAP_BACK", "19": "CAP_SIDE",
    "20": "CAP_FRONT_SIDE", "21": "LOWER_LEFT_CROWN", "22": "LOWER_RIGHT_CROWN",
    "23": "CORNER_ANGLED_TOWEL", "24": "FRONT_CENTER", "25": "FRONT_ON_BAG", "26": "ON_POCKET_ON_BAG"
}

MIN_AREA = 200
IMAGES_FOLDER = "Data_/Images"
LABELS_FOLDER = "Data_/Annotations"

class OBBAnnotator:
    def __init__(self, root):
        self.root = root
        self.root.title("🎯 OBB Polygon Annotator - Speed Edition")
        self.root.geometry("1800x1000")
        self.root.configure(bg='#1a1a1a')
        
        self.images_folder = IMAGES_FOLDER
        self.labels_folder = LABELS_FOLDER
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
        
        # Polygon drawing
        self.polygon_points = []
        self.drawing_polygon = False
        
        self.mode = None
        self.selected_box_idx = None
        self.drag_start = None
        self.auto_save = tk.BooleanVar(value=True)
        self.obb_list = []
        self.box_graphics = []
        
        self.setup_ui()
        
        self.root.bind('<Left>', lambda e: self.prev_image())
        self.root.bind('<Right>', lambda e: self.next_image())
        self.root.bind('<Delete>', lambda e: self.delete_selected())
        self.root.bind('<Control-z>', lambda e: self.undo_last())
        self.root.bind('<Escape>', lambda e: self.cancel_polygon())
        self.root.bind('<Return>', lambda e: self.complete_polygon())
        self.root.bind('<Control-g>', lambda e: self.save_to_category('garments'))
        self.root.bind('<Control-b>', lambda e: self.save_to_category('bags'))
        self.root.bind('<Control-t>', lambda e: self.save_to_category('towels'))
        self.root.bind('<Control-c>', lambda e: self.save_to_category('caps'))
        
    def setup_ui(self):
        self.create_toolbar()
        main = tk.Frame(self.root, bg='#1a1a1a')
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.create_left_sidebar(main)
        self.create_canvas_area(main)
        self.create_right_sidebar(main)
        self.create_status_bar()
        
    def create_toolbar(self):
        toolbar = tk.Frame(self.root, bg='#2d2d2d', height=60, relief=tk.RAISED, bd=2)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        tk.Label(toolbar, text="🎯 Polygon Annotator", font=('Arial', 16, 'bold'),
                bg='#2d2d2d', fg='#00ff88').pack(side=tk.LEFT, padx=20, pady=10)
        
        bf = tk.Frame(toolbar, bg='#2d2d2d')
        bf.pack(side=tk.LEFT, padx=20)
        
        tk.Button(bf, text="📁 Images", command=self.select_images_folder,
                 bg='#4a90e2', fg='white', font=('Arial', 10, 'bold'),
                 relief=tk.FLAT, padx=15, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        tk.Button(bf, text="📂 Labels", command=self.select_labels_folder,
                 bg='#e24a90', fg='white', font=('Arial', 10, 'bold'),
                 relief=tk.FLAT, padx=15, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        tk.Button(toolbar, text="📋 Copy Previous", command=self.copy_previous,
                 bg='#9b59b6', fg='white', font=('Arial', 10, 'bold'),
                 relief=tk.FLAT, padx=15, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=10)
        
        tk.Checkbutton(toolbar, text="Auto-save", variable=self.auto_save,
                      bg='#2d2d2d', fg='white', selectcolor='#1a1a1a',
                      font=('Arial', 10), activebackground='#2d2d2d').pack(side=tk.RIGHT, padx=20)
        
    def create_left_sidebar(self, parent):
        lf = tk.Frame(parent, width=280, bg='#252525')
        lf.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        lf.pack_propagate(False)
        
        tk.Label(lf, text="📂 Images", font=('Arial', 13, 'bold'),
                bg='#252525', fg='white', pady=10).pack(fill=tk.X)
        
        self.progress_label = tk.Label(lf, text="No images", 
                                       bg='#252525', fg='#888888', font=('Arial', 9))
        self.progress_label.pack(fill=tk.X, padx=10, pady=5)
        
        sf = tk.Frame(lf, bg='#252525')
        sf.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(sf, text="🔍", bg='#252525', fg='white').pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_list)
        tk.Entry(sf, textvariable=self.search_var, bg='#1a1a1a', fg='white',
                relief=tk.FLAT, font=('Arial', 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        listf = tk.Frame(lf, bg='#252525')
        listf.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scroll = ttk.Scrollbar(listf)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.image_listbox = tk.Listbox(listf, bg='#1a1a1a', fg='white',
                                       font=('Courier', 9), selectmode=tk.SINGLE,
                                       yscrollcommand=scroll.set, relief=tk.FLAT,
                                       selectbackground='#4a90e2', activestyle='none')
        self.image_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.image_listbox.yview)
        self.image_listbox.bind('<<ListboxSelect>>', self.on_select)
        
        nf = tk.Frame(lf, bg='#252525')
        nf.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(nf, text="⬅ Prev", command=self.prev_image,
                 bg='#666666', fg='white', font=('Arial', 9, 'bold'),
                 relief=tk.FLAT, pady=8, cursor='hand2').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        
        tk.Button(nf, text="Next ➡", command=self.next_image,
                 bg='#666666', fg='white', font=('Arial', 9, 'bold'),
                 relief=tk.FLAT, pady=8, cursor='hand2').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5,0))
        
    def create_canvas_area(self, parent):
        cf = tk.Frame(parent, bg='#1a1a1a')
        cf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ib = tk.Frame(cf, bg='#2d2d2d', height=40)
        ib.pack(fill=tk.X, pady=(0, 5))
        
        self.image_info = tk.Label(ib, text="No image", bg='#2d2d2d', fg='white', font=('Arial', 11, 'bold'))
        self.image_info.pack(side=tk.LEFT, padx=15, pady=8)
        
        self.canvas = tk.Canvas(cf, bg='#2d2d2d', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<ButtonPress-1>", self.on_click)
        self.canvas.bind("<ButtonPress-3>", self.on_rclick)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_move)
        self.canvas.bind("<Double-Button-1>", self.on_dclick)
        
        hf = tk.Frame(cf, bg='#1a1a1a')
        hf.pack(fill=tk.X, pady=(5, 0))
        
        tk.Label(hf, text="💡 Click: Add point | Right/Enter: Complete | Esc: Cancel | DblClick: Delete | Drag: Move/Rotate", 
                bg='#1a1a1a', fg='#888888', font=('Arial', 9, 'italic')).pack(pady=5)
        
    def create_right_sidebar(self, parent):
        rf = tk.Frame(parent, width=350, bg='#252525')
        rf.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        rf.pack_propagate(False)
        
        inf = tk.LabelFrame(rf, text="📊 Info", bg='#252525', fg='white', font=('Arial', 11, 'bold'), bd=2)
        inf.pack(fill=tk.X, padx=10, pady=10)
        
        self.info_text = tk.Text(inf, height=10, bg='#1a1a1a', fg='#00ff88',
                                font=('Courier', 9), relief=tk.FLAT, wrap=tk.WORD)
        self.info_text.pack(fill=tk.X, padx=8, pady=8)
        
        # Category save buttons - FIXED SYNTAX ERROR HERE
        savef = tk.LabelFrame(rf, text="💾 Save Category", bg='#252525', fg='white', font=('Arial', 11, 'bold'), bd=2)
        savef.pack(fill=tk.X, padx=10, pady=10)
        
        btn_config = {'font': ('Arial', 10, 'bold'), 'relief': tk.FLAT, 'pady': 10, 'cursor': 'hand2', 'fg': 'white'}
        
        tk.Button(savef, text="👔 Garments (Ctrl+G)", command=lambda: self.save_to_category('garments'),
                 bg='#3498db', **btn_config).pack(fill=tk.X, padx=8, pady=2)
        
        tk.Button(savef, text="👜 Bags (Ctrl+B)", command=lambda: self.save_to_category('bags'),
                 bg='#e74c3c', **btn_config).pack(fill=tk.X, padx=8, pady=2)
        
        tk.Button(savef, text="🧻 Towels (Ctrl+T)", command=lambda: self.save_to_category('towels'),
                 bg='#2ecc71', **btn_config).pack(fill=tk.X, padx=8, pady=2)
        
        tk.Button(savef, text="🧢 Caps (Ctrl+C)", command=lambda: self.save_to_category('caps'),
                 bg='#f39c12', **btn_config).pack(fill=tk.X, padx=8, pady=2)
        
        actf = tk.LabelFrame(rf, text="⚡ Actions", bg='#252525', fg='white', font=('Arial', 11, 'bold'), bd=2)
        actf.pack(fill=tk.X, padx=10, pady=10)
        
        btn_config2 = {'font': ('Arial', 10, 'bold'), 'relief': tk.FLAT, 'pady': 10, 'cursor': 'hand2'}
        
        tk.Button(actf, text="🗑 Delete", command=self.delete_selected,
                 bg='#dc3545', fg='white', **btn_config2).pack(fill=tk.X, padx=8, pady=3)
        
        tk.Button(actf, text="↶ Undo", command=self.undo_last,
                 bg='#ffc107', fg='black', **btn_config2).pack(fill=tk.X, padx=8, pady=3)
        
        tk.Button(actf, text="🧹 Clear All", command=self.clear_all,
                 bg='#6c757d', fg='white', **btn_config2).pack(fill=tk.X, padx=8, pady=3)
        
        lstf = tk.LabelFrame(rf, text="📋 Annotations (0)", bg='#252525', fg='white', font=('Arial', 11, 'bold'), bd=2)
        lstf.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.list_frame = lstf
        
        ls = ttk.Scrollbar(lstf)
        ls.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4))
        
        self.ann_listbox = tk.Listbox(lstf, bg='#1a1a1a', fg='white',
                                      font=('Courier', 9), selectmode=tk.SINGLE,
                                      yscrollcommand=ls.set, relief=tk.FLAT,
                                      selectbackground='#4a90e2', activestyle='none')
        self.ann_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ls.config(command=self.ann_listbox.yview)
        self.ann_listbox.bind('<<ListboxSelect>>', self.on_list_sel)
        
        stf = tk.Frame(rf, bg='#252525')
        stf.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.stats = tk.Label(stf, text="📊 0 images", bg='#252525', fg='#888888', font=('Arial', 9))
        self.stats.pack()
        
    def create_status_bar(self):
        sf = tk.Frame(self.root, bg='#2d2d2d', height=30)
        sf.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status = tk.StringVar(value="Ready. Click to add polygon points.")
        tk.Label(sf, textvariable=self.status, bd=1, anchor=tk.W, bg='#2d2d2d', 
                fg='#00ff88', font=('Arial', 10), padx=15).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.coords = tk.StringVar(value="")
        tk.Label(sf, textvariable=self.coords, bg='#2d2d2d', fg='#ffaa00', 
                font=('Courier', 9), padx=15).pack(side=tk.RIGHT)
    
    def notify(self, title, message, type='info'):
        """Show notification popup"""
        if type == 'info':
            messagebox.showinfo(title, message)
        elif type == 'warning':
            messagebox.showwarning(title, message)
        elif type == 'error':
            messagebox.showerror(title, message)
        
    def select_images_folder(self):
        f = filedialog.askdirectory(title="Select Images Folder")
        if f:
            self.images_folder = f
            self.load_images()
            self.notify("Success", f"Loaded images from:\n{f}", 'info')
            
    def select_labels_folder(self):
        f = filedialog.askdirectory(title="Select Labels Folder")
        if f:
            self.labels_folder = f
            Path(self.labels_folder).mkdir(parents=True, exist_ok=True)
            self.status.set(f"Labels folder set: {self.labels_folder}")
            self.notify("Success", f"Labels will be saved to:\n{f}", 'info')
    
    def copy_previous(self):
        if self.current_image_idx <= 0:
            self.status.set("⚠ No previous image")
            self.notify("Cannot Copy", "This is the first image!", 'warning')
            return
        
        prev = self.image_files[self.current_image_idx - 1]
        
        for cat in ['garments', 'bags', 'towels', 'caps', '']:
            lbl = (Path(self.labels_folder) / cat / f"{prev.stem}.txt") if cat else (Path(self.labels_folder) / f"{prev.stem}.txt")
            
            if lbl.exists():
                try:
                    self.obb_list.clear()
                    with open(lbl, 'r') as f:
                        for line in f:
                            p = line.strip().split()
                            if len(p) == 9:
                                corners = [(float(p[i])*self.W, float(p[i+1])*self.H) for i in range(1, 8, 2)]
                                self.obb_list.append((corners, p[0]))
                    
                    self.redraw_all()
                    self.update_list()
                    self.update_info()
                    self.status.set(f"✓ Copied {len(self.obb_list)} boxes from previous image")
                    self.notify("Copied!", f"Successfully copied {len(self.obb_list)} annotations from previous image", 'info')
                    return
                except Exception as e:
                    self.notify("Error", f"Failed to copy: {str(e)}", 'error')
                    return
        
        self.status.set("⚠ Previous image has no annotations")
        self.notify("No Annotations", "Previous image has no annotations to copy!", 'warning')
    
    def show_class_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Select Class")
        d.configure(bg='#2b2b2b')
        d.transient(self.root)
        d.grab_set()
        
        sel = tk.StringVar(value=list(CLASS_LABELS.keys())[0])
        
        tk.Label(d, text="Select Class for Polygon", font=('Arial', 14, 'bold'),
                bg='#2b2b2b', fg='white', pady=15).pack()
        
        fr = tk.Frame(d, bg='#1a1a1a', bd=2, relief=tk.SUNKEN)
        fr.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        items = list(CLASS_LABELS.items())
        for i, (cid, cn) in enumerate(items):
            col = i // 6
            row = i % 6
            tk.Radiobutton(fr, text=f"{cid}: {cn}", variable=sel, value=cid,
                          bg='#1a1a1a', fg='white', selectcolor='#2b2b2b',
                          activebackground='#1a1a1a', activeforeground='white',
                          font=('Arial', 10), pady=4, padx=10, anchor='w', cursor='hand2'
                          ).grid(row=row, column=col, sticky='w', padx=5, pady=2)
        
        bf = tk.Frame(d, bg='#2b2b2b')
        bf.pack(fill=tk.X, padx=20, pady=15)
        
        res = {'ok': False, 'id': None}
        
        def ok():
            res['ok'] = True
            res['id'] = sel.get()
            d.destroy()
        
        def cancel():
            res['ok'] = False
            d.destroy()
        
        tk.Button(bf, text="✓ Confirm", command=ok, bg='#28a745', fg='white',
                 font=('Arial', 11, 'bold'), relief=tk.FLAT, padx=30, pady=10, 
                 cursor='hand2').pack(side=tk.LEFT, expand=True, padx=5)
        
        tk.Button(bf, text="✗ Cancel", command=cancel, bg='#dc3545', fg='white',
                 font=('Arial', 11, 'bold'), relief=tk.FLAT, padx=30, pady=10,
                 cursor='hand2').pack(side=tk.RIGHT, expand=True, padx=5)
        
        d.bind('<Return>', lambda e: ok())
        d.bind('<Escape>', lambda e: cancel())
        
        d.update_idletasks()
        dw = max(d.winfo_reqwidth() + 100, 900)
        dh = d.winfo_reqheight()
        
        sw = d.winfo_screenwidth()
        sh = d.winfo_screenheight()
        if dh > sh - 100:
            dh = sh - 100
            
        x = self.root.winfo_x() + (self.root.winfo_width() - dw) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dh) // 2
        x = max(0, min(x, sw - dw))
        y = max(0, min(y, sh - dh))
        
        d.geometry(f"{dw}x{dh}+{x}+{y}")
        self.root.wait_window(d)
        
        return res
            
    def load_images(self):
        if not self.images_folder or not os.path.exists(self.images_folder):
            self.notify("Error", "Invalid images folder!", 'error')
            return
        
        files = set()
        for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            files.update(Path(self.images_folder).rglob(f"*{ext}"))
            files.update(Path(self.images_folder).rglob(f"*{ext.upper()}"))
        
        self.image_files = sorted(list(files))
        
        if not self.image_files:
            self.notify("No Images", "No images found in the selected folder!", 'warning')
            return
        
        self.image_listbox.delete(0, tk.END)
        for img in self.image_files:
            ann = any((Path(self.labels_folder) / c / f"{img.stem}.txt").exists() 
                     for c in ['garments', 'bags', 'towels', 'caps', ''])
            st = "✅" if ann else "○"
            self.image_listbox.insert(tk.END, f"{st} {img.name}")
        
        self.current_image_idx = 0
        self.load_image(0)
        self.update_prog()
        self.status.set(f"Loaded {len(self.image_files)} images")
        
    def filter_list(self, *args):
        t = self.search_var.get().lower()
        self.image_listbox.delete(0, tk.END)
        
        for img in self.image_files:
            if t in img.name.lower():
                ann = any((Path(self.labels_folder) / c / f"{img.stem}.txt").exists() 
                         for c in ['garments', 'bags', 'towels', 'caps', ''])
                st = "✓" if ann else "○"
                self.image_listbox.insert(tk.END, f"{st} {img.name}")
        
    def on_select(self, event):
        s = self.image_listbox.curselection()
        if s:
            n = self.image_listbox.get(s[0])[2:]
            for i, img in enumerate(self.image_files):
                if img.name == n:
                    self.load_image(i)
                    break
        
    def load_image(self, idx):
        if idx < 0 or idx >= len(self.image_files):
            return
        
        if self.auto_save.get() and self.obb_list and self.image_path:
            self.save_to_category('garments', silent=True)
        
        self.current_image_idx = idx
        self.image_path = str(self.image_files[idx])
        self.original_img = cv2.imread(self.image_path)
        
        if self.original_img is None:
            self.notify("Error", f"Failed to load image:\n{self.image_path}", 'error')
            return
        
        self.H, self.W = self.original_img.shape[:2]
        self.polygon_points = []
        self.drawing_polygon = False
        
        self.load_existing()
        self.display()
        self.update_prog()
        self.update_list_title()
        
        n = Path(self.image_path).name
        self.image_info.config(text=f"📄 {n} | {self.W}x{self.H}px")
        self.image_listbox.selection_clear(0, tk.END)
        self.image_listbox.selection_set(idx)
        self.image_listbox.see(idx)
        
    def load_existing(self):
        self.obb_list.clear()
        self.selected_box_idx = None
        
        if not self.labels_folder:
            return
        
        for cat in ['garments', 'bags', 'towels', 'caps', '']:
            lbl = (Path(self.labels_folder) / cat / f"{Path(self.image_path).stem}.txt") if cat else (Path(self.labels_folder) / f"{Path(self.image_path).stem}.txt")
            
            if lbl.exists():
                try:
                    with open(lbl, 'r') as f:
                        for line in f:
                            p = line.strip().split()
                            if len(p) == 9:
                                corners = [(float(p[i])*self.W, float(p[i+1])*self.H) for i in range(1, 8, 2)]
                                self.obb_list.append((corners, p[0]))
                    self.status.set(f"Loaded {len(self.obb_list)} existing annotations")
                    break
                except Exception as e:
                    self.status.set(f"Error loading: {str(e)}")
    
    def prev_image(self):
        if self.image_files and self.current_image_idx > 0:
            self.load_image(self.current_image_idx - 1)
        else:
            self.status.set("⚠ Already at first image")
        
    def next_image(self):
        if self.image_files and self.current_image_idx < len(self.image_files) - 1:
            self.load_image(self.current_image_idx + 1)
        else:
            self.status.set("⚠ Already at last image")
        
    def update_prog(self):
        if self.image_files:
            t = len(self.image_files)
            c = self.current_image_idx + 1
            a = sum(1 for f in self.image_files if any((Path(self.labels_folder) / cat / f"{f.stem}.txt").exists() for cat in ['garments', 'bags', 'towels', 'caps', '']))
            self.progress_label.config(text=f"{c}/{t} | Annotated: {a}/{t} ({a*100//t if t else 0}%)")
            self.stats.config(text=f"📊 {a} images annotated")
        
    def display(self):
        if self.original_img is None:
            return
        
        self.canvas.update()
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        
        self.scale = min((cw-100)/self.W, (ch-100)/self.H, 1.0)
        nw = int(self.W * self.scale)
        nh = int(self.H * self.scale)
        
        self.image_offset_x = (cw - nw) // 2
        self.image_offset_y = (ch - nh) // 2
        
        rgb = cv2.cvtColor(self.original_img, cv2.COLOR_BGR2RGB)
        r = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_LINEAR)
        
        self.photo = ImageTk.PhotoImage(Image.fromarray(r))
        
        self.canvas.delete("all")
        self.canvas.create_image(self.image_offset_x, self.image_offset_y, anchor=tk.NW, image=self.photo, tags='image')
        
        self.redraw_all()
        self.draw_poly()
        self.update_info()
        
    def c2i(self, cx, cy):
        return (cx - self.image_offset_x) / self.scale, (cy - self.image_offset_y) / self.scale
    
    def i2c(self, x, y):
        return x * self.scale + self.image_offset_x, y * self.scale + self.image_offset_y
    
    def on_click(self, e):
        if self.original_img is None:
            return
        
        h = self.get_handle(e.x, e.y)
        b = self.get_box(e.x, e.y)
        
        if h is not None:
            self.mode = 'rot'
            self.selected_box_idx = h
            self.drag_start = (e.x, e.y)
            self.highlight(self.selected_box_idx)
            self.status.set(f"🔄 Rotating box #{self.selected_box_idx + 1}")
        elif b is not None:
            self.mode = 'mov'
            self.selected_box_idx = b
            self.drag_start = (e.x, e.y)
            self.highlight(self.selected_box_idx)
            self.status.set(f"📦 Moving box #{self.selected_box_idx + 1}")
        else:
            ix, iy = self.c2i(e.x, e.y)
            self.polygon_points.append((ix, iy))
            self.drawing_polygon = True
            self.draw_poly()
            self.status.set(f"✏ Drawing polygon ({len(self.polygon_points)} points)")
    
    def on_rclick(self, e):
        if self.drawing_polygon and len(self.polygon_points) >= 3:
            self.complete_polygon()
    
    def cancel_polygon(self):
        if self.drawing_polygon:
            self.polygon_points = []
            self.drawing_polygon = False
            self.redraw_all()
            self.status.set("✗ Polygon cancelled")
    
    def complete_polygon(self):
        """Complete and add the current polygon"""
        if not self.drawing_polygon or len(self.polygon_points) < 3:
            return
        
        if self.calc_area(self.polygon_points) < MIN_AREA:
            self.status.set(f"⚠ Polygon too small (min {MIN_AREA}px²)")
            self.notify("Too Small", f"Polygon area must be at least {MIN_AREA} pixels²", 'warning')
            self.polygon_points = []
            self.drawing_polygon = False
            self.redraw_all()
            return
        
        corners = self.poly2obb(self.polygon_points)
        r = self.show_class_dialog()
        
        if r['ok']:
            self.obb_list.append((corners, r['id']))
            cname = CLASS_LABELS.get(r['id'], r['id'])
            self.status.set(f"✓ Polygon #{len(self.obb_list)} created ({cname})")
        else:
            self.status.set("Polygon creation cancelled")
        
        self.polygon_points = []
        self.drawing_polygon = False
        self.redraw_all()
        self.update_list()
    
    def poly2obb(self, pts):
        """Convert polygon points to OBB (4 corners)"""
        if len(pts) == 4:
            return pts
        pnp = np.array(pts, dtype=np.float32)
        box = cv2.boxPoints(cv2.minAreaRect(pnp))
        return [(float(x), float(y)) for x, y in box]
    
    def calc_area(self, pts):
        if len(pts) < 3:
            return 0
        x = [p[0] for p in pts]
        y = [p[1] for p in pts]
        return 0.5 * abs(sum(x[i]*y[i+1] - x[i+1]*y[i] for i in range(-1, len(pts)-1)))
    
    def draw_poly(self):
        self.canvas.delete('cpoly')
        
        if not self.polygon_points:
            return
        
        # Draw points
        for px, py in self.polygon_points:
            cx, cy = self.i2c(px, py)
            self.canvas.create_oval(cx-4, cy-4, cx+4, cy+4, fill='#00ff00', outline='white', width=2, tags='cpoly')
        
        # Draw lines between points
        if len(self.polygon_points) > 1:
            cp = [self.i2c(x, y) for x, y in self.polygon_points]
            for i in range(len(cp) - 1):
                self.canvas.create_line(cp[i][0], cp[i][1], cp[i+1][0], cp[i+1][1], fill='#00ff00', width=2, tags='cpoly')
            
            # Draw closing line if enough points
            if len(self.polygon_points) >= 3:
                # Draw the closing line to complete the polygon
                self.canvas.create_line(cp[-1][0], cp[-1][1], cp[0][0], cp[0][1], fill='#ffff00', width=2, dash=(5,5), tags='cpoly')
    
    def on_drag(self, e):
        ix, iy = self.c2i(e.x, e.y)
        self.coords.set(f"X: {int(ix)} Y: {int(iy)}")
        
        if self.mode == 'mov' and self.selected_box_idx is not None:
            dx = (e.x - self.drag_start[0]) / self.scale
            dy = (e.y - self.drag_start[1]) / self.scale
            self.drag_start = (e.x, e.y)
            
            c, cid = self.obb_list[self.selected_box_idx]
            nc = [(x+dx, y+dy) for x, y in c]
            self.obb_list[self.selected_box_idx] = (nc, cid)
            self.redraw_box(self.selected_box_idx)
            
        elif self.mode == 'rot' and self.selected_box_idx is not None:
            c, cid = self.obb_list[self.selected_box_idx]
            cx = sum(x for x,y in c)/4
            cy = sum(y for x,y in c)/4
            ccx, ccy = self.i2c(cx, cy)
            
            oa = math.atan2(self.drag_start[1]-ccy, self.drag_start[0]-ccx)
            na = math.atan2(e.y-ccy, e.x-ccx)
            ad = na - oa
            
            ca, sa = math.cos(ad), math.sin(ad)
            nc = [((x-cx)*ca - (y-cy)*sa + cx, (x-cx)*sa + (y-cy)*ca + cy) for x, y in c]
            
            self.obb_list[self.selected_box_idx] = (nc, cid)
            self.drag_start = (e.x, e.y)
            self.redraw_box(self.selected_box_idx)
    
    def on_release(self, e):
        if self.mode in ['mov', 'rot']:
            self.status.set(f"✓ Box #{self.selected_box_idx + 1} updated")
        self.mode = None
        self.drag_start = None
    
    def on_move(self, e):
        if self.mode is None and self.original_img is not None:
            ix, iy = self.c2i(e.x, e.y)
            self.coords.set(f"X: {int(ix)} Y: {int(iy)}")
            
            if self.get_handle(e.x, e.y) is not None:
                self.canvas.config(cursor='exchange')
            elif self.get_box(e.x, e.y) is not None:
                self.canvas.config(cursor='fleur')
            else:
                self.canvas.config(cursor='crosshair')
    
    def on_dclick(self, e):
        b = self.get_box(e.x, e.y)
        if b is not None:
            self.delete_box(b)
    
    def on_list_sel(self, e):
        s = self.ann_listbox.curselection()
        if s:
            self.selected_box_idx = s[0]
            self.highlight(self.selected_box_idx)
            self.update_info()
    
    def get_box(self, cx, cy):
        ix, iy = self.c2i(cx, cy)
        for i, (c, _) in enumerate(self.obb_list):
            if self.pt_in_poly(ix, iy, c):
                return i
        return None
    
    def get_handle(self, cx, cy):
        for i, (c, _) in enumerate(self.obb_list):
            for x, y in c:
                hx, hy = self.i2c(x, y)
                if math.sqrt((cx-hx)**2 + (cy-hy)**2) < 8:
                    return i
        return None
    
    def pt_in_poly(self, x, y, poly):
        n = len(poly)
        inside = False
        p1x, p1y = poly[0]
        for i in range(1, n+1):
            p2x, p2y = poly[i%n]
            if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
                if p1y != p2y:
                    xi = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                if p1x == p2x or x <= xi:
                    inside = not inside
            p1x, p1y = p2x, p2y
        return inside
    
    def redraw_all(self):
        self.canvas.delete('box')
        self.canvas.delete('handle')
        self.canvas.delete('label')
        
        for i, (c, cid) in enumerate(self.obb_list):
            self.draw_box(i, c, cid, sel=(i == self.selected_box_idx))
    
    def redraw_box(self, i):
        if i < len(self.obb_list):
            c, cid = self.obb_list[i]
            self.draw_box(i, c, cid, sel=True, clr=True)
    
    def draw_box(self, i, c, cid, sel=False, clr=False):
        if clr:
            self.canvas.delete(f'box_{i}')
            self.canvas.delete(f'handle_{i}')
            self.canvas.delete(f'label_{i}')
        
        cc = [self.i2c(x, y) for x, y in c]
        pts = []
        for x, y in cc:
            pts.extend([x, y])
        
        col = '#00ffff' if sel else '#ff0000'
        w = 3 if sel else 2
        self.canvas.create_polygon(pts, outline=col, fill='', width=w, tags=('box', f'box_{i}'))
        
        for x, y in cc:
            hc = '#ffff00' if sel else '#ff8800'
            self.canvas.create_oval(x-6, y-6, x+6, y+6, fill=hc, outline='black', width=2, tags=('handle', f'handle_{i}'))
        
        cx = sum(x for x,_ in cc)/4
        cy = sum(y for _,y in cc)/4
        
        self.canvas.create_text(cx, cy-15, text=f"#{i+1}: {CLASS_LABELS.get(cid, cid)}", 
                               fill='#00ff00', font=('Arial', 10, 'bold'), tags=('label', f'label_{i}'))
    
    def highlight(self, i):
        self.redraw_all()
        self.update_info()
    
    def update_info(self):
        self.info_text.delete('1.0', tk.END)
        
        if self.original_img is None:
            self.info_text.insert('1.0', "No image loaded")
            return
        
        n = Path(self.image_path).name
        ann = any((Path(self.labels_folder)/c/f"{Path(self.image_path).stem}.txt").exists() for c in ['garments','bags','towels','caps',''])
        si = "✓" if ann else "○"
        
        h = f"📄 {n} {si}\n{'═'*35}\n\n"
        
        if self.selected_box_idx is not None and self.selected_box_idx < len(self.obb_list):
            c, cid = self.obb_list[self.selected_box_idx]
            cn = CLASS_LABELS.get(cid, cid)
            info = h + f"BOX #{self.selected_box_idx+1}\nClass: {cn} (ID: {cid})\n"
            self.info_text.insert('1.0', info)
        else:
            self.info_text.insert('1.0', h + f"Total Boxes: {len(self.obb_list)}")
    
    def update_list(self):
        self.ann_listbox.delete(0, tk.END)
        for i, (_, cid) in enumerate(self.obb_list):
            self.ann_listbox.insert(tk.END, f"#{i+1}: {CLASS_LABELS.get(cid, cid)}")
        self.update_list_title()
    
    def update_list_title(self):
        self.list_frame.config(text=f"📋 Annotations ({len(self.obb_list)})")
    
    def delete_selected(self):
        if self.selected_box_idx is not None and self.selected_box_idx < len(self.obb_list):
            self.delete_box(self.selected_box_idx)
        else:
            self.status.set("⚠ No box selected")
    
    def delete_box(self, i):
        if 0 <= i < len(self.obb_list):
            cid = self.obb_list[i][1]
            cname = CLASS_LABELS.get(cid, cid)
            self.obb_list.pop(i)
            self.selected_box_idx = None
            self.redraw_all()
            self.update_list()
            self.update_info()
            self.status.set(f"🗑 Deleted box ({cname}). {len(self.obb_list)} boxes remaining")
            self.notify("Deleted", f"Deleted box: {cname}\n{len(self.obb_list)} boxes remaining", 'info')
    
    def undo_last(self):
        if self.obb_list:
            cid = self.obb_list[-1][1]
            cname = CLASS_LABELS.get(cid, cid)
            self.obb_list.pop()
            self.selected_box_idx = None
            self.redraw_all()
            self.update_list()
            self.update_info()
            self.status.set(f"↶ Undone ({cname}). {len(self.obb_list)} boxes remaining")
            self.notify("Undone", f"Removed last box: {cname}\n{len(self.obb_list)} boxes remaining", 'info')
        else:
            self.status.set("⚠ Nothing to undo")
            self.notify("Cannot Undo", "No annotations to undo!", 'warning')
    
    def clear_all(self):
        if self.obb_list:
            count = len(self.obb_list)
            self.obb_list.clear()
            self.selected_box_idx = None
            self.redraw_all()
            self.update_list()
            self.update_info()
            self.status.set("🧹 All boxes cleared")
            self.notify("Cleared", f"Cleared all {count} annotations!", 'info')
        else:
            self.status.set("⚠ No boxes to clear")
            self.notify("Nothing to Clear", "No annotations to clear!", 'warning')
    
    def save_to_category(self, cat, silent=False):
        """Save annotations to category folder - automatically completes any unfinished polygon"""
        
        # Check if there's an unfinished polygon being drawn
        if self.drawing_polygon and len(self.polygon_points) >= 3:
            # Automatically complete the polygon before saving
            self.complete_polygon()
            if not silent:
                self.status.set("✓ Polygon auto-completed before saving")
        
        if not self.obb_list:
            if not silent:
                self.status.set("⚠ No annotations to save")
                self.notify("Nothing to Save", "No annotations to save!", 'warning')
            return
        
        if not self.image_path or not self.labels_folder:
            if not silent:
                self.notify("Error", "No image path or labels folder set!", 'error')
            return
        
        cf = Path(self.labels_folder) / cat
        cf.mkdir(parents=True, exist_ok=True)
        
        out = cf / f"{Path(self.image_path).stem}.txt"
        
        try:
            with open(out, "w") as f:
                for c, cid in self.obb_list:
                    nc = [(x/self.W, y/self.H) for x, y in c]
                    line = cid + "".join(f" {x:.6f} {y:.6f}" for x, y in nc)
                    f.write(line + "\n")
            
            if not silent:
                self.status.set(f"💾 Saved {len(self.obb_list)} annotations → {cat.upper()}")
                self.notify("Saved!", f"Successfully saved {len(self.obb_list)} annotations to {cat.upper()} category!\n\nFile: {out.name}", 'info')
            else:
                self.status.set(f"Auto-saved {len(self.obb_list)} annotations → {cat.upper()}")
            
            self.filter_list()
            self.update_prog()
        except Exception as e:
            if not silent:
                self.status.set(f"❌ Save failed: {str(e)}")
                self.notify("Save Failed", f"Failed to save annotations:\n{str(e)}", 'error')

if __name__ == "__main__":
    root = tk.Tk()
    app = OBBAnnotator(root)
    root.mainloop()