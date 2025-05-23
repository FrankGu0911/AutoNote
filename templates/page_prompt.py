"""
单个幻灯片分析的提示模板
"""

SLIDE_ANALYSIS_TEMPLATE = """
你是一位专业的教育内容分析师。请分析以下PPT幻灯片的内容，并提取其中的关键信息、主要概念和重点。

幻灯片编号: {slide_index}
幻灯片标题: {slide_title}
幻灯片内容:
{slide_content}

请提供以下格式的分析:

1. 主要概念: [简洁列出该页面的主要概念]
2. 关键点: [以要点形式列出重要信息]
3. 定义/公式: [列出该页面包含的所有定义或公式]
4. 例子/案例: [列出该页面的例子或案例]
5. 与前面内容的联系: [该内容如何与之前的概念关联]

请确保你的分析全面、准确，并特别注意捕捉学术或技术性内容。
""" 