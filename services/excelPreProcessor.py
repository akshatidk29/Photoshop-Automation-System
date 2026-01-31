"""
Excel Pre-Processor Service
Pre-processes entire Excel upfront to generate enriched data with resolved paths.
Enables upfront error detection and deterministic processing.
"""

import os
import pandas as pd
from typing import Dict, List, Any, Optional

from services.excelReader import readExcel
from locators.imageLocator import findImageCandidates
from locators.logoLocator import findLogo
from core.utils import detectGarmentTypeFromLocation, parseCustomSize, normalizeLocation
from detectors.comboParser import parseComboPosition

# Try to import config functions
try:
    from configuration.configLoader import (
        getLogoSizeForPosition, 
        getAllLogoSizes, 
        getGarmentTypeForPositions,
        PositionNotFoundError,
        validatePosition
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    getGarmentTypeForPositions = None
    PositionNotFoundError = Exception  # Fallback
    validatePosition = None


class EnrichedColumns:
    """Constants for enriched column names with __AUTO_ prefix to avoid clashes."""
    IMAGE_PATH = "__AUTO_imagePath"
    LOGO_PATH = "__AUTO_logoPath"
    POSITION = "__AUTO_position"
    POSITIONS_LIST = "__AUTO_positionsList"
    LOGO_SIZE = "__AUTO_logoSize"
    LOGO_SIZES_LIST = "__AUTO_logoSizesList"
    GARMENT_TYPE = "__AUTO_garmentType"
    CANVAS_HEIGHT = "__AUTO_canvasHeight"
    STATUS = "__AUTO_status"
    ERROR_MESSAGE = "__AUTO_errorMessage"
    FALLBACK_USED = "__AUTO_fallbackUsed"
    FALLBACK_REASON = "__AUTO_fallbackReason"


class PreProcessingStatus:
    """Status constants for pre-processing results."""
    OK = "OK"
    ERROR = "ERROR"
    WARNING = "WARNING"


def _resolveLogoSize(position: str, customLogoSize: str, useExcelLogoSize: bool, 
                     logoSizesConfig: Dict) -> tuple:
    """
    Resolve logo size for a position using the same logic as main.py.
    
    Priority:
    1. Excel custom size (if useExcelLogoSize is True and value exists)
    2. GUI config logoSizesConfig
    3. Default fallback (99)
    
    Returns:
        tuple: (size, fallbackUsed, fallbackReason)
    """
    fallbackUsed = False
    fallbackReason = ""
    
    # Check Excel first (if enabled)
    if useExcelLogoSize and customLogoSize:
        parsed = parseCustomSize(customLogoSize)
        if parsed is not None:
            # Handle both tuple (width, height) and single float (width-only)
            if isinstance(parsed, tuple):
                return (parsed[0], False, "")
            else:
                return (parsed, False, "")
    
    # Fallback to config
    if CONFIG_AVAILABLE:
        size = getLogoSizeForPosition(position, logoSizesConfig)
        if size != 99:  # 99 is the default, so if we get something else, it's from config
            return (size, False, "")
        else:
            # Still using config, just the default
            return (size, False, "")
    
    # Ultimate fallback
    return (99, True, "No size in Excel or config, using default 99px")


def _resolveLogoSizesForPositions(positions: List[str], customLogoSize: str, 
                                   useExcelLogoSize: bool, logoSizesConfig: Dict) -> tuple:
    """
    Resolve logo sizes for multiple positions.
    
    Supports:
    - Single Excel size applied to all positions: "120" or "120x180"
    - Comma-separated sizes for each position: "99,120" or "99x150,120x180"
    - If fewer Excel sizes than positions, remaining positions use config defaults
    
    Returns:
        tuple: (sizes_list, any_fallback_used, fallback_reasons)
    """
    sizes = []
    anyFallback = False
    reasons = []
    
    # Parse Excel custom sizes (may be list for multiple positions)
    excelSizes = []
    if useExcelLogoSize and customLogoSize:
        parsed = parseCustomSize(customLogoSize)
        if parsed is not None:
            if isinstance(parsed, list):
                # Multiple comma-separated sizes from Excel
                excelSizes = parsed
            else:
                # Single size from Excel - will be used for first position only if multiple positions
                # Or for all positions if only one position
                if len(positions) == 1:
                    excelSizes = [parsed]
                else:
                    # Single Excel value with multiple positions: use it for all
                    excelSizes = [parsed] * len(positions)
    
    # Resolve size for each position
    for idx, pos in enumerate(positions):
        # Check if we have an Excel size for this position index
        if idx < len(excelSizes):
            excelSize = excelSizes[idx]
            # Extract width if tuple (width, height)
            if isinstance(excelSize, tuple):
                sizes.append(excelSize[0])
            else:
                sizes.append(excelSize)
        else:
            # No Excel size for this position - use config default
            size, fallback, reason = _resolveLogoSize(pos, "", False, logoSizesConfig)
            sizes.append(size)
            if fallback:
                anyFallback = True
                reasons.append(f"{pos}: {reason}")
            elif not excelSizes:
                # All positions using config defaults (no Excel sizes at all)
                pass
            else:
                # Some positions had Excel sizes, this one didn't
                reasons.append(f"{pos}: using config default (no Excel size at index {idx})")
    
    return (sizes, anyFallback, "; ".join(reasons) if reasons else "")


def preProcessExcel(excelPath: str, imageRoot: str, logoRoot: str, 
                    settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pre-process entire Excel file to resolve all paths and validate rows.
    
    Args:
        excelPath: Path to Excel file
        imageRoot: Root directory for product images
        logoRoot: Root directory for logo files
        settings: Configuration settings containing:
            - canvasHeight: Default canvas height (1800 or 1200)
            - logoSizes: Dict of position -> size from GUI config
            - useExcelLogoSize: Whether to prioritize Excel logo size
    
    Returns:
        Dict containing:
            - enrichedRows: List of row dicts with __AUTO_ columns added
            - stats: {total, valid, errors, warnings}
            - errors: List of error details
            - warnings: List of warning details
    """
    print("\n" + "=" * 60)
    print("         EXCEL PRE-PROCESSING")
    print("=" * 60)
    
    # Extract settings
    defaultCanvasHeight = settings.get('canvasHeight', 1800)
    logoSizesConfig = settings.get('logoSizes', {})
    useExcelLogoSize = settings.get('useExcelLogoSize', True)
    
    # Read Excel using existing reader
    rows = readExcel(excelPath)
    
    if not rows:
        return {
            'enrichedRows': [],
            'stats': {'total': 0, 'valid': 0, 'errors': 1, 'warnings': 0},
            'errors': [{'row': 0, 'message': 'Failed to read Excel file or no valid rows'}],
            'warnings': []
        }
    
    enrichedRows = []
    errors = []
    warnings = []
    validCount = 0
    
    print(f"\n[PRE-PROCESS] Processing {len(rows)} rows...")
    
    for idx, row in enumerate(rows, 1):
        # Extract row data (using legacy column names from excelReader)
        productId = row.get("Product ID", "")
        supplierName = row.get("Supplier Name", "")
        partId = row.get("Supplier Part ID", "")
        color = row.get("Supplier Color", "")
        decorationCode = row.get("Decoration Code", "")
        locationName = row.get("Decoration Location", "")
        customLogoSize = row.get("Custom Logo Size", "")
        finalName = str(row.get("Final Image Name", "")).split(".jpg")[0]
        
        # Initialize enriched row with original data
        enrichedRow = dict(row)
        enrichedRow[EnrichedColumns.STATUS] = PreProcessingStatus.OK
        enrichedRow[EnrichedColumns.ERROR_MESSAGE] = ""
        enrichedRow[EnrichedColumns.FALLBACK_USED] = False
        enrichedRow[EnrichedColumns.FALLBACK_REASON] = ""
        
        errorMessages = []
        warningMessages = []
        
        # ========== Step 1: Find Image ==========
        imageCandidates = findImageCandidates(imageRoot, supplierName, partId, color, locationName)
        if imageCandidates:
            enrichedRow[EnrichedColumns.IMAGE_PATH] = imageCandidates[0]  # Best match
        else:
            enrichedRow[EnrichedColumns.IMAGE_PATH] = ""
            errorMessages.append(f"Could not find product image for '{partId}' in color '{color}'")
        
        # ========== Step 2: Find Logo ==========
        logoPath = findLogo(logoRoot, decorationCode)
        if logoPath:
            enrichedRow[EnrichedColumns.LOGO_PATH] = logoPath
        else:
            enrichedRow[EnrichedColumns.LOGO_PATH] = ""
            errorMessages.append(f"Could not find logo file '{decorationCode}'")
        
        # ========== Step 3: Resolve Position ==========
        positions = parseComboPosition(locationName)
        normalizedPosition = ",".join(positions)
        enrichedRow[EnrichedColumns.POSITION] = normalizedPosition
        enrichedRow[EnrichedColumns.POSITIONS_LIST] = positions
        
        # Validate each position exists in registry
        if CONFIG_AVAILABLE and validatePosition:
            for pos in positions:
                isValid, canonical = validatePosition(pos)
                if not isValid:
                    errorMessages.append(f"Position '{pos}' not found in positionRegistry.yaml")
        elif not positions:
            if locationName.strip():
                errorMessages.append(f"Could not parse position '{locationName}'")
        
        # ========== Step 4: Detect Garment Type ==========
        # Use parsed positions for accurate garment type detection
        # Raises PositionNotFoundError if position not in registry
        try:
            if CONFIG_AVAILABLE and getGarmentTypeForPositions:
                garmentType = getGarmentTypeForPositions(positions, partId)
            else:
                garmentType = detectGarmentTypeFromLocation(locationName, partId)
            enrichedRow[EnrichedColumns.GARMENT_TYPE] = garmentType
        except PositionNotFoundError as e:
            errorMessages.append(str(e))
            enrichedRow[EnrichedColumns.GARMENT_TYPE] = "UNKNOWN"
        
        # ========== Step 5: Determine Canvas Height ==========
        # Always use the canvas height selected in the GUI
        canvasHeight = defaultCanvasHeight
        enrichedRow[EnrichedColumns.CANVAS_HEIGHT] = canvasHeight
        
        # ========== Step 6: Resolve Logo Sizes ==========
        logoSizes, sizeFallback, sizeReason = _resolveLogoSizesForPositions(
            positions, customLogoSize, useExcelLogoSize, logoSizesConfig
        )
        enrichedRow[EnrichedColumns.LOGO_SIZE] = logoSizes[0] if len(logoSizes) == 1 else logoSizes
        enrichedRow[EnrichedColumns.LOGO_SIZES_LIST] = logoSizes
        
        if sizeFallback:
            enrichedRow[EnrichedColumns.FALLBACK_USED] = True
            enrichedRow[EnrichedColumns.FALLBACK_REASON] = sizeReason
        
        # ========== Finalize Status ==========
        if errorMessages:
            enrichedRow[EnrichedColumns.STATUS] = PreProcessingStatus.ERROR
            enrichedRow[EnrichedColumns.ERROR_MESSAGE] = "; ".join(errorMessages)
            errors.append({
                'row': idx,
                'finalName': finalName,
                'message': "; ".join(errorMessages)
            })
        elif warningMessages:
            enrichedRow[EnrichedColumns.STATUS] = PreProcessingStatus.WARNING
            enrichedRow[EnrichedColumns.ERROR_MESSAGE] = "; ".join(warningMessages)
            warnings.append({
                'row': idx,
                'finalName': finalName,
                'message': "; ".join(warningMessages)
            })
            validCount += 1  # Warnings still count as valid
        else:
            validCount += 1
        
        enrichedRows.append(enrichedRow)
        
        # Progress indicator
        if idx % 10 == 0 or idx == len(rows):
            print(f"  [{idx}/{len(rows)}] Pre-processed...")
    
    # Print summary
    print(f"\n[PRE-PROCESS] Complete!")
    print(f"  Total:    {len(rows)}")
    print(f"  Valid:    {validCount}")
    print(f"  Errors:   {len(errors)}")
    print(f"  Warnings: {len(warnings)}")
    
    if errors:
        print(f"\n[ERRORS] The following rows have issues:")
        for err in errors[:10]:  # Show first 10
            print(f"  Row {err['row']}: {err['message']}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
    
    return {
        'enrichedRows': enrichedRows,
        'stats': {
            'total': len(rows),
            'valid': validCount,
            'errors': len(errors),
            'warnings': len(warnings)
        },
        'errors': errors,
        'warnings': warnings
    }


def saveEnrichedCsv(enrichedRows: List[Dict], outputPath: str) -> bool:
    """
    Save enriched rows to CSV for debugging/inspection.
    
    Args:
        enrichedRows: List of enriched row dictionaries
        outputPath: Path to save CSV
    
    Returns:
        True if saved successfully
    """
    try:
        df = pd.DataFrame(enrichedRows)
        df.to_csv(outputPath, index=False, encoding='utf-8-sig')
        print(f"[INFO] Saved enriched CSV to: {outputPath}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save enriched CSV: {e}")
        return False
