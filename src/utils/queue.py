import asyncio
from asyncio import PriorityQueue


class SpiderPriorityQueue(PriorityQueue):

    def __init__(self, maxsize=0):
        super(SpiderPriorityQueue, self).__init__(maxsize=maxsize)

    async def get(self):
        # if self.empty():
        #     return None
        # else:
        #     return await super().get()
        coro = super(SpiderPriorityQueue, self).get()

        try:
            return await asyncio.wait_for(coro, timeout=0.1)
        except asyncio.TimeoutError:
            return None
