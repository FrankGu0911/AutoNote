import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# API 设置 - 文本LLM
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")  # 自定义API端点
DEFAULT_API_BASE = OPENAI_API_BASE  # 默认API基础URL
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")

# API 设置 - 视觉语言模型
VL_MODEL = os.getenv("VL_MODEL", "qwen2.5-vl-72b")
VL_API_BASE = os.getenv("VL_API_BASE", OPENAI_API_BASE)  # 默认与OPENAI_API_BASE相同
VL_API_KEY = os.getenv("VL_API_KEY", OPENAI_API_KEY)  # 默认与OPENAI_API_KEY相同

# 笔记生成设置
DEFAULT_NOTE_STYLE = "detailed"  # 可选：'concise', 'detailed', 'academic'
HIGHLIGHT_KEYWORDS = True
MAX_TOKENS = 4000
TEMPERATURE = 0.3
DEFAULT_PROCESSING_MODE = "text"  # 可选：'text', 'vl'
DEFAULT_BATCH_SIZE = 3  # VL模式下的默认批处理页数

# 图像转换设置
IMAGE_DPI = int(os.getenv("IMAGE_DPI", "300"))
IMAGE_FORMAT = os.getenv("IMAGE_FORMAT", "png")
IMAGE_QUALITY = 95  # 仅适用于jpg格式
IMAGE_TEMP_DIR = "temp_images"

# 语言设置
DEFAULT_LANGUAGE = "zh"  # 中文

# 文件设置
DEFAULT_OUTPUT_DIR = "output" 