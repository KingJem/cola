"""从 Apache Doris 读取种子。

Doris FE 兼容 MySQL 协议(默认查询端口 9030),直接复用 MySQL 数据源,
仅连接参数改用 DORIS_* 配置。
"""
from cola.datasources.mysql_source import MySQLSeedProvider


class DorisSeedProvider(MySQLSeedProvider):

    settings_prefix = 'DORIS'

    def _conn_kwargs(self):
        kwargs = super()._conn_kwargs()
        if not self.settings.get('DORIS_PORT'):
            kwargs['port'] = 9030
        return kwargs
