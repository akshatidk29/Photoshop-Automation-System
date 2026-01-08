import os
import datetime
from core.config import getLogFile
from core.utils import cleanFilename, ensureFolder

# Global Log (Summary)
logPath = getLogFile()

def logError(message):
    """Log error message to file and console."""
    with open(logPath, "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] [ERROR] {message}\n")
    print(f"[ERROR] {message}")

class RowLogger:
    """
    Logger dedicated to a single row processing.
    Saves to assets/logs/row_{idx}_{name}.log
    """
    def __init__(self, index, name):
        self.index = index
        self.name = cleanFilename(name)
        
        # Setup path
        baseDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.logFolder = os.path.join(baseDir, "assets", "logs")
        ensureFolder(self.logFolder)
        
        self.filePath = os.path.join(self.logFolder, f"row_{index}_{self.name}.log")
        
        # Initialize
        with open(self.filePath, "w", encoding="utf-8") as f:
            f.write(f"Optimization Log for Row {index}: {name}\n")
            f.write("="*50 + "\n")
            
    def log(self, message):
        """Log info message."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [INFO] {message}"
        with open(self.filePath, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        # Optional: Print to console short version?
        # print(f"    -> {message}")

    def error(self, message):
        """Log error message."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [ERROR] {message}"
        with open(self.filePath, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(f"    [ROW ERROR] {message}")
        
    def success(self, message):
        """Log success message."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [SUCCESS] {message}"
        with open(self.filePath, "a", encoding="utf-8") as f:
            f.write(line + "\n")
