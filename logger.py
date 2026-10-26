"""
logger.py — Merkezi Logging Sistemi
Tüm modüllerde print() yerine logging kullan.
Hem dosyaya hem de konsola çıkış sağlar.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# Çıktı klasörü
LOG_DIR = Path(__file__).parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Log dosyası adı (timestamp ile)
log_filename = LOG_DIR / f"mekik_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def setup_logger(name: str = "mekik_test", level=logging.DEBUG) -> logging.Logger:
    """
    Merkezi logger oluştur.
    
    Args:
        name: Logger adı
        level: Minimum log seviyesi (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Yapılandırılmış logger nesnesi
    """
    logger = logging.getLogger(name)
    
    # Logger zaten yapılandırılmışsa tekrar yapılandırma
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Format: [HH:MM:SS] [LEVEL] [Module] Message
    formatter = logging.Formatter(
        fmt='[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 1. Dosya handler — tüm mesajlar dosyaya
    try:
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[UYARI] Log dosyası oluşturulamadı: {e}")
    
    # 2. Konsol handler — INFO ve üzeri
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Global logger
logger = setup_logger()


def get_logger(module_name: str) -> logging.Logger:
    """
    Herhangi bir modülden logger al.
    
    Kullanım:
        from logger import get_logger
        log = get_logger(__name__)
        log.info("Başlandı")
    """
    return logger.getChild(module_name)


def log_exception(exc: Exception, context: str = ""):
    """Hata exception'ı detaylı logla."""
    logger.error(
        f"EXCEPTION: {context}\n{type(exc).__name__}: {str(exc)}",
        exc_info=True
    )
