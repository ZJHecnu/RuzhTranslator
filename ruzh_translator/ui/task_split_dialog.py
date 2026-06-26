"""Task split dialog: configure and execute task splitting for team translation."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QSpinBox,
    QLineEdit,
    QTextEdit,
    QDialogButtonBox,
    QMessageBox,
    QProgressBar,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt

from ruzh_translator.models.base import get_session
from ruzh_translator.services.split_merge_service import build_task_assignments
from ruzh_translator.services.project_service import list_projects


class TaskSplitDialog(QDialog):
    """Dialog for splitting a project into translator task packages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("任务切分 — 分发给翻译人员")
        self.setMinimumSize(600, 500)
        self._session = get_session()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Project selection ──
        proj_layout = QHBoxLayout()
        proj_layout.addWidget(QLabel("项目:"))

        self._project_combo = QComboBox()
        for p in list_projects(self._session):
            self._project_combo.addItem(f"{p.name} [{p.progress['total']}句]", p.id)
        proj_layout.addWidget(self._project_combo, 1)
        layout.addLayout(proj_layout)

        # ── Translators ──
        trans_group = QGroupBox("翻译人员")
        trans_layout = QVBoxLayout(trans_group)

        add_layout = QHBoxLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("输入翻译人员姓名...")
        add_layout.addWidget(self._name_edit)

        add_btn = QPushButton("➕ 添加")
        add_btn.clicked.connect(self._add_translator)
        add_layout.addWidget(add_btn)
        trans_layout.addLayout(add_layout)

        self._translator_list = QListWidget()
        trans_layout.addWidget(self._translator_list)

        remove_btn = QPushButton("➖ 移除选中")
        remove_btn.clicked.connect(self._remove_translator)
        trans_layout.addWidget(remove_btn)

        layout.addWidget(trans_group)

        # ── Options ──
        options_group = QGroupBox("切分选项")
        options_layout = QFormLayout(options_group)

        self._min_spin = QSpinBox()
        self._min_spin.setRange(5, 500)
        self._min_spin.setValue(10)
        self._min_spin.setSuffix(" 句")
        options_layout.addRow("每人最少句数:", self._min_spin)

        self._max_spin = QSpinBox()
        self._max_spin.setRange(10, 1000)
        self._max_spin.setValue(100)
        self._max_spin.setSuffix(" 句")
        options_layout.addRow("每人最多句数:", self._max_spin)

        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("默认为项目共享文件夹")
        options_layout.addRow("输出目录:", self._output_edit)

        layout.addWidget(options_group)

        # ── Progress ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Buttons ──
        buttons = QDialogButtonBox()
        split_btn = QPushButton("✂️ 开始切分")
        split_btn.clicked.connect(self._on_split)
        split_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 8px 24px;")
        buttons.addButton(split_btn, QDialogButtonBox.AcceptRole)
        buttons.addButton(QPushButton("取消"), QDialogButtonBox.RejectRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_translator(self):
        """Add a translator to the list."""
        name = self._name_edit.text().strip()
        if not name:
            return
        # Check duplicate
        for i in range(self._translator_list.count()):
            if self._translator_list.item(i).text() == name:
                return
        self._translator_list.addItem(QListWidgetItem(name))
        self._name_edit.clear()

    def _remove_translator(self):
        """Remove the selected translator."""
        row = self._translator_list.currentRow()
        if row >= 0:
            self._translator_list.takeItem(row)

    def _on_split(self):
        """Execute the task splitting."""
        # Validate
        if self._translator_list.count() < 1:
            QMessageBox.warning(self, "提示", "请添加至少一位翻译人员")
            return

        project_id = self._project_combo.currentData()
        if not project_id:
            QMessageBox.warning(self, "提示", "请选择项目")
            return

        translator_names = [
            self._translator_list.item(i).text()
            for i in range(self._translator_list.count())
        ]

        output_dir = self._output_edit.text().strip() or None

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        try:
            # Override constants
            import ruzh_translator.services.split_merge_service as sms
            sms.MIN_CHUNK_SIZE = self._min_spin.value()
            sms.MAX_CHUNK_SIZE = self._max_spin.value()

            assignments = build_task_assignments(
                self._session,
                project_id,
                translator_names,
                output_dir=output_dir,
            )

            msg = "任务切分完成！\n\n"
            for a in assignments:
                msg += (
                    f"📦 {a.translator_name}: "
                    f"句 {a.segment_range_start + 1} - {a.segment_range_end + 1}"
                    f"  [{a.task_file_path}]\n"
                )
            msg += "\n请将生成的 .ruzh_task 文件分发给对应的翻译人员。"

            QMessageBox.information(self, "切分完成", msg)
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "切分失败", str(e))
        finally:
            self._progress.setVisible(False)
