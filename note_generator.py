import os
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import config
import markdown
import re
from templates.summary_prompt import SUMMARY_TEMPLATE
from utils.cache_manager import CacheManager

class NoteGenerator:
    """
    笔记生成器类，负责整合分析结果，生成最终的Markdown笔记
    """
    def __init__(self, model_name: str = None, style: str = None):
        """
        初始化笔记生成器
        
        Args:
            model_name: 使用的LLM模型名称
            style: 笔记风格，可选：'concise', 'detailed', 'academic'
        """
        self.model_name = model_name or config.DEFAULT_MODEL
        self.style = style or config.DEFAULT_NOTE_STYLE
        self.llm = ChatOpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_API_BASE,
            model_name=self.model_name,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS
        )
        
        # 创建整合模板
        self.summary_template = PromptTemplate(
            input_variables=["style", "all_slides_analysis", "ppt_title"],
            template=SUMMARY_TEMPLATE
        )
        
        # 使用管道方式替代LLMChain
        self.summary_chain = self.summary_template | self.llm
        
        # 初始化缓存管理器
        self.cache_manager = CacheManager()
    
    def extract_ppt_title(self, slides_data: List[Dict[str, Any]]) -> str:
        """
        从幻灯片数据中提取PPT标题
        
        Args:
            slides_data: 包含所有幻灯片数据的列表
            
        Returns:
            str: PPT标题
        """
        # 假设第一张幻灯片的标题通常是PPT的标题
        if slides_data and slides_data[0]["title"]:
            return slides_data[0]["title"]
        return "课程笔记"
    
    def format_slide_analysis(self, slides_data: List[Dict[str, Any]]) -> str:
        """
        格式化所有幻灯片的分析结果
        
        Args:
            slides_data: 包含所有幻灯片数据的列表
            
        Returns:
            str: 格式化后的分析结果
        """
        formatted_analysis = ""
        
        for slide in slides_data:
            slide_index = slide["index"] + 1
            slide_title = slide["title"] or f"幻灯片 {slide_index}"
            
            formatted_analysis += f"--- 幻灯片 {slide_index}: {slide_title} ---\n"
            formatted_analysis += slide["analysis"] + "\n\n"
        
        return formatted_analysis
    
    def generate_notes(self, slides_data: List[Dict[str, Any]], input_file: str = None) -> str:
        """
        生成完整的笔记
        
        Args:
            slides_data: 包含所有带分析的幻灯片数据的列表
            input_file: 输入文件路径，用于缓存
            
        Returns:
            str: 生成的Markdown格式笔记
        """
        # 检查缓存
        cache_mode = f"notes_{self.style}"
        if input_file and self.cache_manager.has_cache(input_file, cache_mode, self.model_name):
            print(f"找到缓存的笔记内容（风格: {self.style}），正在加载...")
            return self.cache_manager.load_cache(input_file, cache_mode, self.model_name)
        
        print(f"开始生成PPT笔记（风格: {self.style}），共 {len(slides_data)} 页...")
        ppt_title = self.extract_ppt_title(slides_data)
        all_slides_analysis = self.format_slide_analysis(slides_data)
        
        # 使用LLM生成最终笔记
        print(f"正在处理 {len(slides_data)} 页内容的分析结果...")
        result = self.summary_chain.invoke({
            "style": self.style,
            "all_slides_analysis": all_slides_analysis,
            "ppt_title": ppt_title
        })
        
        # 根据新API，结果可能直接是消息内容或包含content字段
        if isinstance(result, dict) and "content" in result:
            markdown_note = result["content"]
        elif isinstance(result, dict) and "text" in result:
            markdown_note = result["text"]
        else:
            markdown_note = str(result)
            
        print(f"笔记生成完成：约 {len(markdown_note)} 字符")
        
        # 如果配置了关键词高亮，进行处理
        if config.HIGHLIGHT_KEYWORDS:
            markdown_note = self.highlight_keywords(markdown_note)
        
        # 保存到缓存
        if input_file:
            self.cache_manager.save_cache(input_file, cache_mode, self.model_name, markdown_note)
            print(f"已缓存当前笔记内容（风格: {self.style}）")
            
        return markdown_note
    
    def highlight_keywords(self, markdown_text: str) -> str:
        """
        为重要关键词添加高亮
        
        Args:
            markdown_text: 原始Markdown文本
            
        Returns:
            str: 处理后的Markdown文本
        """
        # 此处可以实现更复杂的关键词提取和高亮逻辑
        # 当前简单实现：已有的加粗内容作为关键词
        return markdown_text
    
    def save_notes(self, markdown_text: str, output_path: str) -> bool:
        """
        保存生成的笔记到文件
        
        Args:
            markdown_text: Markdown格式的笔记内容
            output_path: 输出文件路径
            
        Returns:
            bool: 是否成功保存
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 写入文件
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_text)
            
            print(f"笔记已成功保存到: {output_path}")
            return True
        except Exception as e:
            print(f"保存笔记失败: {e}")
            return False


if __name__ == "__main__":
    # 测试代码，假设我们已经有了带分析的幻灯片数据
    from ppt_parser import PPTParser
    from content_analyzer import ContentAnalyzer
    
    parser = PPTParser()
    slides = parser.process_file("test.pptx")
    
    analyzer = ContentAnalyzer()
    analyzed_slides = analyzer.analyze_presentation(slides)
    
    generator = NoteGenerator(style="detailed")
    notes = generator.generate_notes(analyzed_slides)
    
    # 保存笔记
    output_dir = config.DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "lecture_notes.md")
    
    generator.save_notes(notes, output_path) 