"""DorisPipeline:经 MySQL 协议批量写入 Apache Doris。

Doris FE 兼容 MySQL 协议(查询端口默认 9030),复用 MySQLPipeline,
连接参数改用 DORIS_* 配置。目标表建议为 Duplicate/Unique Key 模型。

配置:
    ITEM_PIPELINES = {'src.pipeline.doris_pipeline.DorisPipeline': 300}
    DORIS_HOST / DORIS_PORT(默认 9030)/ DORIS_USER / DORIS_PASSWORD / DORIS_DB
    DORIS_TABLE = 'results'
    DORIS_BATCH_SIZE = 100
"""
from src.pipeline.mysql_pipeline import MySQLPipeline


class DorisPipeline(MySQLPipeline):

    settings_prefix = 'DORIS'

    def _conn_kwargs(self):
        kwargs = super()._conn_kwargs()
        if not self.settings.get('DORIS_PORT'):
            kwargs['port'] = 9030
        return kwargs
