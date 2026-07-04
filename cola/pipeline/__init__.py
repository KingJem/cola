"""
Item Pipeline 管理器。

ITEM_PIPELINES 配置格式：
    {
        'path.to.MyPipeline': 300,   # 数字为优先级，升序执行
        'cola.pipeline.json_pipeline.JsonPipeline': 800,
    }
"""
import inspect
from typing import List, Optional

from loguru import logger

from cola import event
from cola.pipeline.base import BasePipeline, DropItem
from cola.utils import load_class


async def _call_maybe_async(method, *args):
    if inspect.iscoroutinefunction(method):
        return await method(*args)
    return method(*args)


class PipelineManager:

    def __init__(self, crawler):
        self.crawler = crawler
        self.pipelines: List[BasePipeline] = []
        self._load()

    @classmethod
    def create_instance(cls, crawler):
        return cls(crawler)

    def _load(self):
        setting = self.crawler.settings.get('ITEM_PIPELINES', {})
        if not setting:
            return

        sorted_pipelines = sorted(setting.items(), key=lambda x: x[1])
        enabled = []
        for class_path, priority in sorted_pipelines:
            try:
                cls = load_class(class_path)
                if hasattr(cls, 'create_instance'):
                    instance = cls.create_instance(self.crawler)
                else:
                    instance = cls()
                self.pipelines.append(instance)
                enabled.append(f"  {priority:4d} {class_path}")
            except Exception as e:
                logger.error(f"Failed to load pipeline {class_path}: {e}")

        if enabled:
            logger.info("Enabled item pipelines:\n" + "\n".join(enabled))

    async def open_spider(self, spider):
        for pipeline in self.pipelines:
            if hasattr(pipeline, 'open_spider'):
                await _call_maybe_async(pipeline.open_spider, spider)

    async def close_spider(self, spider):
        for pipeline in self.pipelines:
            if hasattr(pipeline, 'close_spider'):
                await _call_maybe_async(pipeline.close_spider, spider)

    async def process_item(self, item, spider) -> Optional[object]:
        """
        依次通过所有 Pipeline 处理 item。
        若某 Pipeline 抛出 DropItem，停止链并返回 None。
        成功/丢弃分别派发 item_successful / item_discard 事件(供 LogStats)。
        """
        subscriber = getattr(self.crawler, 'subscriber', None)
        for pipeline in self.pipelines:
            try:
                item = await _call_maybe_async(pipeline.process_item, item, spider)
            except DropItem as e:
                logger.info(f"Item dropped by {type(pipeline).__name__}: {e}")
                if subscriber is not None:
                    await subscriber.notify(event.item_discard, item, e, spider)
                return None
        if subscriber is not None:
            await subscriber.notify(event.item_successful, item, spider)
        return item
