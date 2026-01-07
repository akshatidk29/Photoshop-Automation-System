from .baseDetector import getLocationCoordinates

# Location mapping for bags
BAG_MAPPING = {
    "FRONT (ON BAG)": {
        "landmarks": ["LEFT_HIP", "RIGHT_HIP"],
        "method": "midpoint",
        "yOffset": 100
    },
    "ON POCKET (ON BAG)": {
        "landmarks": ["LEFT_HIP", "RIGHT_HIP"],
        "method": "midpoint",
        "yOffset": 200
    }
}


def getBagCoordinates(imagePath, locationName, debug=False):
    """Get coordinates for bag decoration locations."""
    return getLocationCoordinates(imagePath, locationName, BAG_MAPPING, debug)
