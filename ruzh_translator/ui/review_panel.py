"""Review panel: proofreading interface with change tracking and comments."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QTextEdit,
    QSplitter,
    QMessageBox,
    QGroupBox,
    QTreeWidget,
    QTreeWidgetItem,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from ruzh_translator.models.base import get_session
from ruzh_translator.models.segment import AlignmentPair, Segment
from ruzh_translator.services.project_service import list_projects, update_project_status


class ReviewPanel(QWidget):
    """Review and proofreading panel."""

    def __init__(self, project_id: str = None):
        super().__init__()
        self._session = get_session()
        self._project_id = project_id
        self._pairs = []
        self._current_index = -1
        self._original_texts = {}  # pair_id -> original target text for change tracking
        self._setup_ui()

        if project_id:
            self._load_project(project_id)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Toolbar ──
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("项目:"))

        self._project_combo = QComboBox()
        self._project_combo.currentIndexChanged.connect(self._on_project_changed)
        self._refresh_projects()
        toolbar.addWidget(self._project_combo, 1)

        self._progress_label = QLabel("")
        toolbar.addWidget(self._progress_label)

        prev_btn = QPushButton("◀ 上句")
        prev_btn.clicked.connect(self._on_prev)
        toolbar.addWidget(prev_btn)

        next_btn = QPushButton("下句 ▶")
        next_btn.clicked.connect(self._on_next)
        toolbar.addWidget(next_btn)

        layout.addLayout(toolbar)

        # ── Main splitter ──
        splitter = QSplitter(Qt.Vertical)

        # Top: Source and Target comparison
        compare = QSplitter(Qt.Horizontal)

        src_group = QGroupBox("源语（俄语）")
        src_layout = QVBoxLayout(src_group)
        self._source_view = QTextEdit()
        self._source_view.setReadOnly(True)
        self._source_view.setFont(QFont("PingFang SC", 13))
        src_layout.addWidget(self._source_view)
        compare.addWidget(src_group)

        tgt_group = QGroupBox("译文（可修改）")
        tgt_layout = QVBoxLayout(tgt_group)
        self._target_edit = QTextEdit()
        self._target_edit.setFont(QFont("PingFang SC", 13))
        tgt_layout.addWidget(self._target_edit)

        self._original_label = QLabel("")
        self._original_label.setStyleSheet("color: gray; font-style: italic;")
        tgt_layout.addWidget(self._original_label)

        compare.addWidget(tgt_group)
        compare.setSizes([500, 500])
        splitter.addWidget(compare)

        # Bottom: Comments and actions
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)

        comment_layout = QHBoxLayout()
        comment_layout.addWidget(QLabel("审校意见:"))
        self._comment_edit = QTextEdit()
        self._comment_edit.setMaximumHeight(60)
        self._comment_edit.setPlaceholderText("在此输入审校意见...")
        comment_layout.addWidget(self._comment_edit)
        bottom_layout.addLayout(comment_layout)

        actions = QHBoxLayout()

        approve_btn = QPushButton("✅ 批准")
        approve_btn.clicked.connect(lambda: self._set_status("approved"))
        approve_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        actions.addWidget(approve_btn)

        reject_btn = QPushButton("❌ 退回修改")
        reject_btn.clicked.connect(lambda: self._set_status("draft"))
        reject_btn.setStyleSheet("background-color: #F44336; color: white;")
        actions.addWidget(reject_btn)

        mark_reviewed_btn = QPushButton("✓ 标记已审")
        mark_reviewed_btn.clicked.connect(lambda: self._set_status("reviewed"))
        actions.addWidget(mark_reviewed_btn)

        actions.addStretch()

        bulk_approve_btn = QPushButton("⭐ 全部批准")
        bulk_approve_btn.clicked.connect(self._on_bulk_approve)
        bulk_approve_btn.setStyleSheet("background-color: #2196F3; color: white;")
        actions.addWidget(bulk_approve_btn)

        bottom_layout.addLayout(actions)
        splitter.addWidget(bottom)
        splitter.setSizes([500, 200])

        layout.addWidget(splitter)

    def _refresh_projects(self):
        """Refresh the project combo box."""
        self._project_combo.clear()
        self._project_combo.addItem("-- 选择项目 --", None)
        for p in list_projects(self._session):
            self._project_combo.addItem(p.name, p.id)
        if self._project_id:
            for i in range(self._project_combo.count()):
                if self._project_combo.itemData(i) == self._project_id:
                    self._project_combo.setCurrentIndex(i)
                    break

    def _on_project_changed(self):
        """Handle project selection."""
        pid = self._project_combo.currentData()
        if pid:
            self._load_project(pid)

    def _load_project(self, project_id: str):
        """Load project segments for review."""
        self._project_id = project_id

        self._pairs = (
            self._session.query(AlignmentPair)
            .filter(
                AlignmentPair.project_id == project_id,
                AlignmentPair.target_text != "",
            )
            .order_by(AlignmentPair.paragraph_index, AlignmentPair.pair_index)
            .all()
        )

        # Store original texts for change tracking
        self._original_texts = {
            p.id: p.target_text or "" for p in self._pairs
        }

        if self._pairs:
            self._navigate_to(0)

        self._update_progress_label()

    def _navigate_to(self, index: int):
        """Navigate to a specific segment."""
        if index < 0 or index >= len(self._pairs):
            return

        self._current_index = index
        pair = self._pairs[index]

        self._source_view.setPlainText(pair.source_text or "")
        self._target_edit.setPlainText(pair.target_text or "")

        # Show original if changed
        original = self._original_texts.get(pair.id, "")
        if original != (pair.target_text or ""):
            self._original_label.setText(f"原始翻译: {original[:100]}...")
        else:
            self._original_label.setText("")

        # Load existing comment
        seg = self._session.query(Segment).filter(Segment.id == pair.source_segment_id).first()
        if seg and seg.reviewer_comment:
            self._comment_edit.setPlainText(seg.reviewer_comment)
        else:
            self._comment_edit.clear()

    def _on_prev(self):
        if self._current_index > 0:
            self._save_current()
            self._navigate_to(self._current_index - 1)

    def _on_next(self):
        if self._current_index < len(self._pairs) - 1:
            self._save_current()
            self._navigate_to(self._current_index + 1)

    def _save_current(self):
        """Save current review state."""
        if self._current_index < 0:
            return

        pair = self._pairs[self._current_index]
        new_target = self._target_edit.toPlainText()

        if pair.target_text != new_target:
            pair.target_text = new_target
            pair.is_manually_corrected = True

        # Save comment
        seg = self._session.query(Segment).filter(
            Segment.id == pair.source_segment_id
        ).first()
        if seg:
            seg.reviewer_comment = self._comment_edit.toPlainText().strip()

        self._session.commit()

    def _set_status(self, status: str):
        """Set review status for the current segment."""
        self._save_current()
        if self._current_index < 0:
            return

        pair = self._pairs[self._current_index]
        seg = self._session.query(Segment).filter(
            Segment.id == pair.source_segment_id
        ).first()
        if seg:
            seg.status = status
            self._session.commit()

        self._update_progress_label()

    def _on_bulk_approve(self):
        """Approve all segments."""
        reply = QMessageBox.question(
            self,
            "全部批准",
            f"确定要批准全部 {len(self._pairs)} 个句段吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        for pair in self._pairs:
            seg = self._session.query(Segment).filter(
                Segment.id == pair.source_segment_id
            ).first()
            if seg:
                seg.status = "approved"
        self._session.commit()

        # Update project status
        update_project_status(self._session, self._project_id, "completed")
        self._update_progress_label()

        QMessageBox.information(self, "完成", "全部句段已批准，项目状态更新为「已完成」。")

    def _update_progress_label(self):
        """Update the progress display."""
        if not self._pairs:
            return

        approved = 0
        for pair in self._pairs:
            seg = self._session.query(Segment).filter(
                Segment.id == pair.source_segment_id
            ).first()
            if seg and seg.status == "approved":
                approved += 1

        self._progress_label.setText(
            f"已批准: {approved}/{len(self._pairs)} "
            f"({round(approved/len(self._pairs)*100)}%)"
        )
