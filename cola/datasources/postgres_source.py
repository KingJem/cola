"""从 PostgreSQL 读取种子(asyncpg 游标流式读取)。

POSTGRES_DSN 必填,如 postgresql://user:pass@host:5432/db;
SEED_SQL 结果行须含 url 列,其余列进 meta。
"""
from cola.datasources.base import SeedProvider


class PostgresSeedProvider(SeedProvider):

    def __init__(self, crawler):
        super().__init__(crawler)
        self.sql = self.settings.get('SEED_SQL')
        self.dsn = self.settings.get('POSTGRES_DSN')
        if not self.sql:
            raise ValueError('PostgresSeedProvider 需要配置 SEED_SQL')
        if not self.dsn:
            raise ValueError('PostgresSeedProvider 需要配置 POSTGRES_DSN')
        self.conn = None

    async def open(self):
        try:
            import asyncpg
        except ImportError as exc:
            raise RuntimeError(
                "PostgresSeedProvider 需要 asyncpg,"
                "安装:pip install 'cola[postgres]'") from exc
        self.conn = await asyncpg.connect(self.dsn)

    async def seeds(self):
        async with self.conn.transaction():
            async for record in self.conn.cursor(self.sql):
                yield dict(record)

    async def close(self):
        if self.conn:
            await self.conn.close()
