"""项目路径常量。

分层之后各模块的目录深度不同，如果每处都自己用 `Path(__file__)` 往上数，
很容易数错一级（配置、数据、评测集全会指到不存在的位置）。
所以统一在这里定义一次，其余模块一律 `from src.paths import ...`。
"""

from pathlib import Path

# 本文件位于 backend/src/paths.py，上溯两级即 backend/
BACKEND_ROOT = Path(__file__).resolve().parent.parent

# 运行期数据目录
DATA_DIR = BACKEND_ROOT / "data"

# 服务运行日志（启动时自动创建，已被 gitignore）
LOG_DIR = BACKEND_ROOT / "logs"

# 评测集与评测结果
EVAL_DATA_DIR = DATA_DIR / "evaluation"

# 知识库原始资源（已审核的 jsonl）
KB_DATA_DIR = DATA_DIR / "knowledge_base"
