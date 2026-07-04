"""共享 Redis 请求队列的调度器,与内存 Scheduler 同接口。

空闲语义:内存调度器队列一空即 idle;分布式场景下队列短暂为空不代表任务结束
(其他节点可能正要回填),因此 idle() 仅在队列连续为空超过
SCHEDULER_IDLE_TIMEOUT 秒后才为 True;0 表示永不空闲退出(常驻 worker)。
"""
import time
from typing import Optional

from loguru import logger

from src.distributed.connection import get_redis
from src.distributed.queue import RedisPriorityQueue
from src.distributed.serialize import request_to_json, request_from_json


class RedisScheduler:

    def __init__(self, crawler):
        self.crawler = crawler
        settings = crawler.settings
        project = settings.get('PROJECT_NAME', 'cola')
        self.queue_key = settings.get('SCHEDULER_QUEUE_KEY') or f'{project}:requests'
        self.idle_timeout = settings.getfloat('SCHEDULER_IDLE_TIMEOUT', 10.0)
        self.persist = settings.getbool('SCHEDULER_PERSIST', True)
        self.flush_on_start = settings.getbool('SCHEDULER_FLUSH_ON_START', False)
        self.poll_timeout = settings.getfloat('SCHEDULER_POLL_TIMEOUT', 0.5) or 0.5
        self.redis = None
        self.queue: Optional[RedisPriorityQueue] = None
        self._empty_since: Optional[float] = None

    async def open(self):
        self.redis = get_redis(self.crawler.settings)
        self.queue = RedisPriorityQueue(
            self.redis, self.queue_key, poll_timeout=self.poll_timeout)
        if self.flush_on_start:
            await self.queue.clear()
            logger.info(f"RedisScheduler flushed queue {self.queue_key}")
        logger.info(
            f"RedisScheduler ready: queue={self.queue_key} "
            f"idle_timeout={self.idle_timeout}s")

    async def enqueue_request(self, request):
        raw = request_to_json(request, self.crawler.spider)
        await self.queue.push(raw, request.priority)
        self._empty_since = None
        self.crawler.stat_collector.inc_value('scheduled.enqueued.requests.count', 1)

    async def next_request(self):
        raw = await self.queue.pop()
        if raw is None:
            if self._empty_since is None:
                self._empty_since = time.monotonic()
            return None
        self._empty_since = None
        return request_from_json(raw, self.crawler.spider)

    def idle(self) -> bool:
        if self._empty_since is None:
            return False
        if self.idle_timeout <= 0:
            return False
        return time.monotonic() - self._empty_since >= self.idle_timeout

    async def close(self):
        if self.redis is None:
            return
        if not self.persist:
            await self.queue.clear()
        await self.redis.aclose()
