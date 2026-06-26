"""SQLAlchemy ORM models package.

Import order matters: base first, then all models to resolve relationships.
"""

from ruzh_translator.models.base import Base, engine, init_db, get_session, SessionLocal

# Import all models to ensure they are registered with Base's metadata
# and relationship back-references can be resolved.
from ruzh_translator.models.project import Project, Document
from ruzh_translator.models.segment import Segment, AlignmentPair
from ruzh_translator.models.glossary import GlossaryEntry
from ruzh_translator.models.tm import TranslationMemoryEntry
from ruzh_translator.models.task import TaskAssignment

__all__ = [
    "Base", "engine", "init_db", "get_session", "SessionLocal",
    "Project", "Document",
    "Segment", "AlignmentPair",
    "GlossaryEntry",
    "TranslationMemoryEntry",
    "TaskAssignment",
]
