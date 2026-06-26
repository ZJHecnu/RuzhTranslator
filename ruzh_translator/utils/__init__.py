"""Utility modules: text processing, TMX parsing, file locking, embedding cache."""

from ruzh_translator.utils.text_utils import (
    detect_encoding,
    read_text_file,
    detect_language,
    split_sentences,
    split_sentences_ru,
    split_sentences_zh,
    split_paragraphs,
)
from ruzh_translator.utils.tmx_parser import parse_tmx, export_tmx, import_tmx_to_db
from ruzh_translator.utils.file_lock import FileLock
from ruzh_translator.utils.embedding_cache import (
    get_cached_embedding,
    cache_embedding,
    clear_cache,
)

__all__ = [
    "detect_encoding", "read_text_file", "detect_language",
    "split_sentences", "split_sentences_ru", "split_sentences_zh", "split_paragraphs",
    "parse_tmx", "export_tmx", "import_tmx_to_db",
    "FileLock",
    "get_cached_embedding", "cache_embedding", "clear_cache",
]
