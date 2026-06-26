"""Main window: workflow stepper layout.

Left sidebar shows workflow steps (1→2→3→4→5→6).
Right side shows the active work panel via QStackedWidget.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QToolBar,
    QStatusBar,
    QLabel,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QSizePolicy,
    QSplitter,
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction, QKeySequence, QFont, QColor, QIcon

from ruzh_translator.config import APP_NAME, APP_VERSION
from ruzh_translator.models.base import get_session, init_db
from ruzh_translator.services.project_service import get_project

# ── Workflow step definitions ────────────────────────────────────

WORKFLOW_STEPS = [
    ("project",   "📋 1. 项目创建",    "创建或选择翻译项目"),
    ("import",    "📥 2. 导入文档",    "导入源语文档"),
    ("decide",    "🔀 3. 选择路径",    "对齐现有译语 或 直接翻译"),
    ("translate", "✏️ 4. 翻译编辑",    "逐句翻译"),
    ("review",    "✓  5. 审校",        "审校译文"),
    ("export",    "📤 6. 导出",        "导出翻译结果"),
]


class MainWindow(QMainWindow):
    """Main application window with workflow stepper."""

    workflow_changed = Signal(str, str)  # step_key, project_id

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1500, 950)

        self._project_id: str | None = None
        self._current_step: str = "project"
        self._standalone_mode: str = ""  # "alignment"|"translate"|"review"|"glossary"|""

        # Central widget: sidebar + work area
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Left sidebar: workflow stepper ──
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background-color: #263238;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        # App branding
        brand = QLabel(f"  {APP_NAME}")
        brand.setStyleSheet(
            "color: #ECEFF1; font-size: 16px; font-weight: bold; "
            "padding: 16px 12px; background-color: #1B2631;"
        )
        sidebar_layout.addWidget(brand)

        # Step list
        self._step_list = QListWidget()
        self._step_list.setStyleSheet("""
            QListWidget {
                background-color: #263238;
                border: none;
                padding: 8px 0;
            }
            QListWidget::item {
                color: #78909C;
                padding: 12px 16px;
                font-size: 14px;
                border-left: 3px solid transparent;
            }
            QListWidget::item:selected {
                color: #FFFFFF;
                background-color: #37474F;
                border-left: 3px solid #4FC3F7;
            }
            QListWidget::item:hover {
                color: #B0BEC5;
                background-color: #37474F;
            }
        """)
        self._step_list.currentRowChanged.connect(self._on_step_clicked)
        sidebar_layout.addWidget(self._step_list)

        sidebar_layout.addStretch()

        # Version label
        ver_label = QLabel(f"  v{APP_VERSION}")
        ver_label.setStyleSheet("color: #546E7A; padding: 8px 12px; font-size: 11px;")
        sidebar_layout.addWidget(ver_label)

        root_layout.addWidget(sidebar)

        # ── Right: stacked work panels ──
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background-color: #FAFAFA;")
        root_layout.addWidget(self._stack)

        # ── Build step list ──
        for key, label, _ in WORKFLOW_STEPS:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self._step_list.addItem(item)
            # Create corresponding stacked widget (placeholder initially)
            placeholder = QLabel(f"<h2>{label}</h2><p>请先完成前面的步骤</p>")
            placeholder.setAlignment(Qt.AlignCenter)
            self._stack.addWidget(placeholder)

        self._step_list.setCurrentRow(0)

        # ── Menu bar ──
        self._setup_menu()

        # ── Status bar ──
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("就绪 — 请创建或选择项目")
        self._status_bar.addWidget(self._status_label)

    # ── Menu ──────────────────────────────────────────────────

    def _setup_menu(self):
        m = self.menuBar()

        file_menu = m.addMenu("文件(&F)")
        file_menu.addAction("新建项目(&N)", self.goto_create_project, QKeySequence("Ctrl+N"))
        file_menu.addAction("导入文档(&I)", self.goto_import, QKeySequence("Ctrl+I"))
        file_menu.addAction("导出(&E)...", self.goto_export, QKeySequence("Ctrl+E"))
        file_menu.addSeparator()
        file_menu.addAction("退出(&Q)", self.close, QKeySequence("Ctrl+Q"))

        tools_menu = m.addMenu("工具(&T)")
        tools_menu.addAction("语料对齐(&A)...", self.goto_alignment)
        tools_menu.addAction("术语库管理(&G)...", self.goto_glossary, QKeySequence("Ctrl+G"))
        tools_menu.addAction("任务切分(&S)...", self.goto_split)
        tools_menu.addAction("任务合并(&M)...", self.goto_merge)

        help_menu = m.addMenu("帮助(&H)")
        help_menu.addAction("关于(&A)", self._on_about)

    # ── Standalone Mode ───────────────────────────────────────

    def start_standalone(self, mode: str):
        """Start in standalone mode (from launcher)."""
        self._standalone_mode = mode

        if mode == "alignment":
            self.go_to_step("import")
        elif mode == "translate":
            self.go_to_step("project")
        elif mode == "review":
            self.go_to_step("review")
        elif mode == "glossary":
            self.goto_glossary()

    # ── Step Navigation ───────────────────────────────────────

    def set_project(self, project_id: str):
        """Set the active project."""
        self._project_id = project_id
        session = get_session()
        proj = get_project(session, project_id)
        if proj:
            self.set_status(f"当前项目: {proj.name}")
        session.close()

    def go_to_step(self, step_key: str):
        """Navigate to a specific workflow step."""
        for i, (key, _, _) in enumerate(WORKFLOW_STEPS):
            if key == step_key:
                self._step_list.setCurrentRow(i)
                self._current_step = step_key
                self._refresh_step_panel(i, step_key)
                return

    def _on_step_clicked(self, row: int):
        """Handle click on a sidebar step."""
        if row < 0 or row >= len(WORKFLOW_STEPS):
            return
        key, _, _ = WORKFLOW_STEPS[row]

        # Allow navigation even without project for step 1 (project creation)
        if key != "project" and not self._project_id:
            QMessageBox.information(self, "提示", "请先创建或选择一个项目")
            self._step_list.setCurrentRow(0)
            return

        self._current_step = key
        self._refresh_step_panel(row, key)

    def _refresh_step_panel(self, row: int, step_key: str):
        """Refresh the right-side panel for the given step."""
        if step_key == "project":
            self._show_project_dashboard()
        elif step_key == "import":
            self._show_import_panel()
        elif step_key == "decide":
            self._show_decide_panel()
        elif step_key == "translate":
            self._show_translation_panel()
        elif step_key == "review":
            self._show_review_panel()
        elif step_key == "export":
            self._show_export_panel()

    # ── Panel Factories ────────────────────────────────────────

    def _show_project_dashboard(self):
        """Show project dashboard in the stack."""
        from ruzh_translator.ui.project_dashboard import ProjectDashboard
        dashboard = ProjectDashboard(main_window=self)
        self._replace_panel(0, dashboard)

    def _show_import_panel(self):
        """Show import panel."""
        from ruzh_translator.ui.import_dialog import ImportPanel
        panel = ImportPanel(main_window=self, project_id=self._project_id)
        self._replace_panel(1, panel)

    def _show_decide_panel(self):
        """Show path selection panel (align vs translate)."""
        from ruzh_translator.ui.import_dialog import DecidePanel
        panel = DecidePanel(main_window=self, project_id=self._project_id)
        self._replace_panel(2, panel)

    def _show_translation_panel(self):
        """Show translation editor."""
        from ruzh_translator.ui.translation_editor import TranslationEditor
        editor = TranslationEditor(project_id=self._project_id, main_window=self)
        self._replace_panel(3, editor)

    def _show_review_panel(self):
        """Show review panel."""
        from ruzh_translator.ui.review_panel import ReviewPanel
        panel = ReviewPanel(project_id=self._project_id)
        self._replace_panel(4, panel)

    def _show_export_panel(self):
        """Show export panel."""
        from ruzh_translator.ui.export_dialog import ExportPanel
        panel = ExportPanel(main_window=self, project_id=self._project_id)
        self._replace_panel(5, panel)

    def _replace_panel(self, index: int, widget: QWidget):
        """Replace the widget at the given stack index."""
        old = self._stack.widget(index)
        self._stack.removeWidget(old)
        old.deleteLater()
        self._stack.insertWidget(index, widget)
        self._stack.setCurrentIndex(index)

    # ── Convenience Navigation ─────────────────────────────────

    def goto_create_project(self):
        self.go_to_step("project")

    def goto_import(self):
        if not self._project_id:
            QMessageBox.information(self, "提示", "请先创建或选择项目")
            self.go_to_step("project")
            return
        self.go_to_step("import")

    def goto_decide(self):
        """Called after import to choose align vs translate."""
        self.go_to_step("decide")

    def goto_translate(self):
        if not self._project_id:
            QMessageBox.information(self, "提示", "请先创建项目并导入文档")
            self.go_to_step("project")
            return
        self.go_to_step("translate")

    def goto_alignment(self):
        """Open alignment editor (access from decide step or menu)."""
        if not self._project_id:
            QMessageBox.information(self, "提示", "请先创建项目并导入文档")
            self.go_to_step("project")
            return
        from ruzh_translator.ui.alignment_editor import AlignmentEditor
        editor = AlignmentEditor(project_id=self._project_id, main_window=self)
        self._replace_panel(2, editor)

    def goto_review(self):
        if not self._project_id:
            self.go_to_step("project")
            return
        self.go_to_step("review")

    def goto_export(self):
        if not self._project_id:
            self.go_to_step("project")
            return
        self.go_to_step("export")

    def goto_glossary(self):
        """Open glossary editor."""
        from ruzh_translator.ui.glossary_editor import GlossaryEditor
        editor = GlossaryEditor(project_id=self._project_id)
        # Open in a dialog
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("术语库管理")
        dlg.resize(800, 600)
        layout = QVBoxLayout(dlg)
        layout.addWidget(editor)
        dlg.exec()

    def goto_split(self):
        """Open task split dialog."""
        from ruzh_translator.ui.task_split_dialog import TaskSplitDialog
        dlg = TaskSplitDialog(self)
        dlg.exec()

    def goto_merge(self):
        """Open task merge dialog."""
        from ruzh_translator.ui.task_merge_dialog import TaskMergeDialog
        dlg = TaskMergeDialog(self)
        dlg.exec()

    def set_status(self, message: str):
        """Update status bar."""
        self._status_label.setText(message)

    def _on_about(self):
        QMessageBox.about(
            self, f"关于 {APP_NAME}",
            f"<h3>{APP_NAME} v{APP_VERSION}</h3>"
            f"<p>俄汉翻译流程管理软件</p>"
            f"<p>支持俄语 ↔ 中文双向翻译的全流程管理</p>"
            f"<p>工作流：项目创建 → 导入文档 → 翻译/对齐 → 审校 → 导出</p>",
        )
