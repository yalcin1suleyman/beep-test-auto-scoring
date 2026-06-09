"""
conftest.py — Pytest yapılandırması
"""

import sys
from pathlib import Path

# Proje root'u sys.path'e ekle
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# pytest'i sessiz hale getir (ek output yok)
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "unit: Mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: Mark test as an integration test"
    )
