from abc import ABCMeta, abstractmethod
from contextlib import asynccontextmanager, contextmanager
from typing import Final, Set
from typing import Optional

from cola.core.request import Request
from cola.core.response import Response
from cola.middlewares import MiddlewareManager


class DownloadMeta(ABCMeta):
    def __subclasscheck__(cls, subclass):
        return (hasattr(subclass, 'fetch') and
                callable(subclass.fetch) and
                hasattr(subclass, 'download') and
                callable(subclass.download) and
                hasattr(subclass, 'close') and
                callable(subclass.close) and
                hasattr(subclass, 'idle') and
                callable(subclass.idle))


class Downloader(metaclass=DownloadMeta):
    def __init__(self, crawler):
        self.crawler = crawler
        self.middleware: Optional[MiddlewareManager] = None

    @classmethod
    def create_instance(cls, crawler, *args, **kwargs):
        return cls(crawler)

    def open(self):
        self.middleware = MiddlewareManager.create_instance(self.crawler)

    @abstractmethod
    async def fetch(self, request: Request) -> Optional[Response]:
        raise NotImplementedError()

    @abstractmethod
    async def download(self, request: Request):
        raise NotImplementedError()

    @abstractmethod
    async def close(self):
        pass

    @abstractmethod
    def idle(self):
        pass


class BaseDownloaderManager:
    """下载管理器的基类，提供请求管理的通用功能。"""

    def __init__(self):
        """初始化空的活跃请求集合。"""
        self.active: Final[Set] = set()

    def add(self, request: Request):
        """添加请求到活跃集合。"""
        self.active.add(request)

    def remove(self, request: Request):
        """从活跃集合中移除请求。"""
        self.active.discard(request)

    def __len__(self):
        """返回活跃请求数量。"""
        return len(self.active)

    def idle(self):
        """检查是否空闲。"""
        return len(self.active) == 0


class AsyncDownloaderManager(BaseDownloaderManager):
    """异步下载管理器，支持 async with 语句。"""

    @asynccontextmanager
    async def __call__(self, request: Request):
        try:
            self.add(request)
            yield
        finally:
            self.remove(request)


class SyncDownloaderManager(BaseDownloaderManager):
    """同步下载管理器，支持 with 语句。"""

    @contextmanager
    def __call__(self, request: Request):
        try:
            self.add(request)
            yield
        finally:
            self.remove(request)
