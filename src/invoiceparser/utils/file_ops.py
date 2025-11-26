"""Вспомогательные функции для работы с файлами"""
import hashlib
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

def find_documents_in_directory(directory: Path, extensions: List[str] = None) -> List[Path]:
    if extensions is None:
        extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']
    extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in extensions]
    documents = []
    for ext in extensions:
        documents.extend(directory.rglob(f'*{ext}'))
    logger.info(f"Found {len(documents)} documents in {directory}")
    return sorted(documents)

def ensure_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {directory}")

# Алиас для обратной совместимости
ensure_dir = ensure_directory

def get_file_hash(file_path: Path) -> str:
    """
    Вычисляет SHA256 хеш файла
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        SHA256 хеш в виде hex строки
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
