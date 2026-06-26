"""Text processing utilities: encoding detection, sentence splitting."""

import re

import chardet

# Sentence-ending patterns for Russian and Chinese
_SENTENCE_END_RU = re.compile(
    r'([^.!?…]+[.!?…]+[\s»”’]*)',
    re.S,
)
_SENTENCE_END_ZH = re.compile(
    r'([^。！？；…!?]+[。！？；…!?]+)|([^。！？；…!?]+$)',
    re.S,
)


def detect_encoding(file_path: str) -> str:
    """Detect the encoding of a text file using chardet.

    Args:
        file_path: Path to the file.

    Returns:
        Detected encoding name (e.g., 'utf-8', 'windows-1251').
    """
    with open(file_path, "rb") as f:
        raw = f.read(100_000)  # Sample first 100KB
    result = chardet.detect(raw)
    return result["encoding"] or "utf-8"


def read_text_file(file_path: str) -> str:
    """Read a text file with automatic encoding detection.

    Args:
        file_path: Path to the text file.

    Returns:
        File contents as a string.
    """
    encoding = detect_encoding(file_path)
    with open(file_path, "r", encoding=encoding, errors="replace") as f:
        return f.read()


def detect_language(text: str) -> str:
    """Simple heuristic language detection based on Unicode ranges.

    Args:
        text: Input text.

    Returns:
        'ru' if primarily Cyrillic, 'zh-CN' if primarily CJK, else 'unknown'.
    """
    cyrillic = 0
    cjk = 0
    for ch in text[:5000]:
        cp = ord(ch)
        if 0x0400 <= cp <= 0x04FF or 0x0500 <= cp <= 0x052F:
            cyrillic += 1
        elif 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            cjk += 1
    if cyrillic > cjk and cyrillic > 10:
        return "ru"
    elif cjk > cyrillic and cjk > 10:
        return "zh-CN"
    return "unknown"


def split_sentences_ru(text: str) -> list[str]:
    """Split Russian text into sentences.

    Uses regex patterns for Russian punctuation, falls back to
    nltk if available for more accuracy.
    """
    text = text.replace("\r\n", "\n").strip()
    try:
        import nltk
        try:
            return nltk.sent_tokenize(text, language="russian")
        except Exception:
            # NLTK data not available or network error — use regex fallback
            pass
    except ImportError:
        pass

    # Fallback regex-based splitting
    sentences = [m.group(0).strip() for m in _SENTENCE_END_RU.finditer(text)]
    return [s for s in sentences if s]


def split_sentences_zh(text: str) -> list[str]:
    """Split Chinese text into sentences using regex."""
    text = text.replace("\r\n", "\n").strip()
    sentences = [m.group(0).strip() for m in _SENTENCE_END_ZH.finditer(text)]
    return [s for s in sentences if s]


def split_sentences(text: str, language: str = "ru") -> list[str]:
    """Split text into sentences based on language.

    Args:
        text: Input text.
        language: 'ru' for Russian, 'zh-CN' for Chinese.

    Returns:
        List of sentence strings.
    """
    if language == "zh-CN":
        return split_sentences_zh(text)
    return split_sentences_ru(text)


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs (by double newline or single newline).

    Args:
        text: Input text.

    Returns:
        List of paragraph strings.
    """
    text = text.replace("\r\n", "\n").strip()
    # Split by double newline first, then single if no double newlines found
    if "\n\n" in text:
        paragraphs = text.split("\n\n")
    else:
        paragraphs = text.split("\n")
    return [p.strip() for p in paragraphs if p.strip()]
