"""TranslationMemoryEntry ORM model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import relationship

from ruzh_translator.models.base import Base
from ruzh_translator.models.project import _new_id


class TranslationMemoryEntry(Base):
    """A translation memory entry."""

    __tablename__ = "tm_entries"

    id = Column(String(12), primary_key=True, default=_new_id)
    source_text = Column(Text, nullable=False)
    target_text = Column(Text, nullable=False, default="")
    source_lang = Column(String(10), nullable=False, default="ru")
    target_lang = Column(String(10), nullable=False, default="zh-CN")
    project_id = Column(String(12), default="")
    domain = Column(String(128), default="")
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    # Pre-computed embedding for fast lookup (stored as path to .npy file)
    embedding_path = Column(String(1024), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
