"""Translation editor: 3-panel bilingual translation interface.

Supports TWO modes:
1. Direct translation (from Segment records, no alignment needed)
2. Aligned translation (from AlignmentPair records)

Layout: Navigator | Source (read-only) | Target (editable) | Term hints (bottom)
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTextEdit,
    QPushButton,
    QLabel,
    QComboBox,
    QCheckBox,
    QMessageBox,
    QGroupBox,
    QTreeWidget,
    QTreeWidgetItem,
    QStatusBar,
    QProgressBar,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QSyntaxHighlighter

from ruzh_translator.models.base import get_session
from ruzh_translator.models.segment import AlignmentPair, Segment
from ruzh_translator.services.project_service import get_project, update_project_status


class TranslationEditor(QWidget):
    """Three-panel bilingual translation editor.

    Works with both Segment (direct translation) and AlignmentPair (aligned) data.
    """

    segment_changed = Signal(int)

    def __init__(self, project_id: str = None, main_window=None):
        super().__init__()
        self._session = get_session()
        self._project_id = project_id
        self._main_window = main_window
        self._segments = []     # Segment or AlignmentPair list
        self._is_aligned = False  # True if using AlignmentPairs
        self._current_index = -1
        self._setup_ui()

        if project_id:
            self._load_project(project_id)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Top bar ──
        top = QHBoxLayout()

        self._proj_label = QLabel("")
        self._proj_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1565C0;")
        top.addWidget(self._proj_label)

        top.addStretch()

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet("font-size: 14px; color: #616161;")
        top.addWidget(self._progress_label)

        top.addSpacing(20)

        self._auto_mark_cb = QCheckBox("切换时自动标记已译")
        self._auto_mark_cb.setChecked(True)
        self._auto_mark_cb.setToolTip("导航到下一句时，如果当前句子有译文，自动标记为「已翻译」")
        self._auto_mark_cb.setStyleSheet("color: #616161; font-size: 12px;")
        top.addWidget(self._auto_mark_cb)

        top.addSpacing(12)

        prev_btn = QPushButton("◀ 上句")
        prev_btn.clicked.connect(self._on_prev)
        prev_btn.setShortcut("Ctrl+Up")
        top.addWidget(prev_btn)

        self._pos_label = QLabel("0 / 0")
        self._pos_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self._pos_label.setFixedWidth(80)
        self._pos_label.setAlignment(Qt.AlignCenter)
        top.addWidget(self._pos_label)

        next_btn = QPushButton("下句 ▶")
        next_btn.clicked.connect(self._on_next)
        next_btn.setShortcut("Ctrl+Down")
        top.addWidget(next_btn)

        top.addSpacing(12)
        save_btn = QPushButton("💾 保存")
        save_btn.clicked.connect(self._on_save)
        save_btn.setShortcut("Ctrl+S")
        top.addWidget(save_btn)

        layout.addLayout(top)

        # ── 3-Panel body ──
        splitter = QSplitter(Qt.Horizontal)

        # Panel 1: Navigator
        nav_group = QGroupBox("句子列表")
        nav_layout = QVBoxLayout(nav_group)
        self._navigator = QTreeWidget()
        self._navigator.setHeaderLabels(["#", "预览"])
        self._navigator.setColumnWidth(0, 40)
        self._navigator.setMaximumWidth(280)
        self._navigator.currentItemChanged.connect(self._on_navigator_clicked)
        nav_layout.addWidget(self._navigator)
        splitter.addWidget(nav_group)

        # Panel 2: Source (read-only)
        src_group = QGroupBox("源语（俄语）")
        src_layout = QVBoxLayout(src_group)
        self._source_view = QTextEdit()
        self._source_view.setReadOnly(True)
        self._source_view.setFont(QFont("PingFang SC", 15))
        self._source_view.setStyleSheet(
            "QTextEdit { background-color: #FFFDE7; border: 1px solid #E0E0E0; }"
        )
        src_layout.addWidget(self._source_view)

        # Show existing target if aligned
        self._existing_target_label = QLabel("")
        self._existing_target_label.setStyleSheet("color: #9E9E9E; font-style: italic;")
        self._existing_target_label.setWordWrap(True)
        src_layout.addWidget(self._existing_target_label)

        splitter.addWidget(src_group)

        # Panel 3: Target (editable)
        tgt_group = QGroupBox("译文（中文）")
        tgt_layout = QVBoxLayout(tgt_group)
        self._target_edit = QTextEdit()
        self._target_edit.setFont(QFont("PingFang SC", 15))
        self._target_edit.setPlaceholderText("在此输入中文译文...")
        self._target_edit.setStyleSheet(
            "QTextEdit { border: 2px solid #2196F3; }"
        )
        tgt_layout.addWidget(self._target_edit)

        self._status_label = QLabel("状态: 未翻译")
        self._status_label.setStyleSheet("font-size: 13px; color: #9E9E9E;")
        tgt_layout.addWidget(self._status_label)

        splitter.addWidget(tgt_group)

        # Panel 4: TM matches (right side)
        tm_group = QGroupBox("📖 翻译记忆匹配")
        tm_layout = QVBoxLayout(tm_group)
        self._tm_list = QListWidget()
        self._tm_list.setStyleSheet(
            "QListWidget { border: none; } "
            "QListWidget::item { padding: 8px; border-bottom: 1px solid #EEE; } "
            "QListWidget::item:hover { background: #E8F5E9; }"
        )
        self._tm_list.itemDoubleClicked.connect(self._on_tm_insert)
        tm_layout.addWidget(self._tm_list)

        tm_search_layout = QHBoxLayout()
        self._tm_search_edit = QLabel("")
        self._tm_search_edit.setWordWrap(True)
        self._tm_search_edit.setStyleSheet("color: #9E9E9E; font-size: 11px;")
        tm_search_layout.addWidget(self._tm_search_edit)
        tm_layout.addLayout(tm_search_layout)

        splitter.addWidget(tm_group)

        splitter.setSizes([220, 400, 400, 200])
        layout.addWidget(splitter, 1)

        # ── Term Hint Panel ──
        hint_group = QGroupBox("💡 术语提示")
        hint_layout = QHBoxLayout(hint_group)
        self._hint_container = QWidget()
        self._hint_inner = QHBoxLayout(self._hint_container)
        self._hint_inner.setContentsMargins(4, 4, 4, 4)
        self._hint_inner.addStretch()
        hint_layout.addWidget(self._hint_container)
        layout.addWidget(hint_group)

        # ── Bottom action bar ──
        actions = QHBoxLayout()

        self._mark_draft_btn = QPushButton("📝 标记草稿")
        self._mark_draft_btn.clicked.connect(lambda: self._set_status("draft"))
        actions.addWidget(self._mark_draft_btn)

        self._mark_done_btn = QPushButton("✅ 标记已译")
        self._mark_done_btn.clicked.connect(lambda: self._set_status("translated"))
        self._mark_done_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; }"
        )
        actions.addWidget(self._mark_done_btn)

        actions.addStretch()

        tm_btn = QPushButton("📖 查找翻译记忆")
        tm_btn.clicked.connect(self._on_search_tm)
        actions.addWidget(tm_btn)

        term_btn = QPushButton("🔍 查看术语")
        term_btn.clicked.connect(self._on_show_terms)
        actions.addWidget(term_btn)

        layout.addLayout(actions)

    # ── Data Loading ──────────────────────────────────────────

    def _load_project(self, project_id: str):
        """Load project data. Try AlignmentPairs first, fall back to Segments."""
        self._project_id = project_id

        proj = get_project(self._session, project_id)
        if proj:
            self._proj_label.setText(f"📖 {proj.name}")

        # Try AlignmentPairs first
        pairs = (
            self._session.query(AlignmentPair)
            .filter(AlignmentPair.project_id == project_id)
            .order_by(AlignmentPair.paragraph_index, AlignmentPair.pair_index)
            .all()
        )

        if pairs:
            self._segments = pairs
            self._is_aligned = True
        else:
            # Fall back to direct Segments
            segs = (
                self._session.query(Segment)
                .filter(Segment.project_id == project_id)
                .order_by(Segment.paragraph_index, Segment.segment_index)
                .all()
            )
            self._segments = segs
            self._is_aligned = False

        # Build navigator tree
        self._navigator.clear()
        current_para = -1
        para_item = None

        status_icons = {
            "untranslated": "⬜",
            "draft": "📝",
            "translated": "✅",
            "reviewed": "✓",
            "approved": "⭐",
        }

        for i, item in enumerate(self._segments):
            para_idx = item.paragraph_index if item.paragraph_index is not None else 0

            if para_idx != current_para:
                current_para = para_idx
                para_item = QTreeWidgetItem(self._navigator)
                para_item.setText(0, f"段 {current_para + 1}")
                para_item.setText(1, "")
                para_item.setData(0, Qt.UserRole, -1)
                para_item.setExpanded(True)

            source_text = self._get_source_text(item)

            tree_item = QTreeWidgetItem(para_item)
            tree_item.setText(0, str(i + 1))
            preview = (source_text or "")[:30]
            status = getattr(item, "status", "untranslated") or "untranslated"
            icon = status_icons.get(status, "⬜")
            tree_item.setText(1, f"{icon} {preview}...")
            tree_item.setData(0, Qt.UserRole, i)

        # Navigate to first
        if self._segments:
            self._navigate_to(0)

        self._update_progress()

    def _get_source_text(self, item) -> str:
        """Get source text from Segment or AlignmentPair."""
        if isinstance(item, AlignmentPair):
            return item.source_text or ""
        elif isinstance(item, Segment):
            return item.source_text or ""
        return ""

    def _get_target_text(self, item) -> str:
        """Get target text from Segment or AlignmentPair."""
        if isinstance(item, AlignmentPair):
            return item.target_text or ""
        elif isinstance(item, Segment):
            return item.target_text or ""
        return ""

    def _set_target_text(self, item, text: str):
        """Set target text on Segment or AlignmentPair."""
        if isinstance(item, AlignmentPair):
            item.target_text = text
        elif isinstance(item, Segment):
            item.target_text = text

    # ── Navigation ────────────────────────────────────────────

    def _navigate_to(self, index: int):
        """Navigate to a specific segment."""
        if index < 0 or index >= len(self._segments):
            return

        # Auto-save previous + auto-mark if enabled
        if self._current_index >= 0 and self._current_index != index:
            self._save_current()
            # Auto-mark as translated if checkbox is on and target has content
            if self._auto_mark_cb.isChecked():
                prev_item = self._segments[self._current_index]
                if self._get_target_text(prev_item).strip():
                    prev_item.status = "translated"
                    self._session.commit()

        self._current_index = index
        item = self._segments[index]

        # Source text
        source_text = self._get_source_text(item)
        self._source_view.setPlainText(source_text)

        # Target text
        target_text = self._get_target_text(item)
        self._target_edit.setPlainText(target_text)

        # Show existing target if aligned and has one
        if self._is_aligned and isinstance(item, AlignmentPair):
            if item.target_text:
                self._existing_target_label.setText(f"已有译文: {item.target_text[:100]}...")
            else:
                self._existing_target_label.setText("")
        else:
            self._existing_target_label.setText("")

        # Position label
        self._pos_label.setText(f"{index + 1} / {len(self._segments)}")

        # Status
        status = getattr(item, "status", "untranslated") or "untranslated"
        status_map = {
            "untranslated": "状态: ⬜ 未翻译",
            "draft": "状态: 📝 草稿",
            "translated": "状态: ✅ 已翻译",
            "reviewed": "状态: ✓ 已审校",
            "approved": "状态: ⭐ 已批准",
        }
        self._status_label.setText(status_map.get(status, f"状态: {status}"))

        # Highlight current in navigator
        # Find the tree item with matching data
        for i in range(self._navigator.topLevelItemCount()):
            para = self._navigator.topLevelItem(i)
            for j in range(para.childCount()):
                child = para.child(j)
                if child.data(0, Qt.UserRole) == index:
                    self._navigator.setCurrentItem(child)
                    break

        # Refresh term hints + TM panel + term highlighting
        self._refresh_terms()
        self._refresh_tm_panel()
        self._highlight_source_terms()

        # Focus target editor
        self._target_edit.setFocus()

        self.segment_changed.emit(index)

    def _on_navigator_clicked(self, current, previous):
        """Handle click on navigator item."""
        if current is None:
            return
        index = current.data(0, Qt.UserRole)
        if index is not None and index >= 0:
            self._navigate_to(index)

    def _on_prev(self):
        if self._current_index > 0:
            self._navigate_to(self._current_index - 1)

    def _on_next(self):
        if self._current_index < len(self._segments) - 1:
            self._navigate_to(self._current_index + 1)

    # ── Save ──────────────────────────────────────────────────

    def _save_current(self):
        """Save current translation to database and TM."""
        if self._current_index < 0 or self._current_index >= len(self._segments):
            return

        item = self._segments[self._current_index]
        new_target = self._target_edit.toPlainText().strip()
        old_target = self._get_target_text(item)

        if new_target and new_target != old_target:
            self._set_target_text(item, new_target)
            item.is_manually_corrected = True

            # Auto set status
            if getattr(item, "status", "untranslated") in (None, "untranslated"):
                item.status = "draft"

            self._session.commit()

            # Add to TM
            source_text = self._get_source_text(item)
            try:
                from ruzh_translator.services.tm_service import add_tm_entry
                add_tm_entry(
                    self._session,
                    source_text,
                    new_target,
                    project_id=self._project_id,
                )
            except Exception:
                pass  # TM save is non-critical

            # Update navigator icon
            self._update_navigator_item(self._current_index, "draft")

    def _on_save(self):
        """Save button handler."""
        self._save_current()
        self._update_progress()
        if self._main_window:
            self._main_window.set_status("翻译已保存")

    def _set_status(self, status: str):
        """Set the translation status of the current segment."""
        self._save_current()
        if self._current_index < 0:
            return

        item = self._segments[self._current_index]
        item.status = status
        self._session.commit()

        status_map = {
            "draft": "状态: 📝 草稿",
            "translated": "状态: ✅ 已翻译",
            "reviewed": "状态: ✓ 已审校",
            "approved": "状态: ⭐ 已批准",
        }
        self._status_label.setText(status_map.get(status, f"状态: {status}"))
        self._update_navigator_item(self._current_index, status)
        self._update_progress()

    def _update_navigator_item(self, index: int, status: str):
        """Update the icon for a navigator item."""
        status_icons = {
            "untranslated": "⬜",
            "draft": "📝",
            "translated": "✅",
            "reviewed": "✓",
            "approved": "⭐",
        }
        icon = status_icons.get(status, "⬜")
        source_text = self._get_source_text(self._segments[index])

        for i in range(self._navigator.topLevelItemCount()):
            para = self._navigator.topLevelItem(i)
            for j in range(para.childCount()):
                child = para.child(j)
                if child.data(0, Qt.UserRole) == index:
                    child.setText(1, f"{icon} {(source_text or '')[:30]}...")
                    return

    # ── Progress ──────────────────────────────────────────────

    def _update_progress(self):
        """Update the progress label."""
        if not self._segments:
            self._progress_label.setText("无句子数据")
            return

        total = len(self._segments)
        translated = sum(
            1 for s in self._segments
            if getattr(s, "status", "untranslated") in ("translated", "reviewed", "approved")
        )
        reviewed = sum(
            1 for s in self._segments
            if getattr(s, "status", "untranslated") in ("reviewed", "approved")
        )

        # Also count segments with target text but no explicit status
        with_text = sum(
            1 for s in self._segments
            if self._get_target_text(s).strip()
        )

        self._progress_label.setText(
            f"已译: {max(translated, with_text)}/{total}  |  已审: {reviewed}/{total}"
        )

    # ── Term Hints ────────────────────────────────────────────

    def _refresh_terms(self):
        """Refresh term hint panel."""
        # Clear existing
        while self._hint_inner.count() > 1:
            item = self._hint_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._current_index < 0 or not self._project_id:
            return

        item = self._segments[self._current_index]
        source_text = self._get_source_text(item)
        if not source_text:
            return

        try:
            from ruzh_translator.services.term_hint_service import get_term_hints
            hints = get_term_hints(
                self._session,
                source_text,
                self._project_id,
            )

            for hint in hints[:8]:
                btn = QPushButton(f"{hint['source_term']} → {hint['target_term']}")
                btn.setToolTip(f"来源: {hint['source']} (置信度: {hint['score']:.0%})")
                btn.setStyleSheet(
                    "QPushButton { background-color: #E3F2FD; color: #1565C0; "
                    "border: 1px solid #90CAF9; border-radius: 12px; "
                    "padding: 4px 10px; font-size: 12px; } "
                    "QPushButton:hover { background-color: #BBDEFB; }"
                )
                btn.clicked.connect(
                    lambda checked, t=hint["target_term"]: self._insert_term(t)
                )
                self._hint_inner.insertWidget(self._hint_inner.count() - 1, btn)
        except Exception:
            pass  # Non-critical

    def _insert_term(self, term: str):
        """Insert term at cursor position."""
        cursor = self._target_edit.textCursor()
        cursor.insertText(term)
        self._target_edit.setFocus()

    def _refresh_tm_panel(self):
        """Refresh the persistent TM match panel."""
        self._tm_list.clear()
        self._tm_search_edit.setText("")

        if self._current_index < 0 or not self._project_id:
            return

        item = self._segments[self._current_index]
        source_text = self._get_source_text(item)
        if not source_text:
            return

        try:
            from ruzh_translator.services.tm_service import fuzzy_match
            results = fuzzy_match(
                self._session, source_text,
                threshold=0.55, limit=8,
            )
            for r in results:
                score_pct = int(r["score"] * 100)
                bar = "█" * (score_pct // 10) + "░" * (10 - score_pct // 10)
                preview = r["entry"].target_text[:80]
                display = f"{bar} {score_pct}%\n{preview}"
                tm_item = QListWidgetItem(display)
                tm_item.setData(Qt.UserRole, r["entry"].target_text)
                self._tm_list.addItem(tm_item)

            if not results:
                self._tm_search_edit.setText("未找到匹配的翻译记忆")
            else:
                self._tm_search_edit.setText(f"找到 {len(results)} 条匹配")
        except Exception:
            self._tm_search_edit.setText("TM 查询出错")

    def _on_tm_insert(self, item):
        """Insert a TM match into the target editor."""
        text = item.data(Qt.UserRole)
        if text:
            self._target_edit.setPlainText(text)

    def _highlight_source_terms(self):
        """Highlight glossary terms in the source text with blue underline."""
        if self._current_index < 0 or not self._project_id:
            return

        item = self._segments[self._current_index]
        source_text = self._get_source_text(item)
        if not source_text:
            return

        try:
            from ruzh_translator.models.glossary import GlossaryEntry
            entries = (
                self._session.query(GlossaryEntry)
                .filter(GlossaryEntry.project_id == self._project_id)
                .all()
            )

            # Reset formatting
            cursor = self._source_view.textCursor()
            cursor.select(QTextCursor.Document)
            fmt = QTextCharFormat()
            fmt.setUnderlineStyle(QTextCharFormat.NoUnderline)
            fmt.setForeground(QColor("#212121"))
            cursor.mergeCharFormat(fmt)

            # Highlight matched terms
            fmt_hl = QTextCharFormat()
            fmt_hl.setUnderlineStyle(QTextCharFormat.SingleUnderline)
            fmt_hl.setUnderlineColor(QColor("#1565C0"))
            fmt_hl.setForeground(QColor("#1565C0"))

            for entry in entries[:50]:
                if not entry.source_term:
                    continue
                term = entry.source_term
                pos = 0
                while True:
                    pos = source_text.lower().find(term.lower(), pos)
                    if pos < 0:
                        break
                    cursor = self._source_view.textCursor()
                    cursor.setPosition(pos)
                    cursor.setPosition(pos + len(term), QTextCursor.KeepAnchor)
                    cursor.mergeCharFormat(fmt_hl)
                    pos += len(term)
        except Exception:
            pass  # Non-critical

    # ── TM Search ─────────────────────────────────────────────

    def _on_search_tm(self):
        """Search translation memory."""
        if self._current_index < 0:
            return

        item = self._segments[self._current_index]
        source_text = self._get_source_text(item)
        if not source_text:
            return

        from ruzh_translator.services.tm_service import fuzzy_match
        results = fuzzy_match(self._session, source_text, threshold=0.6, limit=5)

        if not results:
            QMessageBox.information(self, "翻译记忆", "未找到相似翻译")
            return

        msg = "找到以下相似翻译:\n\n"
        for i, r in enumerate(results):
            preview = r["entry"].target_text[:120]
            msg += f"{i+1}. [匹配度: {r['score']:.0%}]\n{preview}\n\n"

        QMessageBox.information(self, "翻译记忆查询", msg)

    def _on_show_terms(self):
        """Show glossary terms for the current project."""
        if not self._project_id:
            return

        from ruzh_translator.models.glossary import GlossaryEntry
        entries = (
            self._session.query(GlossaryEntry)
            .filter(GlossaryEntry.project_id == self._project_id)
            .limit(100)
            .all()
        )

        if not entries:
            QMessageBox.information(self, "术语库", "该项目暂无术语条目。")
            return

        msg = f"项目术语 ({len(entries)} 条):\n\n"
        for e in entries[:40]:
            msg += f"• {e.source_term} → {e.target_term}\n"
        if len(entries) > 40:
            msg += f"\n... 还有 {len(entries) - 40} 条"

        QMessageBox.information(self, "项目术语", msg)
