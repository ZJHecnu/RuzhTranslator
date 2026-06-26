"""Settings dialog: AI API, preferences, and paths."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton,
    QDialogButtonBox, QMessageBox, QGroupBox, QTabWidget, QWidget,
    QSpinBox,
)
from PySide6.QtCore import Qt, QSettings

from ruzh_translator.config import APP_NAME, ORG_NAME, DATA_DIR, DB_PATH
from ruzh_translator.utils.embedding_cache import clear_cache


class SettingsDialog(QDialog):
    """Application settings dialog with AI API configuration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("偏好设置")
        self.setMinimumSize(550, 480)
        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # ── AI API tab ──
        api_tab = QWidget()
        api_layout = QVBoxLayout(api_tab)

        api_group = QGroupBox("AI 辅助设置")
        api_form = QFormLayout(api_group)

        self._enable_ai = QCheckBox("启用 AI 辅助")
        api_form.addRow("", self._enable_ai)

        self._api_url = QLineEdit()
        self._api_url.setPlaceholderText("https://api.openai.com/v1")
        api_form.addRow("API 地址:", self._api_url)

        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.Password)
        self._api_key.setPlaceholderText("sk-...")
        api_form.addRow("API Key:", self._api_key)

        self._api_model = QComboBox()
        self._api_model.setEditable(True)
        self._api_model.addItems([
            "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
            "claude-sonnet-4-6", "claude-opus-4-8",
            "deepseek-chat", "custom",
        ])
        api_form.addRow("模型:", self._api_model)

        api_layout.addWidget(api_group)

        # Usage options
        usage_group = QGroupBox("AI 用途")
        usage_layout = QVBoxLayout(usage_group)
        self._use_term_translate = QCheckBox("术语智能翻译 — 自动翻译提取的候选术语")
        self._use_term_translate.setChecked(True)
        usage_layout.addWidget(self._use_term_translate)
        self._use_draft = QCheckBox("翻译草稿生成 — AI 生成初稿译文")
        usage_layout.addWidget(self._use_draft)
        self._use_consistency = QCheckBox("术语一致性检查 — 检查译文中术语的一致性")
        self._use_consistency.setChecked(True)
        usage_layout.addWidget(self._use_consistency)
        api_layout.addWidget(usage_group)

        # Test button
        test_layout = QHBoxLayout()
        self._test_result = QLabel("")
        self._test_result.setStyleSheet("color: #9E9E9E;")
        test_layout.addWidget(self._test_result)
        test_layout.addStretch()
        test_btn = QPushButton("🔌 测试连接")
        test_btn.clicked.connect(self._on_test)
        test_layout.addWidget(test_btn)
        api_layout.addLayout(test_layout)

        api_layout.addStretch()
        tabs.addTab(api_tab, "🤖 AI 辅助")

        # ── General tab ──
        gen_tab = QWidget()
        gen_form = QFormLayout(gen_tab)

        self._translator_name = QLineEdit()
        gen_form.addRow("翻译者姓名:", self._translator_name)

        self._autosave = QCheckBox("自动保存翻译（切换句子时）")
        self._autosave.setChecked(True)
        gen_form.addRow("", self._autosave)

        self._auto_mark = QCheckBox("自动标记已译（切换句子时）")
        self._auto_mark.setChecked(True)
        gen_form.addRow("", self._auto_mark)

        tabs.addTab(gen_tab, "通用")

        # ── Paths tab ──
        paths_tab = QWidget()
        paths_form = QFormLayout(paths_tab)

        paths_form.addRow("本地数据:", QLabel(str(DATA_DIR)))
        paths_form.addRow("数据库:", QLabel(str(DB_PATH)))

        clear_btn = QPushButton("🗑 清除向量缓存")
        clear_btn.clicked.connect(self._on_clear_cache)
        paths_form.addRow("", clear_btn)

        tabs.addTab(paths_tab, "路径")

        layout.addWidget(tabs)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self):
        s = self._settings
        self._translator_name.setText(s.value("translator_name", ""))
        self._enable_ai.setChecked(s.value("ai/enabled", False, type=bool))
        self._api_url.setText(s.value("ai/url", ""))
        self._api_key.setText(s.value("ai/key", ""))
        model = s.value("ai/model", "gpt-4o")
        idx = self._api_model.findText(model)
        if idx >= 0:
            self._api_model.setCurrentIndex(idx)
        else:
            self._api_model.setEditText(model)
        self._use_term_translate.setChecked(s.value("ai/use_term_translate", True, type=bool))
        self._use_draft.setChecked(s.value("ai/use_draft", False, type=bool))
        self._use_consistency.setChecked(s.value("ai/use_consistency", True, type=bool))

    def _on_save(self):
        s = self._settings
        s.setValue("translator_name", self._translator_name.text().strip())
        s.setValue("ai/enabled", self._enable_ai.isChecked())
        s.setValue("ai/url", self._api_url.text().strip())
        s.setValue("ai/key", self._api_key.text().strip())
        s.setValue("ai/model", self._api_model.currentText())
        s.setValue("ai/use_term_translate", self._use_term_translate.isChecked())
        s.setValue("ai/use_draft", self._use_draft.isChecked())
        s.setValue("ai/use_consistency", self._use_consistency.isChecked())
        self.accept()

    def _on_test(self):
        """Test the AI API connection."""
        url = self._api_url.text().strip()
        key = self._api_key.text().strip()
        model = self._api_model.currentText()

        if not url or not key:
            self._test_result.setText("❌ 请填写 API 地址和 Key")
            self._test_result.setStyleSheet("color: #F44336;")
            return

        self._test_result.setText("⏳ 测试中...")
        self._test_result.setStyleSheet("color: #FF9800;")

        try:
            import urllib.request
            import json

            req = urllib.request.Request(
                f"{url.rstrip('/')}/chat/completions",
                data=json.dumps({
                    "model": model,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 5,
                }).encode(),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            urllib.request.urlopen(req, timeout=10)
            self._test_result.setText("✅ 连接成功！")
            self._test_result.setStyleSheet("color: #4CAF50;")
        except Exception as e:
            self._test_result.setText(f"❌ 连接失败: {str(e)[:60]}")
            self._test_result.setStyleSheet("color: #F44336;")

    def _on_clear_cache(self):
        reply = QMessageBox.question(
            self, "确认", "确定要清除所有向量缓存吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            clear_cache()
            QMessageBox.information(self, "完成", "向量缓存已清除")


def get_ai_config() -> dict:
    """Get AI configuration from settings. Returns dict with url, key, model, enabled."""
    s = QSettings(ORG_NAME, APP_NAME)
    return {
        "enabled": s.value("ai/enabled", False, type=bool),
        "url": s.value("ai/url", ""),
        "key": s.value("ai/key", ""),
        "model": s.value("ai/model", "gpt-4o"),
        "use_term_translate": s.value("ai/use_term_translate", True, type=bool),
        "use_draft": s.value("ai/use_draft", False, type=bool),
    }
