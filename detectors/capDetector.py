from .baseDetector import getLocationCoordinates

# Location mapping for caps and hats
CAP_MAPPING = {
    "FRONT-CROWN": {
        "landmarks": ["NOSE"],
        "method": "single",
        "yOffset": -100
    },
    "CAP-BACK": {
        "landmarks": ["NOSE"],
        "method": "single",
        "yOffset": -150
    },
    "CAP-SIDE": {
        "landmarks": ["LEFT_EAR"],
        "method": "single",
        "xOffset": 50
    },
    "CAP-FRONT-SIDE": {
        "landmarks": ["LEFT_EYE"],
        "method": "single",
        "xOffset": 30,
        "yOffset": -80
    },
    "LOWER-LEFT-CROWN": {
        "landmarks": ["NOSE", "LEFT_EYE"],
        "method": "weighted",
        "alpha": 0.5,
        "yOffset": -50
    },
    "LOWER-RIGHT-CROWN": {
        "landmarks": ["NOSE", "RIGHT_EYE"],
        "method": "weighted",
        "alpha": 0.5,
        "yOffset": -50
    }
}


def getCapCoordinates(imagePath, locationName, debug=False):
    """Get coordinates for cap/hat decoration locations."""
    return getLocationCoordinates(imagePath, locationName, CAP_MAPPING, debug)
