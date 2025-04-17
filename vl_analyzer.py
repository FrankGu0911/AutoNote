import os
import base64
from typing import Dict, List, Any, Optional
import requests
import json
from PIL import Image
import io
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import config
from templates.vl_prompt import VL_SINGLE_PAGE_TEMPLATE, VL_BATCH_PAGES_TEMPLATE, VL_SUMMARY_TEMPLATE
from templates.summary_prompt import SUMMARY_TEMPLATE, SUMMARY_WITH_IMAGES_TEMPLATE, SUMMARY_WITH_FULL_PAGES_TEMPLATE, SUMMARY_WITH_ALL_IMAGES_TEMPLATE
from utils.helpers import ensure_directory_exists
from utils.cache_manager import CacheManager
import openai
from openai import OpenAI
import traceback

class VLAnalyzer:
    """
    视觉语言模型分析器类，负责使用VL-LLM分析文档图像
    """
    def __init__(self, model_name: str = None):
        """
        初始化VL分析器
        
        Args:
            model_name: 使用的视觉语言模型名称，默认使用配置中的模型
        """
        self.model_name = model_name or config.VL_MODEL
        self.api_key = config.VL_API_KEY
        self.api_base = config.VL_API_BASE
        self.batch_size = config.DEFAULT_BATCH_SIZE
        
        # 创建单页分析模板
        self.single_page_template = PromptTemplate(
            input_variables=["page_index", "page_title"],
            template=VL_SINGLE_PAGE_TEMPLATE
        )
        
        # 创建批量页面分析模板
        self.batch_pages_template = PromptTemplate(
            input_variables=["page_count", "pages_info", "page_indexes_placeholder", "page_titles_placeholder"],
            template=VL_BATCH_PAGES_TEMPLATE
        )
        
        # 创建摘要模板
        self.summary_template = PromptTemplate(
            input_variables=["document_title", "total_pages"],
            template=VL_SUMMARY_TEMPLATE
        )
        
        # 创建文档摘要模板
        self.document_summary_template = PromptTemplate(
            input_variables=["document_title", "total_pages", "page_analyses"],
            template=VL_SUMMARY_TEMPLATE
        )
        
        # 初始化缓存管理器
        self.cache_manager = CacheManager()
    
    def _encode_image(self, image_path: str) -> str:
        """
        将图像编码为base64格式
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            str: base64编码的图像字符串
        """
        try:
            # 首先检查图片大小并在需要时调整
            image_path = self._resize_image_if_needed(image_path)
            
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            return encoded_string
        except Exception as e:
            print(f"编码图像时出错: {e}")
            raise e
    
    def _resize_image_if_needed(self, image_path: str, max_size: int = 1200) -> str:
        """
        如果图像尺寸超过最大限制，调整图片大小以减少token消耗
        
        Args:
            image_path: 图像文件路径
            max_size: 最大允许的宽度和高度（像素）
            
        Returns:
            str: 调整大小后的图像路径或原始路径
        """
        try:
            # 打开图像并检查尺寸
            with Image.open(image_path) as img:
                width, height = img.size
                
                # 如果图像宽度或高度超过限制，则调整大小
                if width > max_size or height > max_size:
                    # 计算缩放比例
                    ratio = min(max_size / width, max_size / height)
                    
                    # 计算新尺寸
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    
                    print(f"调整图片大小: {width}x{height} -> {new_width}x{new_height}")
                    
                    # 调整图像大小
                    resized_img = img.resize((new_width, new_height), Image.LANCZOS)
                    
                    # 创建临时目录
                    temp_dir = os.path.join(os.path.dirname(os.path.abspath(image_path)), "temp")
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    # 创建新的文件路径
                    file_name = os.path.basename(image_path)
                    resized_path = os.path.join(temp_dir, f"resized_{file_name}")
                    
                    # 保存调整大小后的图像
                    resized_img.save(resized_path, optimize=True, quality=90)
                    
                    return resized_path
            
            # 如果不需要调整大小，则返回原始路径
            return image_path
        
        except Exception as e:
            print(f"调整图像大小时出错: {e}")
            # 出错时返回原始路径
            return image_path
    
    def analyze_single_page(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析单个页面图像
        
        Args:
            page_data: 包含页面数据的字典
            
        Returns:
            Dict: 包含分析结果的字典
        """
        try:
            page_index = page_data["index"] + 1
            page_title = page_data["title"]
            image_path = page_data["image_path"]
            
            # 调整图像大小（如果需要）
            sized_image_path = self._resize_image_if_needed(image_path)
            
            # 编码图像
            base64_image = self._encode_image(sized_image_path)
            
            # 准备提示词
            prompt = self.single_page_template.format(
                page_index=page_index,
                page_title=page_title
            )
            
            # 调用API
            response = self._call_vl_api(prompt, [base64_image])
            
            # 如果调整了图像大小，删除临时文件
            if sized_image_path != image_path:
                try:
                    os.remove(sized_image_path)
                except:
                    pass
            
            # 更新页面数据
            page_data["analysis"] = response
            
            return page_data
            
        except Exception as e:
            print(f"分析页面图像时出错: {e}")
            page_data["analysis"] = "分析失败"
            return page_data
    
    def analyze_batch_pages(self, pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量分析多个页面图像
        
        Args:
            pages_data: 包含多个页面数据的列表
            
        Returns:
            List[Dict]: 包含分析结果的页面数据列表
        """
        try:
            # 收集页面信息
            page_indexes = [p["index"] + 1 for p in pages_data]
            page_titles = [p["title"] for p in pages_data]
            
            # 准备页面信息文本
            pages_info = "\n".join([f"页面 {idx}: {title}" for idx, title in zip(page_indexes, page_titles)])
            
            # 调整图像大小并编码
            base64_images = []
            sized_paths = []
            
            for page in pages_data:
                image_path = page["image_path"]
                sized_path = self._resize_image_if_needed(image_path)
                sized_paths.append(sized_path)
                base64_images.append(self._encode_image(sized_path))
            
            # 准备提示词
            prompt = self.batch_pages_template.format(
                page_count=len(pages_data),
                pages_info=pages_info,
                page_indexes_placeholder=", ".join([str(idx) for idx in page_indexes]),
                page_titles_placeholder=", ".join(page_titles)
            )
            
            # 调用API
            response = self._call_vl_api(prompt, base64_images)
            
            # 清理调整大小的临时文件
            for i, sized_path in enumerate(sized_paths):
                if sized_path != pages_data[i]["image_path"]:
                    try:
                        os.remove(sized_path)
                    except:
                        pass
            
            # 尝试解析响应并分配给各个页面
            try:
                # 尝试按页面分割响应
                page_sections = self._split_response_by_pages(response, page_indexes)
                
                # 将各部分分配给对应页面
                for i, page in enumerate(pages_data):
                    if i < len(page_sections):
                        page["analysis"] = page_sections[i]
                    else:
                        page["analysis"] = "无法提取该页面的分析结果"
            except:
                # 如果无法分割，则将整个响应复制到所有页面
                for page in pages_data:
                    page["analysis"] = response
            
            return pages_data
            
        except Exception as e:
            print(f"批量分析页面图像时出错: {e}")
            for page in pages_data:
                page["analysis"] = "分析失败"
            return pages_data
    
    def _split_response_by_pages(self, response: str, page_indexes: List[int]) -> List[str]:
        """
        将响应按页面拆分
        
        Args:
            response: API响应文本
            page_indexes: 页面索引列表
            
        Returns:
            List[str]: 按页面拆分的响应
        """
        sections = []
        
        # 寻找页面标记
        for i, idx in enumerate(page_indexes):
            # 构建可能的页面标记模式
            patterns = [
                f"## 页面 {idx}",
                f"页面 {idx}",
                f"**页面 {idx}**",
                f"页面{idx}",
                f"第{idx}页"
            ]
            
            start_pos = -1
            
            # 查找当前页面的起始位置
            for pattern in patterns:
                pos = response.find(pattern)
                if pos != -1:
                    start_pos = pos
                    break
            
            # 查找下一页面的起始位置
            end_pos = len(response)
            if i < len(page_indexes) - 1:
                next_idx = page_indexes[i + 1]
                for pattern in [f"## 页面 {next_idx}", f"页面 {next_idx}", f"**页面 {next_idx}**", f"页面{next_idx}", f"第{next_idx}页"]:
                    pos = response.find(pattern)
                    if pos != -1:
                        end_pos = pos
                        break
            
            # 提取当前页面的内容
            if start_pos != -1:
                sections.append(response[start_pos:end_pos].strip())
            else:
                # 如果找不到页面标记，尝试均分响应
                section_length = len(response) // len(page_indexes)
                start = i * section_length
                end = (i + 1) * section_length if i < len(page_indexes) - 1 else len(response)
                sections.append(response[start:end].strip())
        
        return sections
    
    def _call_vl_api(self, prompt: str, base64_images: List[str]) -> str:
        """
        调用多模态API以分析图像
        
        Args:
            prompt: 提示词
            base64_images: base64编码图像列表
            
        Returns:
            str: API响应内容
        """
        try:
            # 准备消息内容
            content = [{"type": "text", "text": prompt}]
            
            # 添加图像到内容中
            for i, img in enumerate(base64_images):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img}"}
                })
            
            # 准备API请求数据
            data = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "system", 
                        "content": "你是一个专业的文档分析助手。分析图像中的内容并提供详细、准确的描述和摘要。"
                    },
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                "max_tokens": 4000,
                "temperature": 0.3
                # 移除 JSON 模式
            }
            
            # 发送API请求
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json=data
            )
            
            # 检查响应状态
            if response.status_code == 200:
                response_json = response.json()
                return response_json["choices"][0]["message"]["content"]
            else:
                print(f"API请求失败: 状态码 {response.status_code}")
                print(f"响应: {response.text}")
                return f"API请求失败: {response.status_code}\n{response.text}"
            
        except Exception as e:
            print(f"调用API时出错: {e}")
            return f"API请求错误: {str(e)}"
    
    def analyze_document(self, pages_data: List[Dict[str, Any]], batch_size: int = None, input_file: str = None) -> List[Dict[str, Any]]:
        """
        分析整个文档的所有页面
        
        Args:
            pages_data: 包含所有页面数据的列表
            batch_size: 批处理大小，默认使用配置中的值
            input_file: 输入文件路径，用于缓存
            
        Returns:
            List[Dict]: 包含分析结果的页面数据列表
        """
        batch_size = batch_size or self.batch_size
        
        # 检查是否有缓存
        cache_key = f"vl_analyze"
        if input_file and self.cache_manager.has_cache(input_file, cache_key, self.model_name):
            print(f"找到缓存的PPT图像分析结果，正在加载...")
            cached_data = self.cache_manager.load_cache(input_file, cache_key, self.model_name)
            
            # 将缓存数据与输入页面数据合并
            # 确保使用最新的metadata (如image_path)，但保留分析结果
            for i, page_data in enumerate(pages_data):
                if i < len(cached_data):
                    # 保留原始页面数据，但更新分析结果
                    page_data["analysis"] = cached_data[i]["analysis"]
            
            print(f"已从缓存加载 {len(cached_data)} 页PPT图像分析结果")
            return pages_data
        
        print(f"开始使用VL模型({self.model_name})分析PPT图像，共 {len(pages_data)} 页...")
        print(f"批处理大小: {batch_size}")
        
        analyzed_pages = []
        
        # 按批处理页面
        for i in range(0, len(pages_data), batch_size):
            batch = pages_data[i:i+batch_size]
            
            # 如果批次只有一页，使用单页分析
            if len(batch) == 1:
                analyzed_page = self.analyze_single_page(batch[0])
                analyzed_pages.append(analyzed_page)
                print(f"已分析第 {batch[0]['index']+1} 页（标题：{batch[0]['title'] or '无标题'}）")
            else:
                # 否则使用批量分析
                analyzed_batch = self.analyze_batch_pages(batch)
                analyzed_pages.extend(analyzed_batch)
                page_nums = [p["index"]+1 for p in batch]
                print(f"已分析第 {min(page_nums)} 到 {max(page_nums)} 页")
            
            # 每处理完一个批次就保存中间结果到缓存
            if input_file:
                cache_data = [
                    {"index": page["index"], "analysis": page.get("analysis", "")} 
                    for page in analyzed_pages
                ]
                
                # 检查是否已有之前保存的数据
                existing_data = []
                if self.cache_manager.has_cache(input_file, cache_key, self.model_name):
                    existing_data = self.cache_manager.load_cache(input_file, cache_key, self.model_name)
                
                # 合并已有数据和新数据
                merged_data = list(existing_data)  # 复制现有数据
                
                # 更新或添加新分析的页面
                for page in cache_data:
                    page_index = page["index"]
                    
                    # 检查页面是否已存在于现有数据中
                    found = False
                    for i, existing_page in enumerate(merged_data):
                        if existing_page["index"] == page_index:
                            merged_data[i] = page  # 更新现有项
                            found = True
                            break
                    
                    if not found:
                        merged_data.append(page)  # 添加新项
                
                # 按页面索引排序
                merged_data.sort(key=lambda x: x["index"])
                
                # 保存合并后的数据
                self.cache_manager.save_cache(input_file, cache_key, self.model_name, merged_data)
                print(f"已缓存当前分析进度：共 {len(merged_data)} 页")
        
        print(f"已完成全部 {len(analyzed_pages)} 页文档分析，结果已{'缓存' if input_file else '生成（未启用缓存）'}")
        
        return analyzed_pages
    
    def generate_document_summary(self, pages_data: List[Dict[str, Any]], document_title: str = None, input_file: str = None) -> str:
        """
        生成文档摘要
        
        Args:
            pages_data: 页面数据列表，包含分析结果
            document_title: 文档标题，如果未提供则使用默认标题
            input_file: 输入文件路径，用于缓存
            
        Returns:
            str: 生成的文档摘要
        """
        try:
            print(f"开始生成文档摘要，共 {len(pages_data)} 页...")
            
            # 获取已缓存的摘要，如果有
            cache_key = "document_summary"
            if input_file and self.cache_manager.has_cache(input_file, cache_key, self.model_name):
                print("找到缓存的文档摘要，正在加载...")
                return self.cache_manager.load_cache(input_file, cache_key, self.model_name)
            
            # 准备分析数据
            analyses = []
            for page_data in pages_data:
                if 'analysis' in page_data:
                    analyses.append({
                        "page_index": page_data.get('index', 0) + 1,
                        "title": page_data.get('title', f"页面 {page_data.get('index', 0) + 1}"),
                        "analysis": page_data['analysis']
                    })
            
            # 使用模板构建提示
            prompt = self.document_summary_template.format(
                document_title=document_title or "未命名文档",
                total_pages=len(pages_data),
                page_analyses=json.dumps(analyses, ensure_ascii=False, indent=2)
            )
            
            # 调用API生成摘要
            print(f"调用API生成文档摘要（模型：{config.DEFAULT_MODEL}）...")
            client = OpenAI(
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_API_BASE
            )
            response = client.chat.completions.create(
                model=config.DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的文档摘要助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1000
            )
            
            summary = response.choices[0].message.content.strip()
            
            print(f"已生成文档摘要：约 {len(summary)} 字符")
            
            # 缓存摘要
            if input_file:
                self.cache_manager.save_cache(input_file, cache_key, self.model_name, summary)
                print("文档摘要已缓存")
            
            return summary
            
        except Exception as e:
            print(f"生成文档摘要时出错: {str(e)}")
            return f"无法生成文档摘要：{str(e)}"
    
    def generate_notes(self, pages_data: List[Dict[str, Any]], output_file: str, style: str = "detailed", include_images: bool = False, input_file: str = None) -> str:
        """
        生成PPT笔记
        
        Args:
            pages_data: 页面数据列表，包含分析结果
            output_file: 输出文件路径
            style: 笔记风格，可选 "detailed"、"concise"、"outline"
            include_images: 是否在笔记中包含图片
            input_file: 输入文件路径，用于缓存
            
        Returns:
            str: 生成的笔记内容
        """
        try:
            # 获取已缓存的笔记，如果有
            cache_key = f"notes_{style}_{'with_images' if include_images else 'no_images'}"
            if input_file and self.cache_manager.has_cache(input_file, cache_key, self.model_name):
                print(f"找到缓存的PPT笔记（风格: {style}），正在加载...")
                return self.cache_manager.load_cache(input_file, cache_key, self.model_name)
            
            print(f"开始生成PPT笔记（风格: {style}，包含图像: {include_images}），共 {len(pages_data)} 页...")
            
            # 验证页面数据
            if not isinstance(pages_data, list) or len(pages_data) == 0:
                print("错误：无有效的页面数据用于生成笔记")
                return None
            
            # 如果检测到严重问题，禁用图片处理
            if include_images and not self._check_images_valid(pages_data):
                print("检测到图片数据存在严重问题，已禁用图片处理功能")
                include_images = False
            
            # 构建缓存标识符，包含样式和图片设置
            cache_mode = f"vl_notes_{style}_{include_images}"
            
            # 检查缓存
            if input_file and self.cache_manager.has_cache(input_file, cache_mode, self.model_name):
                print(f"找到缓存的笔记内容（风格: {style}{'，包含图片' if include_images else ''}），正在加载...")
                try:
                    notes = self.cache_manager.load_cache(input_file, cache_mode, self.model_name)
                    
                    # 删除可能存在的多余markdown标记
                    notes = notes.replace("```markdown", "")
                    notes = notes.lstrip("`")
                    
                    # 确保笔记以正确的格式开始
                    if notes.startswith("```") and not notes.startswith("```python") and not notes.startswith("```java"):
                        notes = notes[3:]
                    
                    # 写入笔记文件
                    try:
                        with open(output_file, "w", encoding="utf-8") as f:
                            f.write(notes)
                        
                        print(f"已从缓存加载笔记内容并写入文件：{output_file}")
                        return notes
                    except Exception as e:
                        print(f"写入缓存的笔记到文件时出错: {str(e)}")
                except Exception as e:
                    print(f"加载缓存笔记时出错: {str(e)}")
                    # 继续执行，重新生成笔记
            
            print(f"开始生成{style}风格的笔记{'，包含图片' if include_images else ''}，共 {len(pages_data)} 页...")
            
            # 确保输出目录存在
            try:
                output_dir = os.path.dirname(output_file)
                if output_dir:
                    ensure_directory_exists(output_dir)
            except Exception as e:
                print(f"创建输出目录时出错: {str(e)}")
            
            # 提取所有页面的分析结果
            analyses = []
            has_images = False
            has_full_pages = False
            
            # 预处理：修复可能的image键名问题
            for page in pages_data:
                # 修复图片列表中的键名
                images = page.get('images', [])
                if images and isinstance(images, list):
                    for i, img in enumerate(images):
                        if isinstance(img, dict) and 'image' in img and 'relative_path' not in img:
                            images[i]['relative_path'] = img['image']
                
                # 修复全页图片的键名
                full_page = page.get('full_page_image')
                if full_page and isinstance(full_page, dict) and 'image' in full_page and 'relative_path' not in full_page:
                    page['full_page_image']['relative_path'] = full_page['image']
            
            for page_data in pages_data:
                try:
                    # 获取分析内容，确保处理缺失值
                    analysis = page_data.get("analysis", f"[页面 {page_data.get('index', 0) + 1} 无分析结果]")
                    
                    # 获取图片列表，确保存在默认空列表
                    images = page_data.get("images", [])
                    
                    # 检查图片列表是否为None，若是则设置为空列表
                    if images is None:
                        images = []
                    elif not isinstance(images, list):
                        images = []
                        print(f"页面 {page_data.get('index', 0) + 1} 的图片列表格式无效，已重置为空列表")
                    
                    # 检查图片对象格式，确保所有必要的字段都存在
                    processed_images = []
                    for i, img in enumerate(images):
                        if isinstance(img, dict):
                            # 创建一个新的图片对象，包含所有必要的字段
                            new_img = {}
                            
                            # 优先使用relative_path，如果不存在则尝试使用image
                            if 'relative_path' in img:
                                new_img['relative_path'] = img['relative_path']
                            elif 'image' in img:
                                new_img['relative_path'] = img['image']
                            else:
                                # 如果没有路径信息，跳过这个图片
                                continue
                            
                            # 复制其他可能有用的字段
                            new_img['index'] = img.get('index', i)
                            new_img['type'] = img.get('type', 'image')
                            new_img['description'] = img.get('description', f'图片 {i+1}')
                            
                            processed_images.append(new_img)
                    
                    # 替换原始图片列表
                    images = processed_images
                    
                    # 更新页面数据中的图片列表
                    page_data['images'] = images
                    
                    # 检查是否有图片和整页图片
                    if images and len(images) > 0:
                        has_images = True
                        print(f"页面 {page_data.get('index', 0) + 1} 有 {len(images)} 张图片")
                    
                    # 安全地检查全页图片
                    full_page_image = page_data.get("full_page_image", None)
                    if full_page_image:
                        if isinstance(full_page_image, dict):
                            # 确保存在relative_path字段
                            if 'relative_path' not in full_page_image and 'image' in full_page_image:
                                full_page_image['relative_path'] = full_page_image['image']
                                
                            if 'relative_path' in full_page_image:
                                has_full_pages = True
                                print(f"页面 {page_data.get('index', 0) + 1} 有全页图片")
                            else:
                                # 如果没有相对路径，则设置为None
                                page_data["full_page_image"] = None
                        else:
                            # 如果不是字典，则设置为None
                            page_data["full_page_image"] = None
                    
                    # 创建分析数据字典，确保所有可能的键都存在
                    analysis_data = {
                        "title": page_data.get("title", f"页面 {page_data.get('index', 0) + 1}"),
                        "content": analysis,
                        "images": images,
                        "full_page_image": page_data.get("full_page_image"),
                        "index": page_data.get("index", 0)
                    }
                    
                    analyses.append(analysis_data)
                except Exception as e:
                    print(f"处理页面 {page_data.get('index', 0) + 1} 数据时出错: {str(e)}")
                    # 添加一个最小的有效数据条目
                    analyses.append({
                        "title": f"页面 {len(analyses) + 1}",
                        "content": "[处理出错]",
                        "images": [],
                        "full_page_image": None,
                        "index": len(analyses)
                    })
            
            # 构建提示词
            if include_images and (has_images or has_full_pages):
                if has_images and has_full_pages:
                    # 同时使用单个图片和完整页面图片
                    template = SUMMARY_WITH_ALL_IMAGES_TEMPLATE
                    template_type = "包含单图和整页图片"
                elif has_full_pages:
                    # 只使用完整页面图片
                    template = SUMMARY_WITH_FULL_PAGES_TEMPLATE
                    template_type = "仅包含整页图片"
                elif has_images:
                    # 只使用单个图片
                    template = SUMMARY_WITH_IMAGES_TEMPLATE
                    template_type = "仅包含单张图片"
                else:
                    # 没有任何图片可用
                    template = SUMMARY_TEMPLATE
                    template_type = "无图片"
            else:
                template = SUMMARY_TEMPLATE
                template_type = "无图片"
                include_images = False  # 重置标志，确保不会尝试处理图片
            
            print(f"使用模板：{template_type}，处理 {len(analyses)} 页内容...")
            
            try:
                # 调试: 序列化为JSON之前检查数据结构
                print("正在序列化分析数据为JSON...")
                try:
                    analyses_json = json.dumps(analyses, ensure_ascii=False, indent=2)
                    print(f"JSON序列化成功，大小：{len(analyses_json)} 字符")
                except Exception as e:
                    print(f"JSON序列化失败: {str(e)}")
                    # 尝试找出问题对象
                    for i, item in enumerate(analyses):
                        try:
                            json.dumps(item)
                        except Exception as e:
                            print(f"第 {i+1} 项无法序列化: {str(e)}")
                            # 尝试简化该项
                            analyses[i] = {
                                "title": item.get("title", f"页面 {i+1}"),
                                "content": item.get("content", "[内容无法序列化]"),
                                "images": [],
                                "full_page_image": None,
                                "index": i
                            }
                    
                    # 重新尝试序列化
                    try:
                        analyses_json = json.dumps(analyses, ensure_ascii=False, indent=2)
                        print("简化后序列化成功")
                    except Exception as e:
                        print(f"简化后仍无法序列化: {str(e)}")
                        # 使用最小化数据
                        analyses = [{"title": f"页面 {i+1}", "content": "[数据结构错误]", "images": [], "full_page_image": None, "index": i} for i in range(len(analyses))]
                        analyses_json = json.dumps(analyses, ensure_ascii=False, indent=2)
                
                prompt = template.format(
                    style=style,
                    analyses=analyses_json
                )
                
                # 调用API生成笔记
                print(f"调用API生成PPT笔记（模型：{config.DEFAULT_MODEL}）...")
                client = OpenAI(
                    api_key=config.OPENAI_API_KEY,
                    base_url=config.OPENAI_API_BASE
                )
                response = client.chat.completions.create(
                    model=config.DEFAULT_MODEL,
                    messages=[
                        {"role": "system", "content": "你是一个专业的PPT笔记助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=4000
                )
                
                notes = response.choices[0].message.content.strip()
                
                # 将笔记写入文件
                try:
                    # 确保输出目录存在
                    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(notes)
                    print(f"PPT笔记已成功写入到文件：{output_file}")
                except Exception as e:
                    print(f"写入笔记文件时出错：{str(e)}")
                
                # 缓存笔记
                if input_file:
                    cache_key = f"notes_{style}_{'with_images' if include_images else 'no_images'}"
                    self.cache_manager.save_cache(input_file, cache_key, notes, self.model_name)
                    print(f"PPT笔记已成功缓存（风格：{style}）")
                
                return notes
            except Exception as e:
                print(f"生成PPT笔记时出错：{str(e)}")
                traceback.print_exc()
                return None
        except Exception as e:
            print(f"生成PPT笔记时出错：{str(e)}")
            traceback.print_exc()
            return None
    
    def _process_image_placeholders(self, notes: str, pages_data: List[Dict[str, Any]]) -> str:
        """
        处理笔记中的图像占位符，替换为实际图像引用
        
        Args:
            notes: 笔记内容
            pages_data: 页面数据
            
        Returns:
            str: 处理后的笔记内容
        """
        try:
            print("【日志】开始执行_process_image_placeholders方法")
            # 构建可用图像映射
            image_map = {}
            
            for page_data in pages_data:
                page_index = page_data.get("index", 0)
                images = page_data.get("images", [])
                
                # 确保images是列表且不为None
                if images is None:
                    images = []
                
                print(f"【日志】处理页面 {page_index + 1} 的图片，数量: {len(images)}")
                # 检查图像列表中的每个元素
                for i, img in enumerate(images):
                    print(f"【日志】处理图片 {i+1}，类型: {type(img)}")
                    if isinstance(img, dict):
                        print(f"【日志】图片 {i+1} 键: {list(img.keys())}")
                    
                    if isinstance(img, dict) and "index" in img:
                        key = f"{page_index}_{img['index']}"
                        print(f"【日志】添加图片映射 key={key}")
                        image_map[key] = img
                    elif isinstance(img, dict) and "relative_path" in img:
                        # 如果没有索引但有路径，使用列表索引作为图片索引
                        img_with_index = img.copy()
                        img_with_index["index"] = i
                        key = f"{page_index}_{i}"
                        print(f"【日志】添加替代图片映射 key={key}")
                        image_map[key] = img_with_index
            
            print(f"【日志】构建了 {len(image_map)} 个图片映射")
            
            # 查找并替换图像占位符标签
            import re
            
            # 定义图像占位符模式
            # 格式为: {{{image: page_x_img_y description}}}
            pattern = r"\{\{\{image:([^}]*)\}\}\}"
            print(f"【日志】使用正则模式: {pattern}")
            
            def replace_image(match):
                try:
                    placeholder = match.group(1).strip()
                    print(f"【日志】找到占位符: {placeholder}")
                    parts = placeholder.split(" ", 1)
                    
                    if len(parts) == 0:
                        print("【日志】占位符格式错误，无法分割")
                        return match.group(0)  # 保持原样
                    
                    # 解析图像标识符和描述
                    img_id = parts[0].strip()
                    description = parts[1].strip() if len(parts) > 1 else ""
                    
                    print(f"【日志】图片ID: {img_id}, 描述: {description}")
                    
                    # 尝试解析页面和图像索引
                    try:
                        if img_id.startswith("page") and "_img" in img_id:
                            print(f"【日志】解析图片ID: {img_id}")
                            page_str, img_str = img_id.replace("page", "").split("_img")
                            page_index = int(page_str) - 1  # 转换为0索引
                            img_index = int(img_str) - 1    # 转换为0索引
                            
                            key = f"{page_index}_{img_index}"
                            print(f"【日志】查找映射键: {key}, 是否存在: {key in image_map}")
                            
                            if key in image_map:
                                img_info = image_map[key]
                                print(f"【日志】找到图片信息: {list(img_info.keys())}")
                                
                                if "relative_path" in img_info:
                                    relative_path = img_info["relative_path"]
                                    print(f"【日志】使用相对路径: {relative_path}")
                                    
                                    if description:
                                        return f"![{description}]({relative_path})"
                                    else:
                                        return f"![图片 {img_id}]({relative_path})"
                                else:
                                    print(f"【错误】图片信息缺少relative_path字段")
                                    print(f"【错误】图片信息内容: {img_info}")
                            else:
                                print(f"【日志】在映射中找不到键: {key}")
                    except Exception as e:
                        print(f"【错误】处理图片引用时出错: {str(e)}")
                        import traceback
                        print(f"【错误】详细堆栈: {traceback.format_exc()}")
                except Exception as e:
                    print(f"【错误】替换图片占位符时出错: {str(e)}")
                    import traceback
                    print(f"【错误】详细堆栈: {traceback.format_exc()}")
                
                # 如果无法解析或找不到图像，保持原样
                return match.group(0)
            
            # 替换所有图像占位符
            print("【日志】开始替换图像占位符")
            processed_notes = re.sub(pattern, replace_image, notes)
            print("【日志】完成图像占位符替换")
            
            return processed_notes
        except Exception as e:
            print(f"【错误】处理图片占位符时出错: {str(e)}")
            import traceback
            print(f"【错误】详细堆栈: {traceback.format_exc()}")
            # 出错时返回原始笔记内容
            return notes
    
    def _process_fullpage_placeholders(self, notes: str, pages_data: List[Dict[str, Any]]) -> str:
        """
        处理笔记中的完整页面图像占位符，替换为实际图像引用
        
        Args:
            notes: 笔记内容
            pages_data: 页面数据
            
        Returns:
            str: 处理后的笔记内容
        """
        try:
            # 查找并替换完整页面图像占位符标签
            import re
            
            # 定义图像占位符模式
            # 格式为: {{{fullpage: page_x description}}}
            pattern = r"\{\{\{fullpage:([^}]*)\}\}\}"
            
            def replace_fullpage(match):
                try:
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
                                    full_page = page["full_page_image"]
                                    if isinstance(full_page, dict) and "relative_path" in full_page:
                                        relative_path = full_page["relative_path"]
                                        
                                        if description:
                                            return f"![{description}]({relative_path})"
                                        else:
                                            return f"![完整页面 {page_index+1}]({relative_path})"
                    except Exception as e:
                        print(f"处理整页图片引用时出错: {str(e)}")
                except Exception as e:
                    print(f"替换整页图片占位符时出错: {str(e)}")
                
                # 如果无法解析或找不到页面，保持原样
                return match.group(0)
            
            # 替换所有完整页面图像占位符
            processed_notes = re.sub(pattern, replace_fullpage, notes)
            
            return processed_notes
        except Exception as e:
            print(f"处理整页图片占位符时出错: {str(e)}")
            # 出错时返回原始笔记内容
            return notes
    
    def _check_images_valid(self, pages_data: List[Dict[str, Any]]) -> bool:
        """
        检查图片数据是否有效
        
        Args:
            pages_data: 页面数据列表
            
        Returns:
            bool: 图片数据是否有效
        """
        try:
            valid_images_count = 0
            valid_full_pages_count = 0
            total_pages = len(pages_data)
            
            for page in pages_data:
                # 检查单个图片
                images = page.get('images', [])
                if images and isinstance(images, list):
                    for img in images:
                        if isinstance(img, dict) and ('relative_path' in img or 'image' in img):
                            valid_images_count += 1
                            break  # 每页只需要一个有效图片即可
                
                # 检查全页图片
                full_page = page.get('full_page_image')
                if full_page and isinstance(full_page, dict) and ('relative_path' in full_page or 'image' in full_page):
                    valid_full_pages_count += 1
            
            print(f"PPT图像分析：有效图片页数 {valid_images_count}/{total_pages}")
            print(f"PPT图像分析：有效全页图片页数 {valid_full_pages_count}/{total_pages}")
            
            # 如果没有任何有效图片或图片太少，返回False
            if valid_images_count == 0 and valid_full_pages_count == 0:
                print("PPT图像分析：未找到任何有效图片")
                return False
            
            # 如果有效图片比例太低，可能是数据问题
            if valid_images_count > 0 and valid_images_count < total_pages * 0.1:
                print(f"PPT图像分析：有效图片比例太低 ({valid_images_count}/{total_pages})")
                # 仍然返回True，因为有一些图片是有效的
                return True
            
            return True
        except Exception as e:
            print(f"检查PPT图片有效性时出错: {str(e)}")
            return False

    def _write_notes_to_file(self, notes: str, output_file: str) -> bool:
        """
        将笔记写入文件
        
        Args:
            notes: 笔记内容
            output_file: 输出文件路径
            
        Returns:
            bool: 是否成功写入
        """
        try:
            # 创建输出目录
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            
            # 写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(notes)
                
            print(f"笔记已成功保存到: {output_file}")
            return True
        except Exception as e:
            print(f"写入笔记文件时出错: {str(e)}")
            return False 