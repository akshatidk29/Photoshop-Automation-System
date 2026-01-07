import os
from services.logger import logError


def findLogo(logoRoot, decorationCode):
    """Find logo file by decoration code."""
    if not decorationCode:
        return None

    for root, _, files in os.walk(logoRoot):
        for ext in (".pdf",):
            name = f"{decorationCode}{ext}"
            if name in files:
                return os.path.join(root, name)

    logError(f"Logo not found: {decorationCode}")
    return None
