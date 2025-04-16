#!/usr/bin/env python
"""
智能图片处理器 - 评估图片与课程内容的相关性，确定合适的插入位置
"""

import os
import json
import re
from typing import Dict, List, Any, Tuple
import requests
from PIL import Image
import base64
import io
import config
from utils.helpers import ensure_directory_exists

class SmartImageProcessor:
    """
    智能图片处理器 - 使用VL模型分析图片并判断是否将其插入到笔记中
    """
    def __init__(self, model_name: str = None):
        """
        初始化智能图片处理器
        
        Args:
            model_name: 使用的视觉语言模型，默认使用配置中的VL模型
        """
        self.model_name = model_name or config.VL_MODEL
        self.api_key = config.VL_API_KEY
        self.api_base = config.VL_API_BASE
    
    def process_notes_with_images(self, notes_file: str, pages_data: List[Dict[str, Any]]) -> str:
        """
        处理笔记文件，评估并插入相关图片
        
        Args:
            notes_file: 笔记文件路径
            pages_data: 文档页面数据，包含图片信息
            
        Returns:
            str: 处理后的笔记内容
        """
        print("开始智能处理图片...")
        
        # 读取原始笔记内容
        with open(notes_file, 'r', encoding='utf-8') as f:
            notes_content = f.read()
        
        # 提取各级标题，用于定位插入位置
        headers = self._extract_headers(notes_content)
        print(f"从笔记中提取了 {len(headers)} 个标题")
        
        # 需要插入的图片列表，格式为[(位置索引, 标题, Markdown图片)]
        images_to_insert = []
        
        # 评估并处理每个页面的图片
        for page in pages_data:
            page_index = page.get("index", 0)
            page_content = page.get("analysis", "")
            page_title = page.get("title", f"页面 {page_index+1}")
            
            # 获取该页面的图片
            images = page.get("images", [])
            
            if not images or len(images) == 0:
                continue
                
            print(f"处理第 {page_index+1} 页的 {len(images)} 张图片")
            
            # 找到该页面对应的标题位置
            section_pos = self._find_section_for_page(headers, page_title, page_index)
            
            # 评估每张图片
            for img_index, img in enumerate(images):
                if not isinstance(img, dict) or "relative_path" not in img:
                    continue
                
                img_path = img.get("path", "")
                if not img_path or not os.path.exists(img_path):
                    # 尝试从相对路径构建完整路径
                    rel_path = img.get("relative_path", "")
                    # 假设工作目录是项目根目录
                    img_path = os.path.join(os.getcwd(), rel_path)
                    if not os.path.exists(img_path):
                        print(f"警告: 找不到图片 {rel_path}")
                        continue
                
                # 评估图片是否与内容相关
                relevance, description = self._evaluate_image_relevance(img_path, page_content, page_title)
                
                # 如果图片相关，加入待插入列表
                if relevance >= 0.6:  # 相关性阈值
                    relative_path = img.get("relative_path", "")
                    markdown_img = f"![{description}]({relative_path})\n\n"
                    
                    # 添加到待插入列表
                    images_to_insert.append((section_pos, page_title, markdown_img))
                    print(f"图片 {img_index+1} 将被插入到 '{page_title}' 章节，描述: {description}，相关性: {relevance:.2f}")
        
        # 对待插入图片按位置排序
        images_to_insert.sort(key=lambda x: x[0])
        
        # 创建新的笔记内容
        if images_to_insert:
            print(f"共有 {len(images_to_insert)} 张相关图片将被插入到笔记中")
            
            # 将笔记内容转换为列表进行处理
            lines = notes_content.split('\n')
            
            # 记录已插入的行号，避免在同一位置重复插入
            inserted_positions = set()
            insertion_count = 0
            
            # 插入图片
            for pos, title, img_markdown in images_to_insert:
                # 跳过重复的插入位置
                if pos in inserted_positions:
                    pos += 1  # 简单地移到下一行
                
                # 插入图片，确保换行
                if pos < len(lines):
                    # 确保前后都有空行
                    img_with_spacing = f"\n{img_markdown.strip()}\n"
                    lines.insert(pos, img_with_spacing)
                    inserted_positions.add(pos)
                    insertion_count += 1
            
            # 重新组合笔记内容
            new_content = '\n'.join(lines)
            
            # 写回文件
            with open(notes_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"智能图片处理完成，共插入 {insertion_count} 张相关图片")
            return new_content
        else:
            print("未找到相关图片，笔记保持不变")
            return notes_content
    
    def _extract_headers(self, text: str) -> List[Tuple[int, int, str]]:
        """
        从文本中提取所有标题
        
        Args:
            text: 笔记文本内容
            
        Returns:
            List[Tuple[int, int, str]]: 标题列表，每项包含(行号, 标题级别, 标题文本)
        """
        headers = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            # 匹配Markdown标题格式 (# 标题)
            match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if match:
                level = len(match.group(1))  # 标题级别
                title = match.group(2).strip()  # 标题文本
                headers.append((i, level, title))
        
        return headers
    
    def _find_section_for_page(self, headers: List[Tuple[int, int, str]], page_title: str, page_index: int) -> int:
        """
        为页面找到对应的章节位置
        
        Args:
            headers: 标题列表
            page_title: 页面标题
            page_index: 页面索引
            
        Returns:
            int: 插入位置（行号）
        """
        # 1. 尝试通过标题匹配
        for i, (line_num, level, title) in enumerate(headers):
            # 检查标题是否包含页面标题或页面索引
            if (page_title.lower() in title.lower() or 
                f"页面 {page_index+1}" in title or 
                f"第{page_index+1}页" in title or
                f"第 {page_index+1} 页" in title):
                
                # 如果找到匹配的标题，插入位置为下一个标题前或文件末尾
                if i < len(headers) - 1:
                    return headers[i+1][0]  # 返回下一个标题的行号
                else:
                    return line_num + 3  # 在当前标题后几行插入
        
        # 2. 如果没有匹配的标题，尝试根据页面索引估算位置
        # 假设页面按顺序对应章节
        if 0 <= page_index < len(headers):
            header_pos = headers[page_index][0]
            # 如果不是最后一个标题，返回下一个标题前
            if page_index < len(headers) - 1:
                return headers[page_index+1][0]
            else:
                return header_pos + 3  # 在当前标题后几行
        
        # 3. 兜底方案：第一个标题后或文件开头
        if headers:
            return headers[0][0] + 3
        
        return 0  # 文件开头
    
    def _resize_image_if_needed(self, img_path: str) -> str:
        """
        如果图片尺寸超过最大限制，调整图片大小以减少token消耗
        
        Args:
            img_path: 图片路径
            
        Returns:
            str: 调整大小后的图片路径（如果有调整）或原始路径
        """
        try:
            # 最大图像尺寸
            max_width = 1200  # 宽度最大限制
            max_height = 1200  # 高度最大限制
            
            # 打开图片
            with Image.open(img_path) as img:
                width, height = img.size
                
                # 检查是否需要调整大小
                if width > max_width or height > max_height:
                    # 计算调整比例
                    ratio = min(max_width / width, max_height / height)
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    
                    print(f"调整图片大小: {width}x{height} -> {new_width}x{new_height}")
                    
                    # 调整图像大小
                    resized_img = img.resize((new_width, new_height), Image.LANCZOS)
                    
                    # 创建临时文件路径
                    temp_dir = os.path.join(os.path.dirname(img_path), "temp")
                    ensure_directory_exists(temp_dir)
                    filename = os.path.basename(img_path)
                    resized_path = os.path.join(temp_dir, f"resized_{filename}")
                    
                    # 保存调整后的图片，优化质量
                    resized_img.save(resized_path, optimize=True, quality=90)
                    
                    print(f"图片已调整至 {new_width}x{new_height}")
                    return resized_path
                    
                # 不需要调整大小
                return img_path
                    
        except Exception as e:
            print(f"调整图片大小时出错: {e}")
        
        return img_path
    
    def _evaluate_image_relevance(self, img_path: str, page_content: str, page_title: str) -> Tuple[float, str]:
        """
        评估图片与内容的相关性，并生成描述
        
        Args:
            img_path: 图片路径
            page_content: 页面内容
            page_title: 页面标题
            
        Returns:
            Tuple[float, str]: (相关性分数, 图片描述)
        """
        try:
            # 调整图片大小（如果需要）
            sized_img_path = self._resize_image_if_needed(img_path)
            
            # 编码图片
            with open(sized_img_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 如果使用了临时调整大小的图片，并且与原始路径不同，删除临时文件
            if sized_img_path != img_path:
                try:
                    os.remove(sized_img_path)
                except:
                    pass
            
            # 准备提示词
            prompt = f"""
            分析这张图片，结合以下内容：
            
            页面标题: {page_title}
            
            页面内容：
            {page_content[:1000] if page_content else '(无内容)'}
            
            请评估:
            1. 这张图片与教学内容的相关性(0-1分)
            2. 简短描述这张图片(25字以内)
            
            按下面格式回答:
            相关性: [0-1之间的数字]
            描述: [图片描述]
            """
            
            # 调用VL API分析图片
            analysis = self._call_vl_api(prompt, encoded_image)
            
            # 从文本中提取信息
            relevance = 0.5  # 默认中等相关性
            description = "图表"  # 默认描述
            
            # 提取相关性
            relevance_match = re.search(r'相关性[：:]\s*(0\.\d+|1\.0|1)', analysis)
            if relevance_match:
                try:
                    relevance = float(relevance_match.group(1))
                except:
                    pass
            
            # 提取描述
            description_match = re.search(r'描述[：:]\s*([^\n]+)', analysis)
            if description_match:
                description = description_match.group(1).strip()
                # 限制描述长度
                if len(description) > 25:
                    description = description[:25] + "..."
            
            return relevance, description
            
        except Exception as e:
            print(f"评估图片时出错: {e}")
            return 0.1, "未知图片"
    
    def _call_vl_api(self, prompt: str, base64_image: str) -> str:
        """
        调用视觉语言模型API
        
        Args:
            prompt: 提示词
            base64_image: base64编码的图像
            
        Returns:
            str: API响应文本
        """
        try:
            # 准备消息
            messages = [
                {"role": "system", "content": "你是一个专业的教育内容图片分析助手，擅长判断图片与教学内容的相关性。"},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ]
            
            # 准备请求数据
            payload = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": 300,  # 降低token消耗
                "temperature": 0.3
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 发送请求
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload
            )
            
            # 解析响应
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                print(f"API请求失败: {response.status_code}")
                print(response.text)
                return """
                相关性: 0.1
                描述: 无法分析的图片
                """
            
        except Exception as e:
            print(f"调用VL API时出错: {e}")
            return """
            相关性: 0.1
            描述: 分析错误
            """

# 测试代码
if __name__ == "__main__":
    processor = SmartImageProcessor()
    # 测试处理图片
    print("初始化图片处理器成功") 