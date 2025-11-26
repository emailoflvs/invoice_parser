"""Конфигурация pytest"""
import pytest
from pathlib import Path
import tempfile
import shutil

@pytest.fixture
def temp_dir():
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)
