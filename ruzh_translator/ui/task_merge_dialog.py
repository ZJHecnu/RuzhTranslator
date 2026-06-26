"""Task merge dialog: merge completed translator tasks with conflict resolution."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QMessageBox,
    QProgressBar,
    QGroupBox,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QSplitter,
)
from PySide6.QtCore import Qt

from ruzh_translator.models.base import get_session
from ruzh_translator.services.split_merge_service import merge_tasks, parse_task_file
from ruzh_translator.services.project_service import list_projects


class TaskMergeDialog(QDialog):
    """Dialog for merging completed task files back into a project."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("任务合并 — 合并翻译结果")
        self.setMinimumSize(800, 600)
        self._session = get_session()
        self._task_paths = []
        self._conflicts = []
        self._resolutions = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Project selection ──
        proj_layout = QHBoxLayout()
        proj_layout.addWidget(QLabel("目标项目:"))

        self._project_combo = QComboBox()
        for p in list_projects(self._session):
            self._project_combo.addItem(p.name, p.id)
        proj_layout.addWidget(self._project_combo, 1)
        layout.addLayout(proj_layout)

        # ── Task files ──
        files_group = QGroupBox("已完成的任务文件 (.ruzh_task)")
        files_layout = QVBoxLayout(files_group)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("📂 添加任务文件")
        add_btn.clicked.connect(self._add_task_files)
        btn_layout.addWidget(add_btn)

        remove_btn = QPushButton("🗑 移除选中")
        remove_btn.clicked.connect(self._remove_task_file)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        files_layout.addLayout(btn_layout)

        self._task_list = QListWidget()
        files_layout.addWidget(self._task_list)

        layout.addWidget(files_group)

        # ── Preview / Conflicts ──
        preview_group = QGroupBox("任务预览与冲突检测")
        preview_layout = QVBoxLayout(preview_group)

        self._preview_btn = QPushButton("🔍 预览并检测冲突")
        self._preview_btn.clicked.connect(self._on_preview)
        preview_layout.addWidget(self._preview_btn)

        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setMaximumHeight(250)
        preview_layout.addWidget(self._preview_text)

        layout.addWidget(preview_group)

        # ── Progress ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Buttons ──
        buttons = QDialogButtonBox()
        merge_btn = QPushButton("🔀 执行合并")
        merge_btn.clicked.connect(self._on_merge)
        merge_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 24px;")
        buttons.addButton(merge_btn, QDialogButtonBox.AcceptRole)
        buttons.addButton(QPushButton("关闭"), QDialogButtonBox.RejectRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_task_files(self):
        """Add .ruzh_task files to the merge list."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择任务文件", "", "任务文件 (*.ruzh_task)"
        )
        for path in paths:
            if path not in self._task_paths:
                self._task_paths.append(path)
                self._task_list.addItem(QListWidgetItem(path))

    def _remove_task_file(self):
        """Remove selected task file."""
        row = self._task_list.currentRow()
        if row >= 0:
            self._task_paths.pop(row)
            self._task_list.takeItem(row)

    def _on_preview(self):
        """Preview task files and detect conflicts."""
        if not self._task_paths:
            QMessageBox.warning(self, "提示", "请先添加任务文件")
            return

        self._preview_text.clear()
        preview_lines = []

        for path in self._task_paths:
            try:
                task = parse_task_file(path)
                manifest = task.get("manifest", {})
                segments = task.get("segments", [])
                translator = manifest.get("translator", "未知")
                translated = sum(1 for s in segments if s.get("target_text", "").strip())

                preview_lines.append(
                    f"📦 {path.split('/')[-1]}\n"
                    f"   翻译者: {translator}\n"
                    f"   总句数: {len(segments)}, 已译: {translated}\n"
                )
            except Exception as e:
                preview_lines.append(f"❌ {path}: 解析失败 - {e}\n")

        # Detect conflicts
        try:
            from ruzh_translator.services.split_merge_service import detect_conflicts
            tasks = [parse_task_file(p) for p in self._task_paths]
            merge_map, conflicts = detect_conflicts(tasks)
            self._conflicts = conflicts

            if conflicts:
                preview_lines.append(f"\n⚠️ 检测到 {len(conflicts)} 处冲突:")
                for c in conflicts:
                    preview_lines.append(f"  句段 {c['pair_id']}:")
                    for t in c["translations"]:
                        preview_lines.append(f"    - {t['translator']}: {t['text'][:60]}...")

            preview_lines.append(f"\n✅ 可自动合并: {len(merge_map)} 句")
        except Exception as e:
            preview_lines.append(f"\n冲突检测出错: {e}")

        self._preview_text.setPlainText("\n".join(preview_lines))

    def _on_merge(self):
        """Execute the merge."""
        if not self._task_paths:
            return

        project_id = self._project_combo.currentData()
        if not project_id:
            QMessageBox.warning(self, "提示", "请选择目标项目")
            return

        if self._conflicts:
            reply = QMessageBox.question(
                self,
                "存在冲突",
                f"检测到 {len(self._conflicts)} 处冲突。\n"
                f"冲突的句段将保留第一个翻译者的版本。\n\n"
                f"建议在合并后手动检查并修正冲突句段。\n\n"
                f"是否继续？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        try:
            result = merge_tasks(
                self._session,
                project_id,
                self._task_paths,
                self._resolutions,
            )

            QMessageBox.information(
                self,
                "合并完成",
                f"已合并 {result['merged_count']} 个句段\n"
                f"冲突句段: {result['conflict_count']} 个\n\n"
                f"建议进入翻译编辑器检查冲突句段。",
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "合并失败", str(e))
        finally:
            self._progress.setVisible(False)
