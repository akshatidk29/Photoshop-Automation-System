# Workflow Refactoring Implementation Plan

## Goal

Refactor the Photoshop automation workflow to:

1. Move all hardcoded values to YAML configuration files
2. Implement two-phase processing (pre-process Excel, then process rows)
3. Add comprehensive batch logging
4. Implement smart image scaling with configurable thresholds
5. Apply camelCase naming conventions throughout

---

## Completed Work ✓

### New Configuration Files

| File                                                                                                                           | Purpose                                                                                                                          |
| ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| [positionRegistry.yaml](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/positionRegistry.yaml)         | **Single source of truth** for all positions (40+ positions with aliases, sizes, clipping, garment types, OBB class names) |
| [imageProcessingRules.yaml](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/imageProcessingRules.yaml) | Scaling rules, entity scaling threshold (40px), background removal settings                                                      |
| [filenameMatching.yaml](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/filenameMatching.yaml)         | View indicators, ignore words, extensions for images and logos                                                                   |
| [outputConfig.yaml](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/outputConfig.yaml)                 | Output folder naming (Outputs/output1, output2), log settings                                                                    |

---

### New Services

#### [excelPreProcessor.py](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/services/excelPreProcessor.py)

Pre-processes entire Excel upfront:

- Finds all images and logos
- Resolves all positions from registry
- Detects garment types
- Generates enriched CSV with `__AUTO_` prefixed columns
- Returns errors/warnings before processing begins

#### [batchLogger.py](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/services/batchLogger.py)

Comprehensive batch logging:

- Tracks errors, fallbacks, warnings, successes
- Writes to log file in real-time
- Generates summary report at the end
- Provides statistics for monitoring

---

### Updated Modules

#### [configLoader.py](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py)

Added new functions:

