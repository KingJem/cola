"""MySQLPipeline:Item 批量 INSERT 到 MySQL 表。

列名取自 Item 的键,目标表需预先建好。攒批 MYSQL_BATCH_SIZE 条后
executemany 写入,爬虫结束时刷出余量。

配置:
    ITEM_PIPELINES = {'src.pipeline.mysql_pipeline.MySQLPipeline': 300}
    MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DB
    MYSQL_TABLE = 'results'
    MYSQL_BATCH_SIZE = 100
"""
from loguru import logger

from src.pipeline.base import BasePipeline


class MySQLPipeline(BasePipeline):

    settings_prefix = 'MYSQL'
    # INSERT 动词,Doris 等方言可覆写(如 INSERT IGNORE 不被 Doris 支持)
    insert_verb = 'INSERT'

    def __init__(self, settings):
        self.settings = settings
        p = self.settings_prefix
        self.table = settings.get(f'{p}_TABLE')
        if not self.table:
            raise ValueError(f'{self.__class__.__name__} 需要配置 {p}_TABLE')
        self.batch_size = settings.getint(f'{p}_BATCH_SIZE', 100) or 100
        self.buffer = []
        self.columns = None
        self.pool = None

    @classmethod
    def create_instance(cls, crawler):
        return cls(crawler.settings)

    def _conn_kwargs(self):
        p = self.settings_prefix
        return dict(
            host=self.settings.get(f'{p}_HOST', 'localhost'),
            port=self.settings.getint(f'{p}_PORT', 3306),
            user=self.settings.get(f'{p}_USER', 'root'),
            password=self.settings.get(f'{p}_PASSWORD', '') or '',
            db=self.settings.get(f'{p}_DB'),
            autocommit=True,
        )

    async def open_spider(self, spider):
        try:
            import aiomysql
        except ImportError as exc:
            raise RuntimeError(
                f"{self.__class__.__name__} 需要 aiomysql,"
                f"安装:pip install 'cola[mysql]'") from exc
        self.pool = await aiomysql.create_pool(
            minsize=1, maxsize=4, **self._conn_kwargs())
        logger.info(
            f"{self.__class__.__name__}: writing to table {self.table} "
            f"(batch={self.batch_size})")

    async def close_spider(self, spider):
        if self.pool is None:
            return
        try:
            await self._flush()
        finally:
            self.pool.close()
            await self.pool.wait_closed()

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
        cols = ', '.join(f'`{c}`' for c in self.columns)
        marks = ', '.join(['%s'] * len(self.columns))
        sql = f'{self.insert_verb} INTO `{self.table}` ({cols}) VALUES ({marks})'
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.executemany(sql, rows)
        except Exception as exc:
            logger.error(
                f"{self.__class__.__name__}: 批量写入失败,丢弃 {len(rows)} 条: {exc}")
