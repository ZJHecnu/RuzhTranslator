"""Terminology extraction service.

Extracts candidate terms from Russian and Chinese text using
language-specific tools, with pure-Python fallback.
"""

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)


def _extract_ru_terms(text: str, top_n: int = 50) -> list[dict]:
    """Extract candidate terms from Russian text.

    Tries YAKE first, then pymorphy3, then falls back to
    regex-based multi-word phrase extraction.
    """
    terms = []

    # Try YAKE first
    try:
        import yake
        kw_extractor = yake.KeywordExtractor(lan="ru", top=top_n, n=3)
        keywords = kw_extractor.extract_keywords(text)
        for kw, score in keywords:
            terms.append({"term": kw, "score": round(score, 4),
                          "frequency": text.lower().count(kw.lower())})
        if terms: return terms
    except Exception:
        pass

    # Try pymorphy3
    try:
        from pymorphy3 import MorphAnalyzer
        morph = MorphAnalyzer()
        words = text.split(); phrases = []; i = 0
        while i < len(words):
            word = words[i].strip(".,!?;:()[]«»\"'")
            if not word: i += 1; continue
            try:
                parsed = morph.parse(word)[0]
                if parsed.tag.POS in ("NOUN", "ADJF"):
                    parts = [parsed.normal_form]
                    j = i + 1
                    while j < len(words) and j - i < 3:
                        nw = words[j].strip(".,!?;:()[]«»\"'")
                        if not nw: j += 1; continue
                        try:
                            np = morph.parse(nw)[0]
                            if np.tag.POS in ("NOUN", "ADJF"):
                                parts.append(np.normal_form); j += 1
                            else: break
                        except: break
                    if len(parts) >= 2: phrases.append(" ".join(parts)); i = j; continue
            except: pass
            i += 1
        counter = Counter(phrases)
        for phrase, freq in counter.most_common(top_n):
            if freq >= 2:
                terms.append({"term": phrase, "score": round(1.0/(1.0+freq), 4), "frequency": freq})
        if terms: return terms
    except Exception:
        pass

    # ── Pure Python fallback: regex multi-word extraction ──
    # Split into words, find repeated 2-3 word sequences
    clean = re.sub(r'[^\w\s]', ' ', text.lower())
    all_words = [w for w in clean.split() if len(w) >= 3]
    bigrams = [" ".join(all_words[i:i+2]) for i in range(len(all_words)-1)]
    trigrams = [" ".join(all_words[i:i+3]) for i in range(len(all_words)-2)]
    counter = Counter(bigrams + trigrams)
    for phrase, freq in counter.most_common(top_n):
        if freq >= 2:
            # Find original-cased version
            terms.append({"term": phrase, "score": round(1.0/(1.0+freq), 4), "frequency": freq})
    return terms


def _extract_zh_terms(text: str, top_n: int = 50) -> list[dict]:
    """Extract candidate terms from Chinese text using jieba.

    Args:
        text: Chinese text.
        top_n: Maximum number of terms to return.

    Returns:
        List of dicts with 'term', 'score', 'frequency' keys.
    """
    terms = []

    # Try YAKE first
    try:
        import yake
        kw_extractor = yake.KeywordExtractor(
            lan="zh",
            top=top_n,
            n=3,
            features=None,
        )
        keywords = kw_extractor.extract_keywords(text)
        for kw, score in keywords:
            terms.append({
                "term": kw,
                "score": round(score, 4),
                "frequency": text.count(kw),
            })
        return terms
    except ImportError:
        pass

    # Fallback: jieba TF-IDF + POS filtering
    try:
        import jieba.analyse
        keywords = jieba.analyse.extract_tags(
            text,
            topK=top_n,
            withWeight=True,
            allowPOS=("n", "nr", "ns", "nt", "nz", "v", "vn", "a"),
        )
        for kw, weight in keywords:
            terms.append({
                "term": kw,
                "score": round(1.0 / (1.0 + weight), 4),
                "frequency": text.count(kw),
            })
    except ImportError:
        logger.debug("jieba not installed")

    return terms


def extract_terms(
    text: str,
    language: str = "ru",
    top_n: int = 50,
) -> list[dict]:
    """Extract candidate terms from text.

    Args:
        text: Input text.
        language: Language code ('ru' or 'zh-CN').
        top_n: Maximum number of terms.

    Returns:
        List of dicts with 'term', 'score', 'frequency'.
    """
    if language == "zh-CN":
        return _extract_zh_terms(text, top_n)
    return _extract_ru_terms(text, top_n)


def extract_terms_from_segments(
    segments: list,
    language: str = "ru",
    top_n: int = 100,
) -> list[dict]:
    """Extract candidate terms from a list of segments.

    Args:
        segments: List of Segment ORM instances.
        language: Language of the source text.
        top_n: Maximum number of terms.

    Returns:
        List of term dicts.
    """
    combined_text = " ".join(seg.source_text for seg in segments if seg.source_text)
    return extract_terms(combined_text, language, top_n)


def translate_terms_with_ai(
    terms: list[str],
    source_lang: str = "ru",
    target_lang: str = "zh-CN",
) -> dict[str, str]:
    """Use AI API to translate extracted terms.

    Requires AI settings to be configured in preferences.

    Args:
        terms: List of source terms to translate.
        source_lang: Source language code.
        target_lang: Target language code.

    Returns:
        Dict mapping source_term → ai_translated_term.
        If AI is not configured or fails, returns empty dict.
    """
    from ruzh_translator.ui.settings_dialog import get_ai_config

    config = get_ai_config()
    if not config["enabled"] or not config["key"]:
        return {}

    if not terms:
        return {}

    lang_names = {"ru": "俄语", "zh-CN": "中文"}
    src_name = lang_names.get(source_lang, source_lang)
    tgt_name = lang_names.get(target_lang, target_lang)

    prompt = (
        f"请将以下{src_name}术语翻译为{tgt_name}。"
        f"对于每个术语，给出最准确的翻译。"
        f"格式: 源术语 -> 目标翻译\n\n"
        + "\n".join(terms[:30])  # Limit to 30 terms per call
    )

    try:
        import urllib.request
        import json

        req = urllib.request.Request(
            f"{config['url'].rstrip('/')}/chat/completions",
            data=json.dumps({
                "model": config["model"],
                "messages": [
                    {"role": "system", "content": "你是一个专业的俄汉翻译助手，擅长术语翻译。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            }).encode(),
            headers={
                "Authorization": f"Bearer {config['key']}",
                "Content-Type": "application/json",
            },
        )

        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"]

        # Parse response: "term -> translation"
        results = {}
        for line in content.strip().split("\n"):
            if "->" in line or "→" in line:
                sep = "->" if "->" in line else "→"
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    src = parts[0].strip()
                    tgt = parts[1].strip()
                    results[src] = tgt

        return results

    except Exception as e:
        logger.warning(f"AI term translation failed: {e}")
        return {}
