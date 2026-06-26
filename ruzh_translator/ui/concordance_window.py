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
        tools.addWidget(QPushButton("📂 导入 TMX", clicked=self._on_import_tmx))
        tools.addWidget(QPushButton("📤 导出结果", clicked=self._on_export))
        layout.addLayout(tools)

        # Body
        split = QSplitter(Qt.Vertical)

        # Top: KWIC results table
        top_g = QGroupBox("KWIC 检索结果")
        top_l = QVBoxLayout(top_g)
        self._kwic_table = QTableWidget()
        self._kwic_table.setColumnCount(4)
        self._kwic_table.setHorizontalHeaderLabels(["#", "左上下文", "关键词", "右上下文"])
        self._kwic_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._kwic_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._kwic_table.setAlternatingRowColors(True)
        self._kwic_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._kwic_table.cellDoubleClicked.connect(self._on_kwic_click)
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

        for i, r in enumerate(results):
            self._kwic_table.setItem(i, 0, QTableWidgetItem(str(i+1)))
            # Find query position in source
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
            # Store full text
            self._kwic_table.item(i, 0).setData(Qt.UserRole, r)

    def _on_kwic_click(self, row, _):
        item = self._kwic_table.item(row, 0)
        if item:
            r = item.data(Qt.UserRole)
            self._detail_src.setPlainText(r["source_text"])
            self._detail_tgt.setPlainText(r["target_text"])

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

    def _on_import_tmx(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入 TMX", "", "TMX 文件 (*.tmx)")
        if not path:
            return
        try:
            from ruzh_translator.utils.tmx_parser import import_tmx_to_db
            entries = import_tmx_to_db(path, self._session)
            QMessageBox.information(self, "导入成功", f"已导入 {len(entries)} 条翻译记忆")
            self._refresh_tm()
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出检索结果", "concordance.xlsx", "Excel (*.xlsx)")
        if not path: return
        import openpyxl; wb = openpyxl.Workbook(); ws = wb.active; ws.title = "KWIC结果"
        for c, h in enumerate(["#","左上下文","关键词","右上下文","完整源语","目标语"],1): ws.cell(1,c,h)
        for r in range(self._kwic_table.rowCount()):
            item = self._kwic_table.item(r, 0)
            if item:
                data = item.data(Qt.UserRole)
                ws.cell(r+2,1,r+1)
                ws.cell(r+2,2,self._kwic_table.item(r,1).text() if self._kwic_table.item(r,1) else "")
                ws.cell(r+2,3,self._kwic_table.item(r,2).text() if self._kwic_table.item(r,2) else "")
                ws.cell(r+2,4,self._kwic_table.item(r,3).text() if self._kwic_table.item(r,3) else "")
                ws.cell(r+2,5,data["source_text"] if data else "")
                ws.cell(r+2,6,data["target_text"] if data else "")
        wb.save(path)
        QMessageBox.information(self, "导出成功", f"已导出到:\n{path}")
