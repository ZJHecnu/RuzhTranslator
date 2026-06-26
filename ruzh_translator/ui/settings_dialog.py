"""Settings dialog: application preferences and configuration."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QDialogButtonBox,
    QMessageBox,
    QGroupBox,
    QFileDialog,
    QTabWidget,
    QWidget,
)
from PySide6.QtCore import Qt, QSettings

from ruzh_translator.config import APP_NAME, ORG_NAME, DATA_DIR, SHARED_DIR, DB_PATH, EMBEDDING_CACHE_DIR
from ruzh_translator.utils.embedding_cache import clear_cache


class SettingsDialog(QDialog):
    """Application settings dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("偏好设置")
        self.setMinimumSize(550, 400)
        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # ── General tab ──
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)

        self._translator_name = QLineEdit()
        self._translator_name.setPlaceholderText("你的姓名（用于任务分配）")
        general_layout.addRow("翻译者姓名:", self._translator_name)

        self._default_src = QComboBox()
        self._default_src.addItem("俄语", "ru")
        self._default_src.addItem("中文", "zh-CN")
        general_layout.addRow("默认源语言:", self._default_src)

        self._default_tgt = QComboBox()
        self._default_tgt.addItem("中文", "zh-CN")
        self._default_tgt.addItem("俄语", "ru")
        self._default_tgt.setCurrentIndex(0)
        general_layout.addRow("默认目标语言:", self._default_tgt)

        self._autosave = QCheckBox("自动保存翻译（每 30 秒）")
        self._autosave.setChecked(True)
        general_layout.addRow("", self._autosave)

        tabs.addTab(general_tab, "通用")

        # ── Paths tab ──
        paths_tab = QWidget()
        paths_layout = QFormLayout(paths_tab)

        self._data_dir_label = QLabel(str(DATA_DIR))
        self._data_dir_label.setStyleSheet("color: gray;")
        paths_layout.addRow("本地数据目录:", self._data_dir_label)

        self._shared_dir_label = QLabel(str(SHARED_DIR))
        self._shared_dir_label.setStyleSheet("color: gray;")
        paths_layout.addRow("共享文件夹:", self._shared_dir_label)

        self._db_path_label = QLabel(str(DB_PATH))
        self._db_path_label.setStyleSheet("color: gray;")
        paths_layout.addRow("数据库路径:", self._db_path_label)

        clear_cache_btn = QPushButton("🗑 清除向量缓存")
        clear_cache_btn.clicked.connect(self._on_clear_cache)
        paths_layout.addRow("", clear_cache_btn)

        tabs.addTab(paths_tab, "路径")

        # ── AI / API tab ──
        api_tab = QWidget()
        api_layout = QFormLayout(api_tab)

        api_layout.addRow(QLabel("（可选）配置 AI 翻译辅助功能"))

        self._api_url = QLineEdit()
        self._api_url.setPlaceholderText("https://api.openai.com/v1")
        api_layout.addRow("API 地址:", self._api_url)

        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.Password)
        self._api_key.setPlaceholderText("sk-...")
        api_layout.addRow("API Key:", self._api_key)

        self._api_model = QLineEdit("gpt-4o")
        api_layout.addRow("模型:", self._api_model)

        self._enable_ai = QCheckBox("启用 AI 辅助翻译建议")
        api_layout.addRow("", self._enable_ai)

        tabs.addTab(api_tab, "AI 辅助")

        layout.addWidget(tabs)

        # ── Buttons ──
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_settings(self):
        """Load settings from QSettings."""
        self._translator_name.setText(
            self._settings.value("translator_name", "")
        )
        # API settings
        self._api_url.setText(
            self._settings.value("api/url", "")
        )
        self._api_key.setText(
            self._settings.value("api/key", "")
        )
        self._api_model.setText(
            self._settings.value("api/model", "gpt-4o")
        )
        self._enable_ai.setChecked(
            self._settings.value("api/enabled", False, type=bool)
        )

    def _on_save(self):
        """Save settings and close."""
        self._settings.setValue("translator_name", self._translator_name.text().strip())

        # API
        self._settings.setValue("api/url", self._api_url.text().strip())
        self._settings.setValue("api/key", self._api_key.text().strip())
        self._settings.setValue("api/model", self._api_model.text().strip())
        self._settings.setValue("api/enabled", self._enable_ai.isChecked())

        self.accept()

    def _on_clear_cache(self):
        """Clear embedding cache."""
        reply = QMessageBox.question(
            self,
            "确认清除",
            "确定要清除所有向量缓存吗？\n下次对齐时将重新计算，可能较慢。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            clear_cache()
            QMessageBox.information(self, "完成", "向量缓存已清除")
