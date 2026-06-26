"""Embedding cache for LaBSE sentence embeddings.

Caches embeddings as .npy files to avoid recomputing them repeatedly.
"""

import hashlib
import pickle
from pathlib import Path

import numpy as np

from ruzh_translator.config import EMBEDDING_CACHE_DIR


def _text_hash(text: str) -> str:
    """Generate a stable hash for a text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def get_cached_embedding(text: str) -> np.ndarray | None:
    """Look up a cached embedding for the given text.

    Args:
        text: Input text to look up.

    Returns:
        Numpy array if cached, None otherwise.
    """
    cache_path = EMBEDDING_CACHE_DIR / f"{_text_hash(text)}.npy"
    if cache_path.exists():
        try:
            return np.load(cache_path)
        except (ValueError, OSError):
            cache_path.unlink(missing_ok=True)
    return None


def cache_embedding(text: str, embedding: np.ndarray):
    """Cache an embedding for the given text.

    Args:
        text: Input text.
        embedding: The embedding vector.
    """
    cache_path = EMBEDDING_CACHE_DIR / f"{_text_hash(text)}.npy"
    np.save(cache_path, embedding)


def get_cached_embeddings_batch(texts: list[str]) -> tuple[list[str], np.ndarray | None, list[int]]:
    """Check cache for a batch of texts.

    Args:
        texts: List of text strings.

    Returns:
        Tuple of (uncached_texts, cached_embeddings_array, uncached_indices).
    """
    uncached = []
    cached_embs = []
    uncached_indices = []

    for i, text in enumerate(texts):
        emb = get_cached_embedding(text)
        if emb is not None:
            cached_embs.append(emb)
        else:
            uncached.append(text)
            uncached_indices.append(i)

    cached_arr = np.stack(cached_embs) if cached_embs else None
    return uncached, cached_arr, uncached_indices


def cache_embeddings_batch(texts: list[str], embeddings: np.ndarray):
    """Cache a batch of embeddings.

    Args:
        texts: List of text strings.
        embeddings: Numpy array of embeddings.
    """
    for text, emb in zip(texts, embeddings):
        cache_embedding(text, emb)


def clear_cache():
    """Remove all cached embeddings."""
    for cache_file in EMBEDDING_CACHE_DIR.glob("*.npy"):
        cache_file.unlink()
