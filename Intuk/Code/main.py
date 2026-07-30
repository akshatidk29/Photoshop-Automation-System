# Photoshop Automation

import os
import shutil

# Services
from services.excelPreProcessor import preProcessExcel, EnrichedColumns, PreProcessingStatus, saveEnrichedCsv, saveOutputExcel
from services.batchLogger import BatchLogger, LogCategory, RowLogger
from services.imageProcessor import ImageProcessor

# Detectors
import detectors.garmentDetector as garmentDetector
import detectors.capDetector as capDetector
import detectors.bagDetector as bagDetector
import detectors.towelDetector as towelDetector

# Core
from photoshop.batchManager import PhotoshopBatchManager
from core.config import OUTPUT_ROOT, PROCESSED_IMG_DIR

# GUI
from gui import AutomationApp


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


def runAutomation(excelPath, imageRoot, logoRoot, canvasHeight, gui, settings):
    """
    Main automation function with two-phase architecture.
    
    Phase 1: Pre-process entire Excel to resolve all paths and validate rows
    Phase 2: Process enriched rows with deterministic data
    """
    print("\n" + "=" * 70)
    print("                 BATCH PROCESS")
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
    
    # Get settings - use a mutable dict so we can update during pause
    currentSettings = {
        'logoSizesConfig': settings.get('logoSizes', {}),
        'clippingEnabled': settings.get('clippingEnabled', False),
        'clippingPositions': settings.get('clippingPositions', {}),
        'useExcelLogoSize': settings.get('useExcelLogoSize', True)
    }
    
    # PHASE 1: Pre-process Excel
    print("\n" + "=" * 60)
    print("  PHASE 1: Reading Excel")
    print("=" * 60)
    
    preProcessSettings = {
        'canvasHeight': canvasHeight,
        'logoSizes': currentSettings['logoSizesConfig'],
        'useExcelLogoSize': currentSettings['useExcelLogoSize']
    }
    
    result = preProcessExcel(excelPath, imageRoot, logoRoot, preProcessSettings)
    
    if result['stats']['total'] == 0:
        print("[ERROR] No rows to process")
        return False
    
    # Show errors upfront
    if result['stats']['errors'] > 0:
        print(f"\n[WARNING] {result['stats']['errors']} rows have errors and will be skipped:")

    
    if result['stats']['valid'] == 0:
        print("[ERROR] No valid rows to process after pre-processing")
        return False
        
    # Save pre-processed data for debugging/reference
    csvPath = os.path.join(outputDir, "preprocessed.csv")
    saveEnrichedCsv(result['enrichedRows'], csvPath)
    
    # PHASE 2: Process Enriched Rows
    print("\n" + "=" * 60)
    print(f"  PHASE 2: Processing {result['stats']['valid']} Valid Rows")
    print("=" * 60)
    
    # Initialize batch logger
    batchName = os.path.splitext(os.path.basename(excelPath))[0]
    batchLogger = BatchLogger(batchName, outputDir)
    
    # Initialize Image Processor
    imgProcessor = ImageProcessor(tempDir=PROCESSED_IMG_DIR)
    
    processed = 0
    failed = 0
    
    # Pass outputDir to manager
    batchMgr = PhotoshopBatchManager(outputDir=outputDir, maxItemsPerBatch=200)
    enrichedRows = result['enrichedRows']
    totalRows = len(enrichedRows)
    
    for idx, row in enumerate(enrichedRows, 1):
        if gui:
            gui.updateProgress(idx - 1, totalRows)
        
        # Check if paused - wait until resumed
        if gui and hasattr(gui, 'pauseEvent'):
            if not gui.pauseEvent.is_set():
                print(f"\n[PAUSED] Waiting to resume...")
                gui.pauseEvent.wait()  # Block until resumed
                print(f"[RESUMED] Continuing processing...")
                
                # Refresh settings from GUI (in case they were changed while paused)
                if hasattr(gui, 'logoSizes'):
                    currentSettings['logoSizesConfig'] = gui.logoSizes.copy()
                if hasattr(gui, 'clippingEnabled'):
                    currentSettings['clippingEnabled'] = gui.clippingEnabled.get()
                if hasattr(gui, 'clippingPositions'):
                    currentSettings['clippingPositions'] = gui.clippingPositions.copy()
                if hasattr(gui, 'useExcelSize'):
                    currentSettings['useExcelLogoSize'] = gui.useExcelSize.get()
        
        # Try to get final name from internal column, fallback to legacy
        finalName = str(row.get("finalImageName", "")).split(".jpg")[0]
        
        # Skip rows with errors (already logged in Phase 1)
        if row.get(EnrichedColumns.STATUS) == PreProcessingStatus.ERROR:
            errorMsg = row.get(EnrichedColumns.ERROR_MESSAGE, "Pre-processing error")
            # Don't set OUTPUT_RESULT here — saveOutputExcel will format it with [SKIPPED] prefix
            batchLogger.logError(idx, finalName, errorMsg)
            if gui:
                gui.errorTracker.addError(idx, finalName, errorMsg)
            failed += 1
            continue
        
        # Use pre-resolved data from enriched columns
        imagePath = row.get(EnrichedColumns.IMAGE_PATH, "")
        logoPath = row.get(EnrichedColumns.LOGO_PATH, "")  # Keep for backward compatibility
        logoPathsList = row.get(EnrichedColumns.LOGO_PATHS_LIST, [])  # New: Multiple logos
        positions = row.get(EnrichedColumns.POSITIONS_LIST, [])
        
        # Logo sizes - recalculate based on current settings (in case changed during pause)
        if currentSettings['useExcelLogoSize']:
            # Use sizes from Excel (already in enriched row)
            logoSizes = row.get(EnrichedColumns.LOGO_SIZES_LIST, [99])
        else:
            # Use sizes from config - recalculate now
            logoSizes = []
            for pos in positions:
                logoSizes.append(currentSettings['logoSizesConfig'].get(pos, 99))
        
        garmentType = row.get(EnrichedColumns.GARMENT_TYPE, "T-SHIRT")
        activeHeight = row.get(EnrichedColumns.CANVAS_HEIGHT, canvasHeight)

        # Undecorated row (no code, or no location saying where the logo goes):
        # resize and export the product image, place nothing.
        isNoLogo = row.get(EnrichedColumns.IS_NO_LOGO, False)
        
        # Dual-view back position data (T-SHIRT)
        isBackPosition = row.get(EnrichedColumns.IS_BACK_POSITION, False)
        frontImagePath = row.get(EnrichedColumns.FRONT_IMAGE_PATH, "")
        backImagePath = row.get(EnrichedColumns.BACK_IMAGE_PATH, "")  # Explicitly found back image
        
        # CAP dual-view data (CAP-BACK, CAP-SIDE)
        isCapDualView = row.get(EnrichedColumns.IS_CAP_DUAL_VIEW, False)
        capFrontImagePath = row.get(EnrichedColumns.CAP_FRONT_IMAGE_PATH, "")
        capBackSideImagePath = row.get(EnrichedColumns.CAP_BACKSIDE_IMAGE_PATH, "")
        
        # Fallback: If no logoPathsList, use single logoPath for backward compatibility
        if not logoPathsList and logoPath:
            logoPathsList = [logoPath]
        
        # Get original row data for logging
        partId = row.get("supplierPartId", "")
        color = row.get("supplierColor", "")
        decorationCode = row.get("decorationCode", "")
        locationName = row.get("decorationLocation", "")
        
        rLog = RowLogger(idx, finalName)
        print(f"\n[Row {idx}/{totalRows}] {finalName}")
        
        # Validate pre-resolved data
        if not imagePath or not os.path.exists(imagePath):
            errorMsg = "Image path not resolved or doesn't exist"
            rLog.error(errorMsg)
            batchLogger.logError(idx, finalName, errorMsg)
            row[EnrichedColumns.OUTPUT_RESULT] = errorMsg  # Track in Excel
            if gui:
                gui.errorTracker.addError(idx, finalName, errorMsg)
            failed += 1
            continue
        
        validLogos = []

        if isNoLogo:
            # Clear everything the placement path would otherwise consume.
            rLog.log("No artwork for this row - exporting image without a logo")
            positions = []
            logoPathsList = []
            logoSizes = []
        else:
            # Validate logo paths (support both single and multi-logo)
            if not logoPathsList:
                errorMsg = "No logo paths resolved"
                rLog.error(errorMsg)
                batchLogger.logError(idx, finalName, errorMsg)
                row[EnrichedColumns.OUTPUT_RESULT] = errorMsg  # Track in Excel
                if gui:
                    gui.errorTracker.addError(idx, finalName, errorMsg)
                failed += 1
                continue

            # Filter out None values and validate that at least one valid logo exists
            validLogos = [lp for lp in logoPathsList if lp and os.path.exists(lp)]

            if not validLogos:
                errorMsg = "No valid logo files found on disk"
                rLog.error(errorMsg)
                batchLogger.logError(idx, finalName, errorMsg)
                row[EnrichedColumns.OUTPUT_RESULT] = errorMsg  # Track in Excel
                if gui:
                    gui.errorTracker.addError(idx, finalName, errorMsg)
                failed += 1
                continue

            if not positions:
                positions = [locationName.upper().replace(" ", "-")]

        # NOTE: Do NOT sort positions - this breaks alignment with logoSizes list
        isCombo = len(positions) > 1
        
        detector = getDetector(garmentType)
        success = False
        
        # Pre-process image based on canvas height
        finalImagePath = imagePath
        processingFailed = False
        useDualView = False  
        useCapDualView = False  
        dualViewLayout = None
        
        try:
            # Check if this is a CAP dual-view (CAP-BACK or CAP-SIDE)
            # Dual-view exists to show a logo sitting on an otherwise hidden face.
            # With no logo there is nothing to reveal, so undecorated rows stay
            # single-view.
            if not isNoLogo and isCapDualView and capFrontImagePath and capBackSideImagePath and \
               os.path.exists(capFrontImagePath) and os.path.exists(capBackSideImagePath):
                rLog.log(f"Processing CAP DUAL-VIEW...")
                
                # First, detect logo position on back/side image for placement decision
                logoPositionOnBackSide = None
                for pos in positions:
                    try:
                        from configuration.configLoader import getPositionViewType
                        viewType, gType = getPositionViewType(pos)
                        if viewType in ('back', 'side'):
                            # This position is on the back/side - detect its coordinates
                            result = detector.getCoordinates(capBackSideImagePath, pos, originalLocation=locationName)
                            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], bool):
                                coords, _ = result
                            else:
                                coords = result
                            if coords:
                                logoPositionOnBackSide = coords
                                rLog.log(f"Logo position on back/side for placement: {coords}")
                                break
                    except Exception as e:
                        rLog.log(f"Could not detect logo position for placement: {e}")
                
                finalImagePath = imgProcessor.processCapDualViewImage(
                    capFrontImagePath, capBackSideImagePath,
                    scalePercent=0.65,
                    logoPositionOnBackSide=logoPositionOnBackSide
                )
                useCapDualView = True
                capDualViewLayout = imgProcessor.getLastCapDualViewLayout()
                rLog.log("CAP dual-view image processing successful")
            # Check if this is a back position that should use dual-view (T-SHIRT/BLANKET)
            elif not isNoLogo and isBackPosition and garmentType in ("T-SHIRT", "BLANKET"):
                # Explicit check for front image existence
                if not frontImagePath or not os.path.exists(frontImagePath):
                    errorMsg = f"Dual-view required for back position but front image not found: {frontImagePath}"
                    rLog.error(errorMsg)
                    batchLogger.logError(idx, finalName, errorMsg)
                    row[EnrichedColumns.OUTPUT_RESULT] = errorMsg
                    if gui:
                        gui.errorTracker.addError(idx, finalName, errorMsg)
                    failed += 1
                    continue
                
                rLog.log(f"Processing DUAL-VIEW for back position...")
                # Use explicit back image if available, otherwise fall back to primary image
                actualBackImage = backImagePath if backImagePath and os.path.exists(backImagePath) else imagePath
                rLog.log(f"  Back image: {os.path.basename(actualBackImage)}")
                rLog.log(f"  Front image: {os.path.basename(frontImagePath)}")
                
                finalImagePath = imgProcessor.processDualViewImage(actualBackImage, frontImagePath, activeHeight)
                useDualView = True
                dualViewLayout = imgProcessor.getLastDualViewLayout()
                rLog.log("Dual-view image processing successful")
            else:
                rLog.log(f"Pre-processing image to {activeHeight}px height...")
                finalImagePath = imgProcessor.processImage(imagePath, activeHeight)
                rLog.log("Image pre-processing successful")
        except Exception as e:
            processingFailed = True
            fallbackMsg = f"Image pre-processing failed, using original image: {e}"
            rLog.fallback("Image pre-processing failed", f"Using original image. Error: {e}")
            batchLogger.logFallback(idx, finalName, 
                                   f"Image pre-processing check failed: {e}", 
                                   "Using original raw image")

            import traceback
            print(f"    [DEBUG] Pre-processing error: {traceback.format_exc()}")
            finalImagePath = imagePath
            useDualView = False
            useCapDualView = False
        
        try:
            # Track detected and failed positions separately
            detectedData = []  # List of (posIndex, pos, coords, rotation)
            failedPositions = []  # List of position names that failed detection
            
            # Import position view type helper for dual-view
            try:
                from configuration.configLoader import getPositionViewType
            except ImportError:
                getPositionViewType = None
            
            # Determine the actual back image to use for dual-view coordinate detection
            actualBackImageForDetection = backImagePath if backImagePath and os.path.exists(backImagePath) else imagePath
            
            for posIdx, pos in enumerate(positions):
                try:
                    # Determine which image to use for coordinate detection
                    if useCapDualView and getPositionViewType:
                        viewType, gType = getPositionViewType(pos)
                        if viewType == 'front':
                            detectionImagePath = capFrontImagePath
                        else:  # back or side
                            detectionImagePath = capBackSideImagePath
                    elif useDualView and getPositionViewType:
                        # T-SHIRT dual-view: use correct image based on position view type
                        viewType, gType = getPositionViewType(pos)
                        if viewType == 'front':
                            detectionImagePath = frontImagePath  # Front image for front positions
                        else:  # back
                            detectionImagePath = actualBackImageForDetection  # Explicit back image
                    else:
                        detectionImagePath = finalImagePath
                    
                    result = detector.getCoordinates(detectionImagePath, pos, originalLocation=locationName)
                    # Handle return format: ((x, y), detected) where detected is bool
                    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], bool):
                        coords, detected = result
                    else:
                        # Legacy format support
                        coords = result
                        detected = coords is not None
                     
                    # Check if position was NOT detected (coords is None)
                    if coords is None or not detected:
                        failedPositions.append(pos)
                        rLog.error(f"Position '{pos}' NOT DETECTED by model - skipping this position")
                        continue  # Skip this position, try next one
                    
                    # Transform coordinates for dual-view
                    if useCapDualView and getPositionViewType:
                        viewType, gType = getPositionViewType(pos)
                        if viewType == 'front':
                            coords = imgProcessor.transformCoordsForCapFront(coords)
                        else:  # back or side
                            coords = imgProcessor.transformCoordsForCapBackSide(coords)
                        rLog.log(f"Transformed CAP coords for {viewType}: {coords}")
                    elif useDualView and dualViewLayout and getPositionViewType:
                        viewType, gType = getPositionViewType(pos)
                        if viewType == 'front':
                            coords = imgProcessor.transformCoordsForDualViewFront(coords)
                        else:  # back
                            coords = imgProcessor.transformCoordinatesForDualView(coords, actualBackImageForDetection)
                        rLog.log(f"Transformed T-SHIRT coords for {viewType}: {coords}")
                    
                    # Get rotation for this position
                    try:
                        rotation = detector.getRotation(detectionImagePath, pos)
                    except:
                        rotation = 0.0
                    
                    # Store successful detection with original index
                    detectedData.append((posIdx, pos, coords, rotation))
                    rLog.log(f"Position '{pos}' detected at {coords}")
                    
                except Exception as e:
                    # Exception during detection - treat as failed
                    failedPositions.append(pos)
                    rLog.error(f"Position '{pos}' detection error: {e}")
                    batchLogger.logError(idx, finalName, f"Position '{pos}' detection error: {e}")
            
            # Check results: ALL failed vs SOME failed vs ALL succeeded.
            # An undecorated row has no positions to detect, so an empty result
            # is expected rather than a failure - it falls through with empty
            # placement lists and is exported image-only.
            if not isNoLogo and len(detectedData) == 0:
                # ALL positions failed - skip entire row
                errorMsg = f"NO positions detected by model. Failed: {', '.join(failedPositions)}"
                rLog.error(errorMsg)
                batchLogger.logError(idx, finalName, errorMsg)
                row[EnrichedColumns.OUTPUT_RESULT] = errorMsg
                if gui:
                    gui.errorTracker.addError(idx, finalName, errorMsg)
                failed += 1
                
                # Cleanup
                if not processingFailed and finalImagePath != imagePath:
                    try:
                        os.remove(finalImagePath)
                    except:
                        pass
                continue
            
            # Log if some positions failed (partial success)
            if failedPositions:
                warningMsg = f"PARTIAL: {len(failedPositions)} position(s) NOT detected: {', '.join(failedPositions)}. Processing {len(detectedData)} detected position(s) only."
                rLog.warn(warningMsg)
                batchLogger.logWarning(idx, finalName, warningMsg)

            
            # Rebuild filtered lists with only detected positions
            positions = [d[1] for d in detectedData]  # Only detected positions
            coordinatesList = [d[2] for d in detectedData]
            rotationsList = [d[3] for d in detectedData]
            
            # Filter logoSizes and logoPathsList to match detected positions
            detectedIndices = [d[0] for d in detectedData]
            logoSizes = [logoSizes[i] if i < len(logoSizes) else 99 for i in detectedIndices]
            logoPathsList = [logoPathsList[i] if i < len(logoPathsList) else logoPathsList[0] for i in detectedIndices]
            
            # Update isCombo based on remaining positions
            isCombo = len(positions) > 1
            
            # Scale logo sizes for dual-view (images are scaled down)
            if useCapDualView:
                # For CAP dual-view, scale based on position's view type
                frontScale, backSideScale = imgProcessor.getCapDualViewScaleFactors()
                scaledLogoSizes = []
                for i, pos in enumerate(positions):
                    if getPositionViewType:
                        viewType, gType = getPositionViewType(pos)
                        if viewType == 'front':
                            scaledLogoSizes.append(int(logoSizes[i] * frontScale) if i < len(logoSizes) else 99)
                        else:
                            scaledLogoSizes.append(int(logoSizes[i] * backSideScale) if i < len(logoSizes) else 99)
                    else:
                        scaledLogoSizes.append(logoSizes[i] if i < len(logoSizes) else 99)
                logoSizes = scaledLogoSizes
                rLog.log(f"Scaled logo sizes for CAP dual-view")
            elif useDualView:
                # For T-SHIRT dual-view, scale based on position's view type
                backScale, frontScale = imgProcessor.getDualViewScaleFactors()
                scaledLogoSizes = []
                for i, pos in enumerate(positions):
                    if getPositionViewType:
                        viewType, gType = getPositionViewType(pos)
                        if viewType == 'front':
                            scaledLogoSizes.append(int(logoSizes[i] * frontScale) if i < len(logoSizes) else 99)
                        else:  # back
                            scaledLogoSizes.append(int(logoSizes[i] * backScale) if i < len(logoSizes) else 99)
                    else:
                        scaledLogoSizes.append(logoSizes[i] if i < len(logoSizes) else 99)
                logoSizes = scaledLogoSizes
                rLog.log(f"Scaled logo sizes for T-SHIRT dual-view (back: {backScale:.2f}, front: {frontScale:.2f})")
            
            # Ensure we have enough logo sizes for all positions
            while len(logoSizes) < len(positions):
                logoSizes.append(99)  # Default fallback
            
            # Ensure we have enough logo paths for all positions (with fallback to first valid)
            # Cycle through valid logos only
            while len(logoPathsList) < len(positions):
                if validLogos:
                    # Cycle through valid logos
                    cycleIdx = len(logoPathsList) % len(validLogos)
                    logoPathsList.append(validLogos[cycleIdx])
                else:
                    # Should not happen due to earlier validation, but safety check
                    logoPathsList.append(None)
            
            # addCombo handles combo, single and undecorated (empty lists) alike
            ok = batchMgr.addCombo(
                partId, finalImagePath, logoPathsList, os.path.basename(imagePath),
                decorationCode, positions, coordinatesList, rotationsList,
                garmentType, logoSizes, finalName, activeHeight,
                clippingEnabled=currentSettings['clippingEnabled'], clippingPositions=currentSettings['clippingPositions']
            )
            
            if ok:
                processed += 1
                rLog.success("Added to batch")
                batchLogger.logSuccess(idx, finalName, "Added to batch successfully")
                # Track in Excel
                row[EnrichedColumns.OUTPUT_RESULT] = "SUCCESS (no logo)" if isNoLogo else "SUCCESS"

                success = True
        
        except Exception as e:
            errorMsg = f"Unexpected error: {str(e)}"
            rLog.error(errorMsg)
            batchLogger.logError(idx, finalName, errorMsg, reason=str(e))
            row[EnrichedColumns.OUTPUT_RESULT] = errorMsg  # Track in Excel

            if gui:
                gui.errorTracker.addError(idx, finalName, str(e))
            failed += 1
            continue
            
        finally:
            # Cleanup temp file
            if not processingFailed and finalImagePath != imagePath and finalImagePath and os.path.exists(finalImagePath):
                try:
                    os.remove(finalImagePath)
                except Exception as e:
                    print(f"Warning: Failed to delete temp file {finalImagePath}: {e}")
            
            # Periodic cleanup every 50 rows
            if idx % 50 == 0:
                imgProcessor.cleanup()
        
        if not success:
            errorMsg = f"Could not process image for {partId}"
            rLog.error(errorMsg, reason="The garment position may not be detected correctly")
            batchLogger.logError(idx, finalName, errorMsg)
            row[EnrichedColumns.OUTPUT_RESULT] = errorMsg  # Track in Excel

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
    
    # Save output Excel with results
    excelOutputPath = os.path.join(outputDir, "output_results.xlsx")
    saveOutputExcel(enrichedRows, excelOutputPath)
    
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
    app = AutomationApp(automationCallback=runAutomation)
    app.mainloop()
