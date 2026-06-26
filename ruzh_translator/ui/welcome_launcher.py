"""Welcome launcher v2: project-first, responsive card grid.

- Top: project selector bar (required to enable function cards)
- Middle: 2×2 grid of function cards (resize with window)
- Bottom: recent projects list
"""

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QComboBox,
    QListWidget, QListWidgetItem, QDialog, QMessageBox,
    QSizePolicy, QSpacerItem,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ruzh_translator.config import APP_NAME, APP_VERSION
from ruzh_translator.models.base import get_session
from ruzh_translator.services.project_service import (
    list_projects, get_project, open_project_folder,
)
from ruzh_translator.models.segment import Segment


class WelcomeLauncher(QWidget):
    """Startup page: project selector + 4 function cards + recent projects."""

    open_alignment = Signal(str)    # project_id
    open_translation = Signal(str)  # project_id
    open_review = Signal(str)       # project_id
    open_glossary = Signal(str)     # project_id

    def __init__(self):
        super().__init__()
        self._session = get_session()
        self._project_id: str | None = None
        self._cards = []  # list of (card_frame, enable_func)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Main content (scrollable if needed) ──
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cl = QVBoxLayout(content)
        cl.setContentsMargins(40, 24, 40, 24)
        cl.setSpacing(16)

        # Header
        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #1565C0;")
        cl.addWidget(title)

        sub = QLabel("俄汉翻译流程管理软件")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 14px; color: #78909C;")
        cl.addWidget(sub)

        cl.addSpacing(8)

        # ── Project selector bar ──
        proj_bar = QFrame()
        proj_bar.setStyleSheet(
            "QFrame { background: #E3F2FD; border-radius: 12px; padding: 12px; }"
        )
        proj_layout = QHBoxLayout(proj_bar)
        proj_layout.setContentsMargins(16, 10, 16, 10)

        proj_layout.addWidget(QLabel("📋 当前项目:"))

        self._proj_combo = QComboBox()
        self._proj_combo.setMinimumWidth(250)
        self._proj_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._proj_combo.currentIndexChanged.connect(self._on_project_selected)
        proj_layout.addWidget(self._proj_combo, 1)

        new_btn = QPushButton("＋ 新建")
        new_btn.clicked.connect(self._on_new_project)
        proj_layout.addWidget(new_btn)

        folder_btn = QPushButton("📂 打开文件夹")
        folder_btn.clicked.connect(self._on_open_folder)
        proj_layout.addWidget(folder_btn)

        self._proj_status = QLabel("")
        self._proj_status.setStyleSheet("color: #616161; font-size: 12px;")
        proj_layout.addWidget(self._proj_status)

        cl.addWidget(proj_bar)

        cl.addSpacing(12)

        # ── 2×2 Card Grid ──
        grid = QGridLayout()
        grid.setSpacing(16)

        # Make grid cells stretch evenly
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        # Card 1: Alignment
        c1, enable_c1 = self._make_card("🔗", "语料对齐",
            "对齐俄中双语文本\n支持 LaBSE 语义对齐\n手动校正连接线可视化",
            "#FF9800")
        c1.clicked = lambda: self._on_card("align")
        grid.addWidget(c1, 0, 0)
        self._cards.append((c1, enable_c1))

        # Card 2: Translation
        c2, enable_c2 = self._make_card("✏️", "翻译编辑",
            "逐句翻译源语文档\n术语高亮 + TM 匹配\n自动标记已译",
            "#4CAF50")
        c2.clicked = lambda: self._on_card("translate")
        grid.addWidget(c2, 0, 1)
        self._cards.append((c2, enable_c2))

        # Card 3: Review
        c3, enable_c3 = self._make_card("✓", "审校",
            "逐句审校译文\n变更追踪 + 评论\n批量批准",
            "#2196F3")
        c3.clicked = lambda: self._on_card("review")
        grid.addWidget(c3, 1, 0)
        self._cards.append((c3, enable_c3))

        # Card 4: Glossary
        c4, enable_c4 = self._make_card("📖", "术语管理",
            "管理翻译术语库\n自动提取候选术语\n导入导出 Excel",
            "#9C27B0")
        c4.clicked = lambda: self._on_card("glossary")
        grid.addWidget(c4, 1, 1)
        self._cards.append((c4, enable_c4))

        cl.addLayout(grid, 1)  # Stretch factor 1 = take remaining space

        cl.addSpacing(12)

        # ── Recent projects ──
        recent_label = QLabel("── 最近项目 ──")
        recent_label.setAlignment(Qt.AlignCenter)
        recent_label.setStyleSheet("color: #BDBDBD; font-size: 12px;")
        cl.addWidget(recent_label)

        self._recent_list = QListWidget()
        self._recent_list.setMaximumHeight(120)
        self._recent_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._recent_list.setStyleSheet("""
            QListWidget { border: 1px solid #E0E0E0; border-radius: 8px; background: #FAFAFA; }
            QListWidget::item { padding: 8px 16px; border-bottom: 1px solid #F0F0F0; }
            QListWidget::item:hover { background: #E3F2FD; }
        """)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_clicked)
        cl.addWidget(self._recent_list)

        layout.addWidget(content, 1)

        # ── Load data ──
        self._refresh_projects()

    # ── Card Factory ─────────────────────────────────────────

    def _make_card(self, icon: str, title: str, desc: str, color: str):
        """Create a responsive card widget.

        Returns (frame, enable_func) where enable_func(enabled: bool) toggles state.
        """
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setCursor(Qt.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.setMinimumSize(180, 140)

        # We track enabled state via a custom property
        card._enabled = False

        def set_enabled(enabled: bool):
            card._enabled = enabled
            if enabled:
                card.setStyleSheet(f"""
                    QFrame {{ background: #FFFFFF; border: 2px solid #E0E0E0; border-radius: 16px; }}
                    QFrame:hover {{ border-color: {color}; background: #FAFAFA; }}
                """)
            else:
                card.setStyleSheet("""
                    QFrame { background: #F5F5F5; border: 2px solid #EEE; border-radius: 16px; }
                """)

        # Start disabled
        set_enabled(False)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: 32px; border: none;")
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: #37474F; border: none;"
        )
        layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setStyleSheet("font-size: 11px; color: #9E9E9E; border: none;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        layout.addStretch()

        card.mousePressEvent = lambda e: self._on_card_click(card)
        return card, set_enabled

    # ── Project Management ─────────────────────────────────

    def _refresh_projects(self):
        """Reload project list and recent projects."""
        self._proj_combo.blockSignals(True)
        self._proj_combo.clear()
        self._proj_combo.addItem("-- 请选择或创建项目 --", None)

        projects = list_projects(self._session)
        for p in projects:
            self._proj_combo.addItem(f"{p.name}  [{p.status}]", p.id)
        self._proj_combo.blockSignals(False)

        # Refresh recent list
        self._recent_list.clear()
        for p in projects[:6]:
            item = QListWidgetItem()
            updated = p.updated_at.strftime("%m-%d %H:%M") if p.updated_at else ""
            item.setText(f"📋 {p.name}  ·  {updated}  ·  {p.status}")
            item.setData(Qt.UserRole, p.id)
            self._recent_list.addItem(item)

    def _on_project_selected(self):
        """Handle project selection change."""
        pid = self._proj_combo.currentData()
        self._project_id = pid

        enabled = pid is not None
        for card, set_enabled in self._cards:
            set_enabled(enabled)

        if pid:
            proj = get_project(self._session, pid)
            if proj:
                progress = proj.progress
                seg_count = (
                    self._session.query(Segment)
                    .filter(Segment.project_id == pid)
                    .count()
                )
                self._proj_status.setText(
                    f"{seg_count}句 | 已译{progress['translated_pct']}% | 已审{progress['approved_pct']}%"
                )
        else:
            self._proj_status.setText("")

    def _on_new_project(self):
        """Create a new project."""
        from ruzh_translator.ui.project_dashboard import NewProjectDialog
        dialog = NewProjectDialog(self)
        if dialog.exec():
            from ruzh_translator.services.project_service import create_project
            proj = create_project(
                self._session,
                dialog.project_name,
                dialog.source_lang,
                dialog.target_lang,
                dialog.description,
            )
            self._refresh_projects()
            # Select the new project
            for i in range(self._proj_combo.count()):
                if self._proj_combo.itemData(i) == proj.id:
                    self._proj_combo.setCurrentIndex(i)
                    break

    def _on_open_folder(self):
        """Open the current project folder in Finder."""
        if not self._project_id:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        open_project_folder(self._project_id)

    def _on_recent_clicked(self, item):
        """Select a recent project."""
        pid = item.data(Qt.UserRole)
        if pid:
            for i in range(self._proj_combo.count()):
                if self._proj_combo.itemData(i) == pid:
                    self._proj_combo.setCurrentIndex(i)
                    break

    # ── Card Clicks ─────────────────────────────────────────

    def _on_card_click(self, card):
        """Handle card click."""
        if not getattr(card, '_enabled', False):
            QMessageBox.information(self, "提示", "请先在顶部选择或创建一个项目")
            return
        if hasattr(card, 'clicked'):
            card.clicked()

    def _on_card(self, mode: str):
        """Route card click to the appropriate signal."""
        if not self._project_id:
            return
        if mode == "align":
            self.open_alignment.emit(self._project_id)
        elif mode == "translate":
            self.open_translation.emit(self._project_id)
        elif mode == "review":
            self.open_review.emit(self._project_id)
        elif mode == "glossary":
            self.open_glossary.emit(self._project_id)
