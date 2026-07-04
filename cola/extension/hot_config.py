"""热配置扩展:通过 Redis Pub/Sub 在运行时更新 settings。

订阅两个频道:
  {PROJECT_NAME}:config           项目级(该项目所有爬虫)
  {PROJECT_NAME}:{spider}:config  爬虫级

消息为 JSON 对象,逐键写入 settings;CONCURRENT_REQUESTS 会同步调整
TaskManager 并发上限,DOWNLOAD_DELAY 由中间件每次请求动态读取即时生效。

启用方式:HOT_CONFIG_ENABLED = True(Crawler 自动挂载本扩展)。
"""
import asyncio
import json

from loguru import logger

from cola import event
from cola.distributed.connection import get_redis


class HotConfig:

    def __init__(self, crawler):
        self.crawler = crawler
        self.settings = crawler.settings
        project = self.settings.get('PROJECT_NAME', 'cola')
        base_channel = self.settings.get('HOT_CONFIG_CHANNEL') or f'{project}:config'
        spider_name = crawler.spider.name if crawler.spider else None
        self.channels = [base_channel]
        if spider_name:
            self.channels.append(f'{project}:{spider_name}:config')
        self.redis = None
        self.pubsub = None
        self.task = None

    @classmethod
    def create_instance(cls, crawler):
        o = cls(crawler)
        crawler.subscriber.subscribe(o.spider_opened, event=event.spider_opened)
        crawler.subscriber.subscribe(o.spider_closed, event=event.spider_closed)
        return o

    async def spider_opened(self):
        self.redis = get_redis(self.settings, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(*self.channels)
        self.task = asyncio.create_task(self._listen())
        logger.info(f"HotConfig listening on channels: {self.channels}")

    async def spider_closed(self):
        if self.task:
            self.task.cancel()
        if self.pubsub:
            try:
                await self.pubsub.aclose()
            except Exception:
                pass
        if self.redis:
            try:
                await self.redis.aclose()
            except Exception:
                pass

    async def _listen(self):
        try:
            async for message in self.pubsub.listen():
                if message.get('type') != 'message':
                    continue
                try:
                    updates = json.loads(message['data'])
                    if not isinstance(updates, dict):
                        raise ValueError('config payload must be a JSON object')
                except (json.JSONDecodeError, ValueError) as exc:
                    logger.error(f"HotConfig 收到非法配置消息: {exc}")
                    continue
                self.apply(updates)
        except asyncio.CancelledError:
            pass

    def apply(self, updates: dict):
        for key, value in updates.items():
            old = self.settings.get(key)
            self.settings.set(key, value)
            logger.info(f"HotConfig applied: {key} = {value!r} (was {old!r})")
            if key == 'CONCURRENT_REQUESTS':
                engine = self.crawler.engine
                if engine and engine.task_manager:
                    engine.task_manager.resize(value)
