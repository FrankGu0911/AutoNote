from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import config
from templates.page_prompt import SLIDE_ANALYSIS_TEMPLATE
from utils.cache_manager import CacheManager

class ContentAnalyzer:
    """
    内容分析器类，负责使用LLM理解PPT内容
    """
    def __init__(self, model_name: str = None):
        """
        初始化内容分析器
        
        Args:
            model_name: 使用的LLM模型名称，默认使用配置中的模型
        """
        self.model_name = model_name or config.DEFAULT_MODEL
        self.llm = ChatOpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_API_BASE,
            model_name=self.model_name,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS
        )
        
        # 创建幻灯片理解模板
        self.slide_template = PromptTemplate(
            input_variables=["slide_index", "slide_title", "slide_content"],
            template=SLIDE_ANALYSIS_TEMPLATE
        )
        
        # 使用管道方式替代LLMChain
        self.slide_chain = self.slide_template | self.llm
        
        # 初始化缓存管理器
        self.cache_manager = CacheManager()
    
    def analyze_slide(self, slide_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析单个幻灯片内容
        
        Args:
            slide_data: 包含幻灯片数据的字典
            
        Returns:
            Dict: 包含分析结果的字典
        """
        slide_index = slide_data["index"] + 1
        slide_title = slide_data["title"] or f"幻灯片 {slide_index}"
        
        # 合并所有内容文本
        slide_content = "\n".join(slide_data["content"])
        
        # 检查是否有图片，若有则添加图片信息
        if slide_data["images"]:
            image_info = f"[该幻灯片包含 {len(slide_data['images'])} 张图片]"
            slide_content = f"{slide_content}\n{image_info}"
        
        # 使用LLM分析内容
        result = self.slide_chain.invoke({
            "slide_index": slide_index,
            "slide_title": slide_title,
            "slide_content": slide_content
        })
        
        # 根据新API，结果可能直接是消息内容或包含content字段
        if isinstance(result, dict) and "content" in result:
            analysis_text = result["content"]
        elif isinstance(result, dict) and "text" in result:
            analysis_text = result["text"]
        else:
            analysis_text = str(result)
        
        # 结果添加到原始数据中
        slide_data["analysis"] = analysis_text
        
        return slide_data
    
    def analyze_presentation(self, slides_data: List[Dict[str, Any]], input_file: str = None) -> List[Dict[str, Any]]:
        """
        分析整个PPT演示文稿
        
        Args:
            slides_data: 包含所有幻灯片数据的列表
            input_file: 输入文件路径，用于缓存
            
        Returns:
            List[Dict]: 包含分析结果的幻灯片数据列表
        """
        # 检查是否有缓存
        cache_key = "text_analyze"
        if input_file and self.cache_manager.has_cache(input_file, cache_key, self.model_name):
            print(f"找到缓存的PPT分析结果，正在加载...")
            cached_data = self.cache_manager.load_cache(input_file, cache_key, self.model_name)
            
            # 将缓存数据与输入幻灯片数据合并
            # 确保使用最新的metadata，但保留分析结果
            for i, slide_data in enumerate(slides_data):
                if i < len(cached_data):
                    # 保留原始页面数据，但更新分析结果
                    slide_data["analysis"] = cached_data[i]["analysis"]
            
            print(f"已从缓存加载 {len(cached_data)} 页分析结果")
            return slides_data
        
        print(f"开始分析PPT内容，共 {len(slides_data)} 页...")
        analyzed_slides = []
        
        # 读取现有缓存数据（如果有）
        existing_data = []
        if input_file and self.cache_manager.has_cache(input_file, cache_key, self.model_name):
            existing_data = self.cache_manager.load_cache(input_file, cache_key, self.model_name)
            
            # 创建索引到分析结果的映射，便于查找
            cached_analyses = {item["index"]: item["analysis"] for item in existing_data}
            
            # 应用已有的缓存结果
            for slide_data in slides_data:
                if slide_data["index"] in cached_analyses:
                    slide_data["analysis"] = cached_analyses[slide_data["index"]]
                    analyzed_slides.append(slide_data)
                    print(f"已从缓存加载第 {slide_data['index'] + 1} 页分析结果")
        
        # 分析尚未缓存的幻灯片
        for slide_data in slides_data:
            # 跳过已有分析结果的幻灯片
            if "analysis" in slide_data:
                continue
            
            print(f"正在分析第 {slide_data['index'] + 1} 页（标题：{slide_data['title'] or '无标题'}）...")
            analyzed_slide = self.analyze_slide(slide_data)
            analyzed_slides.append(analyzed_slide)
            print(f"完成第 {slide_data['index'] + 1} 页分析")
            
            # 每分析一个幻灯片就更新缓存
            if input_file:
                # 准备当前分析的幻灯片数据
                current_slide_data = {"index": slide_data["index"], "analysis": slide_data["analysis"]}
                
                # 检查是否已有之前保存的数据
                if self.cache_manager.has_cache(input_file, cache_key, self.model_name):
                    existing_data = self.cache_manager.load_cache(input_file, cache_key, self.model_name)
                else:
                    existing_data = []
                
                # 合并已有数据和新数据
                merged_data = list(existing_data)  # 复制现有数据
                
                # 更新或添加新分析的幻灯片
                found = False
                for i, existing_slide in enumerate(merged_data):
                    if existing_slide["index"] == current_slide_data["index"]:
                        merged_data[i] = current_slide_data  # 更新现有项
                        found = True
                        break
                
                if not found:
                    merged_data.append(current_slide_data)  # 添加新项
                
                # 按幻灯片索引排序
                merged_data.sort(key=lambda x: x["index"])
                
                # 保存合并后的数据
                self.cache_manager.save_cache(input_file, cache_key, self.model_name, merged_data)
                print(f"已缓存当前分析进度：共 {len(merged_data)} 页")
        
        # 确保按索引排序
        analyzed_slides.sort(key=lambda x: x["index"])
        
        if input_file:
            print(f"已完成全部 {len(analyzed_slides)} 页PPT分析，结果已缓存")
        else:
            print(f"已完成全部 {len(analyzed_slides)} 页PPT分析（未启用缓存）")
            
        return analyzed_slides


if __name__ == "__main__":
    # 测试代码，假设我们已经有了解析好的幻灯片数据
    from ppt_parser import PPTParser
    
    parser = PPTParser()
    slides = parser.process_file("test.pptx")
    
    analyzer = ContentAnalyzer()
    analyzed_slides = analyzer.analyze_presentation(slides)
    
    print(f"已分析 {len(analyzed_slides)} 张幻灯片")
    for slide in analyzed_slides[:1]:  # 只打印第一张幻灯片的分析结果
        print(f"幻灯片 {slide['index']+1}: {slide['title']}")
        print(f"分析结果:\n{slide['analysis']}")
        print("-" * 50) 