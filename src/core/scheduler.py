import asyncio
from typing import Optional

from src.utils.queue import SpiderPriorityQueue


class Scheduler:

    def __init__(self,crawler):
        self.request_queue: Optional[SpiderPriorityQueue] = None
        self.request_queue = SpiderPriorityQueue()
        self.crawler = crawler


    async def next_request(self):
        request = await self.request_queue.get()
        return request

    async def enqueue_request(self, request):
        await self.request_queue.put(request)
        self.crawler.stat_collector.inc_value('scheduled.enqueued.requests.count', 1)

    def __len__(self):
        return self.request_queue.qsize()

    def idle(self):
        return self.request_queue.qsize() == 0
