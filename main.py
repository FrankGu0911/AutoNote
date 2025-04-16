import os
import sys
import argparse
from typing import Dict, List, Any
import config
from ppt_parser import PPTParser
from pdf_parser import PDFParser
from image_converter import ImageConverter
from content_analyzer import ContentAnalyzer
from vl_analyzer import VLAnalyzer
from note_generator import NoteGenerator
from smart_image_processor import SmartImageProcessor
from md_to_pdf_converter import MarkdownToPdfConverter
from utils.helpers import ensure_directory_exists, is_ppt_file, is_pdf_file, is_supported_file

def create_output_filename(input_file: str, output_dir: str) -> str:
    """
    根据输入文件名创建输出文件名
    
    Args:
        input_file: 输入的文件路径
        output_dir: 输出目录
        
    Returns:
        str: 输出文件路径
    """
    base_name = os.path.basename(input_file)
    file_name = os.path.splitext(base_name)[0]
    return os.path.join(output_dir, f"{file_name}_notes.md")

def process_file(input_file: str, output_file: str = None, 
                style: str = None, model: str = None, 
                mode: str = None, batch_size: int = None,
                include_images: bool = False, 
                include_full_pages: bool = False,
                export_pdf: bool = False) -> bool:
    """
    处理文件并生成笔记
    
    Args:
        input_file: 输入的文件路径
        output_file: 输出文件路径，如果为None则自动生成
        style: 笔记风格
        model: 使用的模型
        mode: 处理模式 ('text' 或 'vl')
        batch_size: VL模式下的批处理页数
        include_images: 是否在笔记中包含原始文档的图片
        include_full_pages: 是否在笔记中包含原始文档的整页图片
        export_pdf: 是否导出PDF版本的笔记
        
    Returns:
        bool: 是否成功处理
    """
    if not os.path.exists(input_file):
        print(f"错误: 文件不存在: {input_file}")
        return False
    
    if not is_supported_file(input_file):
        print(f"错误: 文件格式不支持: {input_file}. 仅支持.ppt、.pptx和.pdf文件")
        return False
    
    # 使用默认配置
    style = style or config.DEFAULT_NOTE_STYLE
    model = model or config.DEFAULT_MODEL
    mode = mode or config.DEFAULT_PROCESSING_MODE
    batch_size = batch_size or config.DEFAULT_BATCH_SIZE
    
    # 如果未指定输出文件，则生成默认的输出文件名
    if not output_file:
        output_dir = config.DEFAULT_OUTPUT_DIR
        ensure_directory_exists(output_dir)
        output_file = create_output_filename(input_file, output_dir)
    
    try:
        print(f"开始处理文件: {input_file}")
        print(f"模式: {mode}")
        
        success = False
        if mode == "vl":
            # 视觉语言模型处理流程
            success = process_file_vl(
                input_file=input_file,
                output_file=output_file,
                style=style,
                model=config.VL_MODEL,
                batch_size=batch_size,
                include_images=include_images,
                include_full_pages=include_full_pages
            )
        else:
            # 文本处理流程
            success = process_file_text(
                input_file=input_file,
                output_file=output_file,
                style=style,
                model=model,
                include_images=include_images,
                include_full_pages=include_full_pages
            )
            
        # 如果成功生成笔记且需要导出PDF
        if success and export_pdf and os.path.exists(output_file):
            print("正在将Markdown笔记导出为PDF格式...")
            pdf_converter = MarkdownToPdfConverter()
            pdf_file = pdf_converter.convert_md_to_pdf(output_file)
            if pdf_file:
                print(f"PDF文件已成功导出: {pdf_file}")
            else:
                print("PDF导出失败，请确保安装了所需的依赖")
        
        return success
            
    except Exception as e:
        print(f"错误: 处理文件时出错: {e}")
        return False

