import os
import pandas as pd
from core.config import MANDATORY_COLUMNS
from core.utils import ensureFolder
from .logger import logError


def readExcel(filePath):
    """
    Read Excel file by first converting to CSV to ensure stability.
    Returns list of row dictionaries.
    """
    try:
        # Create processed folder
        baseDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csvFolder = os.path.join(baseDir, "assets", "processed_csvs")
        ensureFolder(csvFolder)

        # 1. Convert to CSV
        if filePath.lower().endswith(('.xlsx', '.xls')):
            filename = os.path.splitext(os.path.basename(filePath))[0] + ".csv"
            csvPath = os.path.join(csvFolder, filename)
            
            # Read Excel
            df_temp = pd.read_excel(filePath)
            # Save to CSV
            df_temp.to_csv(csvPath, index=False, encoding='utf-8-sig')
            
            print(f"[INFO] Converted Excel to CSV: {csvPath}")
        else:
            # Assume it's already CSV or compatible? 
            # The prompt mainly talked about reading excel.
            # If user selects CSV directly, we can use it, but logic says "When reading excel... convert".
            csvPath = filePath

        # 2. Read from CSV
        df = pd.read_csv(csvPath)
        
    except Exception as e:
        logError(f"Failed to read/convert Excel: {e}")
        print(f"[ERROR] Excel Read Failed: {e}")
        return []

    rows = []
    for index, row in df.iterrows():
        # Clean keys and values
        # Check mandatory columns
        missing = [col for col in MANDATORY_COLUMNS if col not in df.columns or pd.isna(row.get(col))]
        
        # Note: If column is missing from DF entirely, row.get(col) might fail or just be nan. 
        # Better check:
        missing = []
        for col in MANDATORY_COLUMNS:
            if col not in df.columns:
                missing.append(col)
            elif pd.isna(row[col]):
                missing.append(col)

        if missing:
            logError(f"Row {index+2} missing columns: {', '.join(missing)}")
            continue

        rowData = {col: str(row[col]).strip() for col in df.columns}
        rows.append(rowData)

    return rows
