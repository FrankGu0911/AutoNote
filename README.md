# AutoNote - 课件笔记自动生成工具

## 项目概述

AutoNote是一个基于LangChain和大语言模型(LLM)的应用程序，能够自动读取PowerPoint课件或PDF文件并生成结构化的Markdown格式课堂笔记。该工具可以帮助学生和专业人士更高效地整理学习材料，突出重点内容，节省记笔记的时间。

## 实现思路

整体流程分为三个主要阶段：

1. **文件转换与解析**：将PPT或PDF转换为图像，保留原始布局和结构信息
2. **内容理解**：使用视觉语言模型（VL-LLM）理解文档图像内容
3. **笔记生成**：整合所有内容的理解，生成结构化笔记

## 技术栈

- Python 3.9+
- LangChain
- 大语言模型 (如OpenAI GPT-4或兼容API)
- 视觉语言模型 (如Qwen2.5-VL 72B)
- python-pptx (用于解析PPT文件)
- PyMuPDF (用于解析PDF文件和生成图像)
- Pillow (用于图像处理)
- Markdown

## 实现步骤

### 1. 环境设置

首先需要安装必要的依赖：

```bash
pip install -r requirements.txt
```

然后配置API设置：
1. 复制`.env.example`为`.env`
2. 填入你的API密钥和端点信息

### 2. 文件转换与解析模块

将PPT或PDF转换为高质量图像，保留其原始布局和结构：

- 根据文件类型选择合适的转换方法
- 将文档每一页渲染为高分辨率图像
- 保存图像和页面顺序信息
- 可选择性地提取部分文本数据作为辅助信息

### 3. 内容理解模块

使用视觉语言模型（VL-LLM）分析文档图像：

- 将多页图像批量发送给VL-LLM
- 使用专门设计的提示词告知页码顺序
- 让VL-LLM理解图像中的文本、布局、结构和视觉元素
- 提取主要概念、重点内容和关系

### 4. 笔记生成模块

整合VL-LLM的分析结果，生成最终的笔记：

- 创建整体结构和大纲
- 标记重点内容
- 添加章节和小节
- 生成Markdown格式的最终笔记

### 5. 优化和增强

- 添加自定义提示，控制笔记的风格和详细程度
- 实现关键词高亮
- 添加笔记模板选项（简洁版、详细版等）
- 支持多种语言

## 代码结构

```
AutoNote/
├── main.py               # 主程序入口
├── ppt_parser.py         # PPT解析模块
├── pdf_parser.py         # PDF解析模块
├── image_converter.py    # 文档转图像模块
├── vl_analyzer.py        # VL-LLM分析模块
├── content_analyzer.py   # 内容理解模块
├── note_generator.py     # 笔记生成模块
├── templates/            # 提示模板
│   ├── page_prompt.py
│   ├── vl_prompt.py      # VL-LLM提示模板
│   └── summary_prompt.py
├── utils/                # 工具函数
│   └── helpers.py
├── config.py             # 配置文件
└── requirements.txt      # 依赖列表
```

## VL-LLM模式的优势

使用视觉语言模型（VL-LLM）处理文档图像相比直接提取文本有以下优势：

1. **保留布局和结构信息**：文档的布局、格式和结构在转换为纯文本时往往会丢失，而这些信息对理解内容至关重要
2. **处理图表和图像**：VL-LLM能够理解幻灯片中的图表、图像及其与文本的关系
3. **理解空间关系**：能够理解文本块之间的空间关系，如标题、正文、注释等的位置
4. **识别重点标记**：可以识别出高亮、加粗等视觉强调手段
5. **处理复杂格式**：能够处理多栏布局、表格、侧边栏等复杂格式

## 使用方法

### 命令行使用

基本使用:
```bash
python main.py 你的课件.pptx --mode vl
```

或者处理PDF:
```bash
python main.py 你的资料.pdf --mode vl
```

高级选项:
```bash
python main.py 你的课件.pptx --mode vl -s academic -o 自定义文件名.md -m qwen2.5-vl-72b
```

参数说明:
- `--mode`: 处理模式，可选 `text`(默认)或`vl`(视觉语言模型)
- `-s`或`--style`: 设置笔记风格 (可选: concise, detailed, academic)
- `-o`或`--output`: 指定输出文件路径
- `-m`或`--model`: 指定使用的模型
- `--batch-size`: VL模式下的批处理页数 (默认: 3)

### 代码中使用

```python
from main import process_file

# 使用VL-LLM处理PPT/PDF文件
success = process_file(
    input_file="your_lecture.pptx",
    output_file="notes.md",
    style="detailed",
    model="qwen2.5-vl-72b",
    mode="vl",
    batch_size=3
)
```

## 自定义API端点

本项目支持使用OpenAI兼容的API端点。要配置自定义API端点：

1. 在`.env`文件中设置以下变量:
   ```
   OPENAI_API_KEY=your_api_key
   OPENAI_API_BASE=https://your-custom-endpoint.com/v1
   OPENAI_MODEL=your-model-name
   VL_MODEL=your-vl-model-name
   ```

2. 程序将自动使用这些设置连接到指定的API端点。

## 下一步计划

1. 支持更多文件格式和样式
2. 添加网页界面
3. 实现批量处理功能
4. 改进VL-LLM提示工程
5. 支持导出为其他格式（如PDF、HTML） 