def process_file_text(input_file: str, output_file: str, 
                     style: str, model: str,
                     include_images: bool = False,
                     include_full_pages: bool = False) -> bool:
    """
    使用文本提取和分析处理文件
    
    Args:
        input_file: 输入的文件路径
        output_file: 输出文件路径
        style: 笔记风格
        model: 使用的LLM模型
        include_images: 是否在笔记中包含原始文档的图片
        include_full_pages: 是否在笔记中包含原始文档的整页图片
        
    Returns:
        bool: 是否成功处理
    """
    try:
        image_map = {}  # 用于存储提取的图片信息
        pages_with_images = []  # 用于存储页面完整图像
        
        # 1. 可选：准备图像（如果需要）
        if include_images or include_full_pages:
            print("1. 准备图像...")
            converter = ImageConverter()
            
            # 转换文件为图像
            pages_with_images = converter.convert_file_to_images(
                input_file, save_for_markdown=True
            )
            
            if not pages_with_images:
                print("警告: 无法创建文档图像，将仅处理文本内容。")
                include_images = False
                include_full_pages = False
            else:
                print(f"   已准备 {len(pages_with_images)} 页图像")
                
                # 创建页面索引到图片的映射
                for page in pages_with_images:
                    # 索引从0开始，但显示从1开始
                    page_index = page["index"]
                    if "images" in page and page["images"]:
                        image_map[page_index] = page["images"]
                
                # 如果需要包含整页图片，处理全页图像
                if include_full_pages:
                    # 创建文档特定的目录
                    base_name = os.path.basename(input_file)
                    doc_name = os.path.splitext(base_name)[0]
                    full_pages_dir = os.path.join(converter.images_dir, f"{doc_name}_fullpages")
                    ensure_directory_exists(full_pages_dir)
                    
                    # 保存每页的完整图像用于Markdown
                    for page in pages_with_images:
                        page_index = page["index"]
                        original_image_path = page["image_path"]
                        
                        # 创建全页图像的目标路径
                        full_page_name = f"fullpage_{page_index+1}.{converter.image_format}"
                        full_page_path = os.path.join(full_pages_dir, full_page_name)
                        
                        # 复制图像
                        import shutil
                        shutil.copy2(original_image_path, full_page_path)
                        
                        # 创建相对路径，用于Markdown引用
                        rel_path = os.path.join("images", f"{doc_name}_fullpages", full_page_name)
                        rel_path = rel_path.replace("\\", "/")
                        
                        # 添加到页面数据
                        page["full_page_image"] = {
                            "path": full_page_path,
                            "relative_path": rel_path
                        }
                    
                    print(f"   已准备 {len(pages_with_images)} 张全页图像")
                
                if include_images:
                    total_images = sum(len(images) for images in image_map.values())
                    print(f"   已提取 {total_images} 张图片用于笔记")
        
        # 根据文件类型选择解析器
        if is_ppt_file(input_file):
            print(f"{'2' if include_images or include_full_pages else '1'}. 解析PPT文件...")
            parser = PPTParser()
        elif is_pdf_file(input_file):
            print(f"{'2' if include_images or include_full_pages else '1'}. 解析PDF文件...")
            parser = PDFParser()
        
        slides = parser.process_file(input_file)
        
        if not slides:
            print("错误: 无法解析文件或文件不包含任何内容")
            return False
        
        print(f"   已解析 {len(slides)} 页内容")
        
        # 如果提取了图片，将图片信息添加到解析结果中
        if include_images or include_full_pages:
            for slide in slides:
                slide_index = slide["index"]
                # 添加内容图片
                if include_images and slide_index in image_map:
                    slide["extracted_images"] = image_map[slide_index]
                
                # 添加全页图片
                if include_full_pages:
                    for page in pages_with_images:
                        if page["index"] == slide_index and "full_page_image" in page:
                            slide["full_page_image"] = page["full_page_image"]
        
        # 分析内容
        print(f"{'3' if include_images or include_full_pages else '2'}. 分析内容...")
        analyzer = ContentAnalyzer(model_name=model)
        analyzed_slides = analyzer.analyze_presentation(slides, input_file=input_file)
        
        # 新方法: 先生成纯文本笔记，再处理图片
        
        # 生成纯文本笔记
        print(f"{'4' if include_images or include_full_pages else '3'}. 生成笔记...")
        generator = NoteGenerator(model_name=model, style=style)
        notes = generator.generate_notes(analyzed_slides, input_file=input_file)
        
        # 保存笔记
        success = generator.save_notes(notes, output_file)
        if not success:
            print("错误: 保存笔记失败")
            return False
        
        # 如果需要包含图片，使用智能图片处理器
        if (include_images or include_full_pages) and success:
            print("5. 智能处理图片...")
            # 准备图片数据
            pages_data = []
            
            for i, slide in enumerate(analyzed_slides):
                page_data = {
                    "index": slide["index"],
                    "title": slide["title"],
                    "analysis": slide["analysis"],
                    "images": [],
                    "full_page_image": None
                }
                
                # 添加内容图片
                if include_images and "extracted_images" in slides[i]:
                    page_data["images"] = slides[i]["extracted_images"]
                
                # 添加全页图片
                if include_full_pages and "full_page_image" in slides[i]:
                    page_data["full_page_image"] = slides[i]["full_page_image"]
                
                pages_data.append(page_data)
            
            # 使用智能图片处理器
            image_processor = SmartImageProcessor(model_name=config.VL_MODEL)
            image_processor.process_notes_with_images(output_file, pages_data)
        
        # 清理临时文件，但保留Markdown引用的图片
        if include_images or include_full_pages:
            converter.cleanup(keep_markdown_images=True)
        
        print(f"处理完成! 笔记已保存到: {output_file}")
        return True
    
    except Exception as e:
        print(f"文本模式处理失败: {e}")
        return False

