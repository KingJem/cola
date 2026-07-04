"""StatsExporter:周期性把爬虫运行指标快照导出,供外部(colad)观测。

与 HotConfig 对称——一个订阅 Redis 收配置,一个周期 push 指标。快照写到:
- STATS_EXPORT_FILE:每周期 append 一行 JSON(colad 单机任务读此文件)
- Redis(可选):SET {PROJECT_NAME}:stats:{NODE_NAME} 供 master 汇总多节点

快照含累计量、窗口速率(pages/s、items/s)、队列深度、平均响应时间、成功率。
启用:STATS_EXPORT_ENABLED = True(Crawler 自动挂载),或显式加入 EXTENSIONS。
"""
import asyncio
import json
from pathlib import Path

from src.event import spider_opened, spider_closed
from src.utils.log import get_logger


class StatsExporter:

    def __init__(self, crawler):
        self.crawler = crawler
        self.settings = crawler.settings
        self.stats = crawler.stat_collector
        self.interval = self.settings.getfloat('STATS_EXPORT_INTERVAL', 5.0) or 5.0
        self.file = self.settings.get('STATS_EXPORT_FILE')
        project = self.settings.get('PROJECT_NAME', 'cola')
        node = self.settings.get('NODE_NAME') or 'standalone'
        self.redis_key = (self.settings.get('STATS_EXPORT_REDIS_KEY')
                          or f'{project}:stats:{node}')
        self.node = node
        self.task = None
        self.redis = None
        self._elapsed = 0.0
        self._last = {'responses': 0, 'items': 0}
        self.logger = get_logger(self.__class__.__name__,
                                 self.settings.get('LOG_LEVEL'))
        if self.file:
            Path(self.file).parent.mkdir(parents=True, exist_ok=True)
            # 覆盖旧文件,避免重跑任务时历史串味
            Path(self.file).write_text('', encoding='utf-8')

    @classmethod
    def create_instance(cls, crawler):
        o = cls(crawler)
        crawler.subscriber.subscribe(o.spider_opened, event=spider_opened)
        crawler.subscriber.subscribe(o.spider_closed, event=spider_closed)
        return o

    async def spider_opened(self):
        if self.settings.get('STATS_EXPORT_REDIS_KEY') is not None \
                or self.settings.get('NODE_ROLE', 'standalone') != 'standalone':
            try:
                from src.distributed.connection import get_redis
                self.redis = get_redis(self.settings, decode_responses=True)
            except Exception as exc:
                self.logger.warning(f'StatsExporter Redis 不可用: {exc}')
        self.task = asyncio.create_task(self._loop())

    async def spider_closed(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        # 收尾再导出一次终态快照
        await self._export(final=True)
        if self.redis:
            try:
                await self.redis.aclose()
            except Exception:
                pass

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
        line = json.dumps(snap, ensure_ascii=False)
        if self.file:
            try:
                with open(self.file, 'a', encoding='utf-8') as fh:
                    fh.write(line + '\n')
            except OSError as exc:
                self.logger.warning(f'StatsExporter 写文件失败: {exc}')
        if self.redis:
            try:
                ttl = int(self.interval * 4) + 10
                await self.redis.set(self.redis_key, line, ex=ttl)
            except Exception as exc:
                self.logger.warning(f'StatsExporter 写 Redis 失败: {exc}')
