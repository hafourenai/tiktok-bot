"""Folder structure migration guide.

OLD STRUCTURE (flat):
├── converter.py           # Monolithic conversion API
├── ocr.py                # Direct tesseract wrapper
└── docconv/              # PDF library

NEW STRUCTURE (organized):
├── src/converter/
│   ├── __init__.py       # Public API exports
│   ├── api.py            # Main conversion functions (was converter.py)
│   ├── ocr.py            # Improved OCR wrapper with retry logic
│   ├── pipeline.py       # Workspace management
│   └── lib/
│       └── docconv/      # PDF library (encapsulated)

MIGRATION BENEFITS:
✓ Better separation of concerns
✓ OCR error handling improved (retry + better logging)
✓ Docconv encapsulated in subdirectory (cleaner structure)
✓ Easier to add new document handlers
✓ Single entry point (src.converter)

BREAKING CHANGES:
- Import from src.converter instead of converter
- OCR errors now raise OCRError/OCRUnavailable (typed exceptions)

BACKWARD COMPATIBILITY:
- bot.py updated to use new import path
- Same function signatures and behavior
- Old files can be removed after verification
"""

import sys
from pathlib import Path

# Verify docconv is accessible
docconv_path = Path(__file__).parent / "lib" / "docconv"
if docconv_path.is_dir():
    print(f"✓ Docconv library found at: {docconv_path}")
else:
    print(f"✗ Docconv library not found at: {docconv_path}")
    sys.exit(1)

# Quick sanity check on imports
try:
    from .api import SUPPORTED_EXTENSIONS
    print(f"✓ API exports {len(SUPPORTED_EXTENSIONS)} format conversions")
except ImportError as e:
    print(f"✗ Failed to import API: {e}")
    sys.exit(1)

print("✓ Structure migration verification passed")
