import asyncio
import itertools
from asyncio import PriorityQueue


class SpiderPriorityQueue(PriorityQueue):
    """优先级越大越先出队(与文档一致);同优先级按入队顺序 FIFO。

    内部以 (-priority, 序号, request) 入堆:取负实现大者先出,
    自增序号保证同优先级稳定排序,也避免堆比较落到 Request 对象上。
    """

    def __init__(self, maxsize=0):
        super(SpiderPriorityQueue, self).__init__(maxsize=maxsize)
        self._counter = itertools.count()

    async def put(self, request):
        priority = getattr(request, 'priority', 0) or 0
        await super().put((-priority, next(self._counter), request))

    async def get(self):
        coro = super(SpiderPriorityQueue, self).get()
        try:
            _, _, request = await asyncio.wait_for(coro, timeout=0.1)
            return request
        except asyncio.TimeoutError:
            return None
