"""ConsolePipeline：将 Item 打印到终端，用于调试"""
from src.pipeline.base import BasePipeline


class ConsolePipeline(BasePipeline):
    """
    将爬取到的 Item 打印到控制台。
    适合开发调试阶段使用。

    配置：
        ITEM_PIPELINES = {
            'src.pipeline.console.ConsolePipeline': 100,
        }
    """

    async def process_item(self, item, spider):
        print(f"[{getattr(spider, 'name', 'spider')}] Item scraped: {dict(item) if hasattr(item, 'items') else item}")
        return item
