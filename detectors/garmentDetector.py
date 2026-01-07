from .baseDetector import getLocationCoordinates, getRotationAngle, getLogoScale, getArmRotationAngle

# Location mapping for garments (T-shirts, shirts, hoodies, jackets, pants)
GARMENT_MAPPING = {
    "FULL-BACK": {
        "landmarks": ["LEFT_SHOULDER", "RIGHT_SHOULDER"],
        "method": "midpoint",
        "xOffset": -30,
        "yOffset": 80
    },
    "FULL-FRONT": {
        "landmarks": ["LEFT_SHOULDER", "RIGHT_SHOULDER"],
        "method": "midpoint",
        "yOffset": 170
    },
    "LEFT-BICEP": {
        "landmarks": ["LEFT_SHOULDER", "LEFT_ELBOW"],
        "method": "midpoint",
        "xOffset": 42,
        "yOffset": -35
    },
    "RIGHT-BICEP": {
        "landmarks": ["RIGHT_SHOULDER", "RIGHT_ELBOW"],
        "method": "midpoint",
        "xOffset": -71,
        "yOffset": -13
    },
    "LEFT-CHEST": {
        "landmarks": ["LEFT_SHOULDER", "RIGHT_SHOULDER"],
        "method": "shoulderBias",
        "side": "left",
        "alpha": 0.5,
        "yOffset": 80
    },
    "RIGHT-CHEST": {
        "landmarks": ["LEFT_SHOULDER", "RIGHT_SHOULDER"],
        "method": "shoulderBias",
        "side": "right",
        "alpha": 0.5,
        "yOffset": 80
    },
    "LEFT-COLLAR": {
        "landmarks": ["LEFT_SHOULDER"],
        "method": "single",
        "xOffset": -189,
        "yOffset": -100
    },
    "RIGHT-COLLAR": {
        "landmarks": ["RIGHT_SHOULDER"],
        "method": "single",
        "xOffset": 185,
        "yOffset": -110
    },
    "LEFT-CUFF": {
        "landmarks": ["LEFT_WRIST"],
        "method": "single",
        "xOffset": -10,
        "yOffset": 2
    },
    "RIGHT-CUFF": {
        "landmarks": ["RIGHT_WRIST"],
        "method": "single",
        "xOffset": -11,
        "yOffset": -16
    },
    "LEFT-HIP": {
        "landmarks": ["LEFT_HIP"],
        "method": "single",
        "xOffset": 50,
        "yOffset": 16
    },
    "RIGHT-HIP": {
        "landmarks": ["RIGHT_HIP"],
        "method": "single",
        "xOffset": -40,
        "yOffset": 16
    },
    "LEFT-SLEEVE": {
        "landmarks": ["LEFT_SHOULDER", "LEFT_ELBOW"],
        "method": "weighted",
        "alpha": 0.7,
        "xOffset": 42,
        "yOffset": -48
    },
    "RIGHT-SLEEVE": {
        "landmarks": ["RIGHT_SHOULDER", "RIGHT_ELBOW"],
        "method": "weighted",
        "alpha": 0.7,
        "xOffset": -9,
        "yOffset": -46
    },
    "LEFT-THIGH-HIGH": {
        "landmarks": ["LEFT_HIP"],
        "method": "single",
        "alpha": 0.2,
        "xOffset": 60,
        "yOffset": 16
    },
    "RIGHT-THIGH-HIGH": {
        "landmarks": ["RIGHT_HIP"],
        "method": "single",
        "alpha": 0.2,
        "xOffset": -60,
        "yOffset": 16
    },
    "ON-POCKET": {
        "landmarks": ["LEFT_HIP", "RIGHT_HIP"],
        "method": "midpoint",
        "xOffset": 220,
        "yOffset": -634
    },
    "BACK-YOKE": {
        "landmarks": ["LEFT_SHOULDER", "RIGHT_SHOULDER"],
        "method": "midpoint",
        "xOffset": -21,
        "yOffset": -87
    }
}


def getGarmentCoordinates(imagePath, locationName, debug=False):
    """Get coordinates for garment decoration locations."""
    return getLocationCoordinates(imagePath, locationName, GARMENT_MAPPING, debug)


def getGarmentRotationAngle(imagePath, locationName):
    """Get rotation angle for garment logo placement."""
    return getRotationAngle(imagePath, locationName)


def getGarmentLogoScale(imagePath, locationName, baseLogoSize=(200, 100)):
    """Calculate logo scale for garment placement."""
    return getLogoScale(imagePath, locationName, baseLogoSize)


def getGarmentArmRotation(imagePath, locationName):
    """Get arm rotation for sleeve/bicep placements on garments."""
    return getArmRotationAngle(imagePath, locationName)
