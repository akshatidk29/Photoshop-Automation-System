"""
Excel Pre-Processor (Phase 1)

Pre-processes Excel file to resolve all paths and validate rows before Photoshop automation.

Flow:
1. Parse positions & garment type
2. Determine view requirements (single/dual-view)
3. Resolve image paths based on view requirements
4. Resolve logo paths
5. Resolve logo sizes
6. Finalize status
"""

import os
import pandas as pd
from typing import Dict, List, Any, Optional

from services.excelReader import readExcel, ROW_INVALID, ROW_INVALID_REASON
from locators.imageLocator import findImage, findImageCandidates
from locators.logoLocator import findLogo, findMultipleLogos
from core.utils import parseCustomSize
from detectors.comboParser import parseComboPosition

# Config imports
try:
    from configuration.configLoader import (
        getLogoSizeForPosition, 
        getGarmentTypeForPositions,
        PositionNotFoundError,
        validatePosition,
        hasAnyBackPosition,
        hasCapDualViewPosition,
        getPositionViewType
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    getGarmentTypeForPositions = None
    PositionNotFoundError = Exception
    validatePosition = None
    hasAnyBackPosition = None
    hasCapDualViewPosition = None
    getPositionViewType = None


class EnrichedColumns:
    """Constants for enriched column names."""
    IMAGE_PATH = "__AUTO_imagePath"
    LOGO_PATH = "__AUTO_logoPath"
    LOGO_PATHS_LIST = "__AUTO_logoPathsList"
    POSITION = "__AUTO_position"
    POSITIONS_LIST = "__AUTO_positionsList"
    LOGO_SIZE = "__AUTO_logoSize"
    LOGO_SIZES_LIST = "__AUTO_logoSizesList"
    GARMENT_TYPE = "__AUTO_garmentType"
    CANVAS_HEIGHT = "__AUTO_canvasHeight"
    STATUS = "__AUTO_status"
    ERROR_MESSAGE = "__AUTO_errorMessage"
    # T-SHIRT dual-view
    IS_BACK_POSITION = "__AUTO_isBackPosition"
    FRONT_IMAGE_PATH = "__AUTO_frontImagePath"
    BACK_IMAGE_PATH = "__AUTO_backImagePath"
    # CAP dual-view
    IS_CAP_DUAL_VIEW = "__AUTO_isCapDualView"
    CAP_FRONT_IMAGE_PATH = "__AUTO_capFrontImagePath"
    CAP_BACKSIDE_IMAGE_PATH = "__AUTO_capBackSideImagePath"
    # Undecorated rows - image is processed and exported, logo placement skipped
    IS_NO_LOGO = "__AUTO_isNoLogo"
    # Output
    OUTPUT_RESULT = "__AUTO_outputResult"


class PreProcessingStatus:
    """Status constants."""
    OK = "OK"
    ERROR = "ERROR"
    WARNING = "WARNING"


# HELPER: Position & Garment Type Resolution

def _resolvePositionsAndGarmentType(locationName: str, partId: str,
                                    isNoLogo: bool = False,
                                    fallbackGarmentType: str = 'T-SHIRT') -> Dict[str, Any]:
    """
    Parse positions and determine garment type, view requirements.

    Args:
        isNoLogo: row carries no artwork. The position, if any, is then used only
                  to pick the right product view - it never fails the row.
        fallbackGarmentType: used when a no-logo row has no usable position.

    Returns dict with:
        positions: List[str]
        garmentType: str
        isBackPosition: bool (T-SHIRT dual-view)
        isCapDualView: bool (CAP dual-view)
        capViewType: str (always 'back' - side is merged with back)
        errors: List[str]
    """
    result = {
        'positions': [],
        'garmentType': 'T-SHIRT',
        'isBackPosition': False,
        'isCapDualView': False,
        'capViewType': 'back',
        'errors': []
    }

    # Parse positions
    positions = parseComboPosition(locationName)
    result['positions'] = positions

    if not positions:
        if isNoLogo:
            # Undecorated row with no usable location: process the image only.
            result['garmentType'] = fallbackGarmentType
        elif locationName.strip():
            result['errors'].append(f"Could not parse position '{locationName}'")
        else:
            result['errors'].append("No decoration location provided")
        return result

    # Validate positions
    if CONFIG_AVAILABLE and validatePosition:
        for pos in positions:
            isValid, _ = validatePosition(pos)
            if not isValid:
                result['errors'].append(f"Position '{pos}' not found in positionRegistry.yaml")
    
    # Detect garment type
    try:
        if CONFIG_AVAILABLE and getGarmentTypeForPositions:
            result['garmentType'] = getGarmentTypeForPositions(positions, partId)
    except PositionNotFoundError as e:
        result['errors'].append(str(e))
        result['garmentType'] = 'UNKNOWN'
    
    # Determine if dual-view is needed
    if CONFIG_AVAILABLE and positions:
        # T-SHIRT: Check for back positions
        if hasAnyBackPosition and result['garmentType'] == 'T-SHIRT':
            result['isBackPosition'] = hasAnyBackPosition(positions)
        
        # CAP: Check for CAP-BACK / CAP-SIDE positions
        if hasCapDualViewPosition and result['garmentType'] == 'CAP':
            result['isCapDualView'] = hasCapDualViewPosition(positions)

    if isNoLogo:
        # An undecorated row is never failed over its position - the position
        # only steers which product view gets picked.
        result['errors'] = []
        if result['garmentType'] in (None, '', 'UNKNOWN'):
            result['garmentType'] = fallbackGarmentType

    return result


def _resolveImagePaths(imageRoot: str, supplierName: str, partId: str, 
                       color: str, garmentType: str, positionInfo: Dict) -> Dict[str, Any]:
    """
    Resolve all required image paths based on garment type and position info.
    
    viewType logic:
        - T-SHIRT/CAP: Use 'front' or 'back' for strict view filtering
        - BAG/BLANKET/other: Use 'any' (no view filtering)
    """
    result = {
        'primaryImage': '',
        'frontImage': '',
        'backImage': '',
        'errors': [],
        'warnings': []
    }
    
    isBackPosition = positionInfo.get('isBackPosition', False)
    isCapDualView = positionInfo.get('isCapDualView', False)
    
    # Determine if this garment type needs strict view filtering
    needsViewFiltering = garmentType in ('T-SHIRT', 'CAP')
    
    # CAP DUAL-VIEW: Need front + back images
    if isCapDualView:
        result['frontImage'] = findImage(imageRoot, supplierName, partId, color, viewType="front")
        if result['frontImage']:
            print(f"  [CAP-DUAL-VIEW] Found front: {os.path.basename(result['frontImage'])}")
        else:
            result['errors'].append("CAP front image not found")
        
        result['backImage'] = findImage(imageRoot, supplierName, partId, color, viewType="back")
        if result['backImage']:
            print(f"  [CAP-DUAL-VIEW] Found back: {os.path.basename(result['backImage'])}")
        else:
            result['errors'].append("CAP back image not found")
        
        result['primaryImage'] = result['frontImage'] or ''
        return result
    
    # T-SHIRT DUAL-VIEW: Need back + front images
    if isBackPosition:
        result['backImage'] = findImage(imageRoot, supplierName, partId, color, viewType="back")
        if result['backImage']:
            print(f"  [DUAL-VIEW] Found back image: {os.path.basename(result['backImage'])}")
        else:
            result['errors'].append(f"Could not find back image for '{partId}' in color '{color}'")
        
        result['frontImage'] = findImage(imageRoot, supplierName, partId, color, viewType="front")
        if result['frontImage']:
            print(f"  [DUAL-VIEW] Found front image: {os.path.basename(result['frontImage'])}")
        else:
            result['errors'].append(f"Could not find front image for '{partId}' in color '{color}'")
        
        result['primaryImage'] = result['backImage'] or ''
        return result
    
    # SINGLE VIEW: Find primary image
    # Use strict filtering for T-SHIRT/CAP, 'none' for BAG/BLANKET etc.
    viewType = "front" if needsViewFiltering else "none"
    primaryImage = findImage(imageRoot, supplierName, partId, color, viewType=viewType)
    
    if primaryImage:
        result['primaryImage'] = primaryImage
    else:
        result['errors'].append(f"Could not find product image for '{partId}' in color '{color}'")
    
    return result


# HELPER: Logo Path Resolution

def _resolveLogoPaths(logoRoot: str, decorationCodesList: List[str], 
                      positions: List[str]) -> Dict[str, Any]:
    """
    Resolve logo paths based on decoration codes.
    
    Returns dict with:
        logoPath: str (first logo for backward compatibility)
        logoPathsList: List[str]
        errors: List[str]
    """
    result = {
        'logoPath': '',
        'logoPathsList': [],
        'errors': []
    }
    
    if not decorationCodesList:
        result['errors'].append("No decoration code provided")
        return result
    
    # Multiple logos
    if len(decorationCodesList) > 1:
        logoPathsList = findMultipleLogos(
            logoRoot, 
            decorationCodesList, 
            positions or None
        )
        result['logoPathsList'] = logoPathsList
        
        # Set first logo for backward compatibility
        if logoPathsList and logoPathsList[0]:
            result['logoPath'] = logoPathsList[0]
        else:
            result['errors'].append(f"Logo(s) not found for codes '{', '.join(decorationCodesList)}'")
    
    # Single logo
    else:
        logoPath = findLogo(logoRoot, decorationCodesList[0])
        
        result['logoPath'] = logoPath or ''
        result['logoPathsList'] = [logoPath] if logoPath else []
        
        if not logoPath:
            result['errors'].append(f"Logo not found for decoration code '{decorationCodesList[0]}'")
    
    return result


# HELPER: Logo Size Resolution

def _resolveLogoSizesForPositions(positions: List[str], customLogoSize: str, 
                                   useExcelLogoSize: bool, logoSizesConfig: Dict) -> tuple:
    """
    Resolve logo sizes for each position.
    
    Returns: (sizes: List[int], fallbackUsed: bool, reason: str)
    """
    sizes = []
    anyFallback = False
    reasons = []
    
    # Parse Excel sizes
    excelSizes = []
    if useExcelLogoSize and customLogoSize:
        parsed = parseCustomSize(customLogoSize)
        if parsed is not None:
            if isinstance(parsed, list):
                excelSizes = parsed
            else:
                excelSizes = [parsed]
    
    # Resolve size for each position
    for idx, pos in enumerate(positions):
        if idx < len(excelSizes):
            # Use Excel size for this position
            excelSize = excelSizes[idx]
            sizes.append(excelSize[0] if isinstance(excelSize, tuple) else excelSize)
        else:
            # Use config default
            if CONFIG_AVAILABLE:
                size = getLogoSizeForPosition(pos, logoSizesConfig)
            else:
                size = 99
            sizes.append(size)
            
            if size == 99 and not excelSizes:
                anyFallback = True
                reasons.append(f"{pos}: using default 99px")
    
    return (sizes, anyFallback, "; ".join(reasons) if reasons else "")


# MAIN: Pre-Process Excel

def preProcessExcel(excelPath: str, imageRoot: str, logoRoot: str, 
                    settings: Dict[str, Any]) -> Dict[str, Any]:
    """Pre-process entire Excel file to resolve all paths and validate rows."""
    
    defaultCanvasHeight = settings.get('canvasHeight', 1800)
    logoSizesConfig = settings.get('logoSizes', {})
    useExcelLogoSize = settings.get('useExcelLogoSize', True)
    
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
    noLogoCount = 0

    # Only used to steer image view filtering for an undecorated row that has no
    # usable position: T-SHIRT/CAP get strict front/back filtering, anything else
    # accepts any view.
    fallbackGarmentType = 'T-SHIRT' if defaultCanvasHeight == 1800 else 'BAG'

    for idx, row in enumerate(rows, 1):
        # Extract row data (using internal field names from excelReader)
        supplierName = row.get("supplierName", "")
        partId = row.get("supplierPartId", "")
        color = row.get("supplierColor", "")
        decorationCode = row.get("decorationCode", "")
        locationName = row.get("decorationLocation", "")
        customLogoSize = row.get("customLogoSize", "")
        finalName = str(row.get("finalImageName", "")).split(".jpg")[0]
        
        # Get parsed list from Excel reader
        decorationCodesList = row.get("decorationCodeList", []) or ([decorationCode] if decorationCode else [])
        
        # Initialize enriched row
        enrichedRow = dict(row)
        enrichedRow[EnrichedColumns.STATUS] = PreProcessingStatus.OK
        enrichedRow[EnrichedColumns.ERROR_MESSAGE] = ""

        
        errorMessages = []
        warningMessages = []

        # ===== STEP 0: Rows the reader could not validate =====
        # Recorded as an error row rather than dropped, so the customer can see
        # exactly which sheet rows need fixing.
        if row.get(ROW_INVALID):
            reason = row.get(ROW_INVALID_REASON) or "Invalid row"
            enrichedRow[EnrichedColumns.STATUS] = PreProcessingStatus.ERROR
            enrichedRow[EnrichedColumns.ERROR_MESSAGE] = reason
            enrichedRow[EnrichedColumns.IS_NO_LOGO] = False
            enrichedRow[EnrichedColumns.POSITION] = ""
            enrichedRow[EnrichedColumns.POSITIONS_LIST] = []
            enrichedRow[EnrichedColumns.GARMENT_TYPE] = "UNKNOWN"
            enrichedRow[EnrichedColumns.IS_BACK_POSITION] = False
            enrichedRow[EnrichedColumns.IS_CAP_DUAL_VIEW] = False
            enrichedRow[EnrichedColumns.IMAGE_PATH] = ""
            enrichedRow[EnrichedColumns.FRONT_IMAGE_PATH] = ""
            enrichedRow[EnrichedColumns.BACK_IMAGE_PATH] = ""
            enrichedRow[EnrichedColumns.CAP_FRONT_IMAGE_PATH] = ""
            enrichedRow[EnrichedColumns.CAP_BACKSIDE_IMAGE_PATH] = ""
            enrichedRow[EnrichedColumns.LOGO_PATH] = ""
            enrichedRow[EnrichedColumns.LOGO_PATHS_LIST] = []
            enrichedRow[EnrichedColumns.LOGO_SIZE] = []
            enrichedRow[EnrichedColumns.LOGO_SIZES_LIST] = []
            enrichedRow[EnrichedColumns.CANVAS_HEIGHT] = defaultCanvasHeight
            errors.append({'row': idx, 'finalName': finalName, 'message': reason})
            enrichedRows.append(enrichedRow)
            continue

        # An undecorated row is one we cannot place artwork for: either there is
        # no decoration code, or there is no location telling us where it goes.
        # Both mean "resize and export the product image, place nothing".
        isNoLogo = (not decorationCodesList) or (not str(locationName).strip())
        enrichedRow[EnrichedColumns.IS_NO_LOGO] = isNoLogo
        if isNoLogo:
            noLogoCount += 1
            # A code with no location is ambiguous - surface it so the customer
            # can tell a deliberately blank thumbnail from a missing location.
            if decorationCodesList and not str(locationName).strip():
                warningMessages.append(
                    f"Decoration code '{decorationCodesList[0]}' present but no decoration "
                    f"location - image exported without a logo"
                )

        # ===== STEP 1: Resolve positions & garment type =====
        positionInfo = _resolvePositionsAndGarmentType(
            locationName, partId, isNoLogo=isNoLogo, fallbackGarmentType=fallbackGarmentType
        )
        positions = positionInfo['positions']
        
        enrichedRow[EnrichedColumns.POSITION] = ",".join(positions)
        enrichedRow[EnrichedColumns.POSITIONS_LIST] = positions
        enrichedRow[EnrichedColumns.GARMENT_TYPE] = positionInfo['garmentType']
        enrichedRow[EnrichedColumns.IS_BACK_POSITION] = positionInfo['isBackPosition']
        enrichedRow[EnrichedColumns.IS_CAP_DUAL_VIEW] = positionInfo['isCapDualView']
        
        errorMessages.extend(positionInfo['errors'])
        
        # ===== STEP 2: Resolve image paths =====
        garmentType = positionInfo['garmentType']
        imageInfo = _resolveImagePaths(imageRoot, supplierName, partId, color, garmentType, positionInfo)
        
        enrichedRow[EnrichedColumns.IMAGE_PATH] = imageInfo['primaryImage']
        enrichedRow[EnrichedColumns.FRONT_IMAGE_PATH] = imageInfo['frontImage']
        enrichedRow[EnrichedColumns.BACK_IMAGE_PATH] = imageInfo['backImage']
        enrichedRow[EnrichedColumns.CAP_FRONT_IMAGE_PATH] = imageInfo['frontImage'] if positionInfo['isCapDualView'] else ""
        enrichedRow[EnrichedColumns.CAP_BACKSIDE_IMAGE_PATH] = imageInfo['backImage'] if positionInfo['isCapDualView'] else ""
        
        errorMessages.extend(imageInfo['errors'])
        warningMessages.extend(imageInfo['warnings'])
        
        # ===== STEP 3: Resolve logo paths =====
        if isNoLogo:
            # Nothing to place - do not look for artwork and do not fail the row.
            enrichedRow[EnrichedColumns.LOGO_PATH] = ''
            enrichedRow[EnrichedColumns.LOGO_PATHS_LIST] = []
        else:
            logoInfo = _resolveLogoPaths(logoRoot, decorationCodesList, positions)

            enrichedRow[EnrichedColumns.LOGO_PATH] = logoInfo['logoPath']
            enrichedRow[EnrichedColumns.LOGO_PATHS_LIST] = logoInfo['logoPathsList']

            errorMessages.extend(logoInfo['errors'])

        # ===== STEP 4: Resolve logo sizes =====
        if isNoLogo:
            logoSizes, sizeFallback, sizeReason = [], False, ""
        else:
            logoSizes, sizeFallback, sizeReason = _resolveLogoSizesForPositions(
                positions, customLogoSize, useExcelLogoSize, logoSizesConfig
            )
        enrichedRow[EnrichedColumns.LOGO_SIZE] = logoSizes[0] if len(logoSizes) == 1 else logoSizes
        enrichedRow[EnrichedColumns.LOGO_SIZES_LIST] = logoSizes
        

        
        # ===== STEP 5: Canvas height =====
        enrichedRow[EnrichedColumns.CANVAS_HEIGHT] = defaultCanvasHeight
        
        # ===== STEP 6: Finalize status =====
        if errorMessages:
            enrichedRow[EnrichedColumns.STATUS] = PreProcessingStatus.ERROR
            enrichedRow[EnrichedColumns.ERROR_MESSAGE] = "; ".join(errorMessages)
            errors.append({'row': idx, 'finalName': finalName, 'message': "; ".join(errorMessages)})
        elif warningMessages:
            enrichedRow[EnrichedColumns.STATUS] = PreProcessingStatus.WARNING
            enrichedRow[EnrichedColumns.ERROR_MESSAGE] = "; ".join(warningMessages)
            warnings.append({'row': idx, 'finalName': finalName, 'message': "; ".join(warningMessages)})
            validCount += 1
        else:
            validCount += 1
        
        enrichedRows.append(enrichedRow)
        
        if idx % 10 == 0 or idx == len(rows):
            print(f"  [{idx}/{len(rows)}] Pre-processed...")
    
    # Summary
    print(f"\n[PRE-PROCESS] Complete!")
    print(f"  Total:    {len(rows)}")
    print(f"  Valid:    {validCount}")
    print(f"  No logo:  {noLogoCount} (image resized and exported, no logo placed)")
    print(f"  Errors:   {len(errors)}")
    print(f"  Warnings: {len(warnings)}")
    
    if errors:
        print(f"\n[ERRORS] The following rows have issues:")
        for err in errors[:10]:
            print(f"  Row {err['row']}: {err['message']}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
    
    return {
        'enrichedRows': enrichedRows,
        'stats': {'total': len(rows), 'valid': validCount, 'errors': len(errors), 'warnings': len(warnings)},
        'errors': errors,
        'warnings': warnings
    }


# OUTPUT: Save Functions

def saveEnrichedCsv(enrichedRows: List[Dict], outputPath: str) -> bool:
    """Save enriched rows to CSV for debugging."""
    try:
        df = pd.DataFrame(enrichedRows)
        df.to_csv(outputPath, index=False, encoding='utf-8-sig')
        print(f"[INFO] Saved enriched CSV to: {outputPath}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save enriched CSV: {e}")
        return False


def saveOutputExcel(enrichedRows: List[Dict], outputPath: str) -> bool:
    """Save results to Excel with all original columns plus Output column."""
    try:
        if not enrichedRows:
            print("[WARNING] No rows to save")
            return False
        
        # Get all original columns from the first row (exclude internal __AUTO_ columns)
        firstRow = enrichedRows[0]
        originalColumns = [
            col for col in firstRow.keys() 
            if not col.startswith('__AUTO_') and col != 'decorationCodeList'
        ]
        
        outputData = []
        for row in enrichedRows:
            # Copy all original columns
            cleanRow = {col: row.get(col, '') for col in originalColumns}
            
            # Build clear Output message
            runtimeResult = row.get(EnrichedColumns.OUTPUT_RESULT, '')
            preStatus = row.get(EnrichedColumns.STATUS, '')
            preError = row.get(EnrichedColumns.ERROR_MESSAGE, '')
            
            if runtimeResult == 'SUCCESS':
                cleanRow['Output'] = 'SUCCESS'
            elif runtimeResult:
                # Runtime error from Phase 2 (batch processing)
                cleanRow['Output'] = runtimeResult
            elif preStatus == PreProcessingStatus.ERROR:
                # Pre-processing error from Phase 1
                cleanRow['Output'] = f"[SKIPPED] {preError}" if preError else 'SKIPPED'
            elif preStatus == PreProcessingStatus.WARNING:
                cleanRow['Output'] = f"[WARNING] {preError}" if preError else 'WARNING'
            else:
                cleanRow['Output'] = 'PENDING'
            
            outputData.append(cleanRow)
        
        df = pd.DataFrame(outputData)
        # Reorder columns: original columns first, then Output
        cols = [c for c in df.columns if c != 'Output'] + ['Output']
        df = df[cols]
        df.to_excel(outputPath, index=False, engine='openpyxl')
        print(f"[INFO] Saved output Excel to: {outputPath}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save output Excel: {e}")
        return False
