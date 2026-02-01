"""Excel Reader - Reads Excel files with flexible column name mapping."""

import re
import pandas as pd
from core.config import MANDATORY_COLUMNS
from .logger import logError


def _cleanValue(value):
    """Clean control characters (like \\r from Windows Excel) from a value."""
    if value is None:
        return ''
    if pd.isna(value):
        return ''
    s = str(value)
    # Remove literal escape sequences like _x000d_ (openpyxl escape for \r)
    s = re.sub(r'_x[0-9a-fA-F]{4}_', '', s)
    # Remove actual control characters
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    return s.strip()

# Import configuration loader
try:
    from configuration.configLoader import findColumnName, getColumnMapping
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False


# Internal field names mapped to legacy column names (fallback)
INTERNAL_TO_LEGACY = {
    'productId': 'Product ID',
    'supplierName': 'Supplier Name',
    'supplierPartId': 'Supplier Part ID',
    'supplierColor': 'Supplier Color',
    'decorationCode': 'Decoration Code',
    'decorationLocation': 'Decoration Location',
    'finalImageName': 'Final Image Name',
    'customLogoSize': 'Custom Logo Size',
}


def _findColumn(dfColumns, internalName):
    """Find the actual column name for an internal field name."""
    # Try configuration-based mapping first
    if CONFIG_AVAILABLE:
        result = findColumnName(dfColumns, internalName)
        if result:
            return result
    
    # Fallback to legacy column name
    legacyName = INTERNAL_TO_LEGACY.get(internalName)
    if legacyName and legacyName in dfColumns:
        return legacyName
    
    return None


def readExcel(filePath):
    """Read Excel file. Returns list of row dictionaries with LEGACY column names."""
    try:
        # 1. Read from Excel
        df = pd.read_excel(filePath)
        dfColumns = list(df.columns)
        
    except Exception as e:
        logError(f"Failed to read/convert Excel: {e}")
        print(f"[ERROR] Excel Read Failed: {e}")
        return []

    # Build column mapping for this file
    columnMap = {}
    for internalName in INTERNAL_TO_LEGACY.keys():
        foundCol = _findColumn(dfColumns, internalName)
        if foundCol:
            columnMap[internalName] = foundCol
    
    print(f"[INFO] Column mapping: {columnMap}")
    
    # Check mandatory columns
    mandatoryInternal = ['productId', 'supplierPartId', 'supplierColor', 
                         'decorationCode', 'decorationLocation', 'finalImageName', 'supplierName']
    
    missingMandatory = []
    for internalName in mandatoryInternal:
        if internalName not in columnMap:
            missingMandatory.append(INTERNAL_TO_LEGACY.get(internalName, internalName))
    
    if missingMandatory:
        logError(f"Missing mandatory columns in Excel: {', '.join(missingMandatory)}")
        print(f"[ERROR] Missing mandatory columns: {missingMandatory}")
        return []
    
    rows = []
    for index, row in df.iterrows():
        # Check if mandatory values are present
        missingValues = []
        for internalName in mandatoryInternal:
            colName = columnMap.get(internalName)
            if colName:
                value = row.get(colName)
                if pd.isna(value) or str(value).strip() == '':
                    missingValues.append(INTERNAL_TO_LEGACY.get(internalName, internalName))
        
        if missingValues:
            logError(f"Row {index+2} missing values for: {', '.join(missingValues)}")
            continue

        # Build row data with LEGACY column names for backward compatibility
        rowData = {}
        for internalName, legacyName in INTERNAL_TO_LEGACY.items():
            colName = columnMap.get(internalName)
            if colName:
                value = row.get(colName)
                if pd.isna(value):
                    rowData[legacyName] = ''
                else:
                    rowData[legacyName] = _cleanValue(value)
            else:
                rowData[legacyName] = ''
        
        # Also include any extra columns from the original file
        for col in dfColumns:
            if col not in columnMap.values():
                value = row.get(col)
                if not pd.isna(value):
                    rowData[col] = _cleanValue(value)
        
        rows.append(rowData)

    print(f"[INFO] Successfully read {len(rows)} valid rows from Excel")
    return rows
