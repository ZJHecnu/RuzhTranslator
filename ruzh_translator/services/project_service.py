"""Project management service: CRUD operations and status tracking."""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ruzh_translator.models.project import Project, Document


def create_project(
    session: Session,
    name: str,
    source_lang: str = "ru",
    target_lang: str = "zh-CN",
    description: str = "",
    shared_folder_path: str = "",
) -> Project:
    """Create a new translation project.

    Also creates the project folder on disk.
    """
    project = Project(
        name=name,
        source_lang=source_lang,
        target_lang=target_lang,
        description=description,
        shared_folder_path=shared_folder_path,
        status="setup",
    )
    session.add(project)
    session.commit()

    # Create project folder
    create_project_folder(project.id, project.name)

    return project


def get_project(session: Session, project_id: str) -> Optional[Project]:
    """Get a project by ID."""
    return session.query(Project).filter(Project.id == project_id).first()


def list_projects(session: Session) -> list[Project]:
    """List all projects ordered by last update."""
    return session.query(Project).order_by(Project.updated_at.desc()).all()


def update_project_status(session: Session, project_id: str, status: str):
    """Update the status of a project.

    Args:
        session: Database session.
        project_id: Project ID.
        status: New status (must be one of PROJECT_STATUSES).
    """
    project = get_project(session, project_id)
    if project:
        project.status = status
        project.updated_at = datetime.utcnow()
        session.commit()


def delete_project(session: Session, project_id: str):
    """Delete a project and all associated data."""
    project = get_project(session, project_id)
    if project:
        session.delete(project)
        session.commit()


def add_document(
    session: Session,
    project_id: str,
    filename: str,
    file_format: str,
    raw_content: str,
    language: str = "",
    paragraph_count: int = 0,
) -> Document:
    """Add a document to a project.

    Args:
        session: Database session.
        project_id: Project ID.
        filename: Original filename.
        file_format: File extension (txt, docx, etc.).
        raw_content: Raw text content.
        language: Detected language code.
        paragraph_count: Number of paragraphs.

    Returns:
        The created Document instance.
    """
    doc = Document(
        project_id=project_id,
        filename=filename,
        file_format=file_format,
        raw_content=raw_content,
        language=language,
        paragraph_count=paragraph_count,
    )
    session.add(doc)
    session.commit()
    return doc


def get_documents(session: Session, project_id: str) -> list[Document]:
    """Get all documents for a project."""
    return (
        session.query(Document)
        .filter(Document.project_id == project_id)
        .order_by(Document.imported_at)
        .all()
    )


def create_project_folder(project_id: str, project_name: str) -> str:
    """Create the on-disk project folder structure.

    Creates: ~/.ruzh_translation/projects/<id>/
      ├── project.json
      ├── documents/
      ├── exports/
      └── tasks/

    Args:
        project_id: Project ID.
        project_name: Human-readable project name.

    Returns:
        Path to the project folder.
    """
    import json
    from pathlib import Path
    from datetime import datetime
    from ruzh_translator.config import DATA_DIR

    proj_dir = DATA_DIR / "projects" / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "documents").mkdir(exist_ok=True)
    (proj_dir / "exports").mkdir(exist_ok=True)
    (proj_dir / "tasks").mkdir(exist_ok=True)

    meta = {
        "project_id": project_id,
        "name": project_name,
        "created_at": datetime.utcnow().isoformat(),
    }
    with open(proj_dir / "project.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return str(proj_dir)


def get_project_folder(project_id: str) -> str:
    """Get the path to a project's folder on disk.

    Args:
        project_id: Project ID.

    Returns:
        Path string. Folder may not exist if not yet created.
    """
    from ruzh_translator.config import DATA_DIR
    return str(DATA_DIR / "projects" / project_id)


def open_project_folder(project_id: str):
    """Open the project folder in the system file manager.

    Args:
        project_id: Project ID.
    """
    import subprocess
    import sys
    folder = get_project_folder(project_id)
    path = __import__('pathlib').Path(folder)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    if sys.platform == "darwin":
        subprocess.run(["open", folder])
    elif sys.platform == "win32":
        subprocess.run(["explorer", folder])
    else:
        subprocess.run(["xdg-open", folder])
