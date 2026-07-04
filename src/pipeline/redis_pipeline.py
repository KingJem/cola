"""RedisPipeline:Item 序列化为 JSON 后 RPUSH 到 Redis 列表。

配置:
    ITEM_PIPELINES = {'src.pipeline.redis_pipeline.RedisPipeline': 300}
    REDIS_URL = 'redis://host:6379/0'
    REDIS_ITEMS_KEY = None  # 默认 '{PROJECT_NAME}:items'
"""
import json

from loguru import logger

from src.distributed.connection import get_redis
from src.pipeline.base import BasePipeline


class RedisPipeline(BasePipeline):

    def __init__(self, settings):
        self.settings = settings
        project = settings.get('PROJECT_NAME', 'cola')
        self.key = settings.get('REDIS_ITEMS_KEY') or f'{project}:items'
        self.redis = None

    @classmethod
    def create_instance(cls, crawler):
        return cls(crawler.settings)

    async def open_spider(self, spider):
        self.redis = get_redis(self.settings)
        logger.info(f"RedisPipeline: pushing items to {self.key}")

    async def close_spider(self, spider):
        if self.redis:
            await self.redis.aclose()

    async def process_item(self, item, spider):
        data = dict(item) if hasattr(item, 'items') else item
        await self.redis.rpush(self.key, json.dumps(data, ensure_ascii=False))
        return item
