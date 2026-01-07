from core.config import getLogFile

logPath = getLogFile()


def logError(message):
    """Log error message to file and console."""
    with open(logPath, "a", encoding="utf-8") as f:
        f.write(message + "\n")
    print("Logged:", message)
