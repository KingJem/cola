"""异步 Redis 去重器(redis.asyncio 版 RedisRFPDupeFilter)。

SADD 原子性保证多 worker 并发下同一请求只被一个节点接受。
is_seen 为协程,由引擎 awaitable 分支调用(见 Engine._schedule_request)。
"""
from src.distributed.connection import get_redis
from src.dupefilter import RFPDupeFilter


class AsyncRedisDupeFilter(RFPDupeFilter):

    def __init__(self, redis_client, key: str, *, debug: bool = False,
                 persist: bool = True):
        super().__init__(debug=debug)
        self.redis = redis_client
        self.key = key
        self.persist = persist

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        project = settings.get('PROJECT_NAME', 'cola')
        key = settings.get('REDIS_DUPEFILTER_KEY') or f'{project}:dupefilter'
        return cls(
            redis_client=get_redis(settings),
            key=key,
            debug=settings.getbool('DUPEFILTER_DEBUG', False),
            persist=settings.getbool('REDIS_DUPEFILTER_PERSIST', True),
        )

    async def is_seen(self, request) -> bool:
        fingerprint = self.request_fingerprint(request)
        added = await self.redis.sadd(self.key, fingerprint)
        return not bool(added)

    def mark_seen(self, request):
        """is_seen 的 SADD 已完成标记,保持空实现。"""

    async def flush(self):
        await self.redis.delete(self.key)

    async def close(self):
        if not self.persist:
            await self.redis.delete(self.key)
        await self.redis.aclose()

    def __len__(self):
        raise TypeError('AsyncRedisDupeFilter 不支持同步 len(),请用 scard')
