"""Export dialog: configure and execute multi-format export."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QDialogButtonBox,
    QMessageBox,
    QProgressBar,
    QGroupBox,
    QFileDialog,
)
from PySide6.QtCore import Qt

from ruzh_translator.models.base import get_session
from ruzh_translator.services.export_service import export_project
from ruzh_translator.services.project_service import list_projects, get_project
from ruzh_translator.config import EXPORT_FORMATS


class ExportDialog(QDialog):
    """Dialog for exporting translation results in various formats."""

    def __init__(self, parent=None, project_id: str = None):
        super().__init__(parent)
        self.setWindowTitle("导出翻译结果")
        self.setMinimumSize(550, 450)
        self._session = get_session()
        self._project_id = project_id
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Project selection ──
        proj_layout = QHBoxLayout()
        proj_layout.addWidget(QLabel("项目:"))

        self._project_combo = QComboBox()
        self._refresh_projects()
        proj_layout.addWidget(self._project_combo, 1)
        layout.addLayout(proj_layout)

        # ── Export formats ──
        formats_group = QGroupBox("导出格式")
        formats_layout = QVBoxLayout(formats_group)

        self._format_checks = {}
        for fmt, desc in EXPORT_FORMATS.items():
            cb = QCheckBox(f"{desc} (.{fmt})")
            cb.setChecked(fmt in ("xlsx", "tmx"))  # Default: xlsx + tmx
            formats_layout.addWidget(cb)
            self._format_checks[fmt] = cb

        layout.addWidget(formats_group)

        # ── Options ──
        options_group = QGroupBox("导出选项")
        options_layout = QFormLayout(options_group)

        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("选择导出目录...")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_output)
        out_layout = QHBoxLayout()
        out_layout.addWidget(self._output_edit)
        out_layout.addWidget(browse_btn)
        options_layout.addRow("输出目录:", out_layout)

        self._approved_only = QCheckBox("仅导出已批准的句段")
        options_layout.addRow("", self._approved_only)

        self._include_metadata = QCheckBox("包含置信度和状态信息（Excel）")
        self._include_metadata.setChecked(True)
        options_layout.addRow("", self._include_metadata)

        layout.addWidget(options_group)

        # ── Progress ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Buttons ──
        buttons = QDialogButtonBox()
        export_btn = QPushButton("📤 导出")
        export_btn.clicked.connect(self._on_export)
        export_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 24px;")
        buttons.addButton(export_btn, QDialogButtonBox.AcceptRole)
        buttons.addButton(QPushButton("取消"), QDialogButtonBox.RejectRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_projects(self):
        """Refresh project combo."""
        self._project_combo.clear()
        for p in list_projects(self._session):
            progress = p.progress
            self._project_combo.addItem(
                f"{p.name} [已译: {progress['translated_pct']}%]",
                p.id,
            )
        if self._project_id:
            for i in range(self._project_combo.count()):
                if self._project_combo.itemData(i) == self._project_id:
                    self._project_combo.setCurrentIndex(i)
                    break

    def _browse_output(self):
        """Browse for output directory."""
        dir_path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if dir_path:
            self._output_edit.setText(dir_path)

    def _on_export(self):
        """Execute the export."""
        project_id = self._project_combo.currentData()
        if not project_id:
            QMessageBox.warning(self, "提示", "请选择项目")
            return

        # Collect selected formats
        formats = [fmt for fmt, cb in self._format_checks.items() if cb.isChecked()]
        if not formats:
            QMessageBox.warning(self, "提示", "请选择至少一种导出格式")
            return

        output_dir = self._output_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "提示", "请选择输出目录")
            return

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        try:
            results = export_project(
                self._session,
                project_id,
                output_dir,
                formats=formats,
            )

            msg = "导出完成！\n\n"
            for fmt, path in results.items():
                msg += f"✅ {EXPORT_FORMATS.get(fmt, fmt)}: {path}\n"

            QMessageBox.information(self, "导出成功", msg)
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
        finally:
            self._progress.setVisible(False)


class ExportPanel(QWidget):
    """Embedded export panel for the workflow stepper (step 6)."""

    export_done = Signal()

    def __init__(self, main_window=None, project_id: str = None):
        super().__init__()
        self._main_window = main_window
        self._session = get_session()
        self._project_id = project_id
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("<h2>📤 导出翻译结果</h2>")
        title.setStyleSheet("color: #37474F;")
        layout.addWidget(title)

        # Data preview
        self._preview_label = QLabel("")
        self._preview_label.setStyleSheet("color: #1565C0; font-size: 14px; margin: 12px 0;")
        layout.addWidget(self._preview_label)

        if self._project_id:
            self._load_preview()

        # Format selection
        fmt_group = QGroupBox("选择导出格式")
        fmt_layout = QVBoxLayout(fmt_group)

        self._format_checks = {}
        defaults = {"xlsx": True, "tmx": True, "docx": False, "html": False}
        for fmt, desc in EXPORT_FORMATS.items():
            cb = QCheckBox(f"{desc} (.{fmt})")
            cb.setChecked(defaults.get(fmt, False))
            fmt_layout.addWidget(cb)
            self._format_checks[fmt] = cb

        layout.addWidget(fmt_group)

        # Output directory
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("输出目录:"))
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("选择导出目录...")
        out_layout.addWidget(self._output_edit)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_output)
        out_layout.addWidget(browse_btn)
        layout.addLayout(out_layout)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Export button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        export_btn = QPushButton("📤 导出")
        export_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "padding: 10px 32px; font-size: 15px; border-radius: 8px; } "
            "QPushButton:hover { background-color: #388E3C; }"
        )
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _load_preview(self):
        """Show a preview of export data count."""
        if not self._project_id:
            return

        from ruzh_translator.models.segment import Segment, AlignmentPair
        pair_count = (
            self._session.query(AlignmentPair)
            .filter(AlignmentPair.project_id == self._project_id)
            .count()
        )
        seg_count = (
            self._session.query(Segment)
            .filter(
                Segment.project_id == self._project_id,
                Segment.target_text != "",
                Segment.target_text.isnot(None),
            )
            .count()
        )
        total = max(pair_count, seg_count)
        if total == 0:
            self._preview_label.setText("⚠️ 暂无翻译数据可导出。请先完成翻译。")
            self._preview_label.setStyleSheet("color: #F44336; font-size: 14px;")
        else:
            self._preview_label.setText(f"可导出 {total} 条翻译记录")
            self._preview_label.setStyleSheet("color: #4CAF50; font-size: 14px;")

    def _browse_output(self):
        """Browse for output directory."""
        dir_path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if dir_path:
            self._output_edit.setText(dir_path)

    def _on_export(self):
        """Execute export."""
        if not self._project_id:
            QMessageBox.warning(self, "提示", "请先选择项目")
            return

        formats = [f for f, cb in self._format_checks.items() if cb.isChecked()]
        if not formats:
            QMessageBox.warning(self, "提示", "请选择至少一种导出格式")
            return

        output_dir = self._output_edit.text().strip() or str(Path.home() / "Desktop")
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        try:
            results = export_project(self._session, self._project_id, output_dir, formats)
            msg = "导出完成！\n\n"
            for fmt, path in results.items():
                msg += f"✅ {EXPORT_FORMATS.get(fmt, fmt)}: {path}\n"
            QMessageBox.information(self, "导出成功", msg)
            self._load_preview()
            self.export_done.emit()
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
        finally:
            self._progress.setVisible(False)
