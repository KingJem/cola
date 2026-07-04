"""Processor:spider 输出(Request / Item / dict)的独立消费者。

之前 enqueue() 内联跑完整个队列,pipeline 慢会拖住解析循环;
现在由后台任务持续消费,enqueue 只入队(有界队列,满时自然反压)。
"""
import asyncio
from asyncio.queues import Queue
from typing import Any, Optional, Union

from loguru import logger

from src.core.request import Request
from src.item.items import Item


class Processor:
    def __init__(self, crawler):
        self.crawler = crawler
        maxsize = crawler.settings.getint('PROCESSOR_QUEUE_SIZE', 128) or 0
        self.queue: Queue = Queue(maxsize=maxsize)
        self._consumer: Optional[asyncio.Task] = None
        self._busy = False

    def open(self):
        self._consumer = asyncio.create_task(self._consume())

    async def _consume(self) -> Any:
        while True:
            result = await self.queue.get()
            self._busy = True
            try:
                if isinstance(result, Request):
                    await self.crawler.engine.enqueue_requests(result)
                else:
                    await self._process_item(result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(f'Processor 处理输出失败: {exc}')
            finally:
                self._busy = False
                self.queue.task_done()

    async def _process_item(self, item: Any) -> Any:
        spider = self.crawler.spider
        pipeline_manager = getattr(self.crawler, 'pipeline_manager', None)
        if pipeline_manager is not None:
            await pipeline_manager.process_item(item, spider)
        return item

    async def enqueue(self, output: Union[Request, Item, dict]) -> Any:
        await self.queue.put(output)

    def idle(self):
        return len(self) == 0 and not self._busy

    async def close(self):
        if self._consumer is None:
            return
        # 引擎在所有组件空闲后才关闭,此处队列理应已空;join 兜底排空
        await self.queue.join()
        self._consumer.cancel()
        await asyncio.gather(self._consumer, return_exceptions=True)

    def __len__(self):
        return self.queue.qsize()
