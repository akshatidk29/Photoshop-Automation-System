"""
Batch Logger Service
Comprehensive logging for entire batch processing with categories:
ERROR, FALLBACK, WARNING, SUCCESS.
Writes to log file in real-time and generates summary report.
"""

import os
import datetime
from typing import Dict, List, Any, Optional
from core.utils import ensureFolder


class LogCategory:
    """Log entry categories."""
    ERROR = "ERROR"
    FALLBACK = "FALLBACK"
    WARNING = "WARNING"
    SUCCESS = "SUCCESS"


class BatchLogger:
    """
    Comprehensive batch logger for tracking entire Excel processing.
    
    Features:
    - Real-time log file writing
    - Categorized entries (ERROR, FALLBACK, WARNING, SUCCESS)
    - Summary report generation
    - Statistics tracking
    """
    
    def __init__(self, batchName: str, outputDir: str):
        """
        Initialize batch logger.
        
        Args:
            batchName: Name of the batch (usually Excel filename)
            outputDir: Directory to save log files
        """
        self.batchName = batchName
        self.startTime = datetime.datetime.now()
        
        # Setup log directory
        self.logDir = os.path.join(outputDir, "logs")
        ensureFolder(self.logDir)
        
        # Log file path
        timestamp = self.startTime.strftime("%Y%m%d_%H%M%S")
        self.logPath = os.path.join(self.logDir, f"{batchName}_{timestamp}_batch.log")
        
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
        """Initialize the log file with header."""
        with open(self.logPath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("BATCH PROCESSING LOG\n")
            f.write("=" * 80 + "\n")
            f.write(f"Batch: {self.batchName}\n")
            f.write(f"Started: {self.startTime.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
    
    def _writeEntry(self, entry: Dict[str, Any]):
        """Write an entry to the log file immediately."""
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
        """
        Log an entry with category, row info, and message.
        
        Args:
            category: LogCategory constant (ERROR, FALLBACK, WARNING, SUCCESS)
            rowIndex: Row number in Excel
            finalName: Final image name for this row
            message: Log message
            details: Optional additional details
        """
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
        
        Args:
            rowIndex: Row number in Excel
            finalName: Final image name
            message: Error message
            reason: Optional reason for the error
        """
        fullMessage = message
        if reason:
            fullMessage += f" — Reason: {reason}"
        self.log(LogCategory.ERROR, rowIndex, finalName, fullMessage)
    
    def logFallback(self, rowIndex: int, finalName: str, message: str, 
                    fallbackUsed: str):
        """
        Log when a fallback option was used.
        
        Args:
            rowIndex: Row number in Excel
            finalName: Final image name
            message: What failed (e.g., "Model did not predict position")
            fallbackUsed: What fallback was used (e.g., "Used MediaPipe coordinates")
        """
        self.log(LogCategory.FALLBACK, rowIndex, finalName, 
                 f"{message} → Using: {fallbackUsed}")
    
    def logWarning(self, rowIndex: int, finalName: str, message: str):
        """
        Log a warning for a specific row.
        
        Args:
            rowIndex: Row number in Excel
            finalName: Final image name
            message: Warning message
        """
        self.log(LogCategory.WARNING, rowIndex, finalName, message)
    
    def logSuccess(self, rowIndex: int, finalName: str, message: str = "Processed successfully"):
        """
        Log successful processing.
        
        Args:
            rowIndex: Row number in Excel
            finalName: Final image name
            message: Success message
        """
        self.log(LogCategory.SUCCESS, rowIndex, finalName, message)
    
    def getStats(self) -> Dict[str, int]:
        """
        Get statistics for the batch.
        
        Returns:
            Dict with counts for each category and total
        """
        return dict(self.stats)
    
    def getEntriesByCategory(self, category: str) -> List[Dict[str, Any]]:
        """Get all entries of a specific category."""
        return [e for e in self.entries if e['category'] == category]
    
    def saveReport(self) -> str:
        """
        Generate and save summary report.
        
        Returns:
            Path to the saved report
        """
        endTime = datetime.datetime.now()
        duration = endTime - self.startTime
        
        with open(self.logPath, 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write("BATCH PROCESSING SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Batch: {self.batchName}\n")
            f.write(f"Started:  {self.startTime.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Finished: {endTime.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Duration: {duration}\n\n")
            
            f.write("-" * 40 + "\n")
            f.write("STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Processed: {self.stats['total']}\n")
            f.write(f"Successful:      {self.stats[LogCategory.SUCCESS]}\n")
            f.write(f"Errors:          {self.stats[LogCategory.ERROR]}\n")
            f.write(f"Fallbacks:       {self.stats[LogCategory.FALLBACK]}\n")
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
            
            # Fallback details
            fallbacks = self.getEntriesByCategory(LogCategory.FALLBACK)
            if fallbacks:
                f.write("-" * 40 + "\n")
                f.write(f"FALLBACKS ({len(fallbacks)})\n")
                f.write("-" * 40 + "\n")
                for entry in fallbacks:
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
