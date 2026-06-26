"""Application configuration and path detection."""

import os
import sys
from pathlib import Path


def _get_data_dir() -> Path:
    """Get the local data directory for the application.

    Uses ~/.ruzh_translation/ for per-user local database and cache.
    """
    home = Path.home()
    data_dir = home / ".ruzh_translation"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _get_shared_dir() -> Path:
    """Detect the iCloud shared project directory.

    The app is installed inside the iCloud directory, so we use
    the parent of this config file's grandparent as the shared root.
    """
    # config.py lives in ruzh_translator/ inside the shared folder
    this_file = Path(__file__).resolve()
    shared_dir = this_file.parent.parent
    return shared_dir


def _get_db_path() -> Path:
    """Get the path to the local SQLite database."""
    return _get_data_dir() / "ruzh_translator.db"


# ---- Exported constants ----
APP_NAME = "Ruzh Translator"
APP_VERSION = "0.1.0"
ORG_NAME = "RuzhTranslator"

DATA_DIR = _get_data_dir()
SHARED_DIR = _get_shared_dir()
DB_PATH = _get_db_path()
EMBEDDING_CACHE_DIR = DATA_DIR / "embeddings"
EMBEDDING_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Supported languages
SOURCE_LANGS = {"ru": "俄语", "zh-CN": "中文"}
TARGET_LANGS = {"ru": "俄语", "zh-CN": "中文"}

# Default language pair
DEFAULT_SOURCE_LANG = "ru"
DEFAULT_TARGET_LANG = "zh-CN"

# Segment statuses
SEGMENT_STATUSES = [
    "untranslated",   # 未翻译
    "draft",          # 草稿
    "translated",     # 已翻译
    "reviewed",       # 已审校
    "approved",       # 已批准
]

# Project statuses
PROJECT_STATUSES = [
    "setup",          # 设置中
    "alignment",      # 对齐阶段
    "translation",    # 翻译阶段
    "review",         # 审校阶段
    "completed",      # 已完成
]

# Supported import formats
IMPORT_FORMATS = {
    ".txt": "纯文本",
    ".docx": "Word 文档",
    ".pdf": "PDF 文档",
    ".rtf": "RTF 文档",
}

# Supported export formats
EXPORT_FORMATS = {
    "tmx": "TMX 翻译记忆",
    "xlsx": "Excel 表格",
    "docx": "Word 双语对照",
    "html": "HTML 网页预览",
    "txt": "纯文本",
}
