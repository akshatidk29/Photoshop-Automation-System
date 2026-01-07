import pandas as pd
from config import MANDATORY_COLUMNS
from logger import log_error

def read_excel(file_path):
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        log_error(f"Failed to read Excel: {e}")
        return []

    rows = []
    for index, row in df.iterrows():
        missing = [col for col in MANDATORY_COLUMNS if pd.isna(row.get(col))]
        if missing:
            log_error(f"Row {index+2} missing columns: {', '.join(missing)}")
            continue

        row_data = {col: str(row[col]).strip() for col in df.columns}
        rows.append(row_data)

    return rows
