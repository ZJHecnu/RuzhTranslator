#!/usr/bin/env python3
"""Ruzh Translator — Aligner · Translator · Concordance · Glossary."""

import os
import sys
from pathlib import Path

if sys.platform == "darwin" and getattr(sys, "frozen", False):
    bundle = Path(sys.executable).resolve().parent.parent
    plugins = bundle / "Frameworks" / "PySide6" / "Qt" / "plugins"
    if plugins.is_dir():
        os.environ["QT_PLUGIN_PATH"] = str(plugins)

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
    app.setFont(QFont(
        ["PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "sans-serif"], 13
    ))

    css = Path(__file__).parent / "resources" / "styles.qss"
    if css.exists():
        with open(css, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    from ruzh_translator.ui.welcome_launcher import WelcomeLauncher
    launcher = WelcomeLauncher()

    _windows = {}

    def _show(name, factory):
        w = _windows.get(name)
        if w is not None:
            try:
                if w.isVisible():
                    w.raise_()
                    w.activateWindow()
                    return
            except RuntimeError:
                pass
            _windows.pop(name, None)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            w = factory()
        finally:
            QApplication.restoreOverrideCursor()

        _windows[name] = w
        w.setAttribute(Qt.WA_DeleteOnClose)
        w.destroyed.connect(lambda obj=None, n=name: _windows.pop(n, None))
        w.show()

    # ── Each handler is a regular function so PyInstaller finds the imports ──

    def open_aligner():
        from ruzh_translator.ui.aligner_window import AlignerWindow
        _show("aligner", AlignerWindow)

    def open_translator():
        from ruzh_translator.ui.translator_window import TranslatorWindow
        _show("translator", TranslatorWindow)

    def open_concordance():
        from ruzh_translator.ui.concordance_window import ConcordanceWindow
        _show("concordance", ConcordanceWindow)

    def open_glossary():
        from ruzh_translator.ui.glossary_window import GlossaryWindow
        _show("glossary", GlossaryWindow)

    def open_settings():
        from ruzh_translator.ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        dlg.exec()

    launcher.open_aligner.connect(open_aligner)
    launcher.open_translator.connect(open_translator)
    launcher.open_concordance.connect(open_concordance)
    launcher.open_glossary.connect(open_glossary)
    launcher.open_settings.connect(open_settings)

    launcher.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
