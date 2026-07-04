"""引擎强化回归:Retry 中间件、offsite、DEPTH_LIMIT、
每域名并发、DOWNLOAD_MAXSIZE、LOG_FILE。
"""
import asyncio

import pytest
from aiohttp import web

from src.crawler import Crawler
from src.http.request import Request
from src.settings.settings_manager import SettingsManager
from src.spiders import Spider

LOG_STATS = ['src.extension.log_stats.LogStats']


@pytest.fixture
async def server():
    state = {'flaky_hits': 0, 'concurrent': 0, 'max_concurrent': 0}

    async def flaky(request):
        state['flaky_hits'] += 1
        if state['flaky_hits'] <= 2:
            return web.Response(status=503)
        return web.json_response({'ok': True})

    async def slow(request):
        state['concurrent'] += 1
        state['max_concurrent'] = max(state['max_concurrent'],
                                      state['concurrent'])
        await asyncio.sleep(0.15)
        state['concurrent'] -= 1
        return web.json_response({'n': int(request.match_info['n'])})

    async def big(request):
        return web.Response(body=b'x' * 10000)

    async def page(request):
        n = int(request.match_info['n'])
        base = f"http://{request.host}"
        nxt = f"{base}/page/{n + 1}" if n < 10 else None
        return web.json_response({'page': n, 'next': nxt})

    app = web.Application()
    app.router.add_get('/flaky', flaky)
    app.router.add_get('/slow/{n}', slow)
    app.router.add_get('/big', big)
    app.router.add_get('/page/{n}', page)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    yield f'http://127.0.0.1:{port}', state
    await runner.cleanup()


async def run_crawl(spider_cls, settings_dict, timeout=30):
    crawler = Crawler(spider_cls, SettingsManager(settings_dict))
    await asyncio.wait_for(crawler.crawl(), timeout=timeout)
    return crawler.stat_collector


async def test_retry_middleware_on_503(server):
    base, state = server

    class FlakySpider(Spider):
        start_urls = [f'{base}/flaky']

        async def parse(self, response):
            yield response.json()

    stats = await run_crawl(FlakySpider, {
        'PROJECT_NAME': 'retry_test', 'EXTENSIONS': LOG_STATS})

    assert state['flaky_hits'] == 3          # 2 次 503 + 1 次成功
    assert stats.get_value('retry_count', 0) == 2
    assert stats.get_value('item_successful_count', 0) == 1


async def test_retry_gives_up_after_max(server):
    base, state = server
    state['flaky_hits'] = -100  # 使其始终返回 503

    class DoomedSpider(Spider):
        start_urls = [f'{base}/flaky']

        async def parse(self, response):
            yield {'status': response.status_code}

    stats = await run_crawl(DoomedSpider, {
        'PROJECT_NAME': 'giveup_test', 'MAX_RETRY_TIMES': 2,
        'EXTENSIONS': LOG_STATS})

    assert stats.get_value('retry_count', 0) == 2
    assert stats.get_value('retry/max_reached', 0) == 1
    # 放弃后响应仍交给回调(status 503 的 item)
    assert stats.get_value('item_successful_count', 0) == 1


async def test_offsite_filter(server):
    base, _ = server

    class SiteSpider(Spider):
        allowed_domains = ['127.0.0.1']
        start_urls = [f'{base}/page/10']

        async def parse(self, response):
            yield {'page': response.json()['page']}
            yield Request(url='http://external.invalid/x',
                          callback=self.parse)

    stats = await run_crawl(SiteSpider, {
        'PROJECT_NAME': 'offsite_test',
        'DOWNLOADER_MIDDLEWARES': {'src.middleware.offsite.Offsite': 50},
        'EXTENSIONS': LOG_STATS})

    assert stats.get_value('request_ignored_count', 0) == 1
    assert stats.get_value('item_successful_count', 0) == 1


async def test_depth_limit(server):
    base, _ = server

    class ChainSpider(Spider):
        start_urls = [f'{base}/page/1']

        async def parse(self, response):
            data = response.json()
            yield {'page': data['page']}
            if data['next']:
                yield Request(url=data['next'], callback=self.parse)

    stats = await run_crawl(ChainSpider, {
        'PROJECT_NAME': 'depth_test', 'DEPTH_LIMIT': 2,
        'EXTENSIONS': LOG_STATS})

    # 种子深度 0,允许到 2 -> 共 3 页;第 4 页被丢弃
    assert stats.get_value('item_successful_count', 0) == 3
    assert stats.get_value('depth_limit/dropped', 0) == 1


async def test_per_domain_concurrency(server):
    base, state = server

    class BurstSpider(Spider):
        start_urls = [f'{base}/slow/{i}' for i in range(4)]

        async def parse(self, response):
            yield response.json()

    await run_crawl(BurstSpider, {
        'PROJECT_NAME': 'domain_test',
        'CONCURRENT_REQUESTS': 8,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
    })
    assert state['max_concurrent'] == 1


async def test_download_maxsize(server):
    base, _ = server

    class BigSpider(Spider):
        start_urls = [f'{base}/big']

        async def parse(self, response):
            yield {'size': len(response.body)}

    stats = await run_crawl(BigSpider, {
        'PROJECT_NAME': 'maxsize_test', 'DOWNLOAD_MAXSIZE': 1000,
        'EXTENSIONS': LOG_STATS})

    assert stats.get_value(
        'download_exceptions/DownloadMaxsizeExceeded', 0) == 1
    assert stats.get_value('item_successful_count', 0) == 0


async def test_log_file(server, tmp_path):
    base, _ = server
    log_file = tmp_path / 'spider.log'

    class QuietSpider(Spider):
        start_urls = [f'{base}/page/10']

        async def parse(self, response):
            yield {'page': response.json()['page']}

    await run_crawl(QuietSpider, {
        'PROJECT_NAME': 'log_test', 'LOG_FILE': str(log_file)})

    assert log_file.exists()
    content = log_file.read_text('utf-8')
    assert 'Cola is starting' in content
