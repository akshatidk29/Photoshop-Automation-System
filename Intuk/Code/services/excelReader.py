"""Excel Reader - Reads Excel files with flexible column name mapping."""

import re
import pandas as pd
from .batchLogger import logError

# Import configuration loader
from configuration.configLoader import findColumnName, getColumnMapping


def _cleanValue(value):
    """Clean control characters from a value."""
    if value is None or pd.isna(value):
        return ''
    s = str(value)
    s = re.sub(r'_x[0-9a-fA-F]{4}_', '', s)
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    return s.strip()


def _parseCommaSeparated(value):
    """Parse comma-separated value into list."""
    if not value or pd.isna(value):
        return []
    cleaned = _cleanValue(value)
    if not cleaned:
        return []
    parts = [p.strip() for p in cleaned.split(',')]
    return [p for p in parts if p]


# Required fields
REQUIRED_FIELDS = [
    'productId', 
    'supplierName',
    'supplierPartId', 
    'supplierColor', 
    'decorationCode', 
    'decorationLocation', 
    'finalImageName'
]

# Optional fields
OPTIONAL_FIELDS = [
    'decorationColor',
    'customLogoSize'
]

ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS


def readExcel(filePath):
    """
    Read Excel file and return list of row dictionaries.
    Column names are mapped using columnMapping.yaml config.
    """
    try:
        df = pd.read_excel(filePath)
        dfColumns = list(df.columns)
    except Exception as e:
        logError(f"Failed to read Excel: {e}")
        print(f"[ERROR] Excel Read Failed: {e}")
        return []

    # Build column mapping from config
    columnMap = {}
    for fieldName in ALL_FIELDS:
        foundCol = findColumnName(dfColumns, fieldName)
        if foundCol:
            columnMap[fieldName] = foundCol
    
    print(f"[INFO] Column mapping: {columnMap}")
    
    # Check required columns
    missing = [f for f in REQUIRED_FIELDS if f not in columnMap]
    if missing:
        logError(f"Missing required columns: {missing}")
        print(f"[ERROR] Missing columns: {missing}")
        return []
    
    rows = []
    for index, row in df.iterrows():
        # Check required values
        missingValues = []
        for field in REQUIRED_FIELDS:
            col = columnMap.get(field)
            if col:
                value = row.get(col)
                if pd.isna(value) or str(value).strip() == '':
                    missingValues.append(field)
        
        if missingValues:
            logError(f"Row {index+2} missing values: {missingValues}")
            continue

        # Build row data using internal field names
        rowData = {}
        for field in ALL_FIELDS:
            col = columnMap.get(field)
            if col:
                value = row.get(col)
                rowData[field] = '' if pd.isna(value) else _cleanValue(value)
                
                # Parse comma-separated for multi-logo support
                if field == 'decorationCode':
                    rowData['decorationCodeList'] = _parseCommaSeparated(value)
            else:
                rowData[field] = ''
        
        # Include extra columns from original file
        for col in dfColumns:
            if col not in columnMap.values():
                value = row.get(col)
                if not pd.isna(value):
                    rowData[col] = _cleanValue(value)
        
        rows.append(rowData)

    print(f"[INFO] Read {len(rows)} valid rows from Excel")
    return rows
