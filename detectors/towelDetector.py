from .baseDetector import getLocationCoordinates

# Location mapping for towels and blankets
TOWEL_MAPPING = {
    "CORNER-ANGLED-TOWEL": {
        "landmarks": ["LEFT_HIP"],
        "method": "single",
        "xOffset": 100,
        "yOffset": 200
    },
    "FRONT_CENTER": {
        "landmarks": ["LEFT_SHOULDER", "RIGHT_SHOULDER"],
        "method": "midpoint",
        "yOffset": 200
    }
}


def getTowelCoordinates(imagePath, locationName, debug=False):
    """Get coordinates for towel/blanket decoration locations."""
    return getLocationCoordinates(imagePath, locationName, TOWEL_MAPPING, debug)
