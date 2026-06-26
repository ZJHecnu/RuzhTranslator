"""Translation Memory service: fuzzy matching, TMX import/export."""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from rapidfuzz import fuzz as rapidfuzz_distance
from sqlalchemy.orm import Session

from ruzh_translator.models.tm import TranslationMemoryEntry

logger = logging.getLogger(__name__)


def exact_match(
    session: Session,
    source_text: str,
    source_lang: str = "ru",
    target_lang: str = "zh-CN",
) -> Optional[TranslationMemoryEntry]:
    """Find an exact match in TM.

    Args:
        session: Database session.
        source_text: Source text to match.
        source_lang: Source language code.
        target_lang: Target language code.

    Returns:
        Matching TM entry or None.
    """
    entry = (
        session.query(TranslationMemoryEntry)
        .filter(
            TranslationMemoryEntry.source_text == source_text,
            TranslationMemoryEntry.source_lang == source_lang,
            TranslationMemoryEntry.target_lang == target_lang,
        )
        .first()
    )
    if entry:
        _record_usage(session, entry)
    return entry


def fuzzy_match(
    session: Session,
    source_text: str,
    source_lang: str = "ru",
    target_lang: str = "zh-CN",
    threshold: float = 0.75,
    limit: int = 10,
) -> list[dict]:
    """Fuzzy match source text against TM entries.

    Uses rapidfuzz for fast partial ratio matching.

    Args:
        session: Database session.
        source_text: Source text to match.
        source_lang: Source language code.
        target_lang: Target language code.
        threshold: Minimum similarity score (0.0-1.0).
        limit: Maximum number of results.

    Returns:
        List of dicts with 'entry', 'score' keys, sorted by score descending.
    """
    # Get candidate entries (same language pair, reasonable length)
    length = len(source_text)
    min_len = max(10, int(length * 0.5))
    max_len = int(length * 2.0)

    candidates = (
        session.query(TranslationMemoryEntry)
        .filter(
            TranslationMemoryEntry.source_lang == source_lang,
            TranslationMemoryEntry.target_lang == target_lang,
        )
        .all()
    )

    results = []
    for entry in candidates:
        score = rapidfuzz_distance.partial_ratio(
            source_text.lower(),
            entry.source_text.lower(),
        ) / 100.0

        if score >= threshold:
            results.append({"entry": entry, "score": round(score, 4)})

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def semantic_match(
    source_text: str,
    entries: list[TranslationMemoryEntry],
    threshold: float = 0.85,
    limit: int = 5,
) -> list[dict]:
    """Semantic match using LaBSE embedding similarity.

    Args:
        source_text: Source text to match.
        entries: Candidate TM entries.
        threshold: Minimum cosine similarity.
        limit: Maximum number of results.

    Returns:
        List of dicts with 'entry', 'score' keys.
    """
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("LaBSE")
    except ImportError:
        return []

    if not entries:
        return []

    src_emb = model.encode([source_text], show_progress_bar=False)[0]
    tgt_texts = [e.source_text for e in entries]
    tgt_embs = model.encode(tgt_texts, show_progress_bar=False)

    src_norm = src_emb / np.linalg.norm(src_emb)
    tgt_norm = tgt_embs / np.linalg.norm(tgt_embs, axis=1, keepdims=True)
    scores = np.dot(tgt_norm, src_norm)

    results = []
    for i, score in enumerate(scores):
        if score >= threshold:
            results.append({"entry": entries[i], "score": round(float(score), 4)})

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def find_best_match(
    session: Session,
    source_text: str,
    source_lang: str = "ru",
    target_lang: str = "zh-CN",
) -> Optional[dict]:
    """Find the best TM match using a cascade strategy.

    1. Exact match first
    2. Fuzzy match with rapidfuzz
    3. Return best overall

    Args:
        session: Database session.
        source_text: Source text.
        source_lang: Source language code.
        target_lang: Target language code.

    Returns:
        Dict with 'entry' and 'score', or None.
    """
    # Step 1: Exact match
    exact = exact_match(session, source_text, source_lang, target_lang)
    if exact:
        return {"entry": exact, "score": 1.0, "match_type": "exact"}

    # Step 2: Fuzzy match
    fuzzy_results = fuzzy_match(session, source_text, source_lang, target_lang)
    if fuzzy_results:
        best = fuzzy_results[0]
        best["match_type"] = "fuzzy"
        return best

    return None


def add_tm_entry(
    session: Session,
    source_text: str,
    target_text: str,
    source_lang: str = "ru",
    target_lang: str = "zh-CN",
    project_id: str = "",
    domain: str = "",
) -> TranslationMemoryEntry:
    """Add or update a TM entry.

    If an exact source match already exists, update its target text.

    Args:
        session: Database session.
        source_text: Source language text.
        target_text: Target language text.
        source_lang: Source language code.
        target_lang: Target language code.
        project_id: Optional project ID.
        domain: Optional domain tag.

    Returns:
        The TranslationMemoryEntry.
    """
    existing = (
        session.query(TranslationMemoryEntry)
        .filter(
            TranslationMemoryEntry.source_text == source_text,
            TranslationMemoryEntry.source_lang == source_lang,
            TranslationMemoryEntry.target_lang == target_lang,
        )
        .first()
    )

    if existing:
        existing.target_text = target_text
        existing.usage_count += 1
        existing.last_used_at = datetime.utcnow()
        session.commit()
        return existing

    entry = TranslationMemoryEntry(
        source_text=source_text,
        target_text=target_text,
        source_lang=source_lang,
        target_lang=target_lang,
        project_id=project_id,
        domain=domain,
    )
    session.add(entry)
    session.commit()
    return entry


def concordance_search(
    session: Session,
    query: str,
    source_lang: str = "ru",
    target_lang: str = "zh-CN",
    limit: int = 20,
) -> list[dict]:
    """Search for a term/phrase in all TM source texts (concordance).

    Finds all TM entries whose source text contains the query,
    and returns the surrounding context.

    Args:
        session: Database session.
        query: Search term or phrase.
        source_lang: Source language code.
        target_lang: Target language code.
        limit: Maximum number of results.

    Returns:
        List of dicts with 'source_text', 'target_text', 'context' keys.
    """
    entries = (
        session.query(TranslationMemoryEntry)
        .filter(
            TranslationMemoryEntry.source_lang == source_lang,
            TranslationMemoryEntry.target_lang == target_lang,
            TranslationMemoryEntry.source_text.contains(query),
        )
        .limit(limit)
        .all()
    )

    results = []
    for entry in entries:
        # Extract context around the query term
        src = entry.source_text or ""
        idx = src.lower().find(query.lower())
        start = max(0, idx - 30)
        end = min(len(src), idx + len(query) + 30)
        context = ("..." if start > 0 else "") + src[start:end] + ("..." if end < len(src) else "")

        results.append({
            "source_text": entry.source_text,
            "target_text": entry.target_text,
            "context": context,
            "usage_count": entry.usage_count or 0,
        })

    return results


def _record_usage(session: Session, entry: TranslationMemoryEntry):
    """Record that a TM entry was used."""
    entry.usage_count = (entry.usage_count or 0) + 1
    entry.last_used_at = datetime.utcnow()
    session.commit()