- [resolvePosition()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#595-691) - resolve any position to canonical form with all properties
- [parseComboPositionFromRegistry()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#693-706) - parse combo positions
- [getLogoSizeFromRegistry()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#708-712), [isClippingEnabledFromRegistry()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#714-718), [getGarmentTypeFromRegistry()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#720-746)
- [getScalingRulesForCanvas()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#776-789), [getBackgroundRemovalSettings()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#791-795)
- [getAllowedImageExtensions()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#824-829), [getAllowedLogoExtensions()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#831-836)
- [getOutputFolderSettings()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#853-857), [getOutputBehaviorSettings()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#859-863)

#### [utils.py](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/core/utils.py)

- Replaced hardcoded `VALID_LOCATIONS` with [getValidLocations()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/core/utils.py#54-64) function
- [normalizeLocation()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/core/utils.py#76-98) now uses registry for canonical name resolution
- [detectGarmentTypeFromLocation()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/core/utils.py#100-114) uses [getGarmentTypeFromRegistry()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#720-746)

#### [comboParser.py](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/detectors/comboParser.py)

- Completely rewritten to use [positionRegistry.yaml](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/positionRegistry.yaml)
- No hardcoded fallback values
- Uses [parseComboPositionFromRegistry()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#693-706) and [resolvePosition()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#595-691)

#### [garmentDetector.py](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/detectors/garmentDetector.py)

- Replaced hardcoded `LOCATION_MAP` with dynamic loading from registry
- [_getObbClassName()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/detectors/garmentDetector.py#76-99) now uses [getObbClassNameFromRegistry()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/configLoader.py#748-752)

#### [logoLocator.py](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/locators/logoLocator.py)

- Replaced hardcoded `SUPPORTED_EXTENSIONS` with [_getExtensions()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/locators/logoLocator.py#29-35) function
- Extensions loaded from [filenameMatching.yaml](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/configuration/filenameMatching.yaml)

#### [imageProcessor.py](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/futureWork/imageProcessor.py)

Smart scaling implementation: 

1. First resize image to target dimensions (1200x1800 or 1200x1200)
2. Add white padding if aspect ratio differs
3. Detect entity bounds
4. **Only scale entity if top gap differs by >40px from target** (configurable threshold)
5. Replace background with white
6. Take inspiration from the futureWork directory.

---

## Remaining Work

### Phase 5: Main.py Integration

#### [MODIFY] [main.py](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/main.py)

Changes needed:

1. Import new services:

```python
from services.excelPreProcessor import preProcessExcel, EnrichedColumns
from services.batchLogger import BatchLogger
```

2. Implement two-phase architecture in [runAutomation()](file:///c:/Users/Akshat%20Mittal/Desktop/photoshopAutomation/main.py#1043-1207):

```python
# Phase 1: Pre-process Excel
result = preProcessExcel(excelPath, imageRoot, logoRoot, settings)
if result['stats']['errors'] > 0:
    # Show errors upfront, ask user whether to continue
  
# Phase 2: Process enriched rows
for row in result['enrichedRows']:
    # Use pre-resolved data from row
    imagePath = row[EnrichedColumns.IMAGE_PATH]
    logoPath = row[EnrichedColumns.LOGO_PATH]
    # ...
```

3. Implement output folder management:

```python
from configuration.configLoader import getOutputFolderSettings, getOutputBehaviorSettings

def getNextOutputFolder(clearPrevious):
    settings = getOutputFolderSettings()
    basePath = settings['basePath']  # "Outputs"
    prefix = settings['folderPrefix']  # "output"
  
    if clearPrevious:
        # Delete all Outputs/output* folders
        # Create Outputs/output1
    else:
        # Find next number and create Outputs/outputN
```

4. Integrate BatchLogger:

```python
logger = BatchLogger(os.path.basename(excelPath), outputDir)
# Log success/error/fallback for each row
logger.saveReport()
```

---

## Verification Plan

### Automated Tests

1. Test position resolution:

   ```bash
   python -c "from configuration.configLoader import resolvePosition; print(resolvePosition('LEFT-CHEST'))"
   ```
2. Test combo parsing:

   ```bash
   python -c "from detectors.comboParser import parseComboPosition; print(parseComboPosition('FULL-BACK & FULL-FRONT'))"
   ```
3. Test image processing:

   ```bash
   python futureWork/imageProcessor.py testing\Imges\SanMar\J354\J354TrRedTrBlkModelBack-1200W.jpg --canvas 1800
   ```

### Manual Verification

- [ ] Run full workflow with sample Excel file
- [ ] Verify output images have correct positioning
- [ ] Check log files in Outputs/logs
- [ ] Confirm output folder naming (output1, output2, etc.)

---

## Key Design Decisions

| Decision                           | Rationale                                                          |
| ---------------------------------- | ------------------------------------------------------------------ |
| `__AUTO_` column prefix          | Prevents clash with user-defined Excel columns                     |
| 40px entity scaling threshold      | Based on user requirement: only scale if gap differs significantly |
| Position registry as single source | Eliminates duplication across 5 YAML files                         |
| Two-phase architecture             | Enables upfront error detection and deterministic processing       |
| camelCase naming                   | Consistent with user's coding standards                            |

---

## Files Modified Summary

```
configuration/
├── positionRegistry.yaml       [NEW] - Master position registry
├── imageProcessingRules.yaml   [NEW] - Image processing rules
├── filenameMatching.yaml       [NEW] - Filename patterns
├── outputConfig.yaml           [NEW] - Output folder settings
└── configLoader.py             [MODIFIED] - Added registry functions

services/
├── excelPreProcessor.py        [NEW] - Excel pre-processing
└── batchLogger.py              [NEW] - Batch logging

core/
└── utils.py                    [MODIFIED] - Removed hardcoding

detectors/
├── comboParser.py              [MODIFIED] - Uses registry
└── garmentDetector.py          [MODIFIED] - Uses registry

locators/
└── logoLocator.py              [MODIFIED] - Uses YAML extensions

futureWork/
└── imageProcessor.py           [MODIFIED] - Smart scaling
```
