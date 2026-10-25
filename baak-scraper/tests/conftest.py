"""Pytest configuration and fixtures."""

import pytest
import os
from pathlib import Path


@pytest.fixture
def sample_baak_html():
    """Load sample BAAK HTML fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_baak.html"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def sample_empty_html():
    """Empty HTML fixture."""
    return "<html><body></body></html>"


@pytest.fixture
def sample_minimal_html():
    """Minimal HTML with no schedule data."""
    return """
    <html>
    <body>
        <table>
            <tr><td>Header</td></tr>
        </table>
    </body>
    </html>
    """
