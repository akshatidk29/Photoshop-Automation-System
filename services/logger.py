"""
Logger module for Photoshop Automation.
Provides user-friendly logging for both console and file output.
"""

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


def logInfo(message):
    """Log info message to console only."""
    print(f"[INFO] {message}")


def logSuccess(message):
    """Log success message to console."""
    print(f"[SUCCESS] ✓ {message}")


class RowLogger:
    """
    Logger dedicated to a single row processing.
    Provides clear, user-friendly messages for each step.
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
            f.write(f"Processing Log for Row {index}: {name}\n")
            f.write("=" * 60 + "\n\n")
            
    def log(self, message):
        """Log info message."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        with open(self.filePath, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def step(self, stepName, details=""):
        """Log a processing step with clear formatting."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        if details:
            line = f"[{timestamp}] ► {stepName}: {details}"
        else:
            line = f"[{timestamp}] ► {stepName}"
        with open(self.filePath, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(f"    ► {stepName}" + (f": {details}" if details else ""))

    def error(self, message, reason=""):
        """
        Log error message with optional reason.
        This will be shown to user in console.
        """
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if reason:
            fullMessage = f"{message} — Reason: {reason}"
        else:
            fullMessage = message
            
        line = f"[{timestamp}] ✗ ERROR: {fullMessage}"
        with open(self.filePath, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        
        # User-friendly console message
        print(f"    ✗ FAILED: {fullMessage}")
        
    def success(self, message):
        """Log success message."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] ✓ SUCCESS: {message}"
        with open(self.filePath, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(f"    ✓ {message}")

    def warn(self, message):
        """Log warning message."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] ⚠ WARNING: {message}"
        with open(self.filePath, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(f"    ⚠ {message}")
