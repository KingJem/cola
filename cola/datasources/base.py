"""SeedProvider 抽象基类。

种子协议:seeds() 异步迭代产出 URL 字符串或 dict:
    {"url": "...", "method": "GET", "meta": {...}, "priority": 0,
     "callback": "parse_detail"}
dict 中除 Request 已知字段外的键一律并入 meta(见 seed_loader.seed_to_request)。
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Union


class SeedProvider(ABC):

    def __init__(self, crawler):
        self.crawler = crawler
        self.settings = crawler.settings

    @classmethod
    def create_instance(cls, crawler):
        return cls(crawler)

    async def open(self):
        """建立连接;子类按需覆写。"""

    @abstractmethod
    def seeds(self) -> AsyncIterator[Union[str, dict]]:
        """异步迭代产出种子;读完即返回(drain 语义)。"""

    async def close(self):
        """释放连接;子类按需覆写。"""
