import os
import win32com.client
import pythoncom
from services.logger import logError
from core.config import PSD_OUTPUT_DIR, IMAGE_OUTPUT_DIR
from .photoshopEngine import preparePairDoc


class PhotoshopBatchManager:
    """Manages batch processing of images in Photoshop."""
    
    def __init__(self, maxItemsPerBatch=200):
        print("Initializing PhotoshopBatchManager...")
        # Initialize COM for this thread (required when called from a different thread)
        pythoncom.CoInitialize()
        self.app = win32com.client.Dispatch("Photoshop.Application")
        self.app.Visible = True
        self.batchIndex = 1
        self.itemsInBatch = 0
        self.batchDoc = None
        self.maxItems = maxItemsPerBatch
        print("PhotoshopBatchManager initialized.")

    def _saveAndCloseBatch(self):
        """Save and close current batch document."""
        if not self.batchDoc:
            return
        try:
            os.makedirs(PSD_OUTPUT_DIR, exist_ok=True)
            batchName = f"Batch_{self.batchIndex}.psd"
            psdPath = os.path.join(PSD_OUTPUT_DIR, batchName)
            options = win32com.client.Dispatch("Photoshop.PhotoshopSaveOptions")
            self.batchDoc.SaveAs(psdPath, options, True)
            try:
                self.batchDoc.Close(2)
            except Exception:
                pass
            print(f"[BATCH] Saved and closed: {batchName}")
        except Exception as e:
            logError(f"Failed to save/close batch {self.batchIndex}: {e}")
        finally:
            self.batchDoc = None

    def finalize(self):
        """Finalize any remaining batch items."""
        if self.batchDoc and self.itemsInBatch > 0:
            self._saveAndCloseBatch()

    def _runSaveForWebJs(self, exportPath):
        """Run ExtendScript for Save For Web export."""
        jsPath = exportPath.replace("\\", "\\\\").replace('"', '\\"')

        jsx = f'''
        try {{
            var file = new File("{jsPath}");
            var opts = new ExportOptionsSaveForWeb();
            opts.format = SaveDocumentType.JPEG;
            opts.includeProfile = false;
            opts.optimized = true;
            opts.interlaced = false;
            opts.quality = 60;
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
            logError(f"DoJavaScript SaveForWeb failed for path {exportPath}: {e}")
            return False

    def addCombo(self, partId, imagePath, logoPath, targetName, decorationCode,
                 positionsList, coordinatesList, rotationsList, garmentType, customLogoSize, finalName, canvasHeight=1200):
        """Add image with multiple logos (combo position) - creates ONE output image."""
        from .photoshopEngine import prepareComboPairDoc
        
        # All coordinates must be present
        if not coordinatesList or None in coordinatesList:
            logError(f"Skipping combo because some coordinates missing for {targetName}")
            return False
        
        # Create doc with ALL logos placed (with rotation)
        tempDoc = prepareComboPairDoc(imagePath, logoPath, positionsList, coordinatesList, rotationsList,
                                       garmentType, customLogoSize, decorationCode, targetName, canvasHeight)
        if tempDoc is None:
            logError(f"prepareComboPairDoc failed for {targetName}")
            return False

        # Export the merged image as JPG (one image with all logos)
        try:
            canvasWidth = 1200
            # canvasHeight = 1800 if garmentType == "T-SHIRT" else 1200 <-- REMOVED
            canvasFolder = f"{canvasWidth} x {canvasHeight}"

            forPrintingDir = os.path.join(IMAGE_OUTPUT_DIR, canvasFolder)
            os.makedirs(forPrintingDir, exist_ok=True)

            jpgFilename = finalName.replace('.jpg', '') if finalName.endswith('.jpg') else finalName
            jpgPath = os.path.join(forPrintingDir, f"{jpgFilename}.jpg")

            exportDoc = tempDoc.Duplicate()
            self.app.ActiveDocument = exportDoc

            try:
                exportDoc.Flatten()
            except Exception:
                pass

            ok = self._runSaveForWebJs(jpgPath)
            if not ok:
                try:
                    jpgOptions = win32com.client.Dispatch("Photoshop.JPEGSaveOptions")
                    jpgOptions.Quality = 6
                    exportDoc.SaveAs(jpgPath, jpgOptions, True)
                except Exception as e:
                    logError(f"Fallback SaveAs JPG failed for {jpgPath}: {e}")

            try:
                exportDoc.Close(2)
            except Exception:
                pass

        except Exception as e:
            logError(f"Failed to export combo JPG for {finalName}: {e}")
            try:
                tempDoc.Close(2)
            except Exception:
                pass
            return False

        # Add layers to batch PSD (image layer + all logo layers)
        try:
            # Ensure batch doc exists
            if self.batchDoc is None:
                width = float(tempDoc.Width)
                height = float(tempDoc.Height)
                res = float(getattr(tempDoc, 'Resolution', 150))
                name = f"Batch_{self.batchIndex}"
                self.batchDoc = self.app.Documents.Add(width, height, res, name)
                self.itemsInBatch = 0

            # Ensure group exists for the product id
            self.app.ActiveDocument = self.batchDoc
            layerSets = self.batchDoc.LayerSets
            targetSet = None
            for i in range(1, layerSets.Count + 1):
                try:
                    s = layerSets[i-1]
                    if s.Name == str(partId):
                        targetSet = s
                        break
                except Exception:
                    continue
            if targetSet is None:
                targetSet = layerSets.Add()
                targetSet.Name = str(partId)

            # Duplicate ALL layers from tempDoc into the group
            # Iterate in REVERSE order (bottom to top) so they stack correctly in target
            # tempDoc layers: [Top Logo, ..., Bottom Image]
            # Duplicating Base Image first -> then Logos on top
            self.app.ActiveDocument = tempDoc
            layers = tempDoc.ArtLayers
            for i in range(layers.Count - 1, -1, -1):
                try:
                    layer = layers[i]
                    layer.Duplicate(targetSet)
                except Exception:
                    pass
            try:
                tempDoc.Close(2)
            except Exception:
                pass

        except Exception as e:
            logError(f"Failed to add combo layers to batch for {partId}: {e}")
            try:
                tempDoc.Close(2)
            except Exception:
                pass

        self.itemsInBatch += 1

        # Save and start new batch if max items reached
        if self.itemsInBatch >= self.maxItems:
            try:
                self._saveAndCloseBatch()
            except Exception as e:
                logError(f"Failed to finalize batch {self.batchIndex}: {e}")
            self.batchIndex += 1
            self.itemsInBatch = 0

        return True

    def addPair(self, partId, imagePath, logoPath, targetName, decorationCode, 
                locationName, coordinates, rotation, garmentType, customLogoSize, finalName, canvasHeight=1200):
        """Add image-logo pair to batch."""
        # Coordinates must be present
        if coordinates is None:
            ctx = {
                'partId': partId,
                'targetName': targetName,
                'imagePath': imagePath,
                'logoPath': logoPath,
                'locationName': locationName,
                'coordinates': coordinates,
                'garmentType': garmentType,
                'customLogoSize': customLogoSize,
                'finalName': finalName,
                'imageExists': os.path.exists(imagePath) if imagePath else False,
                'logoExists': os.path.exists(logoPath) if logoPath else False,
            }
            logError(f"Skipping pair because coordinates missing for {targetName} | context: {ctx}")
            return False

        # Create temp doc with placed logo (with rotation)
        tempDoc = preparePairDoc(imagePath, logoPath, locationName, coordinates, rotation,
                                  garmentType, customLogoSize, decorationCode, targetName, canvasHeight)
        if tempDoc is None:
            ctx = {
                'partId': partId,
                'targetName': targetName,
                'imagePath': imagePath,
                'logoPath': logoPath,
                'locationName': locationName,
                'coordinates': coordinates,
                'garmentType': garmentType,
                'customLogoSize': customLogoSize,
                'finalName': finalName,
                'imageExists': os.path.exists(imagePath) if imagePath else False,
                'logoExists': os.path.exists(logoPath) if logoPath else False,
            }
            logError(f"preparePairDoc failed for {targetName} | context: {ctx}")
            return False

        # Find layers
        try:
            layers = tempDoc.ArtLayers
            imageLayer = None
            logoLayer = None
            for i in range(1, layers.Count + 1):
                l = layers[i-1]
                name = getattr(l, 'Name', '')
                if name == targetName and imageLayer is None:
                    imageLayer = l
                if name == decorationCode and logoLayer is None:
                    logoLayer = l
            if imageLayer is None:
                try:
                    imageLayer = layers[layers.Count-1]
                except Exception:
                    imageLayer = None
            if logoLayer is None:
                try:
                    logoLayer = layers[0]
                except Exception:
                    logoLayer = None
        except Exception as e:
            logError(f"Failed to read layers from temp doc for {targetName}: {e}")
            try:
                tempDoc.Close(2)
            except Exception:
                pass
            return False

        # Export the merged image as JPG
        try:
            canvasWidth = 1200
            # canvasHeight passed in argument is used
            canvasFolder = f"{canvasWidth} x {canvasHeight}"

            forPrintingDir = os.path.join(IMAGE_OUTPUT_DIR, canvasFolder)
            os.makedirs(forPrintingDir, exist_ok=True)

            jpgFilename = finalName.replace('.jpg', '') if finalName.endswith('.jpg') else finalName
            jpgPath = os.path.join(forPrintingDir, f"{jpgFilename}.jpg")

            exportDoc = tempDoc.Duplicate()
            self.app.ActiveDocument = exportDoc

            try:
                exportDoc.Flatten()
            except Exception:
                pass

            ok = self._runSaveForWebJs(jpgPath)
            if not ok:
                try:
                    jpgOptions = win32com.client.Dispatch("Photoshop.JPEGSaveOptions")
                    jpgOptions.Quality = 6
                    exportDoc.SaveAs(jpgPath, jpgOptions, True)
                except Exception as e:
                    logError(f"Fallback SaveAs JPG failed for {jpgPath}: {e}")

            try:
                exportDoc.Close(2)
            except Exception:
                pass

        except Exception as e:
            logError(f"Failed to export JPG for {finalName}: {e}")
            try:
                tempDoc.Close(2)
            except Exception:
                pass
            return False

        # Ensure batch doc exists
        try:
            if self.batchDoc is None:
                width = float(tempDoc.Width)
                height = float(tempDoc.Height)
                res = float(getattr(tempDoc, 'Resolution', 150))
                name = f"Batch_{self.batchIndex}"
                self.batchDoc = self.app.Documents.Add(width, height, res, name)
                self.itemsInBatch = 0
        except Exception as e:
            logError(f"Failed to create batch doc: {e}")
            try:
                tempDoc.Close(2)
            except Exception:
                pass
            return False

        # Ensure group exists for the product id
        try:
            self.app.ActiveDocument = self.batchDoc
            layerSets = self.batchDoc.LayerSets
            targetSet = None
            for i in range(1, layerSets.Count + 1):
                try:
                    s = layerSets[i-1]
                    if s.Name == str(partId):
                        targetSet = s
                        break
                except Exception:
                    continue
            if targetSet is None:
                targetSet = layerSets.Add()
                targetSet.Name = str(partId)
        except Exception as e:
            logError(f"Failed to create/get LayerSet for {partId}: {e}")
            try:
                tempDoc.Close(2)
            except Exception:
                pass
            return False

        # Duplicate layers into group
        try:
            self.app.ActiveDocument = tempDoc
            if imageLayer is not None:
                imageLayer.Duplicate(targetSet)
            if logoLayer is not None:
                logoLayer.Duplicate(targetSet)
            try:
                tempDoc.Close(2)
            except Exception:
                pass
        except Exception as e:
            logError(f"Failed to duplicate layers into group for {partId}: {e}")
            try:
                tempDoc.Close(2)
            except Exception:
                pass
            return False

        # Rename layers if possible
        try:
            self.app.ActiveDocument = self.batchDoc
            groupLayers = targetSet.ArtLayers
            try:
                if groupLayers.Count >= 1:
                    for j in range(1, groupLayers.Count + 1):
                        ly = groupLayers[j-1]
                        if getattr(ly, "Name", "") == decorationCode:
                            pass
                    if groupLayers.Count >= 2:
                        groupLayers[0].Name = decorationCode
                        groupLayers[1].Name = targetName
                    elif groupLayers.Count == 1:
                        groupLayers[0].Name = targetName
            except Exception:
                pass
        except Exception:
            pass

        self.itemsInBatch += 1

        # Save and start new batch if max items reached
        if self.itemsInBatch >= self.maxItems:
            try:
                self._saveAndCloseBatch()
            except Exception as e:
                logError(f"Failed to finalize batch {self.batchIndex}: {e}")
            self.batchIndex += 1
            self.itemsInBatch = 0

        return True
