"""
validators.py — Dosya ve Sistem Doğrulaması
Projenin çalışmaya başlamadan önce gereken dosyaları kontrol eder.
"""

import sys
from pathlib import Path
from logger import get_logger

log = get_logger(__name__)


class ValidationError(Exception):
    """Doğrulama hatası."""
    pass


def validate_file_exists(
    filepath: Path | str,
    description: str = "",
    required: bool = True
) -> bool:
    """
    Dosya var mı kontrol et.
    
    Args:
        filepath: Kontrol edilecek dosya yolu
        description: Hata mesajında gösterilecek açıklama
        required: Zorunlu mu? (True: hata fırlatır, False: uyarı yapar)
    
    Returns:
        Dosya varsa True
    
    Raises:
        ValidationError: required=True ve dosya yoksa
    """
    filepath = Path(filepath)
    
    if filepath.exists() and filepath.is_file():
        log.debug(f"✓ Dosya doğrulandı: {filepath}")
        return True
    
    msg = f"Dosya bulunamadı: {filepath}"
    if description:
        msg = f"{description}: {msg}"
    
    if required:
        log.error(msg)
        raise ValidationError(msg)
    else:
        log.warning(msg)
        return False


def validate_directory_exists(
    dirpath: Path | str,
    description: str = "",
    create_if_missing: bool = False
) -> Path:
    """
    Klasör var mı kontrol et, gerekirse oluştur.
    
    Args:
        dirpath: Kontrol edilecek klasör yolu
        description: Hata mesajında açıklama
        create_if_missing: Yoksa oluştur mu?
    
    Returns:
        Klasör yolu (Path nesnesi)
    
    Raises:
        ValidationError: Yoksa ve create_if_missing=False
    """
    dirpath = Path(dirpath)
    
    if dirpath.exists() and dirpath.is_dir():
        log.debug(f"✓ Klasör doğrulandı: {dirpath}")
        return dirpath
    
    if create_if_missing:
        try:
            dirpath.mkdir(parents=True, exist_ok=True)
            log.info(f"✓ Klasör oluşturuldu: {dirpath}")
            return dirpath
        except Exception as e:
            msg = f"Klasör oluşturulamadı: {dirpath} - {e}"
            log.error(msg)
            raise ValidationError(msg) from e
    
    msg = f"Klasör bulunamadı: {dirpath}"
    if description:
        msg = f"{description}: {msg}"
    log.error(msg)
    raise ValidationError(msg)


def validate_yolo_model(model_path: str | Path) -> Path:
    """
    YOLO model dosyası doğrula (.pt uzantısı).
    
    Args:
        model_path: Model dosya yolu
    
    Returns:
        Model yolu (Path)
    
    Raises:
        ValidationError: Model yoksa veya yanlış format
    """
    model_path = Path(model_path)
    
    if not model_path.is_file():
        log.error(f"YOLO model bulunamadı: {model_path}")
        raise ValidationError(
            f"YOLO model bulunamadı: {model_path}\n"
            f"Lütfen modeli indirin:\n"
            f"  python -c \"from ultralytics import YOLO; YOLO('yolov8n-pose.pt')\""
        )
    
    if model_path.suffix.lower() != '.pt':
        log.error(f"Geçersiz model uzantısı: {model_path.suffix} (beklenen: .pt)")
        raise ValidationError(f"Model dosyası .pt uzantısında olmalıdır: {model_path}")
    
    log.info(f"✓ YOLO model doğrulandı: {model_path}")
    return model_path


def validate_video_file(video_path: str | Path) -> Path:
    """
    Video dosyası doğrula.
    
    Args:
        video_path: Video dosya yolu
    
    Returns:
        Video yolu (Path)
    
    Raises:
        ValidationError: Video yoksa
    """
    video_path = Path(video_path)
    valid_exts = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
    
    if not video_path.is_file():
        log.error(f"Video bulunamadı: {video_path}")
        raise ValidationError(f"Video dosyası bulunamadı: {video_path}")
    
    if video_path.suffix.lower() not in valid_exts:
        log.warning(
            f"Bilinmeyen video formatı: {video_path.suffix}\n"
            f"Desteklenen: {valid_exts}"
        )
    
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    try:
        ret, frame = cap.read()
        if not cap.isOpened() or not ret or frame is None:
            raise ValidationError(f"Video okunamadi veya bozuk: {video_path}")
    finally:
        cap.release()
    log.info(f"✓ Video dosyası doğrulandı: {video_path}")
    return video_path


def validate_environment() -> dict:
    """
    Proje ortamını doğrula (tüm gerekli bağımlılıklar).
    
    Returns:
        dict: {module_name: is_available}
    
    Raises:
        ValidationError: Kritik bağımlılık eksikse
    """
    log.info("Sistem bağımlılıkları kontrol ediliyor...")
    
    required_modules = {
        'cv2': 'OpenCV (opencv-python)',
        'numpy': 'NumPy',
        'pandas': 'Pandas',
        'ultralytics': 'Ultralytics (YOLOv8)',
        'scipy': 'SciPy',
    }
    
    missing = []
    available = {}
    
    for module_name, display_name in required_modules.items():
        try:
            __import__(module_name)
            log.debug(f"  ✓ {display_name}")
            available[module_name] = True
        except ImportError:
            log.warning(f"  ✗ {display_name} bulunamadı")
            available[module_name] = False
            missing.append((module_name, display_name))
    
    if missing:
        missing_str = '\n  '.join([f"- {display_name} ({m})" for m, display_name in missing])
        raise ValidationError(
            f"Eksik bağımlılıklar:\n  {missing_str}\n\n"
            f"Kurmak için:\n  pip install -r requirements.txt"
        )
    
    log.info("✓ Tüm bağımlılıklar mevcut")
    return available


def validate_project_setup(project_root: Path | str) -> dict:
    """
    Proje klasör yapısını doğrula.
    
    Args:
        project_root: Proje root klasörü
    
    Returns:
        dict: paths (input_dir, output_dir, models_dir)
    
    Raises:
        ValidationError: Kritik klasörler eksikse
    """
    project_root = Path(project_root)
    log.info(f"Proje yapısı kontrol ediliyor: {project_root}")
    
    paths = {
        'input_dir': validate_directory_exists(
            project_root / 'data' / 'inputs',
            'Giriş klasörü',
            create_if_missing=True
        ),
        'output_dir': validate_directory_exists(
            project_root / 'data' / 'outputs',
            'Çıkış klasörü',
            create_if_missing=True
        ),
    }
    
    log.info("✓ Proje yapısı doğrulandı")
    return paths
