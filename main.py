import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import time

from excel_reader import read_excel
from image_locator import find_image, find_logo, find_image_candidates
from coordinate_detector import get_location_coordinates
from photoshop_batch_manager_min import PhotoshopBatchManager
from utils import detect_garment_type_from_location, compute_logo_size, parse_custom_size
from logger import log_error


# ============================================================
#               DYNAMIC GUI INPUTS (TKINTER)
# ============================================================

class AutomationGUI:
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

        self.excel_path = None
        self.image_root = None
        self.logo_root = None
        self.processing = False
        self.total_rows = 0
        self.processed_rows = 0
        self.start_time = None

        # UI Layout
        self.build_ui()

    def build_ui(self):
        # Title
        title_label = tk.Label(
            self.root, 
            text="Photoshop Automation", 
            font=("Arial", 16, "bold"), 
            fg="#003366"
        )
        title_label.pack(pady=10)

        # Main Frame for inputs
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=20, pady=5, fill=tk.BOTH, expand=True)

        # ===== INPUT 1: Excel File =====
        excel_frame = tk.LabelFrame(main_frame, text="1️⃣  Excel File", font=("Arial", 10, "bold"), padx=8, pady=5, bg="#E3F2FD")
        excel_frame.pack(fill=tk.X, pady=3)
        
        self.excel_label = tk.Label(excel_frame, text="No file selected", font=("Arial", 9), fg="red", bg="#E3F2FD")
        self.excel_label.pack(anchor=tk.W, pady=2)
        tk.Button(excel_frame, text="📁 Browse Excel File", command=self.select_excel, bg="#4CAF50", fg="white", width=35, height=1).pack(pady=2)

        # ===== INPUT 2: Image Folder =====
        image_frame = tk.LabelFrame(main_frame, text="2️⃣  Images Folder", font=("Arial", 10, "bold"), padx=8, pady=5, bg="#E3F2FD")
        image_frame.pack(fill=tk.X, pady=3)
        
        self.image_label = tk.Label(image_frame, text="No folder selected", font=("Arial", 9), fg="red", bg="#E3F2FD")
        self.image_label.pack(anchor=tk.W, pady=2)
        tk.Button(image_frame, text="📁 Browse Images Folder", command=self.select_image_folder, bg="#2196F3", fg="white", width=35, height=1).pack(pady=2)

        # ===== INPUT 3: Logo Folder =====
        logo_frame = tk.LabelFrame(main_frame, text="3️⃣  Logos Folder", font=("Arial", 10, "bold"), padx=8, pady=5, bg="#E3F2FD")
        logo_frame.pack(fill=tk.X, pady=3)
        
        self.logo_label = tk.Label(logo_frame, text="No folder selected", font=("Arial", 9), fg="red", bg="#E3F2FD")
        self.logo_label.pack(anchor=tk.W, pady=2)
        tk.Button(logo_frame, text="📁 Browse Logos Folder", command=self.select_logo_folder, bg="#FF9800", fg="white", width=35, height=1).pack(pady=2)

        # ===== PROGRESS SECTION =====
        progress_frame = tk.LabelFrame(self.root, text="📊 Progress", font=("Arial", 10, "bold"), padx=10, pady=8)
        progress_frame.pack(padx=20, pady=8, fill=tk.X)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=400, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)

        # Progress label
        self.progress_label = tk.Label(progress_frame, text="Ready to process", font=("Arial", 9), fg="#666")
        self.progress_label.pack(anchor=tk.W, pady=2)

        # Time estimate label
        self.time_label = tk.Label(progress_frame, text="Estimated time: --", font=("Arial", 9), fg="#666")
        self.time_label.pack(anchor=tk.W, pady=2)

        # Start Button
        self.start_button = tk.Button(
            self.root, 
            text="▶ START AUTOMATION", 
            font=("Arial", 11, "bold"), 
            command=self.start_automation, 
            state=tk.DISABLED, 
            bg="#1B5E20", 
            fg="white", 
            height=2,
            cursor="hand2"
        )
        self.start_button.pack(pady=8, padx=20, fill=tk.X)

    def select_excel(self):
        path = filedialog.askopenfilename(
            title="Select Excel Data File",
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
        )
        if path:
            self.excel_path = path
            filename = os.path.basename(path)
            self.excel_label.config(text=f"✓ {filename}", fg="green")
            self.check_enable_start()

    def select_image_folder(self):
        path = filedialog.askdirectory(title="Select Images Folder")
        if path:
            self.image_root = path
            foldername = os.path.basename(path) or path
            self.image_label.config(text=f"✓ {foldername}", fg="green")
            self.check_enable_start()

    def select_logo_folder(self):
        path = filedialog.askdirectory(title="Select Logos Folder")
        if path:
            self.logo_root = path
            foldername = os.path.basename(path) or path
            self.logo_label.config(text=f"✓ {foldername}", fg="green")
            self.check_enable_start()

    def check_enable_start(self):
        if self.excel_path and self.image_root and self.logo_root:
            self.start_button.config(state=tk.NORMAL, cursor="hand2")
        else:
            self.start_button.config(state=tk.DISABLED, cursor="arrow")

    def start_automation(self):
        self.start_button.config(state=tk.DISABLED, text="⏳ PROCESSING...")
        self.processing = True
        self.start_time = time.time()
        self.root.update()
        
        # Run automation in separate thread to keep GUI responsive
        thread = threading.Thread(target=self.run_automation_thread, daemon=True)
        thread.start()

    def run_automation_thread(self):
        success = run_automation(self.excel_path, self.image_root, self.logo_root, self)
        
        self.processing = False
        if success:
            messagebox.showinfo("✓ Success", "Automation Completed Successfully!\n\nCheck 'assets/output/' folder for results.")
        else:
            messagebox.showerror("✗ Error", "Automation failed. Check console for details.")
        
        self.root.destroy()

    def update_progress(self, current, total):
        """Update progress bar and estimated time"""
        if total == 0:
            return
        
        self.total_rows = total
        self.processed_rows = current
        percentage = (current / total) * 100
        self.progress_var.set(percentage)
        
        # Update progress label
        self.progress_label.config(text=f"Processing: {current}/{total} rows ({percentage:.1f}%)")
        
        # Estimate remaining time
        if current > 0 and self.start_time:
            elapsed = time.time() - self.start_time
            avg_time_per_row = elapsed / current
            remaining_rows = total - current
            estimated_remaining = avg_time_per_row * remaining_rows
            
            minutes = int(estimated_remaining // 60)
            seconds = int(estimated_remaining % 60)
            self.time_label.config(text=f"Estimated time remaining: {minutes}m {seconds}s")
        
        self.root.update()


# ============================================================
#              AUTOMATION WITH DYNAMIC INPUTS
# ============================================================

def run_automation(excel_path, image_root, logo_root, gui=None):
    """
    Main automation function with dynamic inputs
    Returns True if successful, False otherwise
    """
    print("\n" + "="*70)
    print("                 PHOTOSHOP BATCH AUTOMATION")
    print("="*70)

    # ===== VALIDATION =====
    if not os.path.exists(excel_path):
        print(f"[ERROR] Excel file not found: {excel_path}")
        if gui:
            messagebox.showerror("Error", f"Excel file not found:\n{excel_path}")
        return False

    if not os.path.isdir(image_root):
        print(f"[ERROR] Image folder not found: {image_root}")
        if gui:
            messagebox.showerror("Error", f"Image folder not found:\n{image_root}")
        return False

    if not os.path.isdir(logo_root):
        print(f"[ERROR] Logo folder not found: {logo_root}")
        if gui:
            messagebox.showerror("Error", f"Logo folder not found:\n{logo_root}")
        return False

    # ===== LOAD EXCEL =====
    rows = read_excel(excel_path)
    if not rows:
        print("[ERROR] No valid rows found in Excel.")
        if gui:
            messagebox.showerror("Error", "No valid rows found in Excel file.")
        return False

    # ===== PRINT CONFIGURATION =====
    print(f"\n[CONFIG] Excel: {os.path.basename(excel_path)}")
    print(f"[CONFIG] Images: {image_root}")
    print(f"[CONFIG] Logos: {logo_root}")
    print(f"[CONFIG] Total rows to process: {len(rows)}")
    print("-"*70)

    processed = 0
    failed = 0
    try:
        # ===== INITIALIZE BATCH MANAGER =====
        batch_mgr = PhotoshopBatchManager(max_items_per_batch=200)
        print("HI")
    except Exception as e:
        print("BATCH ERROR:",str(e))
    # ===== PROCESS EACH ROW =====
    try:
        for idx, row in enumerate(rows, 1):
            # print("ROW>>>>>>>>>>>>>>>>>>>>>",row)
            # Update progress GUI
            if gui:
                gui.update_progress(idx - 1, len(rows))
            
            product_id      = row.get("Product ID")
            supplier_name   = row.get("Supplier Name")
            part_id         = row.get("Supplier Part ID")
            color           = row.get("Supplier Color")
            decoration_code = row.get("Decoration Code")
            location_name   = row.get("Decoration Location")
            custom_logo_size   = row.get("Custom Logo Size")
            final_name      = str(row.get("Final Image Name")).split(".jpg")[0]

            try:
                # Find image candidates + logo
                candidates = find_image_candidates(image_root, supplier_name, part_id, color, location_name)
                if not candidates:
                    print(f"[{idx:3d}/{len(rows)}] [SKIP] Image not found for '{final_name}'")
                    failed += 1
                    continue

                logo_path = find_logo(logo_root, decoration_code)
                if not logo_path:
                    print(f"[{idx:3d}/{len(rows)}] [SKIP] Logo not found for '{decoration_code}'")
                    failed += 1
                    continue

                # Determine garment type (used for canvas and logo sizing)
                garment_type = detect_garment_type_from_location(location_name)

                # Resolve custom logo size: prefer Excel provided size, else compute
                parsed = parse_custom_size(custom_logo_size)
                # print(f"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX Row {idx}: Custom logo size text: '{custom_logo_size}' → parsed: {parsed}")
                if parsed:
                    logo_dims = (float(parsed[0]), float(parsed[1]))
                else:
                    print("ELSE-----------------------------------------")
                    try:
                        logo_dims = compute_logo_size(garment_type, logo_path, location_name)
                    except Exception:
                        logo_dims = (99.0, 99.0)

                # Try candidates sequentially — only log row failure after exhausting them
                success = False
                first_error = None
                target_name = f"{part_id} {color}.jpg"

                for image_path in candidates:
                    try:
                        coords = get_location_coordinates(image_path, location_name)
                        ok = batch_mgr.add_pair(
                            part_id,
                            image_path,
                            logo_path,
                            target_name,
                            decoration_code,
                            location_name,
                            coords,
                            garment_type,
                            logo_dims,
                            final_name,
                        )

                        if ok:
                            processed += 1
                            print(f"[{idx:3d}/{len(rows)}] [✓ OK] {final_name}")
                            success = True
                            break
                        else:
                            # try next candidate
                            continue

                    except Exception as e:
                        if first_error is None:
                            first_error = e
                        # try next candidate
                        continue

                if not success:
                    failed += 1
                    err_msg = str(first_error) if first_error else "No candidate produced a valid result"
                    log_error(f"Row failed: {err_msg}")
                    print(f"[{idx:3d}/{len(rows)}] [✗ FAIL] {final_name}")

            except Exception as e:
                log_error(f"Error in row {idx - 1} : {final_name}: {e}")
                failed += 1
                print(f"[{idx:3d}/{len(rows)}] [✗ ERROR] {final_name}")
                print(f"          Exception: {str(e)[:60]}")
                continue
    except Exception as e:
        print("FOR LOOP ERROR>>>>>>>>>>>>>>>",str(e))
    # ===== FINALIZE REMAINING BATCHES =====
    batch_mgr.finalize()

    # Update progress to 100%
    if gui:
        gui.update_progress(len(rows), len(rows))
        gui.time_label.config(text="✅ Completed!")

    # ===== PRINT RESULTS =====
    print("-"*70)
    print(f"\n[RESULT] Total Processed: {processed}/{len(rows)}")
    print(f"[RESULT] Failed/Skipped: {failed}/{len(rows)}")
    print("\n[OUTPUT] Files saved to:")
    print(f"         📁 PSD Files: assets/output/photoshop/")
    print(f"         📁 JPG Files: assets/output/For Printing/")
    print("\n" + "="*70 + "\n")
    
    return True


# ============================================================
#                     PROGRAM ENTRY
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    gui = AutomationGUI(root)
    root.mainloop()