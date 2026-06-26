# Ruzh Translator — 俄汉翻译流程管理软件

俄语 ↔ 中文双向翻译全流程管理桌面应用，适用于 2-5 人小团队协作翻译。

## 功能概览

| 模块 | 功能 |
|------|------|
| 📊 项目管理 | 创建项目、进度追踪、状态仪表盘 |
| 📥 文档导入 | 支持 TXT/DOCX/PDF/RTF 格式导入 |
| 🔗 语料对齐 | 段落+句子两级对齐，LaBSE 语义对齐 + 匈牙利算法 |
| ✏️ 翻译编辑 | 三面板双语对照编辑，逐句翻译，键盘快捷键 |
| 💡 术语提示 | 翻译时自动识别源语术语，弹出翻译建议 |
| 🔍 术语提取 | 自动从语料中提取候选术语（pymorphy3 + jieba + YAKE） |
| 📖 术语库管理 | 术语 CRUD、Excel 导入导出、术语一致性检查 |
| ✂️ 任务切分 | 按段落智能切分，生成 .ruzh_task 分发包 |
| 🔀 任务合并 | 多人翻译结果合并，冲突检测与手动解决 |
| ✓ 审校 | 逐句审校、变更追踪、评论、批量批准 |
| 📤 多格式导出 | TMX / XLSX / DOCX / HTML / TXT |

## 安装和运行

### 环境要求

- Python 3.10+
- macOS / Windows / Linux

### 安装步骤

```bash
# 1. 进入项目目录
cd "篇章对比研究"

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r ruzh_translator/requirements.txt

# 4. 运行应用
python -m ruzh_translator.main
```

### 可选依赖

```bash
# 语义对齐需要（首次运行会自动下载 LaBSE 模型 ~1.8GB）
pip install sentence-transformers

# 俄语词形还原（术语提取）
pip install pymorphy3

# 中文分词（术语提取）
pip install jieba

# 关键词提取
pip install yake
```

## 项目结构

```
篇章对比研究/
├── ruzh_translator/          # 主应用包
│   ├── main.py               # 入口
│   ├── config.py             # 配置
│   ├── models/               # SQLAlchemy 数据模型
│   ├── services/             # 业务逻辑层
│   ├── ui/                   # PySide6 界面层
│   ├── utils/                # 工具函数
│   └── resources/            # 样式和图标
├── alligner.py               # [原有] 正则对齐脚本
├── alligner2.py              # [原有] LaBSE 对齐脚本
└── README.md
```

## 使用流程

### 典型工作流

```
1. 新建项目 → 设置语言对（俄→中 / 中→俄）
2. 导入文档 → 选择源语和目标语文件
3. 语料对齐 → 自动段落+句子对齐 → 手动校正低置信度句对
4. 术语提取 → 自动提取候选术语 → 审核并翻译术语
5. [可选] 任务切分 → 按段落切分 → 分发给翻译人员
6. 双语翻译 → 逐句翻译，术语提示辅助
7. [可选] 任务合并 → 合并多人翻译 → 解决冲突
8. 审校 → 逐句审校 → 全部批准
9. 导出 → TMX + XLSX + DOCX
```

### 团队协作模式

1. 项目负责人在共享文件夹（iCloud）中创建项目
2. 完成文档导入和对齐
3. 使用「任务切分」将项目切分为多个 .ruzh_task 文件
4. 将 .ruzh_task 文件分发给翻译人员
5. 翻译人员在各自电脑上打开 .ruzh_task 文件进行翻译
6. 翻译完成后将 .ruzh_task 文件返回
7. 负责人使用「任务合并」合并所有翻译结果
8. 解决冲突后进入审校阶段

## 数据存储

- **本地数据库**: `~/.ruzh_translation/ruzh_translator.db`（SQLite）
- **共享文件夹**: iCloud 目录下（TMX + JSON）
- **向量缓存**: `~/.ruzh_translation/embeddings/`

## 技术栈

- **GUI**: PySide6 (Qt 6)
- **数据库**: SQLite + SQLAlchemy ORM
- **对齐引擎**: LaBSE (Sentence-BERT)
- **术语提取**: pymorphy3 + jieba + YAKE
- **模糊匹配**: rapidfuzz
- **导出**: openpyxl / python-docx / lxml

## License

内部学术用途
