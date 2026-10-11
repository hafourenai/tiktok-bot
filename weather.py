"""Compatibility import for existing bot integrations; install with pip install -e ."""

import sys
from bmkg_location_resolver import resolver

# Preserve the legacy module identity, including monkeypatches in existing integrations.
sys.modules[__name__] = resolver
