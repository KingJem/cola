"""StatsExporter:周期性把爬虫运行指标快照导出,供外部(colad/Grafana)观测。

与 HotConfig 对称——一个订阅 Redis 收配置,一个周期 push 指标。导出后端可插拔
(STATS_EXPORT_BACKENDS = file,redis,pushgateway,influxdb),见 stats_backends.py。
Grafana 渲染:pushgateway/influxdb 直接对接;file/redis 由 colad 的 /metrics 端点
转 Prometheus 供 pull。

快照含累计量、窗口速率(pages/s、items/s)、队列深度、平均响应时间、成功率。
启用:STATS_EXPORT_ENABLED = True(Crawler 自动挂载),或显式加入 EXTENSIONS。
"""
import asyncio

from cola.event import spider_opened, spider_closed
from cola.extension.stats_backends import build_backends
from cola.utils.log import get_logger


class StatsExporter:

    def __init__(self, crawler):
        self.crawler = crawler
        self.settings = crawler.settings
        self.stats = crawler.stat_collector
        self.interval = self.settings.getfloat('STATS_EXPORT_INTERVAL', 5.0) or 5.0
        self.file = self.settings.get('STATS_EXPORT_FILE')
        project = self.settings.get('PROJECT_NAME', 'cola')
        node = self.settings.get('NODE_NAME') or 'standalone'
        self.project = project
        self.node = node
        self.redis_key = (self.settings.get('STATS_EXPORT_REDIS_KEY')
                          or f'{project}:stats:{node}')
        self.task = None
        self.backends = []
        self._elapsed = 0.0
        self._last = {'responses': 0, 'items': 0}
        self.logger = get_logger(self.__class__.__name__,
                                 self.settings.get('LOG_LEVEL'))

    @classmethod
    def create_instance(cls, crawler):
        o = cls(crawler)
        crawler.subscriber.subscribe(o.spider_opened, event=spider_opened)
        crawler.subscriber.subscribe(o.spider_closed, event=spider_closed)
        return o

    async def spider_opened(self):
        spider_name = self.crawler.spider.name if self.crawler.spider else ''
        base_labels = {'node': self.node, 'project': self.project,
                       'spider': spider_name}
        self.backends = build_backends(
            self.settings, file_path=self.file, redis_key=self.redis_key,
            redis_ttl=int(self.interval * 4) + 10, base_labels=base_labels)
        for backend in self.backends:
            try:
                await backend.open()
            except Exception as exc:
                self.logger.warning(
                    f'StatsExporter 后端 {type(backend).__name__} 打开失败: {exc}')
        self.logger.info(
            f'StatsExporter 后端: '
            f'{[type(b).__name__ for b in self.backends]}')
        self.task = asyncio.create_task(self._loop())

    async def spider_closed(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        # 收尾再导出一次终态快照
        await self._export(final=True)
        for backend in self.backends:
            await backend.close()

    async def _loop(self):
        try:
            while True:
                await asyncio.sleep(self.interval)
                self._elapsed += self.interval
                await self._export()
        except asyncio.CancelledError:
            pass

    def snapshot(self, final=False) -> dict:
        s = self.stats
        get = lambda k, d=0: s.get_value(k, d)  # noqa: E731

        responses = get('response_received_count')
        items = get('item_successful_count')
        d_resp = responses - self._last['responses']
        d_items = items - self._last['items']
        self._last = {'responses': responses, 'items': items}
        interval = self.interval or 1

        req_count = get('downloader/request_count')
        total_time = get('downloader/response_time_total', 0.0)
        avg_time = (total_time / req_count) if req_count else 0.0

        exceptions = sum(v for k, v in s.get_stat().items()
                         if k.startswith('download_exceptions/'))
        total_attempts = responses + exceptions
        success_rate = (responses / total_attempts) if total_attempts else 1.0

        status_codes = {k.split('/')[-1]: v for k, v in s.get_stat().items()
                        if k.startswith('stats_code/count/')}

        scheduler = self.crawler.engine.scheduler if self.crawler.engine else None
        pending = 0
        try:
            pending = len(scheduler) if scheduler is not None else 0
        except TypeError:
            pending = 0  # RedisScheduler 无同步 len
        in_flight = len(self.crawler.engine.task_manager.current_task) \
            if self.crawler.engine else 0

        return {
            'node': self.node,
            'elapsed': round(self._elapsed, 1),
            'final': final,
            'requests_scheduled': get('request_scheduled_count'),
            'responses': responses,
            'items': items,
            'items_discarded': get('item_discard_count'),
            'retries': get('retry_count'),
            'exceptions': exceptions,
            'requests_ignored': get('request_ignored_count'),
            'pages_per_sec': round(d_resp / interval, 2),
            'items_per_sec': round(d_items / interval, 2),
            'avg_response_time': round(avg_time, 3),
            'max_response_time': round(get('downloader/response_time_max', 0.0), 3),
            'success_rate': round(success_rate, 4),
            'pending_requests': pending,
            'in_flight': in_flight,
            'concurrency_limit': self.crawler.engine.task_manager.limit
            if self.crawler.engine else 0,
            'status_codes': status_codes,
        }

    async def _export(self, final=False):
        snap = self.snapshot(final=final)
        for backend in self.backends:
            try:
                await backend.export(snap)
            except Exception as exc:
                self.logger.warning(
                    f'StatsExporter 后端 {type(backend).__name__} 导出失败: {exc}')
