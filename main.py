# Photoshop Automation

import os
import shutil

# Services
from services.excelPreProcessor import preProcessExcel, EnrichedColumns, PreProcessingStatus, saveEnrichedCsv
from services.batchLogger import BatchLogger, LogCategory
from services.imageProcessor import ImageProcessor
from services.logger import RowLogger

# Detectors
import detectors.garmentDetector as garmentDetector
import detectors.capDetector as capDetector
import detectors.bagDetector as bagDetector
import detectors.towelDetector as towelDetector

# Core
from photoshop.batchManager import PhotoshopBatchManager
from core.config import BASE_DIR, OUTPUT_ROOT

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
    
    # PHASE 1: Pre-process Excel
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
    
    # PHASE 2: Process Enriched Rows
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
            errorMsg = "Image path not resolved or doesn't exist"
            rLog.error(errorMsg)
            batchLogger.logError(idx, finalName, errorMsg)
            if gui:
                gui.errorTracker.addError(idx, finalName, errorMsg)
            failed += 1
            continue
        
        if not logoPath or not os.path.exists(logoPath):
            errorMsg = "Logo path not resolved or doesn't exist"
            rLog.error(errorMsg)
            batchLogger.logError(idx, finalName, errorMsg)
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
        
        try:
            rLog.log(f"Pre-processing image to {activeHeight}px height...")
            finalImagePath = imgProcessor.processImage(imagePath, activeHeight)
            rLog.log("Image pre-processing successful")
        except Exception as e:
            processingFailed = True
            rLog.fallback("Image pre-processing failed", "Using original image")
            batchLogger.logFallback(idx, finalName, 
                                   "Image pre-processing check failed", 
                                   "Using original raw image")
            finalImagePath = imagePath
        
        try:
            coordinatesList = []
            rotationsList = []
            valid = True
            anyFallbackUsed = False
            
            # Use finalImagePath (processed or original) for detection
            for pos in positions:
                try:
                    result = detector.getCoordinates(finalImagePath, pos, originalLocation=locationName)
                    # Handle new return format: ((x, y), usedFallback)
                    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], bool):
                        coords, usedFallback = result
                    else:
                        # Legacy format support
                        coords = result
                        usedFallback = False
                    
                    coordinatesList.append(coords)
                    
                    if usedFallback:
                        anyFallbackUsed = True
                        rLog.fallback(f"OBB not detected for {pos}", "Using heuristic fallback")
                        batchLogger.logFallback(idx, finalName, 
                                                f"OBB model did not detect position {pos}",
                                                "Used heuristic/MediaPipe coordinates")
                    
                    try:
                        rotation = detector.getRotation(finalImagePath, pos)
                    except:
                        rotation = 0.0
                    rotationsList.append(rotation)
                except Exception as e:
                    # Complete failure - can't get coordinates at all
                    rLog.error(f"Failed pos {pos}: {e}")
                    valid = False
                    break
            
            if not valid:
                errorMsg = "Could not get coordinates for all positions"
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
    app = AutomationApp(automationCallback=runAutomation)
    app.mainloop()
