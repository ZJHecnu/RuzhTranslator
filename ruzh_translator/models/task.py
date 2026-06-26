"""TaskAssignment ORM model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ruzh_translator.models.base import Base
from ruzh_translator.models.project import _new_id


class TaskAssignment(Base):
    """A task assignment for distributed translation."""

    __tablename__ = "task_assignments"

    id = Column(String(12), primary_key=True, default=_new_id)
    project_id = Column(String(12), ForeignKey("projects.id"), nullable=False)
    translator_name = Column(String(128), nullable=False)
    segment_range_start = Column(Integer, nullable=False)
    segment_range_end = Column(Integer, nullable=False)
    status = Column(String(20), default="assigned")  # assigned, in_progress, completed
    task_file_path = Column(String(1024), default="")
    deadline = Column(DateTime, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="task_assignments")
