"""Alignment editor: Abbyy Aligner-style dual-pane view.

Features:
- Left: source document sentences (scrollable list)
- Right: target document sentences (scrollable list)
- Connector lines between aligned pairs
- Confidence color bars (green/orange/red)
- Click to select pairs, right-click to split/merge
- Import files → auto-align → manual correction → save/export
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QGroupBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont, QPainterPath, QBrush,
)

from ruzh_translator.models.base import get_session
from ruzh_translator.models.segment import AlignmentPair, Segment
from ruzh_translator.services.alignment_service import align_documents, save_alignment_to_db
from ruzh_translator.services.import_service import import_file, import_and_segment
from ruzh_translator.services.project_service import (
    get_project, get_documents, list_projects, create_project, add_document, update_project_status,
)
from ruzh_translator.config import IMPORT_FORMATS


# ── Connector Line Widget ──────────────────────────────────────

class ConnectorWidget(QWidget):
    """Widget that draws connector lines between aligned source/target items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pairs = []  # [(src_y, tgt_y, confidence), ...]
        self._selected_idx = -1
        self._src_item_count = 0
        self._tgt_item_count = 0
        self.setFixedWidth(60)
        self.setMinimumHeight(100)

    def set_pairs(self, pairs_data: list, src_count: int, tgt_count: int):
        """Set alignment pairs for rendering.

        Args:
            pairs_data: List of (src_index, tgt_index, confidence) tuples.
            src_count: Total number of source items.
            tgt_count: Total number of target items.
        """
        self._pairs = pairs_data
        self._src_item_count = src_count
        self._tgt_item_count = tgt_count
        self.update()

    def set_selected(self, idx: int):
        self._selected_idx = idx
        self.update()

    def paintEvent(self, event):
        if not self._pairs or not self._src_item_count:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        h = self.height()
        src_h = h / max(self._src_item_count, 1)
        tgt_h = h / max(self._tgt_item_count, 1)

        for i, (src_idx, tgt_idx, conf) in enumerate(self._pairs):
            if conf < 0:
                continue  # Unaligned

            # Determine color
            if i == self._selected_idx:
                pen = QPen(QColor("#FF5722"), 3)
            elif conf > 0.8:
                pen = QPen(QColor("#4CAF50"), 2)
            elif conf > 0.5:
                pen = QPen(QColor("#FF9800"), 2)
            else:
                pen = QPen(QColor("#F44336"), 2)

            painter.setPen(pen)

            # Calculate Y positions
            src_y = int(src_h * (src_idx + 0.5))
            tgt_y = int(tgt_h * (tgt_idx + 0.5))

            # Draw bezier curve
            path = QPainterPath()
            start = QPoint(4, src_y)
            end = QPoint(self.width() - 4, tgt_y)
            ctrl1 = QPoint(self.width() * 0.4, src_y)
            ctrl2 = QPoint(self.width() * 0.6, tgt_y)
            path.moveTo(start)
            path.cubicTo(ctrl1, ctrl2, end)
            painter.drawPath(path)

            # Draw confidence badge
            mid_x = self.width() // 2
            mid_y = (src_y + tgt_y) // 2
            painter.setBrush(QBrush(pen.color()))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(mid_x, mid_y), 8, 8)
            painter.setPen(Qt.white)
            painter.setFont(QFont("sans-serif", 7))
            painter.drawText(QRect(mid_x - 8, mid_y - 6, 16, 12), Qt.AlignCenter,
                           f"{int(conf * 100)}")

        painter.end()


# ── Main Alignment Editor ───────────────────────────────────────

