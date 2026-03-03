import asyncio
import inspect
from typing import Optional, Generator, Callable, Union, AsyncGenerator

from loguru import logger

from src.core.process import Processor
from src.core.request import Request
from src.core.scheduler import Scheduler
from src.downloaders import Downloader
from src.item.items import Item
from src.task_manager import TaskManager
from src.utils import load_class


class Engine:

    def __init__(self, crawler):
        self.downloader: Optional[Downloader] = None
        self.spider = None
        self.crawler = crawler
        self.settings = crawler.settings
        self.start_requests: Optional[Generator] = None
        self.scheduler: Optional[Scheduler] = None
        self.processor: Optional[Processor] = None
        self.running = False
        self.task_manager = TaskManager(self.settings)
        self.logger = logger

    async def start_spider(self, spider):
        self.logger.info("Cola is starting...")
        self.logger.info("Current Project: {}".format(self.settings.get('PROJECT_NAME')))
        self.logger.info(f"Concurrent Requests: {self.settings.get('CONCURRENT_REQUESTS')}")
        self.spider = spider
        self.running = True
        self.scheduler = Scheduler(self.crawler)
        self.processor = Processor(self.crawler)
        self.downloader = self.get_downloader()
        self.start_requests = iter(spider.start_requests())
        await self.open_spider()

    def get_downloader(self):
        downloader: str = self.settings.get('DOWNLOADER_CLASS')
        downloader_cls = load_class(downloader)
        if not issubclass(downloader_cls, Downloader):
            raise NotImplementedError(f"Downloader {downloader_cls}is not a subclass of {Downloader}")
        self.logger.info(f"Current downloader is: {downloader}")
        return downloader_cls.create_instance(self.crawler)

    async def open_spider(self):
        await self.open()
        crawling = asyncio.create_task(self.crawl())
        await crawling

    async def crawl(self):
        while self.running:
            request = await self._get_next_request()
            if request:
                await self._crawl(request)
            else:
                try:
                    start_request = next(self.start_requests)  # noqa
                    await self.enqueue_requests(start_request)
                except StopIteration:
                    self.start_requests = None
                    if self._exit():
                        break
                except Exception as e:
                    logger.error(f"Error getting start request: {e}")
                    if self._exit():
                        break
        if not self.running:
            await self.close()

    async def _crawl(self, request):
        async def crawl_task():
            outputs = await self._fetch(request)
            if outputs:
                await self._handle_spider_outputs(outputs)

        await self.task_manager.sem.acquire()
        self.task_manager.create_task(crawl_task())

    @staticmethod
    async def _transform(func_result) -> [Generator, AsyncGenerator]:
        if inspect.isgenerator(func_result):
            for r in func_result:
                yield r
        elif inspect.isasyncgen(func_result):
            async for r in func_result:
                yield r
        else:
            raise Exception('TypeError')

    async def _fetch(self, request) -> [Generator, AsyncGenerator]:
        async def _success(_response):
            callback: Callable = request.callback or self.spider.parse
            _outputs = callback(_response)
            if _outputs:
                if inspect.iscoroutine(_outputs):
                    await _outputs
                else:
                    return self._transform(_outputs)

        _response = await self.downloader.fetch(request)
        if _response is None:
            logger.warning(f"Download failed for {request.url}, skipping")
            return None
        outputs = await _success(_response)
        return outputs

    async def enqueue_requests(self, request):
        await self._schedule_request(request)

    async def _schedule_request(self, request):
        # todo 去重
        await self.scheduler.enqueue_request(request)

    async def _get_next_request(self):
        return await self.scheduler.next_request()

    async def _handle_spider_outputs(self, outputs):
        from collections.abc import MutableMapping
        async for output in outputs:
            if isinstance(output, Request):
                await self.processor.enqueue(output)
            elif isinstance(output, MutableMapping) and hasattr(output, 'FIELDS'):
                # item 实例检查（通过MutableMapping基类和FIELDS属性来判断）
                await self.processor.enqueue(output)
            elif isinstance(output, dict):
                # 支持直接返回字典
                logger.debug(f"Spider yielded dict: {output}")
            else:
                # 其他类型也记录但不抛出异常
                logger.warning(f"Spider yielded unsupported type {type(output)}: {output}")

    def _exit(self):
        # 修复逻辑：所有条件都必须满足才能退出
        if (self.scheduler.idle() and 
            self.task_manager.all_done() and 
            self.processor.idle() and 
            self.downloader.idle()):
            self.running = False
            return True
        return False

    async def close(self):
        self.running = False
        await self.__close(self.scheduler)
        await self.__close(self.processor)
        if self.task_manager.current_task:
            await asyncio.gather(*self.task_manager.current_task, return_exceptions=True)
        await self.__close(self.downloader)
        await self.crawler.close()

    @staticmethod
    async def __close(obj):
        if hasattr(obj, 'close'):
            close = getattr(obj, 'close')
            if inspect.iscoroutinefunction(close):
                await asyncio.shield(close())
            else:
                close()

    async def open(self):
        self.running = True
        await self.__open(self.scheduler)
        await self.__open(self.downloader)
        await self.__open(self.spider)
        await self.__open(self.processor)

    @staticmethod
    async def __open(obj):
        if hasattr(obj, 'open'):
            _open = getattr(obj, 'open')
            if inspect.iscoroutinefunction(_open):
                await asyncio.shield(_open())
            else:
                _open()
