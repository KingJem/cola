import asyncio
import signal
from datetime import datetime
from signal import SIGINT
from typing import Type, Final, Set, Optional

from src.core.engine import Engine
from src.settings.settings_manager import SettingsManager
from src.spiders import Spider
from src.stats_collector import StatsCollector


class Crawler:
    def __init__(self, spider_cls, settings):
        self.spider_cls = spider_cls
        self.spider: Optional[Spider] = None
        self.engine: Optional[Engine] = None
        self.settings: SettingsManager = settings.copy()
        self.stat_collector: Optional[StatsCollector] = None

    def create_spider(self) -> Spider:
        spider = self.spider_cls.create_instance(self)
        self._set_spider()
        return spider

    def create_engine(self) -> Engine:
        engine = Engine(self)
        return engine

    def create_stat_collector(self) -> StatsCollector:
        collector = StatsCollector(self.settings)
        collector['start_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return collector

    async def crawl(self):
        self.engine = self.create_engine()
        self.spider = self.create_spider()
        if hasattr(self.spider, 'custom_settings'):
            custom_settings = getattr(self.spider, 'custom_settings', {})
            self.settings.update(custom_settings)
        self.stat_collector = self.create_stat_collector()
        await self.engine.start_spider(self.spider)

    def _set_spider(self):
        self.merge_settings()

    def merge_settings(self):
        if hasattr(self, 'custom_settings'):
            custom_settings = getattr(self, 'custom_settings', None)
            self.settings.update_values(custom_settings)

    async def close(self, reason='finished'):
        self.stat_collector['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.stat_collector.close_spider(self.spider, reason)


class CrawlerProcess:

    def __init__(self, settings: None):
        self.settings = settings
        self.crawlers: Final[Set] = set()
        self._active: Final[Set] = set()
        signal.signal(SIGINT, self.shutdown)

    async def crawl(self, spider: Type[Spider]):
        crawler: Crawler = self.create_crawler(spider)
        self.crawlers.add(crawler)
        task = await self._crawl(crawler)
        self._active.add(task)

    def create_crawler(self, spider_cls) -> Crawler:
        crawler = Crawler(spider_cls, self.settings)
        return crawler

    @staticmethod
    async def _crawl(crawler: Crawler):
        return asyncio.create_task(crawler.crawl())

    async def start(self):
        await asyncio.gather(*self._active)

    def shutdown(self, signum, frame):
        for crawler in self.crawlers:
            crawler.engine.running = False
            crawler.stat_collector['reason'] = 'shutdown'
