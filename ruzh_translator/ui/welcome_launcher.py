"""Welcome launcher v5: 4 reliable cards using proper QFrame subclass."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from ruzh_translator.config import APP_NAME, APP_VERSION


class CardFrame(QFrame):
    """A clickable card that works. Uses class-level mousePressEvent override."""
    clicked = Signal()

    def __init__(self, icon: str, title: str, eng: str, desc: str, color: str):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(240, 160)
        self._color = color
        self._hovered = False
        self.setStyleSheet(self._style(False))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(4)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 36px; border: none; background: transparent;")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #37474F; border: none; background: transparent;")
        layout.addWidget(title_lbl)

        eng_lbl = QLabel(eng)
        eng_lbl.setStyleSheet("font-size: 11px; color: #90A4AE; border: none; background: transparent;")
        layout.addWidget(eng_lbl)

        layout.addSpacing(8)

        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 12px; color: #757575; border: none; background: transparent;")
        layout.addWidget(desc_lbl)

        layout.addStretch()

    def _style(self, hovered: bool) -> str:
        color = self._color
        if hovered:
            return f"QFrame {{ background: #FFFFFF; border: 2px solid {color}; border-radius: 16px; }}"
        return "QFrame { background: #FFFFFF; border: 2px solid #E0E0E0; border-radius: 16px; }"

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self.setStyleSheet(self._style(True))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.setStyleSheet(self._style(False))
        super().leaveEvent(event)


CARDS = [
    ("🔗", "语料对齐", "Aligner", "对齐俄中双语文本\nLaBSE 语义对齐\n连接线可视化校正\n导出 TMX / XLSX", "#FF9800"),
    ("✏️", "翻译编辑", "Translator", "逐句翻译源语文档\n术语高亮 + TM 匹配\nAI / MT 翻译接口\n导出 XLSX / TMX / DOCX", "#4CAF50"),
    ("📊", "平行语料", "Concordance", "KWIC 上下文检索\n翻译记忆库浏览\n频次统计与搭配\n导入 TMX / 导出结果", "#2196F3"),
    ("📖", "术语管理", "Glossary", "自动提取候选术语\nAI 智能翻译术语\n术语一致性检查\n辅助翻译模块", "#9C27B0"),
]


class WelcomeLauncher(QWidget):
    """Pure 4-card launcher."""

    open_aligner = Signal()
    open_translator = Signal()
    open_concordance = Signal()
    open_glossary = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(680, 480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.setSpacing(12)

        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1565C0;")
        layout.addWidget(title)

        sub = QLabel("俄汉翻译流程管理软件 · 四大模块 · 文件互通")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 12px; color: #90A4AE;")
        layout.addWidget(sub)

        layout.addSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        signals = [self.open_aligner, self.open_translator,
                   self.open_concordance, self.open_glossary]

        for i, (icon, name, eng, desc, color) in enumerate(CARDS):
            card = CardFrame(icon, name, eng, desc, color)
            card.clicked.connect(signals[i].emit)
            grid.addWidget(card, i // 2, i % 2)

        layout.addLayout(grid, 1)

        ver = QLabel(f"v{APP_VERSION}")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color: #CFD8DC; font-size: 10px;")
        layout.addWidget(ver)
