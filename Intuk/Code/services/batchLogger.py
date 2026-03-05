import os
import datetime
from typing import Dict, List, Any, Optional
from core.utils import ensureFolder, cleanFilename


def logError(message):
    """Log error message to console (standalone, no batch context)."""
    print(f"[ERROR] {message}")


class RowLogger:
    """Simple per-row logger for console output."""
    
    def __init__(self, index, name):
        self.index = index
        self.name = cleanFilename(name)

    def log(self, message):
        """Log info message."""
        print(f"    {message}")

    def step(self, stepName, details=""):
        """Log a processing step."""
        print(f"    ► {stepName}" + (f": {details}" if details else ""))

    def error(self, message, reason=""):
        if reason:
            fullMessage = f"{message} — Reason: {reason}"
        else:
            fullMessage = message
        print(f"    ✗ FAILED: {fullMessage}")
        
    def success(self, message):
        """Log success message."""
        print(f"    ✓ {message}")

    def warn(self, message):
        """Log warning message."""
        print(f"    ⚠ {message}")

    def fallback(self, message, fallbackUsed):
        """Log when a fallback option was used."""
        print(f"    ⟳ FALLBACK: {message} → {fallbackUsed}")


class LogCategory:
    ERROR = "ERROR"
    FALLBACK = "FALLBACK"
    WARNING = "WARNING"
    SUCCESS = "SUCCESS"


class BatchLogger:
    
    def __init__(self, batchName: str, outputDir: str):

        self.batchName = batchName
        self.startTime = datetime.datetime.now()
        
        # Setup log directory - Directly use outputDir as requested
        self.logDir = outputDir
        ensureFolder(self.logDir)
        
        # Log file path
        self.logPath = os.path.join(self.logDir, f"{batchName}_batch.log")
        
        # Track entries
        self.entries: List[Dict[str, Any]] = []
        self.stats = {
            LogCategory.ERROR: 0,
            LogCategory.FALLBACK: 0,
            LogCategory.WARNING: 0,
            LogCategory.SUCCESS: 0,
            'total': 0
        }
        
        # Initialize log file
        self._initLogFile()
    
    def _initLogFile(self):
        with open(self.logPath, 'w', encoding='utf-8') as f:
            f.write(f"Batch: {self.batchName}\n")
    
    def _writeEntry(self, entry: Dict[str, Any]):

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        category = entry['category']
        rowIndex = entry['rowIndex']
        finalName = entry['finalName']
        message = entry['message']
        
        # Format based on category
        categorySymbol = {
            LogCategory.ERROR: "✗",
            LogCategory.FALLBACK: "⟳",
            LogCategory.WARNING: "⚠",
            LogCategory.SUCCESS: "✓"
        }.get(category, "•")
        
        line = f"[{timestamp}] [{category}] {categorySymbol} Row {rowIndex} ({finalName}): {message}"
        
        if entry.get('details'):
            line += f"\n    Details: {entry['details']}"
        
        with open(self.logPath, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    
    def log(self, category: str, rowIndex: int, finalName: str, 
            message: str, details: Optional[str] = None):

        entry = {
            'timestamp': datetime.datetime.now(),
            'category': category,
            'rowIndex': rowIndex,
            'finalName': finalName,
            'message': message,
            'details': details
        }
        
        self.entries.append(entry)
        self.stats[category] = self.stats.get(category, 0) + 1
        self.stats['total'] += 1
        
        # Write to file immediately
        self._writeEntry(entry)
        
        # Also print to console for visibility
        symbol = {"ERROR": "✗", "FALLBACK": "⟳", "WARNING": "⚠", "SUCCESS": "✓"}.get(category, "•")
        print(f"    {symbol} [{category}] {message}")
    
    def logError(self, rowIndex: int, finalName: str, message: str, 
                 reason: Optional[str] = None):
        """
        Log an error for a specific row.
        """
        fullMessage = message
        if reason:
            fullMessage += f" — Reason: {reason}"
        self.log(LogCategory.ERROR, rowIndex, finalName, fullMessage)
    
    def logFallback(self, rowIndex: int, finalName: str, message: str, 
                    fallbackUsed: str):
        """
        Log when a fallback option was used.
        """
        self.log(LogCategory.FALLBACK, rowIndex, finalName, 
                 f"{message} → Using: {fallbackUsed}")
    
    def logWarning(self, rowIndex: int, finalName: str, message: str):
        """
        Log a warning for a specific row.
        """
        self.log(LogCategory.WARNING, rowIndex, finalName, message)
    
    def logSuccess(self, rowIndex: int, finalName: str, message: str = "Processed successfully"):
        """
        Log successful processing.
        """
        self.log(LogCategory.SUCCESS, rowIndex, finalName, message)
    
    def getStats(self) -> Dict[str, int]:
        """
        Get statistics for the batch.
        """
        return dict(self.stats)
    
    def getEntriesByCategory(self, category: str) -> List[Dict[str, Any]]:
        """Get all entries of a specific category."""
        return [e for e in self.entries if e['category'] == category]
    
    def saveReport(self) -> str:
        """
        Generate and save summary report.
        """
        
        with open(self.logPath, 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write("BATCH PROCESSING SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Batch: {self.batchName}\n")
            f.write(f"Started:  {self.startTime.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 40 + "\n")
            f.write("STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Processed: {self.stats['total']}\n")
            f.write(f"Successful:      {self.stats[LogCategory.SUCCESS]}\n")
            f.write(f"Errors:          {self.stats[LogCategory.ERROR]}\n")
            f.write(f"Warnings:        {self.stats[LogCategory.WARNING]}\n\n")
            
            # Error details
            errors = self.getEntriesByCategory(LogCategory.ERROR)
            if errors:
                f.write("-" * 40 + "\n")
                f.write(f"ERRORS ({len(errors)})\n")
                f.write("-" * 40 + "\n")
                for entry in errors:
                    f.write(f"Row {entry['rowIndex']}: {entry['finalName']}\n")
                    f.write(f"  {entry['message']}\n")
                f.write("\n")

            
            # Warning details
            warnings = self.getEntriesByCategory(LogCategory.WARNING)
            if warnings:
                f.write("-" * 40 + "\n")
                f.write(f"WARNINGS ({len(warnings)})\n")
                f.write("-" * 40 + "\n")
                for entry in warnings:
                    f.write(f"Row {entry['rowIndex']}: {entry['finalName']}\n")
                    f.write(f"  {entry['message']}\n")
                f.write("\n")
            
            f.write("=" * 80 + "\n")
            f.write("END OF REPORT\n")
            f.write("=" * 80 + "\n")
        
        print(f"\n[BATCH LOG] Report saved to: {self.logPath}")
        return self.logPath
