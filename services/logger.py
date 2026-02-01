"""
Logger module for Photoshop Automation.
Provides user-friendly console logging.
"""

from core.utils import cleanFilename


def logError(message):
    """Log error message to console."""
    print(f"[ERROR] {message}")


class RowLogger:
    """
    Logger dedicated to a single row processing.
    Provides clear, user-friendly messages for each step.
    """
    
    def __init__(self, index, name):
        self.index = index
        self.name = cleanFilename(name)
        # No longer creating individual log files per row
            
    def log(self, message):
        """Log info message."""
        # Console only
        pass

    def step(self, stepName, details=""):
        """Log a processing step with clear formatting."""
        print(f"    ► {stepName}" + (f": {details}" if details else ""))

    def error(self, message, reason=""):
        """
        Log error message with optional reason.
        This will be shown to user in console.
        """
        if reason:
            fullMessage = f"{message} — Reason: {reason}"
        else:
            fullMessage = message
        
        # User-friendly console message
        print(f"    ✗ FAILED: {fullMessage}")
        
    def success(self, message):
        """Log success message."""
        print(f"    ✓ {message}")

    def warn(self, message):
        """Log warning message."""
        print(f"    ⚠ {message}")

    def fallback(self, message, fallbackUsed):
        """Log when a fallback option was used (e.g., model didn't predict)."""
        print(f"    ⟳ FALLBACK: {message} → {fallbackUsed}")
