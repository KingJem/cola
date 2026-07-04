"""引擎事件与统计接线的端到端回归:
request_scheduled / response_received 事件驱动 LogStats 计数,
spider 回调异常被记录且不中断爬取。
"""
import asyncio

import pytest
from aiohttp import web

from cola.crawler import Crawler
from cola.settings.settings_manager import SettingsManager
from cola.spiders import Spider


@pytest.fixture
async def chain_server():
    """页面 n 链接到 n+1,共 4 页;/page/3 的回调会抛异常。"""
    async def page(request):
        n = int(request.match_info['n'])
        base = f"http://{request.host}"
        nxt = f"{base}/page/{n + 1}" if n < 4 else None
        return web.json_response({'page': n, 'next': nxt})

    app = web.Application()
    app.router.add_get('/page/{n}', page)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    yield f'http://127.0.0.1:{port}'
    await runner.cleanup()


async def test_events_counted_and_errors_survive(chain_server):
    class ChainSpider(Spider):
        start_urls = [f'{chain_server}/page/1']

        async def parse(self, response):
            data = response.json()
            if data['page'] == 3:
                raise ValueError('boom on page 3')
            yield {'page': data['page']}
            if data['next']:
                from cola.http.request import Request
                yield Request(url=data['next'], callback=self.parse)

    settings = SettingsManager({
        'PROJECT_NAME': 'events_test',
        'CONCURRENT_REQUESTS': 2,
        'EXTENSIONS': ['cola.extension.log_stats.LogStats'],
    })
    crawler = Crawler(ChainSpider, settings)
    await asyncio.wait_for(crawler.crawl(), timeout=30)

    stats = crawler.stat_collector
    # 事件已接线:调度/响应计数 > 0(此前恒为 0)
    assert stats.get_value('request_scheduled_count', 0) >= 3
    assert stats.get_value('response_received_count', 0) >= 3
    # 页面 3 的回调异常被记录,且没有中断整个爬取(能跑完退出)
    assert stats.get_value('spider_exceptions/ValueError', 0) == 1
