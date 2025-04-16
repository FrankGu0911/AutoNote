from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import config
from templates.page_prompt import SLIDE_ANALYSIS_TEMPLATE

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
        
        self.slide_chain = LLMChain(llm=self.llm, prompt=self.slide_template)
    
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
        
        # 结果添加到原始数据中
        slide_data["analysis"] = result["text"]
        
        return slide_data
    
    def analyze_presentation(self, slides_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        分析整个PPT演示文稿
        
        Args:
            slides_data: 包含所有幻灯片数据的列表
            
        Returns:
            List[Dict]: 包含分析结果的幻灯片数据列表
        """
        analyzed_slides = []
        
        for slide_data in slides_data:
            analyzed_slide = self.analyze_slide(slide_data)
            analyzed_slides.append(analyzed_slide)
            print(f"已分析幻灯片 {slide_data['index'] + 1}")
        
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