"""Standalone Translation window."""

from PySide6.QtWidgets import QMainWindow
from ruzh_translator.models.base import get_session
from ruzh_translator.services.project_service import get_project
from ruzh_translator.ui.translation_editor import TranslationEditor


class TranslationWindow(QMainWindow):
    """Independent translation window for a specific project."""

    def __init__(self, project_id: str):
        super().__init__()
        self._session = get_session()
        self._project_id = project_id

        proj = get_project(self._session, project_id)
        title = f"✏️ 翻译 — {proj.name}" if proj else "✏️ 翻译编辑"
        self.setWindowTitle(title)
        self.resize(1500, 950)

        editor = TranslationEditor(project_id=project_id)
        self.setCentralWidget(editor)
