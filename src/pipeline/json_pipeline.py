"""JsonPipeline：将 Item 写入 JSON Lines 文件"""
import json
from pathlib import Path
from loguru import logger
from src.pipeline.base import BasePipeline


class JsonPipeline(BasePipeline):
    """
    将爬取到的 Item 写入 JSON Lines 格式文件（每行一个 JSON 对象）。

    配置：
        ITEM_PIPELINES = {
            'src.pipeline.json_pipeline.JsonPipeline': 800,
        }
        JSON_FEED_URI = 'output.jl'  # 输出文件路径（默认 output.jl）
    """

    def __init__(self):
        self.file = None
        self.uri = None

    @classmethod
    def create_instance(cls, crawler):
        instance = cls()
        instance.uri = crawler.settings.get('JSON_FEED_URI', 'output.jl')
        return instance

    async def open_spider(self, spider):
        self.file = open(self.uri, 'a', encoding='utf-8')
        logger.info(f"JsonPipeline: writing to {Path(self.uri).resolve()}")

    async def close_spider(self, spider):
        if self.file:
            self.file.flush()
            self.file.close()
            self.file = None
            logger.info(f"JsonPipeline: closed {self.uri}")

    async def process_item(self, item, spider):
        if self.file is None:
            logger.warning("JsonPipeline: file not open, skipping item")
            return item
        data = dict(item) if hasattr(item, 'items') else item
        line = json.dumps(data, ensure_ascii=False)
        self.file.write(line + '\n')
        return item
