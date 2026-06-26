"""Welcome launcher v3: project-first with QPushButton cards (reliable clicks)."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QComboBox,
    QListWidget, QListWidgetItem, QMessageBox,
    QSizePolicy, QSpacerItem,
)
from PySide6.QtCore import Qt, Signal

from ruzh_translator.config import APP_NAME, APP_VERSION
from ruzh_translator.models.base import get_session
from ruzh_translator.services.project_service import (
    list_projects, get_project, open_project_folder,
)
from ruzh_translator.models.segment import Segment


class WelcomeLauncher(QWidget):
    """Startup page: project selector + 4 QPushButton cards."""

    open_alignment = Signal(str)
    open_translation = Signal(str)
    open_review = Signal(str)
    open_glossary = Signal(str)

    def __init__(self):
        super().__init__()
        self._session = get_session()
        self._project_id: str | None = None
        self._card_btns = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cl = QVBoxLayout(content)
        cl.setContentsMargins(40, 24, 40, 24)
        cl.setSpacing(14)

        # Title
        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #1565C0;")
        cl.addWidget(title)

        sub = QLabel("俄汉翻译流程管理软件")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 14px; color: #78909C;")
        cl.addWidget(sub)

        cl.addSpacing(8)

        # ── Project bar ──
        bar = QFrame()
        bar.setStyleSheet("QFrame { background: #E3F2FD; border-radius: 12px; padding: 12px; }")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 10, 16, 10)

        bl.addWidget(QLabel("📋 项目:"))

        self._proj_combo = QComboBox()
        self._proj_combo.setMinimumWidth(220)
        self._proj_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._proj_combo.currentIndexChanged.connect(self._on_project_changed)
        bl.addWidget(self._proj_combo, 1)

        new_btn = QPushButton("＋ 新建")
        new_btn.clicked.connect(self._on_new_project)
        bl.addWidget(new_btn)

        folder_btn = QPushButton("📂 文件夹")
        folder_btn.clicked.connect(self._on_open_folder)
        bl.addWidget(folder_btn)

        self._proj_status = QLabel("")
        self._proj_status.setStyleSheet("color: #616161; font-size: 12px;")
        bl.addWidget(self._proj_status)

        cl.addWidget(bar)
        cl.addSpacing(12)

        # ── 2×2 Card Grid (QPushButton) ──
        grid = QGridLayout()
        grid.setSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        cards = [
            ("🔗", "语料对齐", "对齐俄中双语文本\nLaBSE 语义对齐 + 连接线可视化", "#FF9800",
             lambda: self._emit("align")),
            ("✏️", "翻译编辑", "逐句翻译源语文档\n术语高亮 + TM 匹配 + 自动标记", "#4CAF50",
             lambda: self._emit("translate")),
            ("✓",  "审校", "逐句审校译文\n变更追踪 + 批量批准", "#2196F3",
             lambda: self._emit("review")),
            ("📖", "术语管理", "管理翻译术语库\n自动提取 + AI 翻译 + 导入导出", "#9C27B0",
             lambda: self._emit("glossary")),
        ]

        for i, (icon, title_text, desc, color, handler) in enumerate(cards):
            btn = self._make_card_btn(icon, title_text, desc, color)
            btn.clicked.connect(handler)
            self._card_btns[title_text] = btn
            grid.addWidget(btn, i // 2, i % 2)

        cl.addLayout(grid, 1)

        cl.addSpacing(10)

        # ── Recent projects ──
        recent_label = QLabel("── 最近项目 ──")
        recent_label.setAlignment(Qt.AlignCenter)
        recent_label.setStyleSheet("color: #BDBDBD; font-size: 12px;")
        cl.addWidget(recent_label)

        self._recent_list = QListWidget()
        self._recent_list.setMaximumHeight(110)
        self._recent_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._recent_list.setStyleSheet("""
            QListWidget { border: 1px solid #E0E0E0; border-radius: 8px; background: #FAFAFA; }
            QListWidget::item { padding: 8px 16px; border-bottom: 1px solid #F0F0F0; }
            QListWidget::item:hover { background: #E3F2FD; }
        """)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_clicked)
        cl.addWidget(self._recent_list)

        layout.addWidget(content, 1)
        self._refresh_projects()

    # ── Card Button Factory ─────────────────────────────────

    def _make_card_btn(self, icon: str, title: str, desc: str, color: str) -> QPushButton:
        """Create a styled card-like QPushButton."""
        btn = QPushButton()
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        btn.setMinimumSize(180, 130)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setEnabled(False)  # Disabled until project selected

        text = f"{icon}\n{title}\n\n{desc}"
        btn.setText(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: #F5F5F5;
                border: 2px solid #EEE;
                border-radius: 16px;
                text-align: left;
                padding: 16px;
                font-size: 12px;
                color: #BDBDBD;
            }}
            QPushButton:enabled {{
                background: #FFFFFF;
                border-color: #E0E0E0;
                color: #424242;
            }}
            QPushButton:enabled:hover {{
                border-color: {color};
                background: #FAFAFA;
            }}
            QPushButton:enabled:pressed {{
                background: #F5F5F5;
            }}
        """)
        return btn

    # ── Project Management ─────────────────────────────────

    def _refresh_projects(self):
        self._proj_combo.blockSignals(True)
        self._proj_combo.clear()
        self._proj_combo.addItem("-- 请选择或创建项目 --", None)
        for p in list_projects(self._session):
            self._proj_combo.addItem(f"{p.name}  [{p.status}]", p.id)
        self._proj_combo.blockSignals(False)

        self._recent_list.clear()
        for p in list_projects(self._session)[:6]:
            item = QListWidgetItem()
            updated = p.updated_at.strftime("%m-%d %H:%M") if p.updated_at else ""
            item.setText(f"📋 {p.name}  ·  {updated}  ·  {p.status}")
            item.setData(Qt.UserRole, p.id)
            self._recent_list.addItem(item)

    def _on_project_changed(self):
        pid = self._proj_combo.currentData()
        self._project_id = pid

        enabled = pid is not None
        for btn in self._card_btns.values():
            btn.setEnabled(enabled)

        if pid:
            proj = get_project(self._session, pid)
            if proj:
                seg_count = (
                    self._session.query(Segment)
                    .filter(Segment.project_id == pid)
                    .count()
                )
                p = proj.progress
                self._proj_status.setText(
                    f"{seg_count}句 | 已译{p['translated_pct']}% | 已审{p['approved_pct']}%"
                )
        else:
            self._proj_status.setText("")

    def _on_new_project(self):
        from ruzh_translator.ui.project_wizard import ProjectWizard
        wizard = ProjectWizard(self)
        if wizard.exec():
            self._refresh_projects()
            # Select new project
            for i in range(self._proj_combo.count()):
                if self._proj_combo.itemData(i) == wizard.project_id:
                    self._proj_combo.setCurrentIndex(i)
                    break
            # Open appropriate window based on workflow
            pid = wizard.project_id
            wf = wizard.workflow
            if wf == "align":
                self.open_alignment.emit(pid)
            elif wf == "translate":
                self.open_translation.emit(pid)
            elif wf == "review":
                self.open_review.emit(pid)
            elif wf == "glossary":
                self.open_glossary.emit(pid)
            elif wf == "full":
                # Full workflow: if target doc exists, align first, else translate
                if wizard.target_path:
                    self.open_alignment.emit(pid)
                else:
                    self.open_translation.emit(pid)

    def _on_open_folder(self):
        if not self._project_id:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        open_project_folder(self._project_id)

    def _on_recent_clicked(self, item):
        pid = item.data(Qt.UserRole)
        if pid:
            for i in range(self._proj_combo.count()):
                if self._proj_combo.itemData(i) == pid:
                    self._proj_combo.setCurrentIndex(i)
                    break

    def _emit(self, mode: str):
        """Emit the appropriate signal for the clicked card."""
        if not self._project_id:
            QMessageBox.information(self, "提示", "请先在顶部选择或创建项目")
            return
        if mode == "align":
            self.open_alignment.emit(self._project_id)
        elif mode == "translate":
            self.open_translation.emit(self._project_id)
        elif mode == "review":
            self.open_review.emit(self._project_id)
        elif mode == "glossary":
            self.open_glossary.emit(self._project_id)
