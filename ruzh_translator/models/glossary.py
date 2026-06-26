"""GlossaryEntry ORM model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ruzh_translator.models.base import Base
from ruzh_translator.models.project import _new_id


class GlossaryEntry(Base):
    """A terminology glossary entry."""

    __tablename__ = "glossary_entries"

    id = Column(String(12), primary_key=True, default=_new_id)
    project_id = Column(String(12), ForeignKey("projects.id"), nullable=False)
    source_term = Column(String(512), nullable=False)
    target_term = Column(String(512), nullable=False, default="")
    domain = Column(String(128), default="")
    context_sentence = Column(Text, default="")
    notes = Column(Text, default="")
    created_by = Column(String(64), default="")
    is_approved = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="glossary_entries")
