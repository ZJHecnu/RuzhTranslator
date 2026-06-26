"""Glossary editor: manage terminology database with CRUD and term extraction."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QFileDialog,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QTextEdit,
)
from PySide6.QtCore import Qt, Signal

from ruzh_translator.models.base import get_session
from ruzh_translator.models.glossary import GlossaryEntry
from ruzh_translator.services.term_extraction_service import extract_terms_from_segments
from ruzh_translator.services.project_service import list_projects, get_project


class GlossaryEditor(QWidget):
    """Glossary management widget with term extraction capability."""

    def __init__(self, project_id: str = None):
        super().__init__()
        self._session = get_session()
        self._project_id = project_id
        self._setup_ui()
        if project_id:
            self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Toolbar ──
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("项目:"))

        self._project_combo = QComboBox()
        self._project_combo.currentIndexChanged.connect(self._refresh)
        self._refresh_projects()
        toolbar.addWidget(self._project_combo, 1)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索术语...")
        self._search_edit.textChanged.connect(self._refresh)
        toolbar.addWidget(self._search_edit)

        extract_btn = QPushButton("🔍 提取术语")
        extract_btn.clicked.connect(self.start_extraction)
        toolbar.addWidget(extract_btn)

        layout.addLayout(toolbar)

        # ── Progress ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Glossary table ──
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "源语术语", "目标语翻译", "领域", "状态", "备注"
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self._table)

        # ── Actions ──
        actions = QHBoxLayout()

        add_btn = QPushButton("➕ 添加术语")
        add_btn.clicked.connect(self._on_add)
        actions.addWidget(add_btn)

        edit_btn = QPushButton("✏️ 编辑选中")
        edit_btn.clicked.connect(self._on_edit)
        actions.addWidget(edit_btn)

        delete_btn = QPushButton("🗑 删除选中")
        delete_btn.clicked.connect(self._on_delete)
        actions.addWidget(delete_btn)

        actions.addStretch()

        import_btn = QPushButton("📥 导入 Excel")
        import_btn.clicked.connect(self._on_import_excel)
        actions.addWidget(import_btn)

        export_btn = QPushButton("📤 导出 Excel")
        export_btn.clicked.connect(self._on_export_excel)
        actions.addWidget(export_btn)

        layout.addLayout(actions)

    def _refresh_projects(self):
        """Refresh the project combo."""
        self._project_combo.clear()
        self._project_combo.addItem("-- 选择项目 --", None)
        for p in list_projects(self._session):
            self._project_combo.addItem(p.name, p.id)
        if self._project_id:
            for i in range(self._project_combo.count()):
                if self._project_combo.itemData(i) == self._project_id:
                    self._project_combo.setCurrentIndex(i)
                    break

    def _refresh(self):
        """Refresh the glossary table. Auto-extracts terms if glossary is empty."""
        project_id = self._project_combo.currentData()
        if not project_id:
            self._table.setRowCount(0)
            return

        query = self._session.query(GlossaryEntry).filter(
            GlossaryEntry.project_id == project_id
        )

        search = self._search_edit.text().strip()
        if search:
            query = query.filter(GlossaryEntry.source_term.contains(search))

        entries = query.order_by(GlossaryEntry.source_term).all()
        self._table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            self._table.setItem(row, 0, QTableWidgetItem(entry.source_term))
            self._table.setItem(row, 1, QTableWidgetItem(entry.target_term))
            self._table.setItem(row, 2, QTableWidgetItem(entry.domain or ""))
            status = "✓ 已确认" if entry.is_approved else "待确认"
            self._table.setItem(row, 3, QTableWidgetItem(status))
            self._table.setItem(row, 4, QTableWidgetItem((entry.notes or "")[:50]))

        # Auto-extract if glossary is empty and project has segments
        if not entries and not search:
            self._auto_extract_if_needed(project_id)

    def _auto_extract_if_needed(self, project_id: str):
        """Automatically extract terms if the glossary is empty."""
        from ruzh_translator.models.segment import Segment
        seg_count = (
            self._session.query(Segment)
            .filter(Segment.project_id == project_id)
            .count()
        )
        if seg_count > 0:
            self.start_extraction()

    def _current_project_id(self) -> str | None:
        return self._project_combo.currentData()

    def _on_add(self):
        """Add a new glossary entry."""
        pid = self._current_project_id()
        if not pid:
            QMessageBox.warning(self, "提示", "请先选择项目")
            return

        dialog = GlossaryEntryDialog(self)
        if dialog.exec():
            entry = GlossaryEntry(
                project_id=pid,
                source_term=dialog.source_term,
                target_term=dialog.target_term,
                domain=dialog.domain,
                notes=dialog.notes,
                is_approved=1,
            )
            self._session.add(entry)
            self._session.commit()
            self._refresh()

    def _on_edit(self):
        """Edit the selected glossary entry."""
        row = self._table.currentRow()
        if row < 0:
            return

        pid = self._current_project_id()
        if not pid:
            return

        src = self._table.item(row, 0).text()
        entry = (
            self._session.query(GlossaryEntry)
            .filter(
                GlossaryEntry.project_id == pid,
                GlossaryEntry.source_term == src,
            )
            .first()
        )
        if not entry:
            return

        dialog = GlossaryEntryDialog(
            self,
            source_term=entry.source_term,
            target_term=entry.target_term,
            domain=entry.domain or "",
            notes=entry.notes or "",
        )
        if dialog.exec():
            entry.source_term = dialog.source_term
            entry.target_term = dialog.target_term
            entry.domain = dialog.domain
            entry.notes = dialog.notes
            self._session.commit()
            self._refresh()

    def _on_delete(self):
        """Delete the selected glossary entry."""
        row = self._table.currentRow()
        if row < 0:
            return

        src = self._table.item(row, 0).text()
        pid = self._current_project_id()

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除术语「{src}」吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            entry = (
                self._session.query(GlossaryEntry)
                .filter(
                    GlossaryEntry.project_id == pid,
                    GlossaryEntry.source_term == src,
                )
                .first()
            )
            if entry:
                self._session.delete(entry)
                self._session.commit()
                self._refresh()

    def _on_import_excel(self):
        """Import glossary from Excel file."""
        pid = self._current_project_id()
        if not pid:
            QMessageBox.warning(self, "提示", "请先选择项目")
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "导入术语 Excel", "", "Excel 文件 (*.xlsx)"
        )
        if not path:
            return

        try:
            import pandas as pd
            df = pd.read_excel(path)

            # Expect columns: source_term, target_term (required), domain, notes (optional)
            count = 0
            for _, row in df.iterrows():
                src = str(row.get("source_term", row.iloc[0] if len(row) > 0 else "")).strip()
                tgt = str(row.get("target_term", row.iloc[1] if len(row) > 1 else "")).strip()
                if not src or not tgt:
                    continue

                existing = (
                    self._session.query(GlossaryEntry)
                    .filter(
                        GlossaryEntry.project_id == pid,
                        GlossaryEntry.source_term == src,
                    )
                    .first()
                )
                if existing:
                    existing.target_term = tgt
                else:
                    entry = GlossaryEntry(
                        project_id=pid,
                        source_term=src,
                        target_term=tgt,
                        domain=str(row.get("domain", "")).strip() if "domain" in df.columns else "",
                        notes=str(row.get("notes", "")).strip() if "notes" in df.columns else "",
                        is_approved=1,
                    )
                    self._session.add(entry)
                count += 1

            self._session.commit()
            self._refresh()
            QMessageBox.information(self, "导入成功", f"已导入 {count} 条术语")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))

    def _on_export_excel(self):
        """Export glossary to Excel."""
        pid = self._current_project_id()
        if not pid:
            return

        entries = (
            self._session.query(GlossaryEntry)
            .filter(GlossaryEntry.project_id == pid)
            .all()
        )
        if not entries:
            QMessageBox.warning(self, "提示", "没有可导出的术语")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出术语", "glossary.xlsx", "Excel 文件 (*.xlsx)"
        )
        if not path:
            return

        import pandas as pd
        data = [
            {
                "source_term": e.source_term,
                "target_term": e.target_term,
                "domain": e.domain or "",
                "notes": e.notes or "",
            }
            for e in entries
        ]
        df = pd.DataFrame(data)
        df.to_excel(path, index=False)
        QMessageBox.information(self, "导出成功", f"已导出 {len(entries)} 条术语到:\n{path}")

    def start_extraction(self):
        """Start automatic term extraction for the current project."""
        pid = self._current_project_id()
        if not pid:
            QMessageBox.warning(self, "提示", "请先选择项目")
            return

        from ruzh_translator.models.segment import Segment

        segments = (
            self._session.query(Segment)
            .filter(Segment.project_id == pid)
            .all()
        )

        if not segments:
            QMessageBox.warning(self, "提示", "该项目没有已导入的片段。请先进行文档导入和对齐。")
            return

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        try:
            terms = extract_terms_from_segments(segments, language="ru", top_n=100)

            if not terms:
                QMessageBox.information(self, "提示", "未提取到候选术语")
                return

            # Add to glossary as unconfirmed entries
            added = 0
            for term_dict in terms:
                existing = (
                    self._session.query(GlossaryEntry)
                    .filter(
                        GlossaryEntry.project_id == pid,
                        GlossaryEntry.source_term == term_dict["term"],
                    )
                    .first()
                )
                if not existing:
                    entry = GlossaryEntry(
                        project_id=pid,
                        source_term=term_dict["term"],
                        target_term="",  # Needs manual translation
                        is_approved=0,
                        notes=f"自动提取 (频次: {term_dict.get('frequency', 0)})",
                    )
                    self._session.add(entry)
                    added += 1

            self._session.commit()
            self._refresh()
            QMessageBox.information(
                self,
                "提取完成",
                f"已提取 {len(terms)} 个候选术语，其中 {added} 个为新术语。\n"
                f"请对标记为「待确认」的术语进行审核和翻译。",
            )
        except Exception as e:
            QMessageBox.critical(self, "提取失败", str(e))
        finally:
            self._progress.setVisible(False)


class GlossaryEntryDialog(QDialog):
    """Dialog for adding/editing a glossary entry."""

    def __init__(self, parent=None, source_term="", target_term="", domain="", notes=""):
        super().__init__(parent)
        self.setWindowTitle("编辑术语")
        self.setMinimumWidth(450)
        self.source_term = source_term
        self.target_term = target_term
        self.domain = domain
        self.notes = notes
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._src_edit = QLineEdit(self.source_term)
        self._src_edit.setPlaceholderText("例: порождать")
        form.addRow("源语术语:", self._src_edit)

        self._tgt_edit = QLineEdit(self.target_term)
        self._tgt_edit.setPlaceholderText("例: 造就, 产生")
        form.addRow("目标语翻译:", self._tgt_edit)

        self._domain_edit = QLineEdit(self.domain)
        self._domain_edit.setPlaceholderText("例: 政治, 文学")
        form.addRow("领域:", self._domain_edit)

        self._notes_edit = QTextEdit()
        self._notes_edit.setPlainText(self.notes)
        self._notes_edit.setMaximumHeight(60)
        form.addRow("备注:", self._notes_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        src = self._src_edit.text().strip()
        if not src:
            QMessageBox.warning(self, "提示", "请输入源语术语")
            return
        self.source_term = src
        self.target_term = self._tgt_edit.text().strip()
        self.domain = self._domain_edit.text().strip()
        self.notes = self._notes_edit.toPlainText().strip()
        self.accept()
