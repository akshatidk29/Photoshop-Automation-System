import pandas as pd
from core.config import MANDATORY_COLUMNS
from .logger import logError


def readExcel(filePath):
    """Read and validate Excel file, returning list of row dictionaries."""
    try:
        df = pd.read_excel(filePath)
    except Exception as e:
        logError(f"Failed to read Excel: {e}")
        return []

    rows = []
    for index, row in df.iterrows():
        missing = [col for col in MANDATORY_COLUMNS if pd.isna(row.get(col))]
        if missing:
            logError(f"Row {index+2} missing columns: {', '.join(missing)}")
            continue

        rowData = {col: str(row[col]).strip() for col in df.columns}
        rows.append(rowData)

    return rows
