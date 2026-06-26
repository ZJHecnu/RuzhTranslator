"""Project and Document ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ruzh_translator.models.base import Base


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Project(Base):
    """Translation project."""

    __tablename__ = "projects"

    id = Column(String(12), primary_key=True, default=_new_id)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    source_lang = Column(String(10), nullable=False, default="ru")
    target_lang = Column(String(10), nullable=False, default="zh-CN")
    status = Column(String(20), nullable=False, default="setup")
    shared_folder_path = Column(String(1024), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    segments = relationship("Segment", back_populates="project", cascade="all, delete-orphan")
    alignment_pairs = relationship("AlignmentPair", back_populates="project", cascade="all, delete-orphan")
    glossary_entries = relationship("GlossaryEntry", back_populates="project", cascade="all, delete-orphan")
    task_assignments = relationship("TaskAssignment", back_populates="project", cascade="all, delete-orphan")

    @property
    def progress(self) -> dict:
        """Calculate translation progress percentages."""
        if not self.segments:
            return {"total": 0, "translated": 0, "reviewed": 0, "approved": 0,
                    "translated_pct": 0, "reviewed_pct": 0, "approved_pct": 0}
        total = len(self.segments)
        translated = sum(1 for s in self.segments if s.status in ("translated", "reviewed", "approved"))
        reviewed = sum(1 for s in self.segments if s.status in ("reviewed", "approved"))
        approved = sum(1 for s in self.segments if s.status == "approved")
        return {
            "total": total,
            "translated": translated,
            "reviewed": reviewed,
            "approved": approved,
            "translated_pct": round(translated / total * 100, 1),
            "reviewed_pct": round(reviewed / total * 100, 1),
            "approved_pct": round(approved / total * 100, 1),
        }


class Document(Base):
    """Imported source/target document."""

    __tablename__ = "documents"

    id = Column(String(12), primary_key=True, default=_new_id)
    project_id = Column(String(12), ForeignKey("projects.id"), nullable=False)
    filename = Column(String(512), nullable=False)
    file_format = Column(String(10), nullable=False)
    language = Column(String(10), default="")
    raw_content = Column(Text, default="")
    paragraph_count = Column(Integer, default=0)
    imported_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="documents")
