"""Concordance Window — ParaConc-style parallel corpus browser."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QTextEdit, QFileDialog, QMessageBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox,
)
from PySide6.QtCore import Qt

from ruzh_translator.models.base import get_session
from ruzh_translator.models.tm import TranslationMemoryEntry
from ruzh_translator.services.tm_service import concordance_search, fuzzy_match
from ruzh_translator.config import IMPORT_FORMATS


class ConcordanceWindow(QMainWindow):
    """ParaConc-style KWIC concordance + TM browser."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("📊 平行语料 — Concordance")
        self.resize(1200, 850)
        self._session = get_session()
        self._setup_ui()

    def _setup_ui(self):
        c = QWidget(); self.setCentralWidget(c)
        layout = QVBoxLayout(c); layout.setContentsMargins(8, 8, 8, 8)

        # Tools
        tools = QHBoxLayout()
        tools.addWidget(QLabel("<b>📊 平行语料库</b>"))

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("输入关键词检索上下文 (KWIC)...")
        self._search_edit.returnPressed.connect(self._on_search)
        tools.addWidget(self._search_edit, 1)

        tools.addWidget(QPushButton("🔍 检索", clicked=self._on_search))

        self._proj_combo = QComboBox()
        self._proj_combo.addItem("从项目加载语料...", None)
        self._refresh_projects()
        self._proj_combo.currentIndexChanged.connect(self._on_load_project)
        tools.addWidget(self._proj_combo)

        tools.addWidget(QPushButton("📂 TMX", clicked=self._on_import_tmx))
        tools.addWidget(QPushButton("📂 XLSX", clicked=self._on_import_xlsx))

        self._tag_combo = QComboBox()
        self._tag_combo.setEditable(True)
        self._tag_combo.setPlaceholderText("选择或输入标签...")
        self._tag_combo.setMinimumWidth(120)
        tools.addWidget(self._tag_combo)

        tools.addWidget(QPushButton("🏷️ 标签管理", clicked=self._on_manage_tags))
        tools.addWidget(QPushButton("📤 导出", clicked=self._on_export))
        layout.addLayout(tools)

        # Body
        split = QSplitter(Qt.Vertical)

        # Top: KWIC results table
        top_g = QGroupBox("KWIC 检索结果")
        top_l = QVBoxLayout(top_g)
        self._kwic_table = QTableWidget()
        self._kwic_table.setColumnCount(5)
        self._kwic_table.setHorizontalHeaderLabels(["#", "左上下文", "关键词", "右上下文", "标签"])
        self._kwic_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._kwic_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._kwic_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self._kwic_table.setColumnWidth(4, 100)
        self._kwic_table.setAlternatingRowColors(True)
        self._kwic_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._kwic_table.cellDoubleClicked.connect(self._on_kwic_click)
        self._kwic_table.cellClicked.connect(self._on_cell_click)
        self._kwic_data = []  # Store full data for each row
        self._kwic_tags = {}  # row -> tag string
        top_l.addWidget(self._kwic_table)
        split.addWidget(top_g)

        # Bottom: Detail + TM browse
        bot = QSplitter(Qt.Horizontal)

        # Left: Detail view
        det_g = QGroupBox("详情")
        det_l = QVBoxLayout(det_g)
        self._detail_src = QTextEdit()
        self._detail_src.setReadOnly(True)
        self._detail_src.setMaximumHeight(100)
        det_l.addWidget(QLabel("源语:"))
        det_l.addWidget(self._detail_src)
        self._detail_tgt = QTextEdit()
        self._detail_tgt.setReadOnly(True)
        self._detail_tgt.setMaximumHeight(100)
        det_l.addWidget(QLabel("目标语:"))
        det_l.addWidget(self._detail_tgt)
        bot.addWidget(det_g)

        # Right: TM browser
        tm_g = QGroupBox("翻译记忆库")
        tm_l = QVBoxLayout(tm_g)
        tm_header = QHBoxLayout()
        tm_header.addWidget(QLabel("共 0 条"))
        tm_header.addStretch()
        tm_header.addWidget(QPushButton("🔄 刷新", clicked=self._refresh_tm))
        tm_l.addLayout(tm_header)

        self._tm_browse = QListWidget()
        self._tm_browse.setStyleSheet("QListWidget::item{padding:6px;border-bottom:1px solid #EEE;}")
        self._tm_browse.itemDoubleClicked.connect(self._on_tm_click)
        tm_l.addWidget(self._tm_browse)

        # Stats
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet("color:#9E9E9E;font-size:11px;")
        tm_l.addWidget(self._stats_label)

        bot.addWidget(tm_g)
        bot.setSizes([400, 400])
        split.addWidget(bot)
        split.setSizes([350, 350])
        layout.addWidget(split, 1)

        self._refresh_tm()

    def _on_search(self):
        query = self._search_edit.text().strip()
        if not query: return

        results = concordance_search(self._session, query, limit=100)
        self._kwic_table.setRowCount(len(results))
        self._kwic_data = results
        self._kwic_tags = {}

        for i, r in enumerate(results):
            self._kwic_table.setItem(i, 0, QTableWidgetItem(str(i+1)))
            src = r["source_text"]
            idx = src.lower().find(query.lower())
            left = src[max(0,idx-25):idx] if idx >= 0 else src[:25]
            right = src[idx+len(query):idx+len(query)+25] if idx >= 0 else ""
            keyword = src[idx:idx+len(query)] if idx >= 0 else query

            self._kwic_table.setItem(i, 1, QTableWidgetItem(f"...{left}"))
            kw_item = QTableWidgetItem(keyword)
            from PySide6.QtGui import QFont, QColor
            kw_item.setForeground(QColor("#FF0000"))
            f = QFont(); f.setBold(True); kw_item.setFont(f)
            self._kwic_table.setItem(i, 2, kw_item)
            self._kwic_table.setItem(i, 3, QTableWidgetItem(f"{right}..."))
            # Tag column
            self._kwic_table.setItem(i, 4, QTableWidgetItem(""))
            # Store full data
            self._kwic_table.item(i, 0).setData(Qt.UserRole, r)

    def _on_kwic_click(self, row, _):
        item = self._kwic_table.item(row, 0)
        if item:
            r = item.data(Qt.UserRole)
            self._detail_src.setPlainText(r["source_text"])
            self._detail_tgt.setPlainText(r["target_text"])

    def _on_cell_click(self, row, col):
        """Tag column click — apply current tag to this row."""
        if col == 4:
            tag = self._tag_combo.currentText().strip()
            if tag:
                self._kwic_tags[row] = tag
                self._kwic_table.item(row, 4).setText(tag)
            else:
                # Clear tag
                self._kwic_tags.pop(row, None)
                self._kwic_table.item(row, 4).setText("")

    def _on_manage_tags(self):
        """Open tag management dialog."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("标签管理")
        dlg.setMinimumWidth(450)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("设置常用标签（每行一个）:"))
        edit = QTextEdit()
        # Load existing tags from combo
        existing = [self._tag_combo.itemText(i) for i in range(self._tag_combo.count()) if self._tag_combo.itemText(i)]
        edit.setPlainText("\n".join(existing))
        layout.addWidget(edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        if dlg.exec():
            self._tag_combo.clear()
            tags = [t.strip() for t in edit.toPlainText().split("\n") if t.strip()]
            self._tag_combo.addItems(tags)
            if tags:
                self._tag_combo.setCurrentIndex(0)
            QMessageBox.information(self, "完成", f"已设置 {len(tags)} 个标签\n\n点击 KWIC 表格的「标签」列即可快速标注")

    def _refresh_tm(self):
        self._tm_browse.clear()
        entries = self._session.query(TranslationMemoryEntry).order_by(
            TranslationMemoryEntry.usage_count.desc()
        ).limit(200).all()
        for e in entries:
            src_preview = (e.source_text or "")[:60]
            tgt_preview = (e.target_text or "")[:40]
            item = QListWidgetItem(f"{src_preview}\n  → {tgt_preview}")
            item.setData(Qt.UserRole, e)
            self._tm_browse.addItem(item)
        self._stats_label.setText(f"共 {len(entries)} 条记忆 | 源语: ru | 目标语: zh-CN")

    def _on_tm_click(self, item):
        e = item.data(Qt.UserRole)
        if e:
            self._detail_src.setPlainText(e.source_text or "")
            self._detail_tgt.setPlainText(e.target_text or "")

    def _refresh_projects(self):
        from ruzh_translator.services.project_service import list_projects
        for p in list_projects(self._session):
            self._proj_combo.addItem(f"📋 {p.name}", p.id)

    def _on_load_project(self):
        pid = self._proj_combo.currentData()
        if not pid: return
        from ruzh_translator.models.segment import AlignmentPair, Segment
        # Load AlignmentPairs from project
        pairs = self._session.query(AlignmentPair).filter(
            AlignmentPair.project_id == pid
        ).all()
        if not pairs:
            QMessageBox.information(self, "提示", "该项目没有对齐数据，请先在语料对齐模块中对齐文档")
            return
        from ruzh_translator.services.tm_service import add_tm_entry
        count = 0
        for p in pairs:
            if p.source_text and p.target_text:
                add_tm_entry(self._session, p.source_text, p.target_text, project_id=pid)
                count += 1
        self._refresh_tm()
        QMessageBox.information(self, "加载成功", f"从项目加载了 {count} 条翻译记忆")

    def _on_import_tmx(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入 TMX", "", "TMX 文件 (*.tmx)")
        if not path: return
        try:
            from ruzh_translator.utils.tmx_parser import parse_tmx
            units = parse_tmx(path)
            from ruzh_translator.services.tm_service import add_tm_entry
            count = 0
            for u in units:
                if u.get("source_text"):
                    add_tm_entry(self._session, u["source_text"], u.get("target_text", ""),
                                 u.get("source_lang", "ru"), u.get("target_lang", "zh-CN"))
                    count += 1
            QMessageBox.information(self, "导入成功", f"已导入 {count} 条翻译记忆")
            self._refresh_tm()
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))

    def _on_import_xlsx(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入 XLSX 语料", "", "Excel 文件 (*.xlsx)")
        if not path: return
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path); ws = wb.active
            from ruzh_translator.services.tm_service import add_tm_entry
            count = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or len(row) < 2: continue
                src = str(row[0]).strip() if row[0] else ""
                tgt = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                if not src: continue
                add_tm_entry(self._session, src, tgt)
                count += 1
            QMessageBox.information(self, "导入成功", f"已导入 {count} 条语料")
            self._refresh_tm()
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出检索结果", "concordance.xlsx", "Excel (*.xlsx)")
        if not path: return
        import openpyxl; wb = openpyxl.Workbook(); ws = wb.active; ws.title = "KWIC结果"
        for c, h in enumerate(["#","左上下文","关键词","右上下文","完整源语","目标语","标签"],1): ws.cell(1,c,h)
        for r in range(self._kwic_table.rowCount()):
            item = self._kwic_table.item(r, 0)
            if item:
                data = item.data(Qt.UserRole) if hasattr(item, 'data') else None
                ws.cell(r+2,1,r+1)
                ws.cell(r+2,2,self._kwic_table.item(r,1).text() if self._kwic_table.item(r,1) else "")
                ws.cell(r+2,3,self._kwic_table.item(r,2).text() if self._kwic_table.item(r,2) else "")
                ws.cell(r+2,4,self._kwic_table.item(r,3).text() if self._kwic_table.item(r,3) else "")
                ws.cell(r+2,5,data["source_text"] if data else "")
                ws.cell(r+2,6,data["target_text"] if data else "")
                ws.cell(r+2,7,self._kwic_tags.get(r, ""))
        wb.save(path)
        QMessageBox.information(self, "导出成功", f"已导出到:\n{path}")
