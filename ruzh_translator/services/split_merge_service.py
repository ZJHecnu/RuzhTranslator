"""Task splitting and merging service for distributed translation.

Handles:
- Splitting aligned segments into task packages for multiple translators
- Merging completed task packages back into the project
- Conflict detection and resolution
"""

import json
import logging
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ruzh_translator.models.segment import AlignmentPair, Segment
from ruzh_translator.models.task import TaskAssignment

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────

MIN_CHUNK_SIZE = 10   # Minimum segments per translator
MAX_CHUNK_SIZE = 100  # Maximum segments per translator
CONTEXT_OVERLAP = 2   # Number of context segments before/after each chunk


# ── Splitting ─────────────────────────────────────────────────────


def split_segments_by_paragraph(
    alignment_pairs: list[AlignmentPair],
    num_translators: int,
) -> list[list[AlignmentPair]]:
    """Split aligned segments into chunks, preserving paragraph boundaries.

    Args:
        alignment_pairs: List of AlignmentPair instances, sorted by order.
        num_translators: Number of translators to split across.

    Returns:
        List of chunks, each chunk is a list of AlignmentPair instances.
    """
    if not alignment_pairs:
        return []

    total = len(alignment_pairs)
    target_per = max(MIN_CHUNK_SIZE, min(MAX_CHUNK_SIZE, total // num_translators))

    chunks = []
    current_chunk = []
    current_para = None

    for pair in alignment_pairs:
        # Start new chunk at paragraph boundary when we've reached target size
        if (
            current_para is not None
            and pair.paragraph_index != current_para
            and len(current_chunk) >= target_per
        ):
            # Add context overlap from next chunk (read-only)
            chunks.append(current_chunk)
            current_chunk = []

        current_para = pair.paragraph_index
        current_chunk.append(pair)

    if current_chunk:
        chunks.append(current_chunk)

    # Merge small last chunk into previous if possible
    if len(chunks) >= 2 and len(chunks[-1]) < MIN_CHUNK_SIZE:
        chunks[-2].extend(chunks[-1])
        chunks.pop()

    return chunks


def create_task_package(
    project_name: str,
    translator_name: str,
    assigned_by: str,
    alignment_chunk: list[AlignmentPair],
    glossary_entries: list,
    tm_entries: list,
    output_path: str,
    deadline: Optional[datetime] = None,
) -> str:
    """Create a .ruzh_task package for a translator.

    Args:
        project_name: Name of the project.
        translator_name: Name of the assigned translator.
        assigned_by: Name of the person assigning the task.
        alignment_chunk: List of AlignmentPair instances for this chunk.
        glossary_entries: Relevant glossary entries.
        tm_entries: Relevant TM entries.
        output_path: Path to write the .ruzh_task file.
        deadline: Optional deadline.

    Returns:
        Path to the created task file.
    """
    if not alignment_chunk:
        raise ValueError("Cannot create task package with no segments")

    # Build manifest
    manifest = {
        "task_id": f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "project_name": project_name,
        "translator": translator_name,
        "assigned_by": assigned_by,
        "created_at": datetime.utcnow().isoformat(),
        "deadline": deadline.isoformat() if deadline else None,
        "total_segments": len(alignment_chunk),
        "source_lang": "ru",
        "target_lang": "zh-CN",
        "version": 1,
    }

    # Build segments data
    segments = []
    for pair in alignment_chunk:
        segments.append({
            "pair_id": pair.id,
            "para_index": pair.paragraph_index,
            "pair_index": pair.pair_index,
            "source_text": pair.source_text,
            "target_text": pair.target_text or "",
            "confidence": pair.confidence_score,
        })

    # Build glossary subset
    glossary_data = []
    for entry in glossary_entries:
        glossary_data.append({
            "source_term": entry.source_term,
            "target_term": entry.target_term,
            "domain": entry.domain or "",
            "notes": entry.notes or "",
        })

    # Build TM subset
    tm_data = []
    for entry in tm_entries:
        tm_data.append({
            "source_text": entry.source_text,
            "target_text": entry.target_text,
        })

    # Create zip archive
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("segments.json", json.dumps(segments, ensure_ascii=False, indent=2))
        if glossary_data:
            zf.writestr("glossary_subset.json", json.dumps(glossary_data, ensure_ascii=False, indent=2))
        if tm_data:
            zf.writestr("tm_subset.json", json.dumps(tm_data, ensure_ascii=False, indent=2))
        zf.writestr(
            "readme.txt",
            f"Translation Task: {project_name}\n"
            f"Translator: {translator_name}\n"
            f"Segments: {len(segments)}\n"
            f"Deadline: {deadline.strftime('%Y-%m-%d') if deadline else 'N/A'}\n"
            f"\n"
            f"Open this file with Ruzh Translator to begin translation.\n",
        )

    return output_path


def build_task_assignments(
    session: Session,
    project_id: str,
    translator_names: list[str],
    deadline: Optional[datetime] = None,
    output_dir: Optional[str] = None,
) -> list[TaskAssignment]:
    """Split a project and create task assignments for multiple translators.

    Args:
        session: Database session.
        project_id: Project ID.
        translator_names: List of translator names.
        deadline: Optional deadline for all tasks.
        output_dir: Directory to write task files (defaults to shared folder).

    Returns:
        List of created TaskAssignment instances.
    """
    from ruzh_translator.models.project import Project
    from ruzh_translator.models.glossary import GlossaryEntry
    from ruzh_translator.models.tm import TranslationMemoryEntry

    project = session.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    # Get alignment pairs
    pairs = (
        session.query(AlignmentPair)
        .filter(AlignmentPair.project_id == project_id)
        .order_by(AlignmentPair.paragraph_index, AlignmentPair.pair_index)
        .all()
    )

    if not pairs:
        raise ValueError("No aligned segments to split")

    # Split
    chunks = split_segments_by_paragraph(pairs, len(translator_names))

    # Get glossary and TM
    glossary = (
        session.query(GlossaryEntry)
        .filter(GlossaryEntry.project_id == project_id)
        .all()
    )
    tm_entries = (
        session.query(TranslationMemoryEntry)
        .filter(TranslationMemoryEntry.project_id == project_id)
        .all()
    )

    # Create task files
    output_dir = Path(output_dir or project.shared_folder_path or ".")
    output_dir.mkdir(parents=True, exist_ok=True)

    assignments = []
    for i, (translator_name, chunk) in enumerate(zip(translator_names, chunks)):
        if not chunk:
            continue

        task_path = output_dir / f"task_{project.name}_{translator_name}.ruzh_task"

        create_task_package(
            project_name=project.name,
            translator_name=translator_name,
            assigned_by="project_owner",
            alignment_chunk=chunk,
            glossary_entries=glossary,
            tm_entries=tm_entries,
            output_path=str(task_path),
            deadline=deadline,
        )

        assignment = TaskAssignment(
            project_id=project_id,
            translator_name=translator_name,
            segment_range_start=chunk[0].pair_index,
            segment_range_end=chunk[-1].pair_index,
            status="assigned",
            task_file_path=str(task_path),
            deadline=deadline,
        )
        session.add(assignment)
        assignments.append(assignment)

    session.commit()
    return assignments


# ── Merging ────────────────────────────────────────────────────────


def parse_task_file(task_path: str) -> dict:
    """Parse a .ruzh_task file and return its contents.

    Args:
        task_path: Path to the .ruzh_task file.

    Returns:
        Dict with 'manifest', 'segments', 'glossary', 'tm' keys.
    """
    with zipfile.ZipFile(task_path, "r") as zf:
        result = {}
        if "manifest.json" in zf.namelist():
            result["manifest"] = json.loads(zf.read("manifest.json").decode("utf-8"))
        if "segments.json" in zf.namelist():
            result["segments"] = json.loads(zf.read("segments.json").decode("utf-8"))
        result["glossary"] = []
        if "glossary_subset.json" in zf.namelist():
            result["glossary"] = json.loads(zf.read("glossary_subset.json").decode("utf-8"))
        result["tm"] = []
        if "tm_subset.json" in zf.namelist():
            result["tm"] = json.loads(zf.read("tm_subset.json").decode("utf-8"))
        return result


def detect_conflicts(
    tasks: list[dict],
) -> tuple[dict, list[dict]]:
    """Detect conflicts among multiple completed task files.

    Args:
        tasks: List of parsed task file dicts.

    Returns:
        Tuple of (merge_map, conflicts).
        merge_map: {pair_id: translated_text} for non-conflicting segments.
        conflicts: [{pair_id, translations: [{translator, text}]}] for conflicting.
    """
    # Collect all translations per pair_id
    translations = {}  # pair_id -> [(translator, text)]
    for task in tasks:
        translator = task["manifest"]["translator"]
        for seg in task["segments"]:
            pid = seg["pair_id"]
            text = seg.get("target_text", "").strip()
            if not text:
                continue
            if pid not in translations:
                translations[pid] = []
            translations[pid].append((translator, text))

    merge_map = {}
    conflicts = []

    for pid, trans_list in translations.items():
        if len(trans_list) == 1:
            merge_map[pid] = trans_list[0][1]
        else:
            # Check if all translations are identical
            texts = [t[1] for t in trans_list]
            if len(set(texts)) == 1:
                merge_map[pid] = texts[0]
            else:
                conflicts.append({
                    "pair_id": pid,
                    "translations": [
                        {"translator": t[0], "text": t[1]} for t in trans_list
                    ],
                })

    return merge_map, conflicts


def merge_tasks(
    session: Session,
    project_id: str,
    task_paths: list[str],
    conflict_resolutions: Optional[dict] = None,
) -> dict:
    """Merge completed task files into the project.

    Args:
        session: Database session.
        project_id: Project ID.
        task_paths: List of paths to completed .ruzh_task files.
        conflict_resolutions: {pair_id: chosen_text} for manual conflict resolution.

    Returns:
        Dict with 'merged_count', 'conflict_count', 'conflicts' keys.
    """
    conflict_resolutions = conflict_resolutions or {}

    # Parse all task files
    tasks = [parse_task_file(p) for p in task_paths]

    # Detect conflicts
    merge_map, conflicts = detect_conflicts(tasks)

    # Apply manual resolutions
    for pid, text in conflict_resolutions.items():
        merge_map[pid] = text
        conflicts = [c for c in conflicts if c["pair_id"] != pid]

    # Apply to database
    merged = 0
    for pair_id, target_text in merge_map.items():
        pair = (
            session.query(AlignmentPair)
            .filter(
                AlignmentPair.id == pair_id,
                AlignmentPair.project_id == project_id,
            )
            .first()
        )
        if pair:
            pair.target_text = target_text
            merged += 1

            # Also update the linked segment
            if pair.source_segment_id:
                seg = session.query(Segment).filter(Segment.id == pair.source_segment_id).first()
                if seg:
                    seg.target_text = target_text
                    seg.status = "translated"

    session.commit()

    return {
        "merged_count": merged,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
    }
