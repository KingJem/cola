import asyncio
import signal
from datetime import datetime
from signal import SIGINT
from typing import Type, Final, Set, Optional

from src import event
from src.core.engine import Engine
from src.settings.settings_manager import SettingsManager
from src.spiders import Spider
from src.stats_collector import StatsCollector
from src.subscriber import Subscriber

HOT_CONFIG_EXTENSION = 'src.extension.hot_config.HotConfig'


class Crawler:
    def __init__(self, spider_cls, settings):
        self.spider_cls = spider_cls
        self.spider: Optional[Spider] = None
        self.engine: Optional[Engine] = None
        self.settings: SettingsManager = settings.copy()
        self.stat_collector: Optional[StatsCollector] = None
        self.pipeline_manager = None
        self.subscriber = Subscriber()
        self.extension_manager = None

    @property
    def stats(self):
        """扩展(LogStats/LogInterval)通过 crawler.stats 访问统计收集器。"""
        return self.stat_collector

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
            # 爬虫级配置低于运行时传入的配置(平台/CLI 下发的必须生效)
            from src.settings.settings_manager import PRIORITY_SPIDER
            self.settings.update_values(custom_settings,
                                        priority=PRIORITY_SPIDER)
        self.stat_collector = self.create_stat_collector()
        self._setup_log_file()
        self._load_extensions()
        from src.pipeline import PipelineManager
        self.pipeline_manager = PipelineManager(self)
        await self.pipeline_manager.open_spider(self.spider)
        await self.subscriber.notify(event.spider_opened)
        await self.engine.start_spider(self.spider)

    def _setup_log_file(self):
        log_file = self.settings.get('LOG_FILE')
        if not log_file:
            return
        from loguru import logger
        logger.add(log_file,
                   level=self.settings.get('LOG_LEVEL') or 'INFO',
                   encoding='utf-8', enqueue=True)

    def _load_extensions(self):
        extensions = list(self.settings.getlist('EXTENSIONS') or [])
        if (self.settings.getbool('HOT_CONFIG_ENABLED')
                and HOT_CONFIG_EXTENSION not in extensions):
            extensions.append(HOT_CONFIG_EXTENSION)
        self.settings.set('EXTENSIONS', extensions)
        from src.extension import ExtensionManager
        self.extension_manager = ExtensionManager(self)

    def _set_spider(self):
        self.merge_settings()

    def merge_settings(self):
        if hasattr(self, 'custom_settings'):
            custom_settings = getattr(self, 'custom_settings', None)
            self.settings.update_values(custom_settings)

    async def close(self, reason='finished'):
        # 先排空爬取期间派发的事件(item_successful 等),再收尾统计
        await self.subscriber.drain()
        await self.subscriber.notify(event.spider_closed)
        await self.subscriber.drain()
        if self.pipeline_manager:
            await self.pipeline_manager.close_spider(self.spider)
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
