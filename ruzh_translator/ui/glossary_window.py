"""Standalone Glossary window."""

from PySide6.QtWidgets import QMainWindow
from ruzh_translator.models.base import get_session
from ruzh_translator.services.project_service import get_project
from ruzh_translator.ui.glossary_editor import GlossaryEditor


class GlossaryWindow(QMainWindow):
    """Independent glossary window for a specific project."""

    def __init__(self, project_id: str):
        super().__init__()
        self._session = get_session()
        self._project_id = project_id

        proj = get_project(self._session, project_id)
        title = f"📖 术语管理 — {proj.name}" if proj else "📖 术语管理"
        self.setWindowTitle(title)
        self.resize(1000, 700)

        editor = GlossaryEditor(project_id=project_id)
        self.setCentralWidget(editor)
