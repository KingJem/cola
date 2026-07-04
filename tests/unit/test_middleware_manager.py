import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cola.middlewares import MiddlewareManager
from cola.http.request import Request
from cola.http.response import Response


def make_crawler(middlewares=None):
    crawler = MagicMock()
    crawler.settings.get.return_value = middlewares or {}
    return crawler


def make_request(url='http://example.com/'):
    return Request(url=url)


def make_response(url='http://example.com/', status=200):
    return Response(url=url, status=status, headers={}, request=make_request(url), body=b'')


class SyncMiddleware:
    @classmethod
    def create_instance(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        request.headers = {'X-Test': 'sync'}
        return None  # 继续链

    def process_response(self, request, response, spider):
        return response


class AsyncMiddleware:
    @classmethod
    def create_instance(cls, crawler):
        return cls()

    async def process_request(self, request, spider):
        request.headers = {'X-Async': 'yes'}
        return None

    async def process_response(self, request, response, spider):
        return response


class ShortCircuitMiddleware:
    """在 process_request 中直接返回 Response（短路）"""
    @classmethod
    def create_instance(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        return make_response()  # 短路


@pytest.mark.asyncio
async def test_empty_middleware_returns_request():
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = []
    manager._methods = {'process_request': [], 'process_response': [], 'process_exception': []}
    req = make_request()
    result = await manager.process_request(req, spider=None)
    assert result is req


@pytest.mark.asyncio
async def test_sync_middleware_process_request():
    """同步中间件方法应被正确调用"""
    mw = SyncMiddleware()
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = [mw]
    manager._methods = {
        'process_request': [mw.process_request],
        'process_response': [mw.process_response],
        'process_exception': [],
    }
    req = make_request()
    result = await manager.process_request(req, spider=None)
    assert result is req
    assert req.headers == {'X-Test': 'sync'}


@pytest.mark.asyncio
async def test_async_middleware_process_request():
    """异步中间件方法应被正确调用"""
    mw = AsyncMiddleware()
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = [mw]
    manager._methods = {
        'process_request': [mw.process_request],
        'process_response': [mw.process_response],
        'process_exception': [],
    }
    req = make_request()
    result = await manager.process_request(req, spider=None)
    assert result is req
    assert req.headers == {'X-Async': 'yes'}


@pytest.mark.asyncio
async def test_short_circuit_returns_response():
    """中间件返回 Response 时应短路"""
    mw = ShortCircuitMiddleware()
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = [mw]
    manager._methods = {
        'process_request': [mw.process_request],
        'process_response': [],
        'process_exception': [],
    }
    req = make_request()
    result = await manager.process_request(req, spider=None)
    assert isinstance(result, Response)


@pytest.mark.asyncio
async def test_process_response_called_in_reverse():
    """process_response 应按逆序调用"""
    order = []

    class MW1:
        @classmethod
        def create_instance(cls, crawler): return cls()
        def process_response(self, request, response, spider):
            order.append(1)
            return response

    class MW2:
        @classmethod
        def create_instance(cls, crawler): return cls()
        def process_response(self, request, response, spider):
            order.append(2)
            return response

    mw1, mw2 = MW1(), MW2()
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = [mw1, mw2]
    manager._methods = {
        'process_request': [],
        'process_response': [mw1.process_response, mw2.process_response],
        'process_exception': [],
    }
    req = make_request()
    resp = make_response()
    await manager.process_response(req, resp, spider=None)
    assert order == [2, 1]  # 逆序


@pytest.mark.asyncio
async def test_process_exception_returns_none_when_no_handler():
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = []
    manager._methods = {'process_request': [], 'process_response': [], 'process_exception': []}
    result = await manager.process_exception(make_request(), Exception('err'), spider=None)
    assert result is None
