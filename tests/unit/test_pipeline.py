import asyncio
import json
import os
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.pipeline import PipelineManager, DropItem
from src.pipeline.base import BasePipeline
from src.pipeline.console import ConsolePipeline
from src.item.items import Item


def make_item(**kwargs):
    """创建简单字典 item（测试用）"""
    return kwargs


def make_crawler(pipelines=None):
    from src.subscriber import Subscriber
    crawler = MagicMock()
    crawler.settings.get.return_value = pipelines or {}
    crawler.spider = MagicMock()
    crawler.spider.name = 'test_spider'
    # 真实 Subscriber,使 process_item 里的事件派发可 await(无订阅者即空转)
    crawler.subscriber = Subscriber()
    return crawler


class CountPipeline(BasePipeline):
    def __init__(self):
        self.count = 0

    @classmethod
    def create_instance(cls, crawler):
        return cls()

    async def process_item(self, item, spider):
        self.count += 1
        return item


class DropEvenPipeline(BasePipeline):
    @classmethod
    def create_instance(cls, crawler):
        return cls()

    async def process_item(self, item, spider):
        if item.get('value', 0) % 2 == 0:
            raise DropItem(f"Even value: {item['value']}")
        return item


@pytest.mark.asyncio
async def test_empty_pipeline_returns_item():
    manager = PipelineManager.__new__(PipelineManager)
    manager.crawler = make_crawler()
    manager.pipelines = []
    item = make_item(name='test')
    result = await manager.process_item(item, spider=None)
    assert result == item


@pytest.mark.asyncio
async def test_pipeline_processes_item():
    pipeline = CountPipeline()
    manager = PipelineManager.__new__(PipelineManager)
    manager.crawler = make_crawler()
    manager.pipelines = [pipeline]
    item = make_item(name='test')
    result = await manager.process_item(item, spider=None)
    assert result == item
    assert pipeline.count == 1


@pytest.mark.asyncio
async def test_drop_item_returns_none():
    pipeline = DropEvenPipeline()
    manager = PipelineManager.__new__(PipelineManager)
    manager.crawler = make_crawler()
    manager.pipelines = [pipeline]
    item = make_item(value=2)
    result = await manager.process_item(item, spider=None)
    assert result is None


@pytest.mark.asyncio
async def test_drop_item_stops_pipeline_chain():
    """DropItem 后后续 Pipeline 不应被调用"""
    drop_pipeline = DropEvenPipeline()
    count_pipeline = CountPipeline()
    manager = PipelineManager.__new__(PipelineManager)
    manager.crawler = make_crawler()
    manager.pipelines = [drop_pipeline, count_pipeline]
    item = make_item(value=2)
    result = await manager.process_item(item, spider=None)
    assert result is None
    assert count_pipeline.count == 0  # 不应被调用


@pytest.mark.asyncio
async def test_console_pipeline(capsys):
    pipeline = ConsolePipeline()
    await pipeline.process_item({'name': 'test', 'value': 42}, spider=MagicMock(name='myspider'))
    captured = capsys.readouterr()
    assert 'test' in captured.out or 'value' in captured.out


@pytest.mark.asyncio
async def test_open_close_spider_called(tmp_path):
    """open_spider / close_spider 应被调用"""
    opened = []
    closed = []

    class TrackPipeline(BasePipeline):
        @classmethod
        def create_instance(cls, crawler): return cls()
        async def open_spider(self, spider): opened.append(True)
        async def close_spider(self, spider): closed.append(True)
        async def process_item(self, item, spider): return item

    pipeline = TrackPipeline()
    manager = PipelineManager.__new__(PipelineManager)
    manager.crawler = make_crawler()
    manager.pipelines = [pipeline]
    spider = MagicMock()
    await manager.open_spider(spider)
    await manager.close_spider(spider)
    assert opened == [True]
    assert closed == [True]
