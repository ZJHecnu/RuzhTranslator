"""Alignment service: paragraph and sentence alignment for Russian-Chinese.

Integrates both regex-based alignment (from alligner.py) and semantic
alignment using LaBSE embeddings (from alligner2.py).
"""

import logging
from itertools import zip_longest
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

from ruzh_translator.utils.text_utils import (
    split_paragraphs,
    split_sentences,
    split_sentences_ru,
    split_sentences_zh,
)

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model = None


def _get_model():
    """Lazy-load the LaBSE model for semantic alignment."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("LaBSE")
            logger.info("LaBSE model loaded successfully")
        except ImportError:
            logger.warning("sentence-transformers not installed, using sequential alignment only")
    return _model


# ── Paragraph Alignment ─────────────────────────────────────────────


def align_paragraphs_sequential(
    src_paragraphs: list[str],
    tgt_paragraphs: list[str],
) -> list[tuple[int, int, float]]:
    """Simple sequential paragraph alignment (1:1 mapping).

    Returns:
        List of (src_index, tgt_index, confidence) tuples.
    """
    pairs = []
    for i, (src, tgt) in enumerate(zip_longest(src_paragraphs, tgt_paragraphs, fillvalue="")):
        confidence = 1.0 if (src and tgt) else 0.0
        pairs.append((i, i, confidence))
    return pairs


def align_paragraphs_semantic(
    src_paragraphs: list[str],
    tgt_paragraphs: list[str],
) -> list[tuple[int, int, float]]:
    """Semantic paragraph alignment using LaBSE + Hungarian algorithm.

    Returns:
        List of (src_index, tgt_index, confidence) tuples.
    """
    model = _get_model()
    if model is None:
        return align_paragraphs_sequential(src_paragraphs, tgt_paragraphs)

    src_embs = model.encode(src_paragraphs, show_progress_bar=False)
    tgt_embs = model.encode(tgt_paragraphs, show_progress_bar=False)

    # Cosine similarity matrix
    src_norm = src_embs / np.linalg.norm(src_embs, axis=1, keepdims=True)
    tgt_norm = tgt_embs / np.linalg.norm(tgt_embs, axis=1, keepdims=True)
    sim_matrix = np.dot(src_norm, tgt_norm.T)

    # Hungarian algorithm for optimal assignment
    cost_matrix = 1.0 - sim_matrix
    # Pad to square matrix
    n = max(len(src_paragraphs), len(tgt_paragraphs))
    padded = np.ones((n, n))
    padded[: len(src_paragraphs), : len(tgt_paragraphs)] = cost_matrix

    row_ind, col_ind = linear_sum_assignment(padded)

    pairs = []
    for src_idx, tgt_idx in zip(row_ind, col_ind):
        if src_idx < len(src_paragraphs) and tgt_idx < len(tgt_paragraphs):
            confidence = float(sim_matrix[src_idx, tgt_idx])
        else:
            confidence = 0.0
        pairs.append((int(src_idx), int(tgt_idx), confidence))

    # Sort by source index
    pairs.sort(key=lambda x: x[0])
    return pairs


def align_paragraphs(
    src_paragraphs: list[str],
    tgt_paragraphs: list[str],
    method: str = "semantic",
) -> list[tuple[int, int, float]]:
    """Align paragraphs.

    Args:
        src_paragraphs: Source language paragraphs.
        tgt_paragraphs: Target language paragraphs.
        method: 'sequential' or 'semantic'.

    Returns:
        List of (src_index, tgt_index, confidence) tuples.
    """
    if method == "semantic":
        return align_paragraphs_semantic(src_paragraphs, tgt_paragraphs)
    return align_paragraphs_sequential(src_paragraphs, tgt_paragraphs)


# ── Sentence Alignment ──────────────────────────────────────────────


def align_sentences_within_paragraph(
    src_para: str,
    tgt_para: str,
    src_lang: str = "ru",
    tgt_lang: str = "zh-CN",
    method: str = "semantic",
) -> list[tuple[int, int, float]]:
    """Align sentences within a single paragraph pair.

    Args:
        src_para: Source paragraph text.
        tgt_para: Target paragraph text.
        src_lang: Source language code.
        tgt_lang: Target language code.
        method: 'sequential' or 'semantic'.

    Returns:
        List of (src_sent_index, tgt_sent_index, confidence) tuples.
    """
    src_sents = split_sentences(src_para, src_lang)
    tgt_sents = split_sentences(tgt_para, tgt_lang)

    if not src_sents or not tgt_sents:
        return []

    if method == "sequential" or len(src_sents) <= 1 or len(tgt_sents) <= 1:
        pairs = []
        for i, (src, tgt) in enumerate(zip_longest(src_sents, tgt_sents, fillvalue="")):
            pairs.append((i, i, 0.5 if src and tgt else 0.0))
        return pairs

    # Semantic alignment
    model = _get_model()
    if model is None:
        return align_sentences_within_paragraph(
            src_para, tgt_para, src_lang, tgt_lang, method="sequential"
        )

    src_embs = model.encode(src_sents, show_progress_bar=False)
    tgt_embs = model.encode(tgt_sents, show_progress_bar=False)

    src_norm = src_embs / np.linalg.norm(src_embs, axis=1, keepdims=True)
    tgt_norm = tgt_embs / np.linalg.norm(tgt_embs, axis=1, keepdims=True)
    sim_matrix = np.dot(src_norm, tgt_norm.T)

    # Greedy alignment (from alligner2.py approach)
    if len(src_sents) >= len(tgt_sents):
        pairs = []
        used_tgt = set()
        for i, sims in enumerate(sim_matrix):
            best_tgt = int(np.argmax(sims))
            score = float(sims[best_tgt])
            pairs.append((i, best_tgt, score))
        return pairs
    else:
        pairs = []
        used_src = set()
        for j in range(sim_matrix.shape[1]):
            best_src = int(np.argmax(sim_matrix[:, j]))
            score = float(sim_matrix[best_src, j])
            pairs.append((best_src, j, score))
        # Deduplicate and sort
        seen = set()
        result = []
        for p in sorted(pairs, key=lambda x: x[0]):
            if p[0] not in seen:
                result.append(p)
                seen.add(p[0])
        return result


# ── Full Document Alignment ─────────────────────────────────────────


def align_documents(
    src_text: str,
    tgt_text: str,
    src_lang: str = "ru",
    tgt_lang: str = "zh-CN",
    para_method: str = "semantic",
    sent_method: str = "semantic",
) -> list[dict]:
    """Perform full document alignment (paragraph + sentence level).

    Args:
        src_text: Full source document text.
        tgt_text: Full target document text.
        src_lang: Source language code.
        tgt_lang: Target language code.
        para_method: Paragraph alignment method.
        sent_method: Sentence alignment method.

    Returns:
        List of alignment pair dicts with keys:
        para_index, sent_index, source_text, target_text, confidence.
    """
    src_paras = split_paragraphs(src_text)
    tgt_paras = split_paragraphs(tgt_text)

    para_pairs = align_paragraphs(src_paras, tgt_paras, method=para_method)

    all_pairs = []
    pair_index = 0

    for src_idx, tgt_idx, para_conf in para_pairs:
        src_para = src_paras[src_idx] if src_idx < len(src_paras) else ""
        tgt_para = tgt_paras[tgt_idx] if tgt_idx < len(tgt_paras) else ""

        sent_pairs = align_sentences_within_paragraph(
            src_para, tgt_para, src_lang, tgt_lang, method=sent_method
        )

        src_sents = split_sentences(src_para, src_lang)
        tgt_sents = split_sentences(tgt_para, tgt_lang)

        for s_src_idx, s_tgt_idx, sent_conf in sent_pairs:
            all_pairs.append({
                "para_index": int(src_idx),
                "sent_index": int(pair_index),
                "source_text": src_sents[s_src_idx] if s_src_idx < len(src_sents) else "",
                "target_text": tgt_sents[s_tgt_idx] if s_tgt_idx < len(tgt_sents) else "",
                "confidence": round(float(sent_conf) * float(para_conf), 4),
                "is_manually_corrected": False,
            })
            pair_index += 1

    return all_pairs


def save_alignment_to_db(
    session,
    project_id: str,
    document_id: str,
    alignment_pairs: list[dict],
):
    """Save alignment results to the database.

    Args:
        session: SQLAlchemy session.
        project_id: Project ID.
        document_id: Document ID.
        alignment_pairs: List of alignment pair dicts.

    Returns:
        List of created AlignmentPair instances.
    """
    from ruzh_translator.models.segment import AlignmentPair, Segment

    pairs = []
    for ap in alignment_pairs:
        # Create source segment
        src_seg = Segment(
            project_id=project_id,
            document_id=document_id,
            paragraph_index=ap["para_index"],
            segment_index=ap["sent_index"],
            source_text=ap["source_text"],
            target_text="",
            status="untranslated",
        )
        session.add(src_seg)
        session.flush()

        pair = AlignmentPair(
            project_id=project_id,
            document_id=document_id,
            paragraph_index=ap["para_index"],
            pair_index=ap["sent_index"],
            source_segment_id=src_seg.id,
            source_text=ap["source_text"],
            target_text=ap.get("target_text", ""),
            confidence_score=ap["confidence"],
            is_manually_corrected=1 if ap.get("is_manually_corrected") else 0,
        )
        session.add(pair)
        pairs.append(pair)

    session.commit()
    return pairs