def process_file_vl(input_file: str, output_file: str, 
                   style: str, model: str, batch_size: int,
                   include_images: bool = False,
                   include_full_pages: bool = False) -> bool:
    """
    使用视觉语言模型处理文件
    
    Args:
        input_file: 输入的文件路径
        output_file: 输出文件路径
        style: 笔记风格
        model: 使用的VL-LLM模型
        batch_size: 批处理页数
        include_images: 是否在笔记中包含原始文档的图片
        include_full_pages: 是否在笔记中包含原始文档的整页图片
        
    Returns:
        bool: 是否成功处理
    """
    try:
        # 创建图像转换器
        converter = ImageConverter()
        
        # 1. 将文件转换为图像
        print("1. 将文件转换为图像...")
        save_for_markdown = include_images or include_full_pages
        pages_data = converter.convert_file_to_images(input_file, save_for_markdown=save_for_markdown)
        
        if not pages_data:
            print("错误: 无法将文件转换为图像")
            return False
        
        print(f"   已转换 {len(pages_data)} 页到图像")
        
        # 处理全页图像
        if include_full_pages:
            # 创建文档特定的目录
            base_name = os.path.basename(input_file)
            doc_name = os.path.splitext(base_name)[0]
            full_pages_dir = os.path.join(converter.images_dir, f"{doc_name}_fullpages")
            ensure_directory_exists(full_pages_dir)
            
            # 保存每页的完整图像用于Markdown
            for page in pages_data:
                page_index = page["index"]
                original_image_path = page["image_path"]
                
                # 创建全页图像的目标路径
                full_page_name = f"fullpage_{page_index+1}.{converter.image_format}"
                full_page_path = os.path.join(full_pages_dir, full_page_name)
                
                # 复制图像
                import shutil
                shutil.copy2(original_image_path, full_page_path)
                
                # 创建相对路径，用于Markdown引用
                rel_path = os.path.join("images", f"{doc_name}_fullpages", full_page_name)
                rel_path = rel_path.replace("\\", "/")
                
                # 添加到页面数据
                page["full_page_image"] = {
                    "path": full_page_path,
                    "relative_path": rel_path
                }
            
            print(f"   已准备 {len(pages_data)} 张全页图像")
        
        if include_images:
            image_count = sum(len(page.get("images", [])) for page in pages_data)
            print(f"   已提取 {image_count} 张图片用于笔记")
        
        # 2. 使用VL-LLM分析图像
        print("2. 使用视觉语言模型分析内容...")
        analyzer = VLAnalyzer(model_name=model)
        # 传递input_file参数用于缓存
        analyzed_pages = analyzer.analyze_document(pages_data, batch_size=batch_size, input_file=input_file)
        
        # 3. 提取文档标题
        document_title = analyzed_pages[0]["title"] if analyzed_pages else "文档"
        
        # 4. 可选：生成整体摘要
        print("3. 生成文档摘要...")
        # 传递input_file参数用于缓存
        document_summary = analyzer.generate_document_summary(analyzed_pages, document_title, input_file=input_file)
        
        # 新方法: 分两步处理笔记生成和图片
        
        # 5. 先生成纯文本笔记
        print("4. 生成纯文本笔记...")
        # 从analyzed_pages中移除图片信息，仅保留分析结果
        text_only_pages = []
        for page in analyzed_pages:
            text_page = page.copy()
            # 删除图片相关字段，只保留文本分析结果
            if "images" in text_page:
                del text_page["images"]
            if "full_page_image" in text_page:
                del text_page["full_page_image"]
            text_only_pages.append(text_page)
        
        # 使用VL分析器生成纯文本笔记
        notes = analyzer.generate_notes(text_only_pages, output_file, style, False, input_file=input_file)
        
        # 6. 如需图片，使用智能图片处理器处理图片插入
        if (include_images or include_full_pages) and notes:
            print("5. 智能处理图片...")
            # 使用智能图片处理器
            image_processor = SmartImageProcessor(model_name=model)
            image_processor.process_notes_with_images(output_file, analyzed_pages)
        
        # 7. 清理临时图像文件，但保留Markdown引用的图片
        converter.cleanup(keep_markdown_images=(include_images or include_full_pages))
        
        print(f"处理完成! 笔记已保存到: {output_file}")
        return True
    
    except Exception as e:
        print(f"视觉模式处理失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return False

def process_full_page_references(notes: str, pages_data: List[Dict[str, Any]]) -> str:
    """
    处理笔记中的全页图像引用
    
    Args:
        notes: 笔记内容
        pages_data: 页面数据列表
        
    Returns:
        str: 处理后的笔记内容
    """
    import re
    
    # 定义全页图像占位符模式 
    # 格式为: {{{fullpage: page_X 描述}}}
    pattern = r"\{\{\{fullpage:([^}]*)\}\}\}"
    
    def replace_fullpage(match):
        placeholder = match.group(1).strip()
        parts = placeholder.split(" ", 1)
        
        if len(parts) == 0:
            return match.group(0)  # 保持原样
        
        # 解析页面标识符和描述
        page_id = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        
        # 尝试解析页面索引
        try:
            if page_id.startswith("page"):
                page_str = page_id.replace("page", "")
                page_index = int(page_str) - 1  # 转换为0索引
                
                # 查找对应页面
                for page in pages_data:
                    if page["index"] == page_index and "full_page_image" in page:
                        relative_path = page["full_page_image"]["relative_path"]
                        
                        if description:
                            return f"![{description}]({relative_path})"
                        else:
                            return f"![完整页面 {page_index+1}]({relative_path})"
        except:
            pass
        
        # 如果无法解析或找不到页面，保持原样
        return match.group(0)
    
    # 替换所有全页图像占位符
    processed_notes = re.sub(pattern, replace_fullpage, notes)
    
    return processed_notes

def setup_arg_parser() -> argparse.ArgumentParser:
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="AutoNote - 自动从PPT或PDF生成课堂笔记"
    )
    
    parser.add_argument(
        "input_file",
        help="输入的PPT或PDF文件路径"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="输出笔记文件的路径"
    )
    
    parser.add_argument(
        "-s", "--style",
        choices=["concise", "detailed", "academic"],
        default=config.DEFAULT_NOTE_STYLE,
        help="笔记的风格"
    )
    
    parser.add_argument(
        "-m", "--model",
        default=config.DEFAULT_MODEL,
        help="使用的模型"
    )
    
    parser.add_argument(
        "--mode",
        choices=["text", "vl"],
        default=config.DEFAULT_PROCESSING_MODE,
        help="处理模式: text(文本提取) 或 vl(视觉语言模型)"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=config.DEFAULT_BATCH_SIZE,
        help="VL模式下的批处理页数"
    )
    
    parser.add_argument(
        "--include-images",
        action="store_true",
        help="在生成的笔记中包含原始文档的图片"
    )
    
    parser.add_argument(
        "--include-full-pages",
        action="store_true",
        help="在生成的笔记中包含原始文档的完整页面图片"
    )
    
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="清除指定文件的缓存，如果不指定文件，则清除所有缓存"
    )
    
    parser.add_argument(
        "--export-pdf",
        action="store_true",
        help="将生成的Markdown笔记同时导出为PDF格式"
    )
    
    return parser

