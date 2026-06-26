"""Sync service: synchronize local database with shared iCloud folder.

Handles:
- Exporting project data to shared folder (TMX + JSON)
- Importing project data from shared folder
- File locking to prevent concurrent writes
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ruzh_translator.models.project import Project
from ruzh_translator.models.segment import AlignmentPair, Segment
from ruzh_translator.models.glossary import GlossaryEntry
from ruzh_translator.utils.file_lock import FileLock
from ruzh_translator.utils.tmx_parser import export_tmx, parse_tmx

logger = logging.getLogger(__name__)


def export_project_to_shared(
    session: Session,
    project_id: str,
    shared_dir: Optional[str] = None,
) -> dict:
    """Export a project's data to the shared folder for team access.

    Creates:
    - project_manifest.json: Project metadata and summary
    - project_segments.json: All segments
    - project_glossary.json: Glossary entries
    - project.tmx: TMX exchange file

    Args:
        session: Database session.
        project_id: Project ID.
        shared_dir: Shared directory path (defaults to project's shared_folder_path).

    Returns:
        Dict with paths to exported files.
    """
    project = session.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    shared_dir = Path(shared_dir or project.shared_folder_path or ".")
    project_dir = shared_dir / f"project_{project.id}"
    project_dir.mkdir(parents=True, exist_ok=True)

    lock = FileLock(str(project_dir / ".lock"), timeout=5.0)

    if not lock.acquire():
        raise TimeoutError(f"Project {project.name} is locked by another user")

    try:
        # Export manifest
        manifest = {
            "project_id": project.id,
            "name": project.name,
            "description": project.description,
            "source_lang": project.source_lang,
            "target_lang": project.target_lang,
            "status": project.status,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
            "exported_at": datetime.utcnow().isoformat(),
            "progress": project.progress,
        }
        manifest_path = project_dir / "project_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # Export segments
        segments = (
            session.query(AlignmentPair)
            .filter(AlignmentPair.project_id == project_id)
            .order_by(AlignmentPair.paragraph_index, AlignmentPair.pair_index)
            .all()
        )
        segments_data = []
        for seg in segments:
            segments_data.append({
                "id": seg.id,
                "para_index": seg.paragraph_index,
                "pair_index": seg.pair_index,
                "source_text": seg.source_text,
                "target_text": seg.target_text or "",
                "confidence": seg.confidence_score,
                "is_corrected": bool(seg.is_manually_corrected),
            })
        seg_path = project_dir / "project_segments.json"
        with open(seg_path, "w", encoding="utf-8") as f:
            json.dump(segments_data, f, ensure_ascii=False, indent=2)

        # Export glossary
        glossary = (
            session.query(GlossaryEntry)
            .filter(GlossaryEntry.project_id == project_id)
            .all()
        )
        glossary_data = []
        for entry in glossary:
            glossary_data.append({
                "source_term": entry.source_term,
                "target_term": entry.target_term,
                "domain": entry.domain,
                "notes": entry.notes,
            })
        glos_path = project_dir / "project_glossary.json"
        with open(glos_path, "w", encoding="utf-8") as f:
            json.dump(glossary_data, f, ensure_ascii=False, indent=2)

        # Export TMX
        tmx_path = project_dir / "project.tmx"
        translated_pairs = [
            {"source_text": s.source_text, "target_text": s.target_text or ""}
            for s in segments
            if s.target_text
        ]
        export_tmx(
            translated_pairs,
            str(tmx_path),
            project.source_lang,
            project.target_lang,
        )

        return {
            "manifest": str(manifest_path),
            "segments": str(seg_path),
            "glossary": str(glos_path),
            "tmx": str(tmx_path),
        }
    finally:
        lock.release()


def import_project_from_shared(
    session: Session,
    shared_dir: str,
) -> Optional[Project]:
    """Import a project from shared folder data.

    Reads project_manifest.json and creates/updates the project in local DB.

    Args:
        session: Database session.
        shared_dir: Path to the project directory in shared folder.

    Returns:
        The imported/updated Project instance, or None if not found.
    """
    shared_path = Path(shared_dir)
    manifest_path = shared_path / "project_manifest.json"

    if not manifest_path.exists():
        logger.warning(f"No manifest found at {manifest_path}")
        return None

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Check if project already exists locally
    project = (
        session.query(Project)
        .filter(Project.id == manifest["project_id"])
        .first()
    )

    if not project:
        project = Project(
            id=manifest["project_id"],
            name=manifest["name"],
            description=manifest.get("description", ""),
            source_lang=manifest.get("source_lang", "ru"),
            target_lang=manifest.get("target_lang", "zh-CN"),
            status=manifest.get("status", "setup"),
        )
        session.add(project)
    else:
        project.name = manifest["name"]
        project.status = manifest.get("status", project.status)

    session.commit()

    # Import segments if available
    seg_path = shared_path / "project_segments.json"
    if seg_path.exists():
        with open(seg_path, "r", encoding="utf-8") as f:
            segments_data = json.load(f)

        for seg_data in segments_data:
            existing = (
                session.query(AlignmentPair)
                .filter(AlignmentPair.id == seg_data["id"])
                .first()
            )
            if not existing:
                pair = AlignmentPair(
                    id=seg_data["id"],
                    project_id=project.id,
                    paragraph_index=seg_data["para_index"],
                    pair_index=seg_data["pair_index"],
                    source_text=seg_data["source_text"],
                    target_text=seg_data.get("target_text", ""),
                    confidence_score=seg_data.get("confidence", 0),
                    is_manually_corrected=1 if seg_data.get("is_corrected") else 0,
                )
                session.add(pair)
            else:
                if not existing.target_text and seg_data.get("target_text"):
                    existing.target_text = seg_data["target_text"]

        session.commit()

    return project
