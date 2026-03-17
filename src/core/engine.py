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
        self.dupe_filter = None
        self.middleware_manager = None
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
        dupefilter_cls_path = self.settings.get('DUPEFILTER_CLASS', 'src.dupefilter.RFPDupeFilter')
        dupefilter_cls = load_class(dupefilter_cls_path)
        self.dupe_filter = dupefilter_cls.from_crawler(self.crawler)
        from src.middlewares import MiddlewareManager
        self.middleware_manager = MiddlewareManager(self.crawler)
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

    async def _fetch(self, request):
        # 1. 中间件 process_request 链
        result = await self.middleware_manager.process_request(request, self.spider)

        from src.http.response import Response as HttpResponse
        if isinstance(result, HttpResponse):
            response = result  # 中间件短路返回了 Response
        else:
            if isinstance(result, Request):
                request = result  # 中间件返回了修改后的 Request
            # 2. 实际下载
            try:
                response = await self.downloader.fetch(request)
                if response is None:
                    logger.warning(f"Download failed for {request.url}, skipping")
                    return None
            except Exception as e:
                # 3a. 中间件 process_exception 链
                exc_result = await self.middleware_manager.process_exception(request, e, self.spider)
                if exc_result is None:
                    logger.error(f"Unhandled download exception for {request.url}: {e}")
                    return None
                response = exc_result

        # 3b. 中间件 process_response 链
        response = await self.middleware_manager.process_response(request, response, self.spider)

        # 4. 调用 spider callback
        callback = request.callback or self.spider.parse
        outputs = callback(response)
        if outputs is None:
            return None
        if inspect.iscoroutine(outputs):
            await outputs
            return None
        return self._transform(outputs)

    async def enqueue_requests(self, request):
        await self._schedule_request(request)

    async def _schedule_request(self, request):
        if not request.dont_filter and self.dupe_filter.is_seen(request):
            if self.dupe_filter.debug:
                self.logger.debug(f"Filtered duplicate request: {request.url}")
            return
        self.dupe_filter.mark_seen(request)
        await self.scheduler.enqueue_request(request)

    async def _get_next_request(self):
        return await self.scheduler.next_request()

    async def _handle_spider_outputs(self, outputs):
        from collections.abc import MutableMapping
        async for output in outputs:
            if isinstance(output, Request):
                await self.processor.enqueue(output)
            elif isinstance(output, MutableMapping) and hasattr(output, 'FIELDS'):
                # Item 实例（通过 MutableMapping 基类和 FIELDS 属性判断）
                await self.processor.enqueue(output)
            elif isinstance(output, dict):
                # dict 也送入 Processor -> Pipeline 处理
                await self.processor.enqueue(output)
            else:
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
        if self.dupe_filter is not None:
            self.dupe_filter.close()
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
