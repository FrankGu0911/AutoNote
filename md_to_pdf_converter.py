import os
import subprocess
import fitz  # PyMuPDF
from typing import Optional
import sys
import tempfile
from utils.helpers import ensure_directory_exists

class MarkdownToPdfConverter:
    """
    Markdown转PDF转换器，负责将Markdown文件转换为PDF格式
    """
    def __init__(self):
        """初始化转换器"""
        pass
    
    def convert_md_to_pdf(self, md_file_path: str, pdf_output_path: Optional[str] = None) -> Optional[str]:
        """
        将Markdown文件转换为PDF
        
        Args:
            md_file_path: Markdown文件路径
            pdf_output_path: 输出PDF文件路径，如果为None则自动生成
            
        Returns:
            str: 生成的PDF文件路径，转换失败则返回None
        """
        if not os.path.exists(md_file_path):
            print(f"错误: Markdown文件不存在: {md_file_path}")
            return None
            
        # 如果未指定输出路径，则自动生成
        if not pdf_output_path:
            base_name = os.path.basename(md_file_path)
            file_name = os.path.splitext(base_name)[0]
            output_dir = os.path.dirname(md_file_path)
            pdf_output_path = os.path.join(output_dir, f"{file_name}.pdf")
        
        # 确保输出目录存在
        ensure_directory_exists(os.path.dirname(pdf_output_path))
        
        # 尝试安装可能缺少的依赖
        self._check_and_install_missing_dependencies()
        
        # 尝试不同的转换方法
        if self._convert_with_pandoc(md_file_path, pdf_output_path):
            return pdf_output_path
        
        if self._convert_with_weasyprint(md_file_path, pdf_output_path):
            return pdf_output_path
        
        if self._convert_with_pymupdf(md_file_path, pdf_output_path):
            return pdf_output_path
        
        if self._convert_with_pure_text(md_file_path, pdf_output_path):
            return pdf_output_path
        
        print(f"无法将Markdown转换为PDF: {md_file_path}")
        return None
    
    def _check_and_install_missing_dependencies(self):
        """
        检查并尝试安装缺少的依赖
        """
        try:
            # 检查是否可以自动安装依赖
            import platform
            system = platform.system()
            
            # 检查是否有pip
            try:
                import pip
                can_install = True
            except ImportError:
                can_install = False
                print("无法自动安装依赖：未找到pip")
                return
            
            # 尝试导入必要的模块，如果不存在则安装
            try:
                import markdown
            except ImportError:
                if can_install:
                    print("正在安装缺少的依赖: markdown")
                    subprocess.run([sys.executable, "-m", "pip", "install", "markdown"], 
                                   capture_output=True, check=False)
            
            # 尝试导入WeasyPrint
            try:
                import weasyprint
            except ImportError:
                if can_install:
                    print("正在安装缺少的依赖: weasyprint")
                    # WeasyPrint在Windows上有额外依赖，所以给用户提示
                    if system == "Windows":
                        print("注意: WeasyPrint在Windows上需要额外安装GTK")
                        print("请访问: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows")
                    
                    subprocess.run([sys.executable, "-m", "pip", "install", "weasyprint"], 
                                   capture_output=True, check=False)
            
            # 检查是否有pandoc
            has_pandoc = False
            try:
                result = subprocess.run(["pandoc", "--version"], 
                                       capture_output=True, text=True, check=False)
                has_pandoc = result.returncode == 0
            except:
                has_pandoc = False
            
            if not has_pandoc:
                print("未检测到Pandoc。Pandoc提供最佳的Markdown到PDF转换效果。")
                if system == "Windows":
                    print("请从 https://pandoc.org/installing.html 下载安装")
                elif system == "Darwin":  # macOS
                    print("可以使用 'brew install pandoc' 安装")
                else:  # Linux
                    print("可以使用 'sudo apt-get install pandoc texlive-xelatex' 安装")
            
        except Exception as e:
            print(f"检查依赖时出错: {e}")
    
    def _convert_with_pandoc(self, md_file_path: str, pdf_output_path: str) -> bool:
        """
        使用pandoc转换Markdown为PDF
        
        Args:
            md_file_path: Markdown文件路径
            pdf_output_path: 输出PDF文件路径
            
        Returns:
            bool: 转换是否成功
        """
        try:
            print("尝试使用Pandoc转换Markdown为PDF...")
            
            # 检查系统平台
            import platform
            system = platform.system()
            
            # 定义命令参数
            cmd = ["pandoc", md_file_path, "-o", pdf_output_path, "--pdf-engine=xelatex", "-V", "CJKmainfont=SimSun"]
            
            # 在Windows上，手动处理编码问题
            if system == "Windows":
                import subprocess
                
                # 创建过程时指定编码为UTF-8
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                # 手动获取输出
                stdout, stderr = process.communicate()
                
                # 检查结果
                if process.returncode == 0 and os.path.exists(pdf_output_path):
                    print(f"已成功使用Pandoc将Markdown转换为PDF: {pdf_output_path}")
                    return True
                
                if stderr:
                    print(f"Pandoc转换错误: {stderr}")
                    if "xelatex" in stderr:
                        print("提示: 确保已安装LaTeX环境，如MiKTeX或TeX Live")
                    
            else:
                # 非Windows系统使用原始方法
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0 and os.path.exists(pdf_output_path):
                    print(f"已成功使用Pandoc将Markdown转换为PDF: {pdf_output_path}")
                    return True
                    
                if result.stderr:
                    print(f"Pandoc转换错误: {result.stderr}")
                
        except Exception as e:
            print(f"使用Pandoc转换失败: {e}")
            print("提示: 确认是否已正确安装Pandoc并添加到PATH中")
            
        return False
    
    def _convert_with_weasyprint(self, md_file_path: str, pdf_output_path: str) -> bool:
        """
        使用WeasyPrint转换Markdown为PDF
        
        Args:
            md_file_path: Markdown文件路径
            pdf_output_path: 输出PDF文件路径
            
        Returns:
            bool: 转换是否成功
        """
        try:
            print("尝试使用WeasyPrint转换Markdown为PDF...")
            # 检查系统平台
            import platform
            system = platform.system()
            
            if system == "Windows":
                print("检测到Windows系统，WeasyPrint可能需要额外安装GTK库")
                print("请访问: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows")
                print("安装提示: 安装GTK后，可能需要重启系统或IDE")
            
            # 先将Markdown转换为HTML
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False, encoding='utf-8', mode='w+') as tmp_html:
                tmp_html_path = tmp_html.name
            
            # 尝试使用markdown库转换为HTML
            try:
                import markdown
                with open(md_file_path, 'r', encoding='utf-8') as md_file:
                    md_content = md_file.read()
                    
                # 确定使用何种字体，优先选择系统可能有的中文字体
                default_font = "sans-serif"
                if system == "Windows":
                    font_options = "'Microsoft YaHei', 'SimSun', 'SimHei', 'Arial Unicode MS'"
                elif system == "Darwin":  # macOS
                    font_options = "'PingFang SC', 'Hiragino Sans GB', 'Heiti SC'"
                else:  # Linux等
                    font_options = "'Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'Droid Sans Fallback'"
                
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        @font-face {{
                            font-family: 'OpenSans';
                            src: local('Open Sans');
                        }}
                        body {{ 
                            font-family: {font_options}, {default_font};
                            margin: 2cm;
                            line-height: 1.5;
                        }}
                        pre {{ background-color: #f0f0f0; padding: 10px; overflow-x: auto; }}
                        img {{ max-width: 100%; }}
                        h1, h2, h3, h4, h5, h6 {{ margin-top: 1em; }}
                        table {{ border-collapse: collapse; width: 100%; }}
                        table, th, td {{ border: 1px solid #ddd; padding: 5px; }}
                        code {{ background-color: #f5f5f5; padding: 2px 4px; }}
                    </style>
                </head>
                <body>
                    {markdown.markdown(md_content, extensions=['tables', 'fenced_code', 'nl2br'])}
                </body>
                </html>
                """
                
                with open(tmp_html_path, 'w', encoding='utf-8') as html_file:
                    html_file.write(html_content)
                    
                # 使用WeasyPrint将HTML转换为PDF
                try:
                    from weasyprint import HTML
                    HTML(tmp_html_path).write_pdf(pdf_output_path)
                    
                    if os.path.exists(pdf_output_path):
                        print(f"已成功使用WeasyPrint将Markdown转换为PDF: {pdf_output_path}")
                        os.unlink(tmp_html_path)
                        return True
                except ImportError:
                    print("WeasyPrint未正确安装，请检查依赖")
                    print("Windows用户: 请确保已安装GTK")
                    print("Linux用户: 请确保已安装libffi-dev, libcairo2, libpango-1.0-0")
                except Exception as e:
                    if "libgobject" in str(e) or "gobject" in str(e).lower():
                        print("WeasyPrint缺少GTK依赖")
                        print("Windows用户: 请按照以下步骤安装GTK:")
                        print("1. 访问 https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases")
                        print("2. 下载并安装最新版本的GTK运行时")
                        print("3. 重启计算机后重试")
                    else:
                        print(f"WeasyPrint HTML渲染错误: {e}")
                
                try:
                    os.unlink(tmp_html_path)
                except:
                    pass
                    
            except Exception as e:
                print(f"WeasyPrint HTML渲染错误: {e}")
                try:
                    os.unlink(tmp_html_path)
                except:
                    pass
                
        except Exception as e:
            print(f"使用WeasyPrint转换失败: {e}")
            
        return False
    
    def _convert_with_pymupdf(self, md_file_path: str, pdf_output_path: str) -> bool:
        """
        使用PyMuPDF转换Markdown为PDF
        
        Args:
            md_file_path: Markdown文件路径
            pdf_output_path: 输出PDF文件路径
            
        Returns:
            bool: 转换是否成功
        """
        try:
            print("尝试使用PyMuPDF转换Markdown为PDF...")
            # 创建新的PDF文档
            doc = fitz.open()
            
            # 读取Markdown内容
            with open(md_file_path, 'r', encoding='utf-8') as md_file:
                md_content = md_file.read()
            
            # 检查内容是否包含中文
            has_chinese = False
            for char in md_content:
                if '\u4e00' <= char <= '\u9fff':
                    has_chinese = True
                    break
            
            # 设置页面大小为A4
            page_rect = fitz.paper_rect("a4")
            page_width, page_height = page_rect.width, page_rect.height
            
            # 页面边距
            margin = 72  # 1英寸边距
            
            # 确定字体
            import platform
            system = platform.system()
            
            font_name = "helv"  # 默认字体
            font_size = 11
            
            # 如果有中文内容，尝试更适合的字体
            if has_chinese and system == "Windows":
                # 按顺序尝试常见的中文字体
                for test_font in ["simsun", "simhei", "microsoft yahei", "simsun-extb", "nsimsun"]:
                    try:
                        # 创建测试页
                        test_page = doc.new_page()
                        # 尝试用该字体渲染中文
                        test_page.insert_text((50, 50), "测试中文", fontname=test_font)
                        # 如果成功，使用该字体
                        font_name = test_font
                        # 删除测试页
                        doc.delete_page(0)
                        break
                    except:
                        # 删除失败的测试页
                        if doc.page_count > 0:
                            doc.delete_page(0)
                        continue
            
            # 简单处理Markdown内容，提取标题和段落结构
            # 这个处理比纯文本方式要简单，主要是保留基本文档结构
            text_blocks = []
            current_block = []
            in_code_block = False
            
            for line in md_content.split("\n"):
                # 处理代码块
                if line.startswith("```"):
                    if in_code_block:
                        # 结束代码块
                        in_code_block = False
                        if current_block:
                            text_blocks.append("\n".join(current_block))
                            current_block = []
                    else:
                        # 开始代码块
                        in_code_block = True
                        if current_block:
                            text_blocks.append("\n".join(current_block))
                            current_block = []
                    continue
                
                # 在代码块内的内容
                if in_code_block:
                    current_block.append(line)
                    continue
                
                # 处理标题行
                if line.startswith("#"):
                    # 结束当前块
                    if current_block:
                        text_blocks.append("\n".join(current_block))
                        current_block = []
                    
                    # 添加标题作为新块
                    # 移除 # 符号
                    heading_level = 0
                    while heading_level < len(line) and line[heading_level] == '#':
                        heading_level += 1
                    
                    if heading_level <= 6:
                        heading_text = line[heading_level:].strip()
                        text_blocks.append(f"{'=' * (7-heading_level)} {heading_text}")
                    continue
                
                # 空行表示段落分隔
                if not line.strip():
                    if current_block:
                        text_blocks.append("\n".join(current_block))
                        current_block = []
                    continue
                
                # 添加到当前块
                current_block.append(line)
            
            # 确保最后一个块被添加
            if current_block:
                text_blocks.append("\n".join(current_block))
            
            # 页面布局参数
            y_pos = margin
            line_height = font_size * 1.5
            page = None
            
            # 遍历文本块渲染到PDF
            for block in text_blocks:
                # 估计块的高度
                lines_in_block = len(block.split("\n"))
                estimated_height = lines_in_block * line_height
                
                # 检查是否需要新页面
                if page is None or y_pos + estimated_height > page_height - margin:
                    page = doc.new_page(width=page_width, height=page_height)
                    y_pos = margin
                
                # 渲染文本块
                try:
                    page.insert_text(
                        fitz.Point(margin, y_pos), 
                        block, 
                        fontname=font_name,
                        fontsize=font_size
                    )
                except Exception as e:
                    print(f"PyMuPDF渲染错误: {e}")
                    # 如果指定字体失败，尝试不指定字体
                    try:
                        page.insert_text(
                            fitz.Point(margin, y_pos), 
                            block, 
                            fontsize=font_size
                        )
                    except:
                        # 最后尝试使用内置字体和ASCII文本
                        ascii_text = "".join(c if ord(c) < 128 else '?' for c in block)
                        page.insert_text(
                            fitz.Point(margin, y_pos), 
                            ascii_text, 
                            fontname="helv",
                            fontsize=font_size
                        )
                
                # 更新Y位置
                y_pos += estimated_height + line_height  # 块间额外间距
            
            # 保存PDF
            doc.save(pdf_output_path)
            doc.close()
            
            if os.path.exists(pdf_output_path):
                print(f"已使用PyMuPDF将Markdown转换为PDF: {pdf_output_path}")
                return True
                
        except Exception as e:
            print(f"使用PyMuPDF转换失败: {e}")
            
        return False
    
    def _convert_with_pure_text(self, md_file_path: str, pdf_output_path: str) -> bool:
        """
        使用最简单的纯文本方式转换Markdown为PDF
        无需额外依赖，应该在任何环境下都能工作
        
        Args:
            md_file_path: Markdown文件路径
            pdf_output_path: 输出PDF文件路径
            
        Returns:
            bool: 转换是否成功
        """
        try:
            print("尝试使用纯文本方式转换Markdown为PDF（最后的备选方案）...")
            
            # 读取Markdown内容
            with open(md_file_path, 'r', encoding='utf-8') as md_file:
                md_content = md_file.read()
            
            # 检查内容是否包含中文
            has_chinese = False
            for char in md_content:
                if '\u4e00' <= char <= '\u9fff':
                    has_chinese = True
                    break
            
            # 创建PDF文档
            doc = fitz.open()
            
            # 设置页面大小为A4
            page_rect = fitz.paper_rect("a4")
            page_width, page_height = page_rect.width, page_rect.height
            
            # 页面边距
            margin = 72  # 1英寸边距
            
            # 简单格式化Markdown文本
            lines = md_content.split('\n')
            formatted_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    formatted_lines.append("")
                    continue
                    
                # 移除Markdown标记
                # 标题
                if line.startswith('#'):
                    # 计算标题级别
                    level = 0
                    while level < len(line) and line[level] == '#':
                        level += 1
                    
                    if level <= 6:  # 标题级别不超过6
                        title_text = line[level:].strip()
                        formatted_lines.append(f"{'=' * (7-level)} {title_text} {'=' * (7-level)}")
                    else:
                        formatted_lines.append(line)
                # 列表项
                elif line.startswith('- ') or line.startswith('* '):
                    formatted_lines.append("• " + line[2:])
                # 数字列表
                elif len(line) > 2 and line[0].isdigit() and line[1] == '.' and line[2] == ' ':
                    formatted_lines.append(line)
                # 代码块
                elif line.startswith('```'):
                    formatted_lines.append("----- 代码块 -----")
                # 普通文本
                else:
                    formatted_lines.append(line)
            
            formatted_text = '\n'.join(formatted_lines)
            
            # 将文本分成多页
            # 估计每页能容纳的行数（简单估计）
            lines_per_page = 40
            all_lines = formatted_text.split('\n')
            
            # 确定字体和字号
            font_name = "helv"  # 默认使用内置Helvetica字体
            font_size = 11
            
            # 如果有中文内容，尝试使用更适合的字体
            if has_chinese:
                import platform
                system = platform.system()
                if system == "Windows":
                    # 尝试几种Windows可能有的中文字体
                    chinese_fonts = ["simsun", "simhei", "microsoft yahei", "simsun-extb"]
                    for font in chinese_fonts:
                        try:
                            # 测试是否能加载该字体
                            page = doc.new_page()
                            page.insert_text((50, 50), "测试中文", fontname=font)
                            doc.delete_page(0)  # 删除测试页
                            font_name = font
                            break
                        except:
                            continue
                    
                    # 如果没有合适的中文字体，警告用户
                    if font_name == "helv":
                        print("警告: 未找到支持中文的字体，中文可能无法正确显示")
            
            # 分页处理
            for i in range(0, len(all_lines), lines_per_page):
                page_lines = all_lines[i:i+lines_per_page]
                page_text = '\n'.join(page_lines)
                
                page = doc.new_page(width=page_width, height=page_height)
                
                try:
                    # 使用确定的字体
                    page.insert_text(
                        fitz.Point(margin, margin), 
                        page_text,
                        fontname=font_name,
                        fontsize=font_size
                    )
                except Exception as e:
                    print(f"插入文本时出错: {e}")
                    # 尝试不指定字体
                    try:
                        page.insert_text(
                            fitz.Point(margin, margin), 
                            page_text,
                            fontsize=font_size
                        )
                    except:
                        # 最后的尝试：使用内置字体和ASCII编码
                        try:
                            ascii_text = "".join(c if ord(c) < 128 else '?' for c in page_text)
                            page.insert_text(
                                fitz.Point(margin, margin), 
                                ascii_text,
                                fontname="helv",
                                fontsize=font_size
                            )
                        except:
                            print("无法使用任何字体渲染文本")
                            return False
            
            # 保存PDF
            doc.save(pdf_output_path)
            doc.close()
            
            if os.path.exists(pdf_output_path):
                print(f"已使用纯文本方式将Markdown转换为PDF: {pdf_output_path}")
                print("注意: 此方法生成的PDF格式非常简单，仅包含基本文本")
                return True
                
        except Exception as e:
            print(f"使用纯文本方式转换失败: {e}")
            
        return False 