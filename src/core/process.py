from asyncio.queues import Queue
from typing import Any, Union

from src.core.request import Request
from src.item.items import Item


class Processor:
    def __init__(self, crawler):
        self.queue = Queue()
        self.crawler = crawler

    async def process(self) -> Any:
        while not self.idle():
            result = await self.queue.get()
            if isinstance(result, Request):
                await self.crawler.engine.enqueue_requests(result)
            else:
                # Item 或 dict
                await self._process_item(result)

    async def _process_item(self, item: Any) -> Any:
        spider = self.crawler.spider
        pipeline_manager = getattr(self.crawler, 'pipeline_manager', None)
        if pipeline_manager is not None:
            await pipeline_manager.process_item(item, spider)
        return item

    async def enqueue(self, output: Union[Request, Item, dict]) -> Any:
        await self.queue.put(output)
        await self.process()

    def idle(self):
        return len(self) == 0

    def __len__(self):
        return self.queue.qsize()
