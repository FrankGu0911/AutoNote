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
                mode: str = None, batch_size: int = None) -> bool:
    """
    处理文件并生成笔记
    
    Args:
        input_file: 输入的文件路径
        output_file: 输出文件路径，如果为None则自动生成
        style: 笔记风格
        model: 使用的模型
        mode: 处理模式 ('text' 或 'vl')
        batch_size: VL模式下的批处理页数
        
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
        
        if mode == "vl":
            # 视觉语言模型处理流程
            return process_file_vl(
                input_file=input_file,
                output_file=output_file,
                style=style,
                model=model,
                batch_size=batch_size
            )
        else:
            # 文本处理流程
            return process_file_text(
                input_file=input_file,
                output_file=output_file,
                style=style,
                model=model
            )
            
    except Exception as e:
        print(f"错误: 处理文件时出错: {e}")
        return False

def process_file_text(input_file: str, output_file: str, 
                     style: str, model: str) -> bool:
    """
    使用文本模式处理文件
    
    Args:
        input_file: 输入的文件路径
        output_file: 输出文件路径
        style: 笔记风格
        model: 使用的LLM模型
        
    Returns:
        bool: 是否成功处理
    """
    try:
        # 根据文件类型选择解析器
        if is_ppt_file(input_file):
            print("1. 解析PPT文件...")
            parser = PPTParser()
        elif is_pdf_file(input_file):
            print("1. 解析PDF文件...")
            parser = PDFParser()
        
        slides = parser.process_file(input_file)
        
        if not slides:
            print("错误: 无法解析文件或文件不包含任何内容")
            return False
        
        print(f"   已解析 {len(slides)} 页内容")
        
        # 分析内容
        print("2. 分析内容...")
        analyzer = ContentAnalyzer(model_name=model)
        analyzed_slides = analyzer.analyze_presentation(slides)
        
        # 生成笔记
        print("3. 生成笔记...")
        generator = NoteGenerator(model_name=model, style=style)
        notes = generator.generate_notes(analyzed_slides)
        
        # 保存笔记
        print("4. 保存笔记...")
        success = generator.save_notes(notes, output_file)
        
        if success:
            print(f"处理完成! 笔记已保存到: {output_file}")
            return True
        else:
            print("错误: 保存笔记失败")
            return False
    
    except Exception as e:
        print(f"文本模式处理失败: {e}")
        return False

def process_file_vl(input_file: str, output_file: str, 
                   style: str, model: str, batch_size: int) -> bool:
    """
    使用视觉语言模型处理文件
    
    Args:
        input_file: 输入的文件路径
        output_file: 输出文件路径
        style: 笔记风格
        model: 使用的VL-LLM模型
        batch_size: 批处理页数
        
    Returns:
        bool: 是否成功处理
    """
    try:
        # 创建图像转换器
        converter = ImageConverter()
        
        # 1. 将文件转换为图像
        print("1. 将文件转换为图像...")
        pages_data = converter.convert_file_to_images(input_file)
        
        if not pages_data:
            print("错误: 无法将文件转换为图像")
            return False
        
        print(f"   已转换 {len(pages_data)} 页到图像")
        
        # 2. 使用VL-LLM分析图像
        print("2. 使用视觉语言模型分析内容...")
        analyzer = VLAnalyzer(model_name=model)
        analyzed_pages = analyzer.analyze_document(pages_data, batch_size=batch_size)
        
        # 3. 提取文档标题
        document_title = analyzed_pages[0]["title"] if analyzed_pages else "文档"
        
        # 4. 可选：生成整体摘要
        print("3. 生成文档摘要...")
        document_summary = analyzer.generate_document_summary(analyzed_pages, document_title)
        
        # 5. 生成笔记
        print("4. 整合笔记...")
        generator = NoteGenerator(model_name=config.DEFAULT_MODEL, style=style)
        notes = generator.generate_notes(analyzed_pages)
        
        # 6. 保存笔记
        print("5. 保存笔记...")
        success = generator.save_notes(notes, output_file)
        
        # 7. 清理临时图像文件
        converter.cleanup()
        
        if success:
            print(f"处理完成! 笔记已保存到: {output_file}")
            return True
        else:
            print("错误: 保存笔记失败")
            return False
    
    except Exception as e:
        print(f"视觉模式处理失败: {e}")
        return False

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
    
    return parser

def main():
    """主函数"""
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    # 验证必要的配置
    if not config.OPENAI_API_KEY:
        print("错误: 未设置API密钥。请在config.py中设置或添加OPENAI_API_KEY环境变量。")
        return 1
    
    # 如果是VL模式，检查VL API设置
    if args.mode == "vl" and not config.VL_API_KEY:
        print("错误: 未设置VL API密钥。请在config.py中设置或添加VL_API_KEY环境变量。")
        return 1
    
    # 处理文件
    success = process_file(
        input_file=args.input_file,
        output_file=args.output,
        style=args.style,
        model=args.model,
        mode=args.mode,
        batch_size=args.batch_size
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())