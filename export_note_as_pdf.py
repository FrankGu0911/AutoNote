import os
import sys
import argparse
from md_to_pdf_converter import MarkdownToPdfConverter

def main():
    """
    将Markdown格式的笔记导出为PDF格式
    """
    parser = argparse.ArgumentParser(
        description="将Markdown笔记导出为PDF格式"
    )
    
    parser.add_argument(
        "markdown_file",
        help="输入的Markdown文件路径"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="输出PDF文件的路径（可选，默认为同名PDF文件）"
    )
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.markdown_file):
        print(f"错误: Markdown文件不存在: {args.markdown_file}")
        return 1
    
    # 开始转换
    print(f"正在将 {args.markdown_file} 转换为PDF...")
    converter = MarkdownToPdfConverter()
    pdf_file = converter.convert_md_to_pdf(args.markdown_file, args.output)
    
    if pdf_file:
        print(f"转换成功! PDF文件已保存为: {pdf_file}")
        return 0
    else:
        print("转换失败，请检查控制台输出以了解详细错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 