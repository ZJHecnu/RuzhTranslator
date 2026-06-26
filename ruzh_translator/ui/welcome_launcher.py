"""Welcome launcher v4: Pure 4-card interface. Nothing else."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from ruzh_translator.config import APP_NAME, APP_VERSION

CARDS = [
    ("aligner",   "🔗", "语料对齐", "Aligner",
     "对齐俄中双语文本\nLaBSE 语义对齐\n连接线可视化校正\n导出 TMX / XLSX", "#FF9800"),
    ("translator","✏️", "翻译编辑", "Translator",
     "逐句翻译源语文档\n术语高亮 + TM 匹配\nAI / MT 翻译接口\n导出 XLSX / TMX / DOCX", "#4CAF50"),
    ("concordance","📊","平行语料", "Concordance",
     "KWIC 上下文检索\n翻译记忆库浏览\n频次统计与搭配\n导入 TMX / 导出结果", "#2196F3"),
    ("glossary",  "📖", "术语管理", "Glossary",
     "自动提取候选术语\nAI 智能翻译术语\n术语一致性检查\n辅助翻译模块", "#9C27B0"),
]


class WelcomeLauncher(QWidget):
    """Pure 4-card launcher. Click a card → open that module."""

    open_aligner = Signal()
    open_translator = Signal()
    open_concordance = Signal()
    open_glossary = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(700, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(16)

        # Title
        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #1565C0;")
        layout.addWidget(title)

        sub = QLabel("俄汉翻译流程管理软件 · 四大模块 · 文件互通")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 13px; color: #90A4AE;")
        layout.addWidget(sub)

        layout.addSpacing(8)

        # 2×2 Card Grid
        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        for i, (key, icon, name, eng, desc, color) in enumerate(CARDS):
            btn = QPushButton()
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setMinimumSize(260, 180)
            btn.setCursor(Qt.PointingHandCursor)

            text = f"<span style='font-size:36px;'>{icon}</span><br><br>" \
                   f"<span style='font-size:18px;font-weight:bold;'>{name}</span><br>" \
                   f"<span style='font-size:11px;color:#90A4AE;'>{eng}</span><br><br>" \
                   f"<span style='font-size:12px;color:#757575;'>{desc.replace(chr(10),'<br>')}</span>"
            btn.setText(text)

            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #FFFFFF;
                    border: 2px solid #E0E0E0;
                    border-radius: 16px;
                    text-align: left;
                    padding: 20px;
                }}
                QPushButton:hover {{
                    border-color: {color};
                    background: #FAFAFA;
                }}
                QPushButton:pressed {{
                    background: #F0F0F0;
                }}
            """)

            if key == "aligner":
                btn.clicked.connect(lambda: self.open_aligner.emit())
            elif key == "translator":
                btn.clicked.connect(lambda: self.open_translator.emit())
            elif key == "concordance":
                btn.clicked.connect(lambda: self.open_concordance.emit())
            elif key == "glossary":
                btn.clicked.connect(lambda: self.open_glossary.emit())

            grid.addWidget(btn, i // 2, i % 2)

        layout.addLayout(grid, 1)

        # Version
        ver = QLabel(f"v{APP_VERSION}")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color: #CFD8DC; font-size: 11px; margin-top: 4px;")
        layout.addWidget(ver)
