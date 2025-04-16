import os
import fitz  # PyMuPDF
from typing import Dict, List, Any, Optional
import base64
from io import BytesIO

class PDFParser:
    """
    PDF解析类，负责从PDF文件中提取内容
    """
    def __init__(self):
        self.document = None
        self.pages_data = []
    
    def load_document(self, file_path: str) -> bool:
        """
        加载PDF文件
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            bool: 是否成功加载
        """
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return False
        
        try:
            self.document = fitz.open(file_path)
            return True
        except Exception as e:
            print(f"加载PDF文件失败: {e}")
            return False
    
    def extract_text_from_page(self, page) -> str:
        """
        从页面中提取文本
        
        Args:
            page: PDF页面对象
            
        Returns:
            str: 提取的文本
        """
        try:
            return page.get_text()
        except Exception as e:
            print(f"提取文本失败: {e}")
            return ""
    
    def extract_images_from_page(self, page) -> List[Dict[str, Any]]:
        """
        从页面中提取图片
        
        Args:
            page: PDF页面对象
            
        Returns:
            List[Dict]: 图片数据列表
        """
        images = []
        try:
            # 获取页面上的图片
            image_list = page.get_images(full=True)
            
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = self.document.extract_image(xref)
                
                if base_image:
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # 转换为base64
                    encoded = base64.b64encode(image_bytes).decode('utf-8')
                    images.append({
                        "data": f"data:image/{image_ext};base64,{encoded}",
                        "alt_text": f"图片 {img_index+1}"
                    })
        except Exception as e:
            print(f"提取图片失败: {e}")
        
        return images
    
    def extract_page_title(self, page, page_index: int) -> str:
        """
        尝试从页面提取标题
        
        Args:
            page: PDF页面对象
            page_index: 页面索引
            
        Returns:
            str: 提取的标题
        """
        try:
            # 简单实现：尝试找到第一行文本作为标题
            text = page.get_text()
            lines = text.strip().split('\n')
            if lines and lines[0]:
                # 限制标题长度，防止整个段落被当作标题
                title = lines[0].strip()
                if len(title) <= 100:  # 标题不超过100个字符
                    return title
        except:
            pass
        
        # 如果无法提取标题，返回默认标题
        return f"页面 {page_index + 1}"
    
    def parse_page(self, page, page_index: int) -> Dict[str, Any]:
        """
        解析单个PDF页面
        
        Args:
            page: PDF页面对象
            page_index: 页面索引
            
        Returns:
            Dict: 包含页面解析数据的字典
        """
        page_data = {
            "index": page_index,
            "title": self.extract_page_title(page, page_index),
            "content": [],
            "images": []
        }
        
        # 提取文本
        text = self.extract_text_from_page(page)
        if text:
            page_data["content"].append(text)
        
        # 提取图片
        images = self.extract_images_from_page(page)
        if images:
            page_data["images"].extend(images)
        
        return page_data
    
    def parse_document(self) -> List[Dict[str, Any]]:
        """
        解析整个PDF文档
        
        Returns:
            List[Dict]: 包含所有页面数据的列表
        """
        if not self.document:
            print("未加载PDF文件")
            return []
        
        self.pages_data = []
        
        for i in range(len(self.document)):
            page = self.document[i]
            page_data = self.parse_page(page, i)
            self.pages_data.append(page_data)
        
        return self.pages_data
    
    def process_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        处理PDF文件并返回解析后的数据
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            List[Dict]: 包含所有页面数据的列表
        """
        if self.load_document(file_path):
            return self.parse_document()
        return []


if __name__ == "__main__":
    # 测试代码
    parser = PDFParser()
    pages = parser.process_file("test.pdf")
    print(f"解析了 {len(pages)} 页PDF")
    for page in pages:
        print(f"页面 {page['index']+1}: {page['title']}")
        print(f"内容长度: {len(page['content'][0]) if page['content'] else 0} 字符")
        print(f"图片数量: {len(page['images'])}")
        print("-" * 50) 