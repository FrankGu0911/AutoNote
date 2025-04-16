import os
import fitz  # PyMuPDF
from PIL import Image
import io
import tempfile
from pptx import Presentation
from typing import List, Dict, Any, Optional, Tuple
import config
from utils.helpers import ensure_directory_exists, is_ppt_file, is_pdf_file

class ImageConverter:
    """
    文档图像转换器，负责将PPT或PDF文件转换为高质量图像
    """
    def __init__(self, temp_dir: str = None):
        """
        初始化图像转换器
        
        Args:
            temp_dir: 临时图像存储目录
        """
        self.temp_dir = temp_dir or config.IMAGE_TEMP_DIR
        ensure_directory_exists(self.temp_dir)
        self.image_paths = []
        self.dpi = config.IMAGE_DPI
        self.image_format = config.IMAGE_FORMAT
        self.image_quality = config.IMAGE_QUALITY
    
    def convert_pdf_to_images(self, file_path: str) -> List[Dict[str, Any]]:
        """
        将PDF文件转换为图像
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            List[Dict]: 包含图像路径和元数据的列表
        """
        self.image_paths = []
        result = []
        
        try:
            # 打开PDF文件
            pdf_document = fitz.open(file_path)
            
            # 遍历每一页
            for page_index in range(len(pdf_document)):
                page = pdf_document[page_index]
                
                # 渲染页面为图像
                pix = page.get_pixmap(dpi=self.dpi)
                
                # 创建图像路径
                image_path = os.path.join(self.temp_dir, f"page_{page_index+1}.{self.image_format}")
                
                # 保存图像
                if self.image_format.lower() == "png":
                    pix.save(image_path)
                else:
                    # 转换为PIL图像以支持其他格式
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img.save(image_path, quality=self.image_quality)
                
                self.image_paths.append(image_path)
                
                # 提取基本文本作为辅助信息
                text = page.get_text()
                
                # 尝试提取标题
                title = self._extract_page_title(text, page_index)
                
                # 创建页面数据
                page_data = {
                    "index": page_index,
                    "title": title,
                    "image_path": image_path,
                    "text_hint": text[:500] if text else "",  # 仅保留部分文本作为辅助提示
                }
                
                result.append(page_data)
            
            pdf_document.close()
            
        except Exception as e:
            print(f"PDF转图像失败: {e}")
        
        return result
    
    def convert_ppt_to_images(self, file_path: str) -> List[Dict[str, Any]]:
        """
        将PPT文件转换为图像
        
        Args:
            file_path: PPT文件路径
            
        Returns:
            List[Dict]: 包含图像路径和元数据的列表
        """
        self.image_paths = []
        result = []
        
        try:
            # 使用PDF作为中间格式
            # 先将PPT转换为PDF，再将PDF转换为图像
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                tmp_pdf_path = tmp_pdf.name
            
            self._convert_ppt_to_pdf(file_path, tmp_pdf_path)
            
            # 然后使用现有的PDF转图像功能
            result = self.convert_pdf_to_images(tmp_pdf_path)
            
            # 删除临时PDF文件
            os.unlink(tmp_pdf_path)
            
            # 对于PPT，尝试从原始文件中提取标题
            self._update_titles_from_ppt(file_path, result)
            
        except Exception as e:
            print(f"PPT转图像失败: {e}")
        
        return result
    
    def _convert_ppt_to_pdf(self, ppt_path: str, pdf_path: str) -> bool:
        """
        将PPT转换为PDF（使用外部工具LibreOffice或提示用户）
        
        Args:
            ppt_path: PPT文件路径
            pdf_path: 输出PDF路径
            
        Returns:
            bool: 转换是否成功
        """
        try:
            # 尝试使用LibreOffice转换（如果安装了的话）
            import subprocess
            result = subprocess.run(
                ["soffice", "--headless", "--convert-to", "pdf", "--outdir", 
                 os.path.dirname(pdf_path), ppt_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # 重命名输出文件
                base_name = os.path.basename(ppt_path)
                file_name = os.path.splitext(base_name)[0]
                orig_pdf = os.path.join(os.path.dirname(pdf_path), f"{file_name}.pdf")
                os.rename(orig_pdf, pdf_path)
                return True
            
            raise Exception("LibreOffice转换失败")
            
        except Exception as e:
            print(f"无法自动转换PPT到PDF: {e}")
            print("请手动将PPT转换为PDF后重试，或使用文本模式处理。")
            return False
    
    def _update_titles_from_ppt(self, ppt_path: str, pages_data: List[Dict[str, Any]]) -> None:
        """
        从原始PPT中提取标题并更新页面数据
        
        Args:
            ppt_path: PPT文件路径
            pages_data: 页面数据列表
        """
        try:
            presentation = Presentation(ppt_path)
            
            for i, slide in enumerate(presentation.slides):
                if i < len(pages_data) and slide.shapes.title:
                    pages_data[i]["title"] = slide.shapes.title.text
        except:
            pass
    
    def _extract_page_title(self, text: str, page_index: int) -> str:
        """
        尝试从页面文本中提取标题
        
        Args:
            text: 页面文本
            page_index: 页面索引
            
        Returns:
            str: 提取的标题
        """
        if not text:
            return f"页面 {page_index + 1}"
        
        # 简单实现：尝试使用第一行作为标题
        lines = text.strip().split('\n')
        if lines:
            title = lines[0].strip()
            # 标题不应该太长
            if len(title) <= 100:
                return title
        
        return f"页面 {page_index + 1}"
    
    def convert_file_to_images(self, file_path: str) -> List[Dict[str, Any]]:
        """
        根据文件类型将文件转换为图像
        
        Args:
            file_path: 文件路径
            
        Returns:
            List[Dict]: 包含图像路径和元数据的列表
        """
        if is_pdf_file(file_path):
            return self.convert_pdf_to_images(file_path)
        elif is_ppt_file(file_path):
            return self.convert_ppt_to_images(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {file_path}")
    
    def cleanup(self) -> None:
        """
        清理临时图像文件
        """
        for image_path in self.image_paths:
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except:
                    pass


if __name__ == "__main__":
    # 测试代码
    converter = ImageConverter()
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"正在转换文件: {file_path}")
        
        pages = converter.convert_file_to_images(file_path)
        print(f"已转换 {len(pages)} 页到图像")
        
        for page in pages:
            print(f"页面 {page['index']+1}: {page['title']}")
            print(f"图像路径: {page['image_path']}")
            print("-" * 50)
    else:
        print("请提供文件路径作为参数") 