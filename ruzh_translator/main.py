#!/usr/bin/env python3
"""Ruzh Translator — Russian-Chinese Translation Workflow Management.

Entry: Welcome Launcher → Independent module windows.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ruzh_translator.config import APP_NAME, ORG_NAME
from ruzh_translator.models.base import init_db


def main():
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    font = QFont()
    font.setFamilies([
        "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC",
        "Segoe UI", "sans-serif",
    ])
    font.setPointSize(13)
    app.setFont(font)

    _load_stylesheet(app)

    from ruzh_translator.ui.welcome_launcher import WelcomeLauncher
    launcher = WelcomeLauncher()

    # Track open windows per project to avoid duplicates
    _open_windows = {}

    def _open_window(window_class, project_id: str):
        """Open or raise an independent module window."""
        key = (window_class.__name__, project_id)
        if key in _open_windows:
            win = _open_windows[key]
            win.raise_()
            win.activateWindow()
        else:
            win = window_class(project_id)
            win.setAttribute(Qt.WA_DeleteOnClose)
            win.destroyed.connect(lambda: _open_windows.pop(key, None))
            _open_windows[key] = win
            win.show()

    def on_open_alignment(pid):
        from ruzh_translator.ui.alignment_window import AlignmentWindow
        _open_window(AlignmentWindow, pid)

    def on_open_translation(pid):
        from ruzh_translator.ui.translation_window import TranslationWindow
        _open_window(TranslationWindow, pid)

    def on_open_review(pid):
        from ruzh_translator.ui.review_window import ReviewWindow
        _open_window(ReviewWindow, pid)

    def on_open_glossary(pid):
        from ruzh_translator.ui.glossary_window import GlossaryWindow
        _open_window(GlossaryWindow, pid)

    launcher.open_alignment.connect(on_open_alignment)
    launcher.open_translation.connect(on_open_translation)
    launcher.open_review.connect(on_open_review)
    launcher.open_glossary.connect(on_open_glossary)

    launcher.show()
    sys.exit(app.exec())


def _load_stylesheet(app: QApplication):
    style_path = Path(__file__).parent / "resources" / "styles.qss"
    if style_path.exists():
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())


if __name__ == "__main__":
    main()