class AlignmentEditor(QWidget):
    """Abbyy-style alignment editor with dual sentence lists and connector lines."""

    alignment_done = Signal()

    def __init__(self, project_id: str = None, main_window=None):
        super().__init__()
        self._session = get_session()
        self._project_id = project_id
        self._main_window = main_window
        self._src_sentences = []  # list of source sentence texts
        self._tgt_sentences = []  # list of target sentence texts
        self._pairs_data = []     # [(src_idx, tgt_idx, confidence), ...]
        self._selected_pair = -1
        self._setup_ui()

        if project_id:
            self._load_project_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Top toolbar ──
        top = QHBoxLayout()

        top.addWidget(QLabel("<b>🔗 语料对齐</b>"))

        self._proj_combo = QComboBox()
        self._proj_combo.addItem("-- 选择项目或独立对齐 --", None)
        self._refresh_projects()
        self._proj_combo.currentIndexChanged.connect(self._on_project_changed)
        top.addWidget(self._proj_combo, 1)

        # Quick file buttons for standalone mode
        src_btn = QPushButton("📂 源语文件")
        src_btn.clicked.connect(self._on_browse_source)
        top.addWidget(src_btn)

        tgt_btn = QPushButton("📂 目标语文件")
        tgt_btn.clicked.connect(self._on_browse_target)
        top.addWidget(tgt_btn)

        top.addWidget(QLabel("方式:"))
        self._method_combo = QComboBox()
        self._method_combo.addItem("语义 (LaBSE)", "semantic")
        self._method_combo.addItem("顺序", "sequential")
        top.addWidget(self._method_combo)

        align_btn = QPushButton("🔗 开始对齐")
        align_btn.clicked.connect(self._on_align)
        align_btn.setStyleSheet("background: #FF9800; color: white; padding: 6px 16px;")
        top.addWidget(align_btn)

        layout.addLayout(top)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Three-pane body: Source | Connector | Target ──
        body = QHBoxLayout()
        body.setSpacing(0)

        # Source list
        src_group = QGroupBox("源语（俄语）")
        src_layout = QVBoxLayout(src_group)
        self._src_list = QListWidget()
        self._src_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._src_list.setStyleSheet(
            "QListWidget::item { padding: 8px; border-bottom: 1px solid #EEE; font-size: 13px; } "
            "QListWidget::item:selected { background: #E3F2FD; }"
        )
        self._src_list.currentRowChanged.connect(self._on_src_selected)
        src_layout.addWidget(self._src_list)
        body.addWidget(src_group, 4)

        # Connector lines
        self._connector = ConnectorWidget()
        body.addWidget(self._connector, 0)

        # Target list
        tgt_group = QGroupBox("目标语（中文）")
        tgt_layout = QVBoxLayout(tgt_group)
        self._tgt_list = QListWidget()
        self._tgt_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tgt_list.setStyleSheet(
            "QListWidget::item { padding: 8px; border-bottom: 1px solid #EEE; font-size: 13px; } "
            "QListWidget::item:selected { background: #FFF9C4; }"
        )
        self._tgt_list.currentRowChanged.connect(self._on_tgt_selected)
        tgt_layout.addWidget(self._tgt_list)
        body.addWidget(tgt_group, 4)

        # Sync scroll
        self._src_list.verticalScrollBar().valueChanged.connect(
            self._tgt_list.verticalScrollBar().setValue
        )
        self._tgt_list.verticalScrollBar().valueChanged.connect(
            self._src_list.verticalScrollBar().setValue
        )

        layout.addLayout(body, 1)

        # ── Bottom toolbar ──
        bottom = QHBoxLayout()

        split_btn = QPushButton("✂️ 拆分句子")
        split_btn.clicked.connect(self._on_split)
        split_btn.setToolTip("将选中的句子拆分为两句")
        bottom.addWidget(split_btn)

        merge_btn = QPushButton("🔗 合并到上一句")
        merge_btn.clicked.connect(self._on_merge)
        merge_btn.setToolTip("将选中句子与上一句合并")
        bottom.addWidget(merge_btn)

        unlink_btn = QPushButton("⚠️ 标记错配")
        unlink_btn.clicked.connect(self._on_mark_misaligned)
        bottom.addWidget(unlink_btn)

        relink_btn = QPushButton("🔗 重新连接")
        relink_btn.clicked.connect(self._on_relink)
        relink_btn.setToolTip("手动将当前源语句与当前目标语句连接")
        bottom.addWidget(relink_btn)

        bottom.addStretch()

        save_btn = QPushButton("💾 保存对齐")
        save_btn.clicked.connect(self._on_save_alignment)
        save_btn.setStyleSheet("background: #1565C0; color: white; padding: 8px 16px;")
        bottom.addWidget(save_btn)

        translate_btn = QPushButton("✏️ 继续翻译")
        translate_btn.clicked.connect(self._on_go_translate)
        translate_btn.setStyleSheet("background: #4CAF50; color: white; padding: 8px 16px;")
        bottom.addWidget(translate_btn)

        export_btn = QPushButton("📤 导出 XLSX")
        export_btn.clicked.connect(self._on_export)
        bottom.addWidget(export_btn)

        layout.addLayout(bottom)

        # Status label
        self._status_label = QLabel("请导入文件或选择项目，然后点击「开始对齐」")
        self._status_label.setStyleSheet("color: #9E9E9E; padding: 4px;")
        layout.addWidget(self._status_label)

    # ── Data loading ───────────────────────────────────────────

    def _refresh_projects(self):
        """Refresh project combo."""
        for p in list_projects(self._session):
            self._proj_combo.addItem(f"{p.name}", p.id)

    def _on_project_changed(self):
        """Load project data."""
        pid = self._proj_combo.currentData()
        if pid:
            self._project_id = pid
            self._load_project_data()

    def _load_project_data(self):
        """Load existing alignment data from a project."""
        pid = self._project_id
        if not pid:
            return

        # Try loading Segments first (from import or wizard)
        from ruzh_translator.models.segment import Segment
        segments = (
            self._session.query(Segment)
            .filter(Segment.project_id == pid)
            .order_by(Segment.paragraph_index, Segment.segment_index)
            .all()
        )

        if segments:
            # Separate source and target segments by language detection
            src_sents = []
            tgt_sents = []
            for seg in segments:
                text = (seg.source_text or "").strip()
                if not text:
                    continue
                # Detect language: Cyrillic = Russian, CJK = Chinese
                has_cyrillic = any(0x0400 <= ord(c) <= 0x04FF for c in text[:50])
                has_cjk = any(0x4E00 <= ord(c) <= 0x9FFF for c in text[:50])
                if has_cyrillic and not has_cjk:
                    src_sents.append(text)
                elif has_cjk and not has_cyrillic:
                    tgt_sents.append(text)
                elif seg.target_text and seg.target_text.strip():
                    # Has a translation — could be either
                    src_sents.append(text)
                    tgt_sents.append(seg.target_text.strip())
                else:
                    src_sents.append(text)

            self._src_sentences = src_sents
            self._tgt_sentences = tgt_sents
            self._populate_lists()
            self._status_label.setText(
                f"已加载 {len(src_sents)} 个源语句子 | {len(tgt_sents)} 个目标语句子"
                if tgt_sents else
                f"已加载 {len(src_sents)} 个源语句子 — 请导入目标语文件"
            )

        # Also try Documents
        docs = get_documents(self._session, pid)
        if len(docs) >= 2 and not self._src_sentences:
            # Use raw document content for display
            for doc in docs:
                sentences = doc.raw_content.replace('\r\n', '\n').split('\n')
                all_sents = []
                for line in sentences:
                    line = line.strip()
                    if line:
                        from ruzh_translator.utils.text_utils import split_sentences
                        all_sents.extend(split_sentences(line, doc.language or "ru"))
                if doc.language == "zh-CN" or (not self._tgt_sentences and self._src_sentences):
                    self._tgt_sentences = [s for s in all_sents if s]
                else:
                    self._src_sentences = [s for s in all_sents if s]
            self._populate_lists()

        # Try loading existing pairs
        pairs = (
            self._session.query(AlignmentPair)
            .filter(AlignmentPair.project_id == pid)
            .order_by(AlignmentPair.paragraph_index, AlignmentPair.pair_index)
            .all()
        )
        if pairs:
            self._pairs_data = []
            for p in pairs:
                # Find indices
                src_idx = self._find_index(self._src_sentences, p.source_text or "")
                tgt_idx = self._find_index(self._tgt_sentences, p.target_text or "")
                self._pairs_data.append((
                    src_idx if src_idx >= 0 else p.pair_index or 0,
                    tgt_idx if tgt_idx >= 0 else p.pair_index or 0,
                    p.confidence_score or 0.5,
                ))
            self._update_connector()
            self._status_label.setText(
                f"已加载 {len(self._pairs_data)} 个对齐对 | "
                f"源语 {len(self._src_sentences)} 句 | 目标语 {len(self._tgt_sentences)} 句"
            )

        # Empty state: no data loaded
        if not self._src_sentences and not self._tgt_sentences:
            self._status_label.setText(
                "📂 项目暂无数据。请点击上方按钮导入源语和目标语文件，然后点击「开始对齐」。"
            )
            self._status_label.setStyleSheet("color: #F44336; padding: 8px; font-weight: bold;")

    def _find_index(self, lst, text):
        """Find text in list, return index."""
        for i, item in enumerate(lst):
            if item.strip() == text.strip():
                return i
        return -1

    def _populate_lists(self):
        """Populate the two list widgets."""
        self._src_list.clear()
        for s in self._src_sentences:
            item = QListWidgetItem(s[:100])
            item.setToolTip(s)
            self._src_list.addItem(item)

        self._tgt_list.clear()
        for s in self._tgt_sentences:
            item = QListWidgetItem(s[:100])
            item.setToolTip(s)
            self._tgt_list.addItem(item)

    def _update_connector(self):
        """Update the connector widget."""
        self._connector.set_pairs(
            self._pairs_data,
            len(self._src_sentences),
            len(self._tgt_sentences),
        )

    # ── File import (standalone mode) ──────────────────────────

    def _on_browse_source(self):
        """Browse for source file (standalone mode)."""
        filters = ";;".join(f"{d} (*{e})" for e, d in IMPORT_FORMATS.items())
        path, _ = QFileDialog.getOpenFileName(self, "选择源语文件", "", filters)
        if not path:
            return

        data = import_file(path)
        from ruzh_translator.utils.text_utils import split_sentences
        lang = data["language"]
        all_sents = []
        for para in data["paragraphs"]:
            all_sents.extend(split_sentences(para, lang))
        self._src_sentences = [s.strip() for s in all_sents if s.strip()]
        self._populate_lists()
        self._status_label.setText(f"源语: {len(self._src_sentences)} 句 — 请导入目标语文件")

    def _on_browse_target(self):
        """Browse for target file (standalone mode)."""
        filters = ";;".join(f"{d} (*{e})" for e, d in IMPORT_FORMATS.items())
        path, _ = QFileDialog.getOpenFileName(self, "选择目标语文件", "", filters)
        if not path:
            return

        data = import_file(path)
        from ruzh_translator.utils.text_utils import split_sentences
        all_sents = []
        for para in data["paragraphs"]:
            all_sents.extend(split_sentences(para, "zh-CN"))
        self._tgt_sentences = [s.strip() for s in all_sents if s.strip()]
        self._populate_lists()
        self._status_label.setText(
            f"源语: {len(self._src_sentences)} 句 | 目标语: {len(self._tgt_sentences)} 句 — 请点击「开始对齐」"
        )

    # ── Alignment ──────────────────────────────────────────────

    def _on_align(self):
        """Run alignment."""
        if not self._src_sentences or not self._tgt_sentences:
            QMessageBox.warning(self, "提示", "请先导入源语和目标语文件")
            return

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

        try:
            method = self._method_combo.currentData()

            src_text = "\n\n".join(self._src_sentences)
            tgt_text = "\n\n".join(self._tgt_sentences)

            pairs_dicts = align_documents(
                src_text, tgt_text,
                src_lang="ru", tgt_lang="zh-CN",
                para_method=method, sent_method=method,
            )

            # Build pair indices from alignment results
            self._pairs_data = []
            for pd in pairs_dicts:
                src_idx = self._find_index(self._src_sentences, pd["source_text"])
                tgt_idx = self._find_index(self._tgt_sentences, pd["target_text"])
                if src_idx < 0:
                    # Try to find the sentence in its paragraph context
                    src_idx = pd.get("sent_index", len(self._pairs_data))
                if tgt_idx < 0:
                    tgt_idx = pd.get("sent_index", len(self._pairs_data))
                self._pairs_data.append((
                    min(src_idx, len(self._src_sentences) - 1) if src_idx >= 0 else pd.get("sent_index", 0),
                    min(tgt_idx, len(self._tgt_sentences) - 1) if tgt_idx >= 0 else pd.get("sent_index", 0),
                    pd["confidence"],
                ))

            self._update_connector()

            # Color-code the list items
            self._apply_confidence_colors()

            self._status_label.setText(
                f"对齐完成: {len(self._pairs_data)} 对 | "
                f"绿色({sum(1 for _,_,c in self._pairs_data if c > 0.8)}) | "
                f"橙色({sum(1 for _,_,c in self._pairs_data if 0.5 <= c <= 0.8)}) | "
                f"红色({sum(1 for _,_,c in self._pairs_data if c < 0.5)})"
            )

            QMessageBox.information(
                self, "对齐完成",
                f"共对齐 {len(self._pairs_data)} 个句子对。\n\n"
                f"🔴 低置信度 (<50%): 请重点检查\n"
                f"🟠 中置信度 (50-80%): 建议复查\n"
                f"🟢 高置信度 (>80%): 基本可信\n\n"
                f"可以手动调整对齐后保存。"
            )
            self.alignment_done.emit()

        except Exception as e:
            QMessageBox.critical(self, "对齐失败", str(e))
        finally:
            self._progress.setVisible(False)

    def _apply_confidence_colors(self):
        """Apply confidence-based background colors to list items."""
        # Mark which source items are aligned
        aligned_src = set()
        aligned_tgt = set()
        for src_idx, tgt_idx, conf in self._pairs_data:
            aligned_src.add(src_idx)
            aligned_tgt.add(tgt_idx)

            color = (
                QColor("#C8E6C9") if conf > 0.8 else
                QColor("#FFE0B2") if conf > 0.5 else
                QColor("#FFCDD2")
            )
            if src_idx < self._src_list.count():
                self._src_list.item(src_idx).setBackground(color)
            if tgt_idx < self._tgt_list.count():
                self._tgt_list.item(tgt_idx).setBackground(color)

        # Gray out unaligned items
        for i in range(self._src_list.count()):
            if i not in aligned_src:
                self._src_list.item(i).setForeground(QColor("#BDBDBD"))
        for i in range(self._tgt_list.count()):
            if i not in aligned_tgt:
                self._tgt_list.item(i).setForeground(QColor("#BDBDBD"))

    # ── Selection & Navigation ─────────────────────────────────

    def _on_src_selected(self, row: int):
        """Source item selected — find and highlight its pair."""
        # Find which pair contains this source
        for i, (src_idx, tgt_idx, conf) in enumerate(self._pairs_data):
            if src_idx == row:
                self._selected_pair = i
                self._connector.set_selected(i)
                # Also select the target
                self._tgt_list.blockSignals(True)
                self._tgt_list.setCurrentRow(min(tgt_idx, self._tgt_list.count() - 1))
                self._tgt_list.blockSignals(False)
                return

    def _on_tgt_selected(self, row: int):
        """Target item selected — find and highlight its pair."""
        for i, (src_idx, tgt_idx, conf) in enumerate(self._pairs_data):
            if tgt_idx == row:
                self._selected_pair = i
                self._connector.set_selected(i)
                self._src_list.blockSignals(True)
                self._src_list.setCurrentRow(min(src_idx, self._src_list.count() - 1))
                self._src_list.blockSignals(False)
                return

    # ── Manual Correction ──────────────────────────────────────

    def _on_split(self):
        """Split a sentence in the source list."""
        row = self._src_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先在源语列表中选中要拆分的句子")
            return

        text = self._src_sentences[row]
        # Simple split: try to find a natural break point
        mid = len(text) // 2
        # Find nearest punctuation
        for punct in [',', '，', ';', '；']:
            idx = text.rfind(punct, 0, mid + len(text) // 4)
            if idx > 0:
                mid = idx + 1
                break

        part1 = text[:mid].strip()
        part2 = text[mid:].strip()
        if not part1 or not part2:
            QMessageBox.warning(self, "提示", "无法自动拆分此句子，请手动编辑文本")
            return

        self._src_sentences[row] = part1
        self._src_sentences.insert(row + 1, part2)

        # Update pairs
        new_pairs = []
        for src_idx, tgt_idx, conf in self._pairs_data:
            if src_idx == row:
                new_pairs.append((src_idx, tgt_idx, conf))
                new_pairs.append((src_idx + 1, -1, 0.0))  # New sentence unaligned
            elif src_idx > row:
                new_pairs.append((src_idx + 1, tgt_idx, conf))
            else:
                new_pairs.append((src_idx, tgt_idx, conf))
        self._pairs_data = new_pairs

        self._populate_lists()
        self._apply_confidence_colors()
        self._update_connector()
        self._status_label.setText(f"已拆分句子 {row + 1}")

    def _on_merge(self):
        """Merge current item with the previous one."""
        row = self._src_list.currentRow()
        if row <= 0:
            return

        self._src_sentences[row - 1] += " " + self._src_sentences[row]
        self._src_sentences.pop(row)

        # Update pairs
        new_pairs = []
        for src_idx, tgt_idx, conf in self._pairs_data:
            if src_idx == row:
                continue  # Remove pair for merged sentence
            elif src_idx > row:
                new_pairs.append((src_idx - 1, tgt_idx, conf))
            else:
                new_pairs.append((src_idx, tgt_idx, conf))
        self._pairs_data = new_pairs

        self._populate_lists()
        self._apply_confidence_colors()
        self._update_connector()

    def _on_mark_misaligned(self):
        """Mark the selected pair as misaligned."""
        if self._selected_pair < 0:
            QMessageBox.warning(self, "提示", "请先点击选择一个对齐对")
            return

        src_idx, tgt_idx, _ = self._pairs_data[self._selected_pair]
        self._pairs_data[self._selected_pair] = (src_idx, tgt_idx, 0.0)
        self._apply_confidence_colors()
        self._update_connector()

    def _on_relink(self):
        """Manually link the currently selected source and target items."""
        src_row = self._src_list.currentRow()
        tgt_row = self._tgt_list.currentRow()
        if src_row < 0 or tgt_row < 0:
            QMessageBox.warning(self, "提示", "请分别在源语和目标语列表中选中要连接的句子")
            return

        # Check if either is already paired
        for i, (s, t, c) in enumerate(self._pairs_data):
            if s == src_row or t == tgt_row:
                self._pairs_data[i] = (src_row, tgt_row, 0.5)
                self._update_connector()
                self._apply_confidence_colors()
                return

        self._pairs_data.append((src_row, tgt_row, 0.5))
        self._update_connector()
        self._apply_confidence_colors()

    # ── Save & Export ──────────────────────────────────────────

    def _on_save_alignment(self):
        """Save alignment pairs to database."""
        if not self._pairs_data:
            QMessageBox.warning(self, "提示", "没有可保存的对齐数据")
            return

        # Ensure we have a project
        if not self._project_id:
            # Create a temporary project for standalone alignment
            proj_name = f"对齐_临时项目"
            proj = create_project(self._session, proj_name)
            self._project_id = proj.id
            self._proj_combo.addItem(proj.name, proj.id)
            self._proj_combo.setCurrentText(proj.name)

            # Save documents
            src_text = "\n\n".join(self._src_sentences)
            tgt_text = "\n\n".join(self._tgt_sentences)
            add_document(self._session, self._project_id, "source.txt", ".txt", src_text, "ru", len(self._src_sentences))
            add_document(self._session, self._project_id, "target.txt", ".txt", tgt_text, "zh-CN", len(self._tgt_sentences))

        # Clear old pairs
        self._session.query(AlignmentPair).filter(
            AlignmentPair.project_id == self._project_id
        ).delete()

        # Save new pairs
        pairs_to_save = []
        for i, (src_idx, tgt_idx, conf) in enumerate(self._pairs_data):
            pairs_to_save.append({
                "para_index": 0,
                "sent_index": i,
                "source_text": self._src_sentences[src_idx] if src_idx < len(self._src_sentences) else "",
                "target_text": self._tgt_sentences[tgt_idx] if tgt_idx < len(self._tgt_sentences) else "",
                "confidence": conf,
                "is_manually_corrected": conf < 0.8,
            })

        from ruzh_translator.services.alignment_service import save_alignment_to_db
        save_alignment_to_db(
            self._session, self._project_id,
            "",  # No specific document ID
            pairs_to_save,
        )

        # Update project status
        update_project_status(self._session, self._project_id, "alignment")

        QMessageBox.information(
            self, "保存成功",
            f"已保存 {len(pairs_to_save)} 个对齐对到项目。"
        )

    def _on_go_translate(self):
        """Navigate to translation editor."""
        if self._main_window:
            self._main_window.goto_translate()

    def _on_export(self):
        """Export alignment to XLSX."""
        if not self._pairs_data:
            QMessageBox.warning(self, "提示", "没有可导出的对齐数据")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出对齐结果", "aligned.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return

        pairs_for_export = [
            {
                "source_text": self._src_sentences[s] if s < len(self._src_sentences) else "",
                "target_text": self._tgt_sentences[t] if t < len(self._tgt_sentences) else "",
                "confidence_score": c,
                "paragraph_index": 0,
            }
            for s, t, c in self._pairs_data
        ]

        from ruzh_translator.services.export_service import export_to_xlsx
        export_to_xlsx(pairs_for_export, path)
        QMessageBox.information(self, "导出成功", f"已导出到:\n{path}")
