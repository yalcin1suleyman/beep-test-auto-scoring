"""
test_validators.py — Validator modülü testleri
"""

import pytest
from pathlib import Path
import tempfile

from validators import (
    validate_file_exists,
    validate_directory_exists,
    validate_video_file,
    validate_yolo_model,
    ValidationError,
)


class TestValidateFileExists:
    """validate_file_exists testleri."""
    
    def test_file_exists_returns_true(self):
        """Dosya varsa True döndür."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            assert validate_file_exists(tmp_path, required=True) is True
        finally:
            tmp_path.unlink()
    
    def test_file_not_exists_required_raises(self):
        """Dosya yoksa ve required=True ise hata fırlatır."""
        with pytest.raises(ValidationError):
            validate_file_exists(Path("/nonexistent/file.txt"), required=True)
    
    def test_file_not_exists_not_required_returns_false(self):
        """Dosya yoksa ve required=False ise False döndür."""
        assert validate_file_exists(Path("/nonexistent/file.txt"), required=False) is False


class TestValidateDirectoryExists:
    """validate_directory_exists testleri."""
    
    def test_directory_exists_returns_path(self):
        """Klasör varsa Path döndür."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_directory_exists(tmpdir)
            assert result == Path(tmpdir)
    
    def test_directory_not_exists_create_true(self):
        """Klasör yoksa ve create_if_missing=True ise oluştur."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new_folder"
            result = validate_directory_exists(new_dir, create_if_missing=True)
            assert result.exists()
            assert result.is_dir()
    
    def test_directory_not_exists_create_false_raises(self):
        """Klasör yoksa ve create_if_missing=False ise hata fırlatır."""
        with pytest.raises(ValidationError):
            validate_directory_exists(Path("/nonexistent/folder"), create_if_missing=False)


class TestValidateVideoFile:
    """validate_video_file testleri."""
    
    def test_video_not_exists_raises(self):
        """Video yoksa hata fırlatır."""
        with pytest.raises(ValidationError):
            validate_video_file(Path("/nonexistent/video.mp4"))
    
    def test_video_exists_returns_path(self):
        """Video varsa Path döndür."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            result = validate_video_file(tmp_path)
            assert result == tmp_path
        finally:
            tmp_path.unlink()


class TestValidateYoloModel:
    """validate_yolo_model testleri."""
    
    def test_model_not_exists_raises(self):
        """Model yoksa hata fırlatır."""
        with pytest.raises(ValidationError):
            validate_yolo_model(Path("/nonexistent/model.pt"))
    
    def test_model_wrong_extension_raises(self):
        """Model .pt uzantısında değilse hata fırlatır."""
        with tempfile.NamedTemporaryFile(suffix=".pth", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            with pytest.raises(ValidationError):
                validate_yolo_model(tmp_path)
        finally:
            tmp_path.unlink()
    
    def test_model_correct_extension_returns_path(self):
        """Model .pt uzantısındaysa Path döndür."""
        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            result = validate_yolo_model(tmp_path)
            assert result == tmp_path
        finally:
            tmp_path.unlink()
