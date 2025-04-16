"""
辅助函数模块，提供各种工具函数
"""

import os
import re
from typing import List, Dict, Any

def ensure_directory_exists(directory_path: str) -> None:
    """
    确保指定的目录存在，如果不存在则创建
    
    Args:
        directory_path: 目录路径
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path, exist_ok=True)

def get_file_extension(file_path: str) -> str:
    """
    获取文件扩展名
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: 文件扩展名（小写）
    """
    _, ext = os.path.splitext(file_path)
    return ext.lower()

def is_ppt_file(file_path: str) -> bool:
    """
    检查文件是否是PPT文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        bool: 如果是PPT文件返回True
    """
    ext = get_file_extension(file_path)
    return ext in ['.ppt', '.pptx']

def is_pdf_file(file_path: str) -> bool:
    """
    检查文件是否是PDF文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        bool: 如果是PDF文件返回True
    """
    ext = get_file_extension(file_path)
    return ext == '.pdf'

def is_supported_file(file_path: str) -> bool:
    """
    检查文件是否是支持的文件格式（PPT或PDF）
    
    Args:
        file_path: 文件路径
        
    Returns:
        bool: 如果是支持的文件返回True
    """
    return is_ppt_file(file_path) or is_pdf_file(file_path)

def extract_keywords(text: str) -> List[str]:
    """
    从文本中提取关键词
    
    Args:
        text: 输入文本
        
    Returns:
        List[str]: 提取的关键词列表
    """
    # 简单实现：提取加粗内容作为关键词
    # 匹配**之间的内容
    bold_pattern = re.compile(r'\*\*(.*?)\*\*')
    bold_words = bold_pattern.findall(text)
    
    # 去除重复项并返回
    return list(set(bold_words))

def format_slide_reference(slide_data: Dict[str, Any]) -> str:
    """
    格式化幻灯片引用信息
    
    Args:
        slide_data: 幻灯片数据
        
    Returns:
        str: 格式化的引用信息
    """
    slide_index = slide_data["index"] + 1
    slide_title = slide_data["title"] or f"幻灯片 {slide_index}"
    return f"[幻灯片 {slide_index}: {slide_title}]" 