def main():
    """主函数"""
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    # 检查文件是否存在且格式支持
    if not os.path.exists(args.input_file):
        print(f"错误: 输入文件不存在: {args.input_file}")
        return
    
    if not is_supported_file(args.input_file):
        print(f"错误: 不支持的文件格式: {args.input_file}")
        return
    
    # 如果需要清除缓存
    if args.clear_cache:
        from utils.cache_manager import CacheManager
        cache_manager = CacheManager()
        
        if os.path.exists(args.input_file):
            # 清除特定文件的缓存
            cleared = cache_manager.clear_cache(file_path=args.input_file)
            print(f"已清除 {args.input_file} 的 {cleared} 条缓存记录")
        else:
            # 清除所有缓存
            cleared = cache_manager.clear_cache()
            print(f"已清除所有缓存，共 {cleared} 条记录")
        
        # 如果只是清除缓存，不生成笔记，直接返回
        if not hasattr(args, 'output') or not args.output:
            return
    
    # 处理输出文件路径
    output_file = args.output
    if not output_file:
        output_file = create_output_filename(args.input_file, config.DEFAULT_OUTPUT_DIR)
    
    # 处理文件
    success = process_file(
        args.input_file,
        output_file,
        args.style,
        args.model,
        args.mode,
        args.batch_size,
        args.include_images,
        args.include_full_pages,
        args.export_pdf
    )
    
    if not success:
        print(f"处理文件时出错: {args.input_file}")
        return

if __name__ == "__main__":
    sys.exit(main())