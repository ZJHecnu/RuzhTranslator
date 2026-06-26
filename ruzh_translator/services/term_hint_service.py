"""Term hint service: provides terminology suggestions during translation.

When a translator works on a segment, this service:
1. Extracts source terms from the current source sentence
2. Looks up translations in glossary and TM
3. Returns ranked suggestions
"""

import logging
from typing import Optional

from rapidfuzz import fuzz as rapidfuzz_distance
from sqlalchemy.orm import Session

from ruzh_translator.models.glossary import GlossaryEntry
from ruzh_translator.services.tm_service import fuzzy_match as tm_fuzzy_match

logger = logging.getLogger(__name__)


def get_term_hints(
    session: Session,
    source_sentence: str,
    project_id: str,
    source_lang: str = "ru",
    target_lang: str = "zh-CN",
    max_hints: int = 8,
) -> list[dict]:
    """Get terminology hints for a source sentence.

    Strategy:
    1. Look up exact source terms in project glossary
    2. Fuzzy-match source terms against glossary
    3. Fuzzy-match against TM entries
    4. Rank by match quality

    Args:
        session: Database session.
        source_sentence: The source sentence being translated.
        project_id: Current project ID.
        source_lang: Source language code.
        target_lang: Target language code.
        max_hints: Maximum number of hints to return.

    Returns:
        List of hint dicts with keys:
        source_term, target_term, score, source (glossary/tm), match_type.
    """
    if not source_sentence.strip():
        return []

    # Load project glossary
    glossary_entries = (
        session.query(GlossaryEntry)
        .filter(GlossaryEntry.project_id == project_id)
        .all()
    )

    hints = []

    # Strategy 1: Check if any glossary source terms appear in the sentence
    for entry in glossary_entries:
        if entry.source_term and entry.source_term.lower() in source_sentence.lower():
            hints.append({
                "source_term": entry.source_term,
                "target_term": entry.target_term,
                "score": 1.0,
                "source": "glossary",
                "match_type": "exact",
            })

    # Strategy 2: Fuzzy match sentence words against glossary
    words = _extract_content_words(source_sentence, source_lang)
    for word in words[:15]:  # Check top 15 content words
        if len(word) < 3:
            continue
        for entry in glossary_entries:
            if not entry.source_term:
                continue
            score = rapidfuzz_distance.partial_ratio(
                word.lower(), entry.source_term.lower()
            ) / 100.0
            if score > 0.80:
                # Avoid duplicates
                if not any(
                    h["source_term"] == entry.source_term and h["source"] == "glossary"
                    for h in hints
                ):
                    hints.append({
                        "source_term": entry.source_term,
                        "target_term": entry.target_term,
                        "score": round(score, 4),
                        "source": "glossary",
                        "match_type": "fuzzy",
                    })

    # Strategy 3: TM fuzzy match for the full sentence
    tm_results = tm_fuzzy_match(
        session,
        source_sentence,
        source_lang=source_lang,
        target_lang=target_lang,
        threshold=0.70,
        limit=3,
    )
    for result in tm_results:
        hints.append({
            "source_term": result["entry"].source_text[:80],
            "target_term": result["entry"].target_text[:120],
            "score": result["score"],
            "source": "tm",
            "match_type": "fuzzy",
        })

    # Sort by score descending, remove duplicates keeping best score
    hints.sort(key=lambda h: h["score"], reverse=True)

    # Deduplicate by source_term
    seen = set()
    unique_hints = []
    for hint in hints:
        key = (hint["source_term"].lower(), hint["source"])
        if key not in seen:
            seen.add(key)
            unique_hints.append(hint)

    return unique_hints[:max_hints]


def _extract_content_words(text: str, language: str) -> list[str]:
    """Extract content words from text for terminology matching.

    Args:
        text: Input text.
        language: Language code.

    Returns:
        List of content words (nouns, adjectives, verbs).
    """
    if language == "ru":
        # Russian: split by whitespace, filter punctuation
        words = []
        for w in text.split():
            cleaned = w.strip(".,!?;:()[]«»\"'-–—")
            if len(cleaned) >= 2:
                words.append(cleaned)
        return words
    else:
        # Chinese: use jieba if available
        try:
            import jieba
            words = list(jieba.cut(text))
            return [w for w in words if len(w.strip()) >= 1 and w.strip()]
        except ImportError:
            # Fallback: character-based n-grams
            return [text[i : i + 2] for i in range(len(text) - 1)]


def suggest_term_translations(
    source_term: str,
    project_id: str,
    session: Session,
    source_lang: str = "ru",
    target_lang: str = "zh-CN",
) -> list[str]:
    """Get suggested translations for a source term.

    Looks up from:
    1. Project glossary
    2. TM entries

    Args:
        source_term: Source language term.
        project_id: Project ID.
        session: Database session.
        source_lang: Source language code.
        target_lang: Target language code.

    Returns:
        List of suggested target translations, best first.
    """
    suggestions = []

    # Glossary lookup
    glossary_matches = (
        session.query(GlossaryEntry)
        .filter(
            GlossaryEntry.project_id == project_id,
            GlossaryEntry.source_term == source_term,
        )
        .all()
    )
    for entry in glossary_matches:
        if entry.target_term and entry.target_term not in suggestions:
            suggestions.append(entry.target_term)

    # TM fuzzy lookup
    tm_results = tm_fuzzy_match(
        session,
        source_term,
        source_lang=source_lang,
        target_lang=target_lang,
        threshold=0.70,
        limit=5,
    )
    for result in tm_results:
        target = result["entry"].target_text[:100]
        if target and target not in suggestions:
            suggestions.append(target)

    return suggestions[:5]
