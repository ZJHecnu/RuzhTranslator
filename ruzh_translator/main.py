#!/usr/bin/env python3
"""Ruzh Translator — 4-in-1: Aligner · Translator · Concordance · Glossary."""

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
    app.setFont(QFont(["PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "sans-serif"], 13))
    _load_stylesheet(app)

    from ruzh_translator.ui.welcome_launcher import WelcomeLauncher
    launcher = WelcomeLauncher()

    _wins = {}

    def _show(key, factory):
        if key in _wins:
            _wins[key].raise_(); _wins[key].activateWindow()
        else:
            w = factory()
            w.setAttribute(Qt.WA_DeleteOnClose)
            w.destroyed.connect(lambda: _wins.pop(key, None))
            _wins[key] = w
            w.show()

    launcher.open_aligner.connect(lambda: _show("aligner",
        lambda: __import__("ruzh_translator.ui.aligner_window", fromlist=["AlignerWindow"]).AlignerWindow()))
    launcher.open_translator.connect(lambda: _show("translator",
        lambda: __import__("ruzh_translator.ui.translator_window", fromlist=["TranslatorWindow"]).TranslatorWindow()))
    launcher.open_concordance.connect(lambda: _show("concordance",
        lambda: __import__("ruzh_translator.ui.concordance_window", fromlist=["ConcordanceWindow"]).ConcordanceWindow()))
    launcher.open_glossary.connect(lambda: _show("glossary",
        lambda: __import__("ruzh_translator.ui.glossary_window", fromlist=["GlossaryWindow"]).GlossaryWindow()))

    launcher.show()
    sys.exit(app.exec())


def _load_stylesheet(app):
    p = Path(__file__).parent / "resources" / "styles.qss"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())


if __name__ == "__main__":
    main()
