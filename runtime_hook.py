"""PyInstaller runtime hook: set QT_PLUGIN_PATH for macOS .app bundles."""

import os
import sys

# PyInstaller on macOS puts PySide6 plugins in Frameworks/PySide6/Qt/plugins
if sys.platform == "darwin":
    base = os.path.dirname(sys.executable)
    # In a PyInstaller .app: Contents/MacOS/executable
    # Frameworks are at Contents/Frameworks
    plugins_path = os.path.join(
        os.path.dirname(base), "Frameworks", "PySide6", "Qt", "plugins"
    )
    if os.path.isdir(plugins_path):
        os.environ["QT_PLUGIN_PATH"] = plugins_path
