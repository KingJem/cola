"""从 Redis 列表读取种子(LPOP 逐条弹出,读空为止)。

种子元素为纯 URL 或 JSON 对象字符串。键名 SEED_REDIS_KEY,
默认 '{PROJECT_NAME}:seeds'。
"""
import json

from cola.datasources.base import SeedProvider
from cola.distributed.connection import get_redis


class RedisSeedProvider(SeedProvider):

    def __init__(self, crawler):
        super().__init__(crawler)
        project = self.settings.get('PROJECT_NAME', 'cola')
        self.key = self.settings.get('SEED_REDIS_KEY') or f'{project}:seeds'
        self.redis = None

    async def open(self):
        self.redis = get_redis(self.settings, decode_responses=True)

    async def seeds(self):
        while True:
            raw = await self.redis.lpop(self.key)
            if raw is None:
                return
            raw = raw.strip()
            if not raw:
                continue
            if raw.startswith('{'):
                try:
                    yield json.loads(raw)
                    continue
                except json.JSONDecodeError:
                    pass
            yield raw

    async def close(self):
        if self.redis:
            await self.redis.aclose()
