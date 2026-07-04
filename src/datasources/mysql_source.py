"""从 MySQL 读取种子。

SEED_SQL 必填,如:SELECT url, category FROM seeds WHERE status = 0
结果行须含 url 列,其余列自动进入 request.meta。
使用服务端游标(SSCursor)流式读取,大表不占内存。
"""
from src.datasources.base import SeedProvider


class MySQLSeedProvider(SeedProvider):

    # 子类(Doris)覆写此前缀以复用连接逻辑
    settings_prefix = 'MYSQL'

    def __init__(self, crawler):
        super().__init__(crawler)
        self.sql = self.settings.get('SEED_SQL')
        if not self.sql:
            raise ValueError(f'{self.__class__.__name__} 需要配置 SEED_SQL')
        self.conn = None

    def _conn_kwargs(self):
        p = self.settings_prefix
        return dict(
            host=self.settings.get(f'{p}_HOST', 'localhost'),
            port=self.settings.getint(f'{p}_PORT', 3306),
            user=self.settings.get(f'{p}_USER', 'root'),
            password=self.settings.get(f'{p}_PASSWORD', '') or '',
            db=self.settings.get(f'{p}_DB'),
        )

    async def open(self):
        try:
            import aiomysql
        except ImportError as exc:
            raise RuntimeError(
                f"{self.__class__.__name__} 需要 aiomysql,"
                f"安装:pip install 'cola[mysql]'") from exc
        self._aiomysql = aiomysql
        self.conn = await aiomysql.connect(**self._conn_kwargs())

    async def seeds(self):
        async with self.conn.cursor(self._aiomysql.SSDictCursor) as cursor:
            await cursor.execute(self.sql)
            while True:
                row = await cursor.fetchone()
                if row is None:
                    return
                yield dict(row)

    async def close(self):
        if self.conn:
            self.conn.close()
