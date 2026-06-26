#!/usr/bin/env python3
"""Ruzh Translator — Aligner · Translator · Concordance · Glossary."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ruzh_translator.config import APP_NAME, ORG_NAME
from ruzh_translator.models.base import init_db

# Explicit imports — required for PyInstaller
from ruzh_translator.ui.welcome_launcher import WelcomeLauncher
from ruzh_translator.ui.aligner_window import AlignerWindow
from ruzh_translator.ui.translator_window import TranslatorWindow
from ruzh_translator.ui.concordance_window import ConcordanceWindow
from ruzh_translator.ui.glossary_window import GlossaryWindow


def main():
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setFont(QFont(
        ["PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "sans-serif"], 13
    ))

    # Stylesheet
    p = Path(__file__).parent / "resources" / "styles.qss"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    launcher = WelcomeLauncher()

    # Track open windows: one per module
    _windows = {}

    def _show(name: str, factory):
        if name in _windows:
            w = _windows[name]
            w.raise_()
            w.activateWindow()
        else:
            w = factory()
            w.setAttribute(Qt.WA_DeleteOnClose)
            w.destroyed.connect(lambda: _windows.pop(name, None))
            _windows[name] = w
            w.show()

    launcher.open_aligner.connect(lambda: _show("aligner", AlignerWindow))
    launcher.open_translator.connect(lambda: _show("translator", TranslatorWindow))
    launcher.open_concordance.connect(lambda: _show("concordance", ConcordanceWindow))
    launcher.open_glossary.connect(lambda: _show("glossary", GlossaryWindow))

    launcher.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
