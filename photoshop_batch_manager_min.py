import os
import win32com.client
from logger import log_error
from config import PSD_OUTPUT_DIR, IMAGE_OUTPUT_DIR
from photoshop_engine import prepare_pair_doc


class PhotoshopBatchManager:
    def __init__(self, max_items_per_batch=200):
        print("Initializing PhotoshopBatchManager...")
        self.app = win32com.client.Dispatch("Photoshop.Application")
        # Visible True helps debugging; set False if you want headless
        self.app.Visible = True
        self.batch_index = 1
        self.items_in_batch = 0
        self.batch_doc = None
        self.max_items = max_items_per_batch
        print("PhotoshopBatchManager initialized.")

    def _save_and_close_batch(self):
        if not self.batch_doc:
            return
        try:
            os.makedirs(PSD_OUTPUT_DIR, exist_ok=True)
            batch_name = f"Batch_{self.batch_index}.psd"
            psd_path = os.path.join(PSD_OUTPUT_DIR, batch_name)
            options = win32com.client.Dispatch("Photoshop.PhotoshopSaveOptions")
            self.batch_doc.SaveAs(psd_path, options, True)
            try:
                self.batch_doc.Close(2)
            except Exception:
                pass
            print(f"[BATCH] Saved and closed: {batch_name}")
        except Exception as e:
            log_error(f"Failed to save/close batch {self.batch_index}: {e}")
        finally:
            self.batch_doc = None

    def finalize(self):
        if self.batch_doc and self.items_in_batch > 0:
            self._save_and_close_batch()

    def _run_save_for_web_js(self, export_path):
        """
        Run an ExtendScript (JSX) to perform Save For Web (Legacy) with JPEG High preset.
        export_path should be a full Windows path string (escaped).
        """
        # Escape backslashes for JS string literal
        js_path = export_path.replace("\\", "\\\\").replace('"', '\\"')

        jsx = f'''
        // Save For Web (Legacy) export via script
        try {{
            var file = new File("{js_path}");
            var opts = new ExportOptionsSaveForWeb();
            opts.format = SaveDocumentType.JPEG;
            opts.includeProfile = false;
            opts.optimized = true;
            opts.interlaced = false;
            opts.quality = 60; // JPEG High
            // Perform export on active document
            app.activeDocument.exportDocument(file, ExportType.SAVEFORWEB, opts);
            "OK";
        }} catch(e) {{
            throw(e);
        }}
        '''
        try:
            result = self.app.DoJavaScript(jsx)
            return True
        except Exception as e:
            log_error(f"DoJavaScript SaveForWeb failed for path {export_path}: {e}")
            return False

    def add_pair(self, part_id, image_path, logo_path, target_name, decoration_code, location_name, coordinates, garment_type, custom_logo_size, final_name):
        # Defensive: coordinates must be present (pose detection may fail)
        if coordinates is None:
            ctx = {
                'part_id': part_id,
                'target_name': target_name,
                'image_path': image_path,
                'logo_path': logo_path,
                'location_name': location_name,
                'coordinates': coordinates,
                'garment_type': garment_type,
                'custom_logo_size': custom_logo_size,
                'final_name': final_name,
                'image_exists': os.path.exists(image_path) if image_path else False,
                'logo_exists': os.path.exists(logo_path) if logo_path else False,
            }
            log_error(f"Skipping pair because coordinates missing for {target_name} | context: {ctx}")
            return False

        # Create temp doc with placed logo
        temp_doc = prepare_pair_doc(image_path, logo_path, location_name, coordinates, garment_type, custom_logo_size, decoration_code, target_name)
        if temp_doc is None:
            # Provide richer diagnostics when prepare_pair_doc fails
            ctx = {
                'part_id': part_id,
                'target_name': target_name,
                'image_path': image_path,
                'logo_path': logo_path,
                'location_name': location_name,
                'coordinates': coordinates,
                'garment_type': garment_type,
                'custom_logo_size': custom_logo_size,
                'final_name': final_name,
                'image_exists': os.path.exists(image_path) if image_path else False,
                'logo_exists': os.path.exists(logo_path) if logo_path else False,
            }
            log_error(f"prepare_pair_doc failed for {target_name} | context: {ctx}")
            return False

        # find layers
        try:
            layers = temp_doc.ArtLayers
            image_layer = None
            logo_layer = None
            # Note: COM collections are 0-indexed in your earlier code usage
            for i in range(1, layers.Count + 1):
                l = layers[i-1]
                name = getattr(l, 'Name', '')
                if name == target_name and image_layer is None:
                    image_layer = l
                if name == decoration_code and logo_layer is None:
                    logo_layer = l
            if image_layer is None:
                # fallback heuristics
                try:
                    image_layer = layers[layers.Count-1]
                except Exception:
                    image_layer = None
            if logo_layer is None:
                try:
                    logo_layer = layers[0]
                except Exception:
                    logo_layer = None
        except Exception as e:
            log_error(f"Failed to read layers from temp doc for {target_name}: {e}")
            try:
                temp_doc.Close(2)
            except Exception:
                pass
            return False

        # Export the merged image (logo on image) as JPG using Save For Web (Legacy)
        try:
            # Determine canvas size based on garment type
            canvas_width = 1200
            canvas_height = 1800 if garment_type == "T-SHIRT" else 1200
            canvas_folder = f"{canvas_width} x {canvas_height}"

            # Create dynamic folder structure: For Printing/[canvas dimensions]/
            for_printing_dir = os.path.join(IMAGE_OUTPUT_DIR, canvas_folder)
            os.makedirs(for_printing_dir, exist_ok=True)

            jpg_filename = final_name.replace('.jpg', '') if final_name.endswith('.jpg') else final_name
            jpg_path = os.path.join(for_printing_dir, f"{jpg_filename}.jpg")

            # Duplicate temp_doc for exporting (keeps original temp_doc intact for duplication into batch PSD)
            export_doc = temp_doc.Duplicate()

            # Make sure export_doc is the active document
            self.app.ActiveDocument = export_doc

            # Flatten export_doc to merge logo + image
            try:
                export_doc.Flatten()
            except Exception:
                # If flatten fails, continue — SaveForWeb will still operate on merged visible layers
                pass

            # Use ExtendScript Save For Web to get exact UI-like JPEG High behavior
            ok = self._run_save_for_web_js(jpg_path)
            if not ok:
                # fallback: attempt a SaveAs with conservative jpeg settings (smaller quality)
                try:
                    jpg_options = win32com.client.Dispatch("Photoshop.JPEGSaveOptions")
                    jpg_options.Quality = 6
                    export_doc.SaveAs(jpg_path, jpg_options, True)
                except Exception as e:
                    log_error(f"Fallback SaveAs JPG failed for {jpg_path}: {e}")

            # Close export_doc
            try:
                export_doc.Close(2)
            except Exception:
                pass

        except Exception as e:
            log_error(f"Failed to export JPG for {final_name}: {e}")
            try:
                temp_doc.Close(2)
            except Exception:
                pass
            return False

        # ensure batch doc
        try:
            if self.batch_doc is None:
                width = float(temp_doc.Width)
                height = float(temp_doc.Height)
                res = float(getattr(temp_doc, 'Resolution', 150))
                name = f"Batch_{self.batch_index}"
                # Create a new blank document for batch with same dimensions & resolution
                # Use RGB, 8 bits/channel (defaults)
                self.batch_doc = self.app.Documents.Add(width, height, res, name)
                self.items_in_batch = 0
        except Exception as e:
            log_error(f"Failed to create batch doc: {e}")
            try:
                temp_doc.Close(2)
            except Exception:
                pass
            return False

        # ensure group (LayerSet) exists for the product id at root level of PSD
        try:
            self.app.ActiveDocument = self.batch_doc
            layer_sets = self.batch_doc.LayerSets
            target_set = None
            for i in range(1, layer_sets.Count + 1):
                try:
                    s = layer_sets[i-1]
                    if s.Name == str(part_id):
                        target_set = s
                        break
                except Exception:
                    continue
            if target_set is None:
                target_set = layer_sets.Add()
                target_set.Name = str(part_id)
        except Exception as e:
            log_error(f"Failed to create/get LayerSet for {part_id}: {e}")
            try:
                temp_doc.Close(2)
            except Exception:
                pass
            return False

        # duplicate into group: image then logo
        try:
            self.app.ActiveDocument = temp_doc
            # Duplicate image and logo layers into the LayerSet (target_set)
            if image_layer is not None:
                image_layer.Duplicate(target_set)
            if logo_layer is not None:
                logo_layer.Duplicate(target_set)
            try:
                temp_doc.Close(2)
            except Exception:
                pass
        except Exception as e:
            log_error(f"Failed to duplicate layers into group for {part_id}: {e}")
            try:
                temp_doc.Close(2)
            except Exception:
                pass
            return False

        # rename top two if possible (attempt to name decoration_code first, then image layer)
        try:
            self.app.ActiveDocument = self.batch_doc
            group_layers = target_set.ArtLayers
            # Rename last two added layers if they exist
            # Note: layer order inside target_set depends on Duplicate behavior; attempt both ways
            try:
                if group_layers.Count >= 1:
                    # attempt to find and name layer matching decoration_code / target_name
                    for j in range(1, group_layers.Count + 1):
                        ly = group_layers[j-1]
                        # best-effort naming: if layer already matches skip
                        if getattr(ly, "Name", "") == decoration_code:
                            pass
                    # Finally try to set last two layers names (safest attempt)
                    if group_layers.Count >= 2:
                        group_layers[0].Name = decoration_code
                        group_layers[1].Name = target_name
                    elif group_layers.Count == 1:
                        group_layers[0].Name = target_name
            except Exception:
                pass
        except Exception:
            pass

        # increment count (each pair counts as 1 item)
        self.items_in_batch += 1

        # if reached max items -> save and open next batch
        if self.items_in_batch >= self.max_items:
            try:
                self._save_and_close_batch()
            except Exception as e:
                log_error(f"Failed to finalize batch {self.batch_index}: {e}")
            self.batch_index += 1
            self.items_in_batch = 0

        return True