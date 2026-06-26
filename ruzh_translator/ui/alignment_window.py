"""Standalone Alignment window."""

from PySide6.QtWidgets import QMainWindow
from ruzh_translator.models.base import get_session
from ruzh_translator.services.project_service import get_project
from ruzh_translator.ui.alignment_editor import AlignmentEditor


class AlignmentWindow(QMainWindow):
    """Independent alignment window for a specific project."""

    def __init__(self, project_id: str):
        super().__init__()
        self._session = get_session()
        self._project_id = project_id

        proj = get_project(self._session, project_id)
        title = f"🔗 语料对齐 — {proj.name}" if proj else "🔗 语料对齐"
        self.setWindowTitle(title)
        self.resize(1400, 900)

        editor = AlignmentEditor(project_id=project_id)
        editor.alignment_done.connect(self._on_alignment_done)
        self.setCentralWidget(editor)

    def _on_alignment_done(self):
        proj = get_project(self._session, self._project_id)
        if proj:
            self.setWindowTitle(f"🔗 语料对齐 — {proj.name} ✓")
