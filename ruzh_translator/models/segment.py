"""Segment and AlignmentPair ORM models."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ruzh_translator.models.base import Base
from ruzh_translator.models.project import _new_id


class Segment(Base):
    """A translation segment (sentence or paragraph)."""

    __tablename__ = "segments"

    id = Column(String(12), primary_key=True, default=_new_id)
    project_id = Column(String(12), ForeignKey("projects.id"), nullable=False)
    document_id = Column(String(12), ForeignKey("documents.id"), nullable=True)
    paragraph_index = Column(Integer, nullable=False, default=0)
    segment_index = Column(Integer, nullable=False, default=0)
    source_text = Column(Text, nullable=False, default="")
    target_text = Column(Text, default="")
    status = Column(String(20), nullable=False, default="untranslated")
    translator_id = Column(String(64), default="")
    reviewer_id = Column(String(64), default="")
    terminology_notes = Column(Text, default="")
    reviewer_comment = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="segments")
    alignment_pairs_as_source = relationship(
        "AlignmentPair",
        foreign_keys="AlignmentPair.source_segment_id",
        back_populates="source_segment",
        cascade="all, delete-orphan",
    )
    alignment_pairs_as_target = relationship(
        "AlignmentPair",
        foreign_keys="AlignmentPair.target_segment_id",
        back_populates="target_segment",
        cascade="all, delete-orphan",
    )


class AlignmentPair(Base):
    """An aligned source-target segment pair."""

    __tablename__ = "alignment_pairs"

    id = Column(String(12), primary_key=True, default=_new_id)
    project_id = Column(String(12), ForeignKey("projects.id"), nullable=False)
    document_id = Column(String(12), ForeignKey("documents.id"), nullable=True)
    paragraph_index = Column(Integer, nullable=False, default=0)
    pair_index = Column(Integer, nullable=False, default=0)
    source_segment_id = Column(String(12), ForeignKey("segments.id"), nullable=True)
    target_segment_id = Column(String(12), ForeignKey("segments.id"), nullable=True)
    source_text = Column(Text, nullable=False, default="")
    target_text = Column(Text, default="")
    confidence_score = Column(Float, default=0.0)
    is_manually_corrected = Column(Integer, default=0)
    aligned_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="alignment_pairs")
    source_segment = relationship(
        "Segment",
        foreign_keys=[source_segment_id],
        back_populates="alignment_pairs_as_source",
    )
    target_segment = relationship(
        "Segment",
        foreign_keys=[target_segment_id],
        back_populates="alignment_pairs_as_target",
    )
