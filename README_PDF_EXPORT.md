# Markdown笔记导出PDF功能

## 功能介绍

AutoNote现已支持将生成的Markdown格式笔记自动导出为PDF文件，方便用户打印或在不支持Markdown的设备上查看。

## 使用方法

### 1. 在生成笔记时同时导出PDF

在使用AutoNote生成笔记时，添加`--export-pdf`参数即可同时生成PDF版本：

```bash
python main.py 你的PPT或PDF文件.pptx --export-pdf
```

或

```bash
python main.py 你的PPT或PDF文件.pdf --export-pdf --include-images
```

生成的PDF文件将保存在与Markdown文件相同的目录下，文件名为原Markdown文件名加上`.pdf`后缀。

### 2. 将已有笔记转换为PDF

如果你已经有了Markdown格式的笔记，可以使用单独的转换工具将其转换为PDF：

```bash
python export_note_as_pdf.py 你的笔记文件.md
```

指定输出文件：

```bash
python export_note_as_pdf.py 你的笔记文件.md -o 输出文件.pdf
```

## 技术实现

PDF导出功能尝试使用以下四种方法进行转换，按优先级顺序：

1. **Pandoc**: 高质量的文档转换工具，支持几乎所有格式之间的转换
2. **WeasyPrint**: 基于HTML和CSS的PDF生成库，通过将Markdown转为HTML再生成PDF
3. **PyMuPDF**: 使用PyMuPDF库直接处理Markdown内容
4. **纯文本模式**: 最基本的文本转换方法，在其他方法都失败时使用

## 依赖安装

### 基本依赖

安装基本Python依赖：

```bash
pip install -r requirements.txt
```

### Pandoc安装

Pandoc是最高质量的转换工具，强烈建议安装：

- **Windows**: 
  1. 从[Pandoc官网](https://pandoc.org/installing.html)下载安装程序
  2. 运行安装程序并按照提示完成安装
  3. 重启终端或IDE

- **Linux**: 
  ```bash
  sudo apt-get install pandoc texlive-xetex texlive-lang-chinese
  ```

- **Mac**: 
  ```bash
  brew install pandoc
  ```

### WeasyPrint依赖 (Windows特别说明)

在Windows系统上，WeasyPrint需要GTK库：

1. 访问 [GTK for Windows Runtime Environment Installer](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases)
2. 下载并安装最新版本的GTK运行时环境 (例如 `gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe`)
3. 安装完成后**重启计算机**（重要！）
4. 安装后再次运行PDF导出功能

### 字体安装

为确保中文正确显示，建议安装以下字体：

- **Windows**: 通常已预装宋体(SimSun)、微软雅黑等中文字体
- **Linux**: 
  ```bash
  sudo apt-get install fonts-noto-cjk
  ```
- **Mac**: 
  ```bash
  brew install --cask font-noto-sans-cjk
  ```

## 常见问题

### 1. WeasyPrint错误: "cannot load library 'libgobject-2.0-0'"

这表示缺少GTK库：
- 按照上面的"WeasyPrint依赖"部分安装GTK
- 安装后重启计算机
- 如果仍然出错，尝试在环境变量中添加GTK的bin目录

### 2. PyMuPDF错误: "need font file or buffer"

这表示找不到合适的字体：
- Windows用户应已有内置字体，通常不会出现此错误
- Linux用户安装字体：`sudo apt-get install fonts-liberation`
- Mac用户安装字体：`brew install --cask font-liberation`

### 3. 所有方法都失败

如果以上所有方法都失败，程序会使用纯文本模式转换，这种模式生成的PDF格式非常简单，但至少能保证文本内容正确显示。

### 4. 其他常见问题

- **PDF中文字显示为方块或乱码**  
  请确保安装了中文字体，如宋体、思源黑体等。

- **图片无法显示**  
  确保Markdown文件中引用的图片路径正确，最好使用相对路径。

- **转换过程非常慢**  
  Pandoc转换大型文档可能需要较长时间，特别是包含复杂格式或大量图片时。 