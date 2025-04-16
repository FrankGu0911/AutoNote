import os
import base64
from typing import Dict, List, Any, Optional
import requests
import json
from PIL import Image
import io
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import config
from templates.vl_prompt import VL_SINGLE_PAGE_TEMPLATE, VL_BATCH_PAGES_TEMPLATE, VL_SUMMARY_TEMPLATE

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
    
    def _encode_image(self, image_path: str) -> str:
        """
        将图像编码为base64字符串
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            str: base64编码的图像
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _resize_image_if_needed(self, image_path: str, max_size: int = 4096) -> str:
        """
        如果图像太大，调整其大小
        
        Args:
            image_path: 图像文件路径
            max_size: 最大尺寸（宽度或高度）
            
        Returns:
            str: 调整后的图像路径（如果调整了）
        """
        try:
            img = Image.open(image_path)
            width, height = img.size
            
            # 检查是否需要调整大小
            if width > max_size or height > max_size:
                # 计算调整后的尺寸
                if width > height:
                    new_width = max_size
                    new_height = int(height * (max_size / width))
                else:
                    new_height = max_size
                    new_width = int(width * (max_size / height))
                
                # 调整图像大小
                resized_img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # 创建调整后的图像路径
                base_path, ext = os.path.splitext(image_path)
                resized_path = f"{base_path}_resized{ext}"
                
                # 保存调整后的图像
                resized_img.save(resized_path)
                
                return resized_path
        except Exception as e:
            print(f"调整图像大小时出错: {e}")
        
        # 如果没有调整或出错，返回原始路径
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
        调用视觉语言模型API
        
        Args:
            prompt: 提示词
            base64_images: base64编码的图像列表
            
        Returns:
            str: API响应文本
        """
        try:
            # 准备消息
            messages = [
                {"role": "system", "content": "你是一个能够理解图像的专业教育内容分析助手。"},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt}
                ]}
            ]
            
            # 添加图像到消息中
            for base64_image in base64_images:
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })
            
            # 准备请求数据
            payload = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": config.MAX_TOKENS,
                "temperature": config.TEMPERATURE
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 发送请求
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            
            # 解析响应
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                print(f"API请求失败: {response.status_code}")
                print(response.text)
                return f"API请求失败: {response.status_code}"
            
        except Exception as e:
            print(f"调用VL API时出错: {e}")
            return f"API调用错误: {str(e)}"
    
    def analyze_document(self, pages_data: List[Dict[str, Any]], batch_size: int = None) -> List[Dict[str, Any]]:
        """
        分析整个文档的所有页面
        
        Args:
            pages_data: 包含所有页面数据的列表
            batch_size: 批处理大小，默认使用配置中的值
            
        Returns:
            List[Dict]: 包含分析结果的页面数据列表
        """
        batch_size = batch_size or self.batch_size
        analyzed_pages = []
        
        print(f"使用VL模型({self.model_name})分析文档...")
        print(f"批处理大小: {batch_size}")
        
        # 按批处理页面
        for i in range(0, len(pages_data), batch_size):
            batch = pages_data[i:i+batch_size]
            
            # 如果批次只有一页，使用单页分析
            if len(batch) == 1:
                analyzed_page = self.analyze_single_page(batch[0])
                analyzed_pages.append(analyzed_page)
                print(f"已分析第 {batch[0]['index']+1} 页")
            else:
                # 否则使用批量分析
                analyzed_batch = self.analyze_batch_pages(batch)
                analyzed_pages.extend(analyzed_batch)
                page_nums = [p["index"]+1 for p in batch]
                print(f"已分析第 {min(page_nums)} 到 {max(page_nums)} 页")
        
        return analyzed_pages
    
    def generate_document_summary(self, pages_data: List[Dict[str, Any]], document_title: str = "文档") -> str:
        """
        生成整个文档的摘要
        
        Args:
            pages_data: 包含所有页面数据的列表
            document_title: 文档标题
            
        Returns:
            str: 文档摘要
        """
        try:
            # 准备提示词
            prompt = self.summary_template.format(
                document_title=document_title,
                total_pages=len(pages_data)
            )
            
            # 提取所有页面的分析结果
            all_analyses = "\n\n".join([f"页面 {p['index']+1}: {p['analysis']}" for p in pages_data])
            
            # 使用普通LLM生成摘要
            llm = ChatOpenAI(
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_API_BASE,
                model_name=config.DEFAULT_MODEL,
                temperature=config.TEMPERATURE,
                max_tokens=config.MAX_TOKENS
            )
            
            summary_chain = LLMChain(
                llm=llm,
                prompt=PromptTemplate(
                    input_variables=["prompt", "analyses"],
                    template="{prompt}\n\n以下是各页面的分析结果:\n\n{analyses}"
                )
            )
            
            result = summary_chain.invoke({
                "prompt": prompt,
                "analyses": all_analyses
            })
            
            return result["text"]
            
        except Exception as e:
            print(f"生成文档摘要时出错: {e}")
            return "无法生成文档摘要" 