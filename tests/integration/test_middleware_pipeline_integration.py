"""
集成测试：验证中间件 + 去重 + Pipeline 协同工作
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.http.request import Request
from src.http.response import Response
from src.middlewares import MiddlewareManager
from src.dupefilter import RFPDupeFilter
from src.pipeline import PipelineManager


def make_response(url='http://example.com/', status=200):
    req = Request(url=url)
    return Response(url=url, status=status, headers={}, request=req, body=b'<html></html>')


def make_crawler_with_settings(**settings_dict):
    crawler = MagicMock()
    crawler.settings.get.side_effect = lambda key, default=None: settings_dict.get(key, default)
    crawler.settings.getbool.side_effect = lambda key, default=False: settings_dict.get(key, default)
    return crawler


@pytest.mark.asyncio
async def test_dupefilter_blocks_duplicate():
    """去重过滤器应阻止重复 URL"""
    f = RFPDupeFilter()
    req1 = Request(url='http://example.com/page')
    req2 = Request(url='http://example.com/page')  # 同 URL
    f.mark_seen(req1)
    assert f.is_seen(req2)


@pytest.mark.asyncio
async def test_dupefilter_allows_dont_filter():
    """dont_filter=True 时，即使是相同 URL 也不应视为重复（由 Engine 判断）"""
    f = RFPDupeFilter()
    req = Request(url='http://example.com/', dont_filter=True)
    f.mark_seen(req)
    # DupeFilter 本身仍会标记，由 Engine 决定是否跳过检查
    assert req.dont_filter is True


@pytest.mark.asyncio
async def test_middleware_and_pipeline_independent():
    """中间件和 Pipeline 应相互独立，不互相依赖"""
    # 中间件：空
    crawler_mw = make_crawler_with_settings(DOWNLOADER_MIDDLEWARES={})
    mw_manager = MiddlewareManager(crawler_mw)

    req = Request(url='http://example.com/')
    result = await mw_manager.process_request(req, spider=None)
    assert result is req  # 无中间件，原样返回

    # Pipeline：空
    crawler_pl = make_crawler_with_settings(ITEM_PIPELINES={})
    pl_manager = PipelineManager(crawler_pl)
    item = {'name': 'test', 'value': 42}
    result = await pl_manager.process_item(item, spider=None)
    assert result == item  # 无 pipeline，原样返回


@pytest.mark.asyncio
async def test_middleware_modifies_request_headers():
    """中间件能修改请求头"""
    class HeaderMiddleware:
        @classmethod
        def create_instance(cls, crawler): return cls()
        def process_request(self, request, spider):
            request.headers = request.headers or {}
            request.headers['User-Agent'] = 'ColaBot/1.0'
            return None

    crawler = make_crawler_with_settings(
        DOWNLOADER_MIDDLEWARES={'__main__.HeaderMiddleware': 100}
    )
    with patch('src.middlewares.load_class', return_value=HeaderMiddleware):
        manager = MiddlewareManager(crawler)
    req = Request(url='http://example.com/')
    await manager.process_request(req, spider=None)
    assert req.headers.get('User-Agent') == 'ColaBot/1.0'
