"""StatsExporter 端到端:运行一个爬虫,校验快照文件的指标。"""
import asyncio
import json

import pytest
from aiohttp import web

from cola.crawler import Crawler
from cola.settings.settings_manager import SettingsManager
from cola.spiders import Spider


@pytest.fixture
async def server():
    async def page(request):
        n = int(request.match_info['n'])
        base = f"http://{request.host}"
        nxt = f"{base}/page/{n + 1}" if n < 6 else None
        await asyncio.sleep(0.02)
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


async def test_exporter_writes_snapshots(server, tmp_path):
    metrics = tmp_path / 'task.metrics.jsonl'

    class ChainSpider(Spider):
        start_urls = [f'{server}/page/1']

        async def parse(self, response):
            data = response.json()
            yield {'page': data['page']}
            if data['next']:
                from cola.http.request import Request
                yield Request(url=data['next'], callback=self.parse)

    crawler = Crawler(ChainSpider, SettingsManager({
        'PROJECT_NAME': 'exporter_test',
        'STATS_EXPORT_ENABLED': True,
        'STATS_EXPORT_INTERVAL': 0.1,
        'STATS_EXPORT_FILE': str(metrics),
    }))
    await asyncio.wait_for(crawler.crawl(), timeout=30)

    assert metrics.exists()
    snaps = [json.loads(line) for line in
             metrics.read_text('utf-8').splitlines() if line.strip()]
    assert snaps, '至少应有一条快照'

    final = snaps[-1]
    assert final['final'] is True
    assert final['responses'] == 6
    assert final['items'] == 6
    assert final['avg_response_time'] > 0        # 下载耗时被采集
    assert final['success_rate'] == 1.0
    # 快照结构完整
    for key in ('pages_per_sec', 'items_per_sec', 'pending_requests',
                'in_flight', 'concurrency_limit', 'status_codes'):
        assert key in final
    assert final['status_codes'].get('200', 0) >= 6


async def test_exporter_disabled_by_default(server, tmp_path):
    metrics = tmp_path / 'none.jsonl'

    class OneSpider(Spider):
        start_urls = [f'{server}/page/6']

        async def parse(self, response):
            yield {'ok': 1}

    crawler = Crawler(OneSpider, SettingsManager({
        'PROJECT_NAME': 'no_export',
        'STATS_EXPORT_FILE': str(metrics),  # 未开 ENABLED
    }))
    await asyncio.wait_for(crawler.crawl(), timeout=15)
    assert not metrics.exists()
