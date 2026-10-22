from pathlib import Path

import pytest

from app.storage import Storage


@pytest.fixture
def storage(tmp_path: Path):
    instance = Storage(tmp_path / "test.db")
    yield instance
    instance.close()
