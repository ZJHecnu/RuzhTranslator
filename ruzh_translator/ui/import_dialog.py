"""Import panel + path-decision panel for the workflow stepper.

ImportPanel: embedded widget for document import with preview.
DecidePanel: post-import path selection (align vs translate).
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QFileDialog,
    QTextEdit,
    QMessageBox,
    QProgressBar,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QFrame,
)
from PySide6.QtCore import Qt, Signal

from ruzh_translator.config import IMPORT_FORMATS
from ruzh_translator.models.base import get_session
from ruzh_translator.services.import_service import import_file, import_and_segment
from ruzh_translator.services.project_service import add_document, get_project, update_project_status
from ruzh_translator.models.segment import Segment


class ImportPanel(QWidget):
    """Embedded import panel for the workflow stepper (step 2)."""

    import_done = Signal()  # Emitted when import completes

    def __init__(self, main_window=None, project_id: str = None):
        super().__init__()
        self._main_window = main_window
        self._session = get_session()
        self._project_id = project_id
        self._source_path = ""
        self._target_path = ""
        self._source_data = None
        self._target_data = None
        self._source_segments = []
        self._target_segments = []
        self._setup_ui()

        if project_id:
            self._load_project_info()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        title = QLabel("<h2>📥 导入文档</h2>")
        title.setStyleSheet("color: #37474F;")
        layout.addWidget(title)

        desc = QLabel("选择源语（俄语）和目标语（中文）文件。如果只需翻译源语文档，可仅导入源语文件。")
        desc.setStyleSheet("color: #78909C; margin-bottom: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Project info
        self._proj_label = QLabel("")
        self._proj_label.setStyleSheet("color: #1565C0; font-weight: bold; margin-bottom: 16px;")
        layout.addWidget(self._proj_label)

        # ── File selection ──
        files_layout = QHBoxLayout()

        # Source file
        src_group = QGroupBox("源语文件（俄语）")
        src_glayout = QVBoxLayout(src_group)
        self._src_status = QLabel("未选择文件")
        self._src_status.setStyleSheet("color: #9E9E9E;")
        src_glayout.addWidget(self._src_status)
        src_btn = QPushButton("📂 选择源语文件...")
        src_btn.clicked.connect(self._on_browse_source)
        src_glayout.addWidget(src_btn)
        self._src_preview = QTextEdit()
        self._src_preview.setReadOnly(True)
        self._src_preview.setMaximumHeight(120)
        self._src_preview.setPlaceholderText("文件内容预览...")
        src_glayout.addWidget(self._src_preview)
        files_layout.addWidget(src_group)

        # Target file
        tgt_group = QGroupBox("目标语文件（中文，可选）")
        tgt_glayout = QVBoxLayout(tgt_group)
        self._tgt_status = QLabel("未选择文件（可选）")
        self._tgt_status.setStyleSheet("color: #9E9E9E;")
        tgt_glayout.addWidget(self._tgt_status)
        tgt_btn = QPushButton("📂 选择目标语文件...")
        tgt_btn.clicked.connect(self._on_browse_target)
        tgt_glayout.addWidget(tgt_btn)
        self._tgt_preview = QTextEdit()
        self._tgt_preview.setReadOnly(True)
        self._tgt_preview.setMaximumHeight(120)
        self._tgt_preview.setPlaceholderText("文件内容预览...")
        tgt_glayout.addWidget(self._tgt_preview)
        files_layout.addWidget(tgt_group)

        layout.addLayout(files_layout)

        # ── Progress ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Import button ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._import_btn = QPushButton("📥 导入文档并继续")
        self._import_btn.setStyleSheet(
            "QPushButton { background-color: #1565C0; color: white; "
            "padding: 10px 32px; font-size: 15px; border-radius: 8px; } "
            "QPushButton:hover { background-color: #1976D2; }"
        )
        self._import_btn.clicked.connect(self._on_import)
        self._import_btn.setEnabled(False)
        btn_layout.addWidget(self._import_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _load_project_info(self):
        """Show current project name."""
        if self._project_id:
            proj = get_project(self._session, self._project_id)
            if proj:
                self._proj_label.setText(f"项目: {proj.name}")

    def _on_browse_source(self):
        """Browse for source file."""
        filters = ";;".join(f"{desc} (*{ext})" for ext, desc in IMPORT_FORMATS.items())
        path, _ = QFileDialog.getOpenFileName(self, "选择源语文件", "", filters)
        if path:
            self._source_path = path
            self._src_status.setText(f"✓ {Path(path).name}")
            self._src_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
            try:
                self._source_data = import_file(path)
                preview = self._source_data["raw_text"][:1500]
                self._src_preview.setPlainText(preview)
            except Exception as e:
                QMessageBox.warning(self, "导入错误", f"无法读取文件: {e}")
                return
            self._update_import_btn()

    def _on_browse_target(self):
        """Browse for target file."""
        filters = ";;".join(f"{desc} (*{ext})" for ext, desc in IMPORT_FORMATS.items())
        path, _ = QFileDialog.getOpenFileName(self, "选择目标语文件", "", filters)
        if path:
            self._target_path = path
            self._tgt_status.setText(f"✓ {Path(path).name}")
            self._tgt_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
            try:
                self._target_data = import_file(path)
                preview = self._target_data["raw_text"][:1500]
                self._tgt_preview.setPlainText(preview)
            except Exception as e:
                QMessageBox.warning(self, "导入错误", f"无法读取文件: {e}")
                return
            self._update_import_btn()

    def _update_import_btn(self):
        """Enable import button when source file is selected."""
        self._import_btn.setEnabled(bool(self._source_path))

    def _on_import(self):
        """Import files and create segments."""
        if not self._source_path:
            return

        if not self._project_id:
            QMessageBox.warning(self, "提示", "请先在步骤1中创建或选择项目")
            return

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        try:
            # Import source with auto-segmentation
            result = import_and_segment(
                self._source_path,
                self._session,
                self._project_id,
            )
            self._source_segments = result["segments"]

            # Import target if available (also segmented)
            if self._target_path:
                tgt_result = import_and_segment(
                    self._target_path,
                    self._session,
                    self._project_id,
                    language="zh-CN",
                )
                self._target_segments = tgt_result["segments"]

            # Update project status
            update_project_status(self._session, self._project_id, "translation")

            if self._main_window:
                self._main_window.set_status(
                    f"已导入: {Path(self._source_path).name} "
                    f"({result['sentence_count']} 句)"
                )

            self.import_done.emit()

            # Navigate to decide step
            if self._main_window:
                self._main_window.goto_decide()

        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
        finally:
            self._progress.setVisible(False)


class DecidePanel(QWidget):
    """Post-import path selection: Align vs Translate (step 3)."""

    def __init__(self, main_window=None, project_id: str = None):
        super().__init__()
        self._main_window = main_window
        self._session = get_session()
        self._project_id = project_id
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("<h2>🔀 选择翻译路径</h2>")
        title.setStyleSheet("color: #37474F;")
        layout.addWidget(title)

        desc = QLabel("文档已成功导入。请选择后续处理方式：")
        desc.setStyleSheet("color: #78909C; margin-bottom: 24px;")
        layout.addWidget(desc)

        # ── Stats ──
        if self._project_id:
            src_segs = (
                self._session.query(Segment)
                .filter(Segment.project_id == self._project_id)
                .all()
            )
            total = len(src_segs)
            stats_text = f"已导入 {total} 个句子片段，等待处理。"
        else:
            stats_text = "请先导入文档。"
        stats = QLabel(stats_text)
        stats.setStyleSheet("font-size: 14px; color: #1565C0; margin-bottom: 24px;")
        layout.addWidget(stats)

        # ── Two path cards ──
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(24)

        # Path A: Align
        align_card = QFrame()
        align_card.setFrameShape(QFrame.StyledPanel)
        align_card.setStyleSheet(
            "QFrame { background: #FFFFFF; border: 2px solid #E0E0E0; "
            "border-radius: 12px; padding: 24px; } "
            "QFrame:hover { border-color: #FF9800; }"
        )
        align_layout = QVBoxLayout(align_card)
        align_layout.addWidget(QLabel("<h3>🔗 对齐现有译语</h3>"))
        align_desc = QLabel(
            "如果已有对应译文文档，使用此路径进行\n"
            "句子级别的双语对齐，生成平行语料。\n\n"
            "适用场景：构建双语语料库，对照研究"
        )
        align_desc.setWordWrap(True)
        align_desc.setStyleSheet("color: #616161;")
        align_layout.addWidget(align_desc)
        align_layout.addStretch()
        align_btn = QPushButton("🔗 开始对齐")
        align_btn.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; "
            "padding: 12px 24px; font-size: 15px; border-radius: 8px; } "
            "QPushButton:hover { background-color: #F57C00; }"
        )
        align_btn.clicked.connect(self._on_choose_align)
        align_layout.addWidget(align_btn)
        cards_layout.addWidget(align_card)

        # Path B: Translate
        trans_card = QFrame()
        trans_card.setFrameShape(QFrame.StyledPanel)
        trans_card.setStyleSheet(
            "QFrame { background: #FFFFFF; border: 2px solid #E0E0E0; "
            "border-radius: 12px; padding: 24px; } "
            "QFrame:hover { border-color: #4CAF50; }"
        )
        trans_layout = QVBoxLayout(trans_card)
        trans_layout.addWidget(QLabel("<h3>✏️ 直接翻译</h3>"))
        trans_desc = QLabel(
            "逐句翻译源语文档，无需现有译文。\n"
            "翻译编辑器将显示每个源语句子，\n"
            "提供术语提示和翻译记忆辅助。\n\n"
            "适用场景：首次翻译，无现成译文"
        )
        trans_desc.setWordWrap(True)
        trans_desc.setStyleSheet("color: #616161;")
        trans_layout.addWidget(trans_desc)
        trans_layout.addStretch()
        trans_btn = QPushButton("✏️ 开始翻译")
        trans_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "padding: 12px 24px; font-size: 15px; border-radius: 8px; } "
            "QPushButton:hover { background-color: #388E3C; }"
        )
        trans_btn.clicked.connect(self._on_choose_translate)
        trans_layout.addWidget(trans_btn)
        cards_layout.addWidget(trans_card)

        layout.addLayout(cards_layout)
        layout.addStretch()

    def _on_choose_align(self):
        """User chose alignment path."""
        if self._main_window:
            self._main_window.goto_alignment()

    def _on_choose_translate(self):
        """User chose direct translation path."""
        if self._main_window:
            self._main_window.goto_translate()
