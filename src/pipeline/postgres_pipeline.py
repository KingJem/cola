"""PostgresPipeline:Item 批量 INSERT 到 PostgreSQL 表(asyncpg)。

配置:
    ITEM_PIPELINES = {'src.pipeline.postgres_pipeline.PostgresPipeline': 300}
    POSTGRES_DSN = 'postgresql://user:pass@host:5432/db'
    POSTGRES_TABLE = 'results'
    POSTGRES_BATCH_SIZE = 100
"""
from loguru import logger

from src.pipeline.base import BasePipeline


class PostgresPipeline(BasePipeline):

    def __init__(self, settings):
        self.settings = settings
        self.dsn = settings.get('POSTGRES_DSN')
        self.table = settings.get('POSTGRES_TABLE')
        if not self.dsn:
            raise ValueError('PostgresPipeline 需要配置 POSTGRES_DSN')
        if not self.table:
            raise ValueError('PostgresPipeline 需要配置 POSTGRES_TABLE')
        self.batch_size = settings.getint('POSTGRES_BATCH_SIZE', 100) or 100
        self.buffer = []
        self.columns = None
        self.pool = None

    @classmethod
    def create_instance(cls, crawler):
        return cls(crawler.settings)

    async def open_spider(self, spider):
        try:
            import asyncpg
        except ImportError as exc:
            raise RuntimeError(
                "PostgresPipeline 需要 asyncpg,"
                "安装:pip install 'cola[postgres]'") from exc
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=4)
        logger.info(
            f"PostgresPipeline: writing to table {self.table} "
            f"(batch={self.batch_size})")

    async def close_spider(self, spider):
        if self.pool is None:
            return
        try:
            await self._flush()
        finally:
            await self.pool.close()

    async def process_item(self, item, spider):
        data = dict(item) if hasattr(item, 'items') else item
        if self.columns is None:
            self.columns = list(data.keys())
        self.buffer.append([data.get(col) for col in self.columns])
        if len(self.buffer) >= self.batch_size:
            await self._flush()
        return item

    async def _flush(self):
        if not self.buffer:
            return
        rows, self.buffer = self.buffer, []
        cols = ', '.join(f'"{c}"' for c in self.columns)
        marks = ', '.join(f'${i + 1}' for i in range(len(self.columns)))
        sql = f'INSERT INTO "{self.table}" ({cols}) VALUES ({marks})'
        try:
            async with self.pool.acquire() as conn:
                await conn.executemany(sql, rows)
        except Exception as exc:
            logger.error(f"PostgresPipeline: 批量写入失败,丢弃 {len(rows)} 条: {exc}")
