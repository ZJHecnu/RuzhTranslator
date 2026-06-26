"""Project dashboard: list projects and display status/progress."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from ruzh_translator.config import SOURCE_LANGS, TARGET_LANGS, PROJECT_STATUSES
from ruzh_translator.models.base import get_session
from ruzh_translator.services.project_service import (
    create_project,
    list_projects,
    delete_project,
    update_project_status,
)


class ProjectDashboard(QWidget):
    """Project list and management dashboard."""

    project_opened = Signal(str)  # project_id

    def __init__(self, main_window=None):
        super().__init__()
        self._main_window = main_window
        self._session = get_session()
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("<h2>📊 翻译项目</h2>")
        header.addWidget(title)
        header.addStretch()

        new_btn = QPushButton("➕ 新建项目")
        new_btn.clicked.connect(self._on_new_project)
        header.addWidget(new_btn)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_list)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # ── Project table ──
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "项目名称", "语言对", "状态", "总句数",
            "已译%", "已审%", "更新时间",
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.doubleClicked.connect(self._on_open_project)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        # ── Action buttons ──
        actions = QHBoxLayout()

        open_btn = QPushButton("📂 打开项目")
        open_btn.clicked.connect(self._on_open_project)
        actions.addWidget(open_btn)

        delete_btn = QPushButton("🗑 删除项目")
        delete_btn.clicked.connect(self._on_delete_project)
        actions.addWidget(delete_btn)

        actions.addStretch()
        layout.addLayout(actions)

    def _refresh_list(self):
        """Refresh the project table."""
        projects = list_projects(self._session)
        self._table.setRowCount(len(projects))

        status_colors = {
            "setup": QColor("#9E9E9E"),
            "alignment": QColor("#2196F3"),
            "translation": QColor("#FF9800"),
            "review": QColor("#4CAF50"),
            "completed": QColor("#388E3C"),
        }

        for row, project in enumerate(projects):
            self._table.setItem(row, 0, QTableWidgetItem(project.name))
            lang_pair = f"{SOURCE_LANGS.get(project.source_lang, project.source_lang)} → {TARGET_LANGS.get(project.target_lang, project.target_lang)}"
            self._table.setItem(row, 1, QTableWidgetItem(lang_pair))

            status_item = QTableWidgetItem(project.status)
            color = status_colors.get(project.status, QColor("#9E9E9E"))
            status_item.setForeground(color)
            self._table.setItem(row, 2, status_item)

            progress = project.progress
            self._table.setItem(row, 3, QTableWidgetItem(str(progress["total"])))
            self._table.setItem(row, 4, QTableWidgetItem(f"{progress['translated_pct']}%"))
            self._table.setItem(row, 5, QTableWidgetItem(f"{progress['approved_pct']}%"))

            updated = project.updated_at.strftime("%Y-%m-%d %H:%M") if project.updated_at else ""
            self._table.setItem(row, 6, QTableWidgetItem(updated))

            # Store project ID in first column item
            self._table.item(row, 0).setData(Qt.UserRole, project.id)

    def _current_project_id(self) -> str | None:
        """Get the ID of the currently selected project."""
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _on_new_project(self):
        """Open new project dialog."""
        dialog = NewProjectDialog(self)
        if dialog.exec():
            project = create_project(
                self._session,
                name=dialog.project_name,
                source_lang=dialog.source_lang,
                target_lang=dialog.target_lang,
                description=dialog.description,
            )
            self._refresh_list()
            if self._main_window:
                self._main_window.set_project(project.id)
                self._main_window.set_status(f"已创建项目: {project.name}")
                self._main_window.goto_import()

    def _on_open_project(self):
        """Open the selected project and navigate to import step."""
        project_id = self._current_project_id()
        if not project_id:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return

        if self._main_window:
            self._main_window.set_project(project_id)
            self._main_window.goto_import()
        self.project_opened.emit(project_id)

    def _on_import_clicked(self):
        """Navigate to import step for selected project."""
        project_id = self._current_project_id()
        if not project_id:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return

        if self._main_window:
            self._main_window.set_project(project_id)
            self._main_window.goto_import()

    def _on_translate_clicked(self):
        """Navigate to translation editor."""
        project_id = self._current_project_id()
        if not project_id:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return

        if self._main_window:
            self._main_window.set_project(project_id)
            self._main_window.goto_translate()

    def _on_delete_project(self):
        """Delete the selected project."""
        project_id = self._current_project_id()
        if not project_id:
            return

        item = self._table.item(self._table.currentRow(), 0)
        name = item.text()

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除项目「{name}」吗？\n此操作不可撤销，所有翻译数据将被永久删除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            delete_project(self._session, project_id)
            self._refresh_list()
            if self._main_window:
                self._main_window.set_status(f"已删除项目: {name}")


class NewProjectDialog(QDialog):
    """Dialog for creating a new translation project."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建翻译项目")
        self.setMinimumWidth(500)
        self.project_name = ""
        self.source_lang = "ru"
        self.target_lang = "zh-CN"
        self.description = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("输入项目名称，如：邓小平文选第三章翻译")
        form.addRow("项目名称:", self._name_edit)

        self._src_combo = QComboBox()
        for code, name in SOURCE_LANGS.items():
            self._src_combo.addItem(name, code)
        self._src_combo.setCurrentIndex(0)  # ru = 俄语
        form.addRow("源语言:", self._src_combo)

        self._tgt_combo = QComboBox()
        for code, name in TARGET_LANGS.items():
            self._tgt_combo.addItem(name, code)
        self._tgt_combo.setCurrentIndex(1)  # zh-CN = 中文
        form.addRow("目标语言:", self._tgt_combo)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("项目描述（可选）")
        self._desc_edit.setMaximumHeight(80)
        form.addRow("描述:", self._desc_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入项目名称")
            return
        self.project_name = name
        self.source_lang = self._src_combo.currentData()
        self.target_lang = self._tgt_combo.currentData()
        self.description = self._desc_edit.toPlainText().strip()
        self.accept()
