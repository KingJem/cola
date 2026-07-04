"""Redis ZSET 优先级队列。

score = -priority,BZPOPMIN 弹出 score 最小者,即 priority 最大者最先出队,
与文档语义(priority 越大越优先)一致。member 为排序后的请求 JSON,
完全相同的请求天然合并(去重器在入队前已过滤,此处只是兜底)。
"""
from typing import Optional


class RedisPriorityQueue:

    def __init__(self, redis, key: str, *, poll_timeout: float = 0.1):
        self.redis = redis
        self.key = key
        self.poll_timeout = poll_timeout

    async def push(self, raw: str, priority: int = 0):
        await self.redis.zadd(self.key, {raw: -priority})

    async def pop(self) -> Optional[bytes]:
        """空队列时最多阻塞 poll_timeout 秒后返回 None(与内存队列语义一致)。"""
        result = await self.redis.bzpopmin(self.key, timeout=self.poll_timeout)
        if result is None:
            return None
        _key, member, _score = result
        return member

    async def qsize(self) -> int:
        return int(await self.redis.zcard(self.key))

    async def clear(self):
        await self.redis.delete(self.key)
