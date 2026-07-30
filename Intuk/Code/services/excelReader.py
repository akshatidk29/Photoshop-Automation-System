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
    s = s.strip()
    # With dtype=str in play, some pandas versions surface an empty cell as the
    # literal string "nan" rather than NaN.
    if s.lower() in ('nan', 'none'):
        return ''
    return s


def _parseCommaSeparated(value):
    """Parse comma-separated value into list."""
    if not value or pd.isna(value):
        return []
    cleaned = _cleanValue(value)
    if not cleaned:
        return []
    parts = [p.strip() for p in cleaned.split(',')]
    return [p for p in parts if p]


# Markers added to a row that failed validation. They carry the __AUTO_ prefix so
# saveOutputExcel() strips them from the customer-facing sheet.
ROW_INVALID = "__AUTO_rowInvalid"
ROW_INVALID_REASON = "__AUTO_rowInvalidReason"

# Fields a row genuinely cannot be processed without - without a part ID or a
# colour there is no way to locate the product image. A row missing any of these
# is still returned, flagged via ROW_INVALID, so it surfaces as an error row in
# the output instead of disappearing.
REQUIRED_FIELDS = [
    'productId',
    'supplierName',
    'supplierPartId',
    'supplierColor',
    'finalImageName'
]

# Optional fields. decorationCode and decorationLocation are optional because an
# undecorated product (e.g. a trouser that takes no logo) still needs its image
# resized and exported.
OPTIONAL_FIELDS = [
    'decorationCode',
    'decorationLocation',
    'decorationColor',
    'customLogoSize'
]

# Listed explicitly (rather than REQUIRED + OPTIONAL) so the column order of
# output_results.xlsx stays exactly as it has always been for the customer.
ALL_FIELDS = [
    'productId',
    'supplierName',
    'supplierPartId',
    'supplierColor',
    'decorationCode',
    'decorationLocation',
    'finalImageName',
    'decorationColor',
    'customLogoSize'
]


def readExcel(filePath):
    """
    Read Excel file and return list of row dictionaries.
    Column names are mapped using columnMapping.yaml config.
    """
    try:
        # dtype=str is essential. Without it pandas types each column as a whole,
        # and a column cannot hold a blank alongside int64 - so ONE empty
        # Decoration Code cell upcasts the whole column to float64 and turns
        # every code "131924" into "131924.0", breaking every logo lookup in the
        # file. A genuine decimal code ("12345.01") causes the same upcast.
        # dtype=str converts per cell instead, so neither can affect other rows.
        df = pd.read_excel(filePath, dtype=str)
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
    invalidCount = 0
    for index, row in df.iterrows():
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

        # Validate AFTER building, so an invalid row still carries whatever data
        # it had. Flag it rather than dropping it - a silently discarded row is
        # invisible in preprocessed.csv, output_results.xlsx and the batch log,
        # which leaves the customer with no way to find out what went wrong.
        missingValues = [f for f in REQUIRED_FIELDS if not str(rowData.get(f, '')).strip()]

        if missingValues:
            reason = f"Missing required value(s): {', '.join(missingValues)}"
            rowData[ROW_INVALID] = True
            rowData[ROW_INVALID_REASON] = reason
            logError(f"Row {index+2} - {reason}")
            invalidCount += 1
        else:
            rowData[ROW_INVALID] = False
            rowData[ROW_INVALID_REASON] = ''

        rows.append(rowData)

    print(f"[INFO] Read {len(rows)} rows from Excel ({len(rows) - invalidCount} valid, {invalidCount} invalid)")
    return rows
