"""端到端分布式爬取:master 从 Redis 种子源注入,master+worker 共享
Redis 队列与去重集合并发消费,结果写入 RedisPipeline,验证不重不漏。
"""
import asyncio
import json

import pytest
from aiohttp import web

from src.crawler import Crawler
from src.settings.settings_manager import SettingsManager
from src.spiders import Spider
from tests.distributed.conftest import REDIS_URL

PROJECT = 'cola_e2e'
TOTAL_PAGES = 15  # 二叉树 1..15


class TreeSpider(Spider):
    """页面 n 链接到 2n 和 2n+1,构成 15 节点二叉树。"""
    start_urls = []

    async def parse(self, response):
        data = response.json()
        yield {'page': data['page'], 'node': self.crawler.settings.get('NODE_NAME')}
        from src.http.request import Request
        for link in data['links']:
            yield Request(url=link, callback=self.parse)


@pytest.fixture
async def tree_server():
    async def page(request):
        n = int(request.match_info['n'])
        base = f"http://{request.host}"
        links = [f"{base}/page/{c}" for c in (2 * n, 2 * n + 1)
                 if c <= TOTAL_PAGES]
        return web.json_response({'page': n, 'links': links})

    app = web.Application()
    app.router.add_get('/page/{n}', page)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    yield f'http://127.0.0.1:{port}'
    await runner.cleanup()


def node_settings(role, name):
    return SettingsManager({
        'PROJECT_NAME': PROJECT,
        'NODE_ROLE': role,
        'NODE_NAME': name,
        'REDIS_URL': REDIS_URL,
        'SCHEDULER_CLASS': 'src.distributed.scheduler.RedisScheduler',
        'DUPEFILTER_CLASS': 'src.distributed.dupefilter.AsyncRedisDupeFilter',
        'SCHEDULER_IDLE_TIMEOUT': 1.5,
        'SCHEDULER_POLL_TIMEOUT': 0.1,
        'SCHEDULER_PERSIST': False,
        'REDIS_DUPEFILTER_PERSIST': False,
        'SEED_SOURCES': ['src.datasources.redis_source.RedisSeedProvider']
                        if role == 'master' else [],
        'ITEM_PIPELINES': {'src.pipeline.redis_pipeline.RedisPipeline': 100},
        'CONCURRENT_REQUESTS': 4,
        'TIMEOUT': 10,
        'MAX_RETRY': 1,
    })


async def test_master_worker_crawl(redis_client, tree_server):
    # 种子:树根页面
    await redis_client.rpush(f'{PROJECT}:seeds', f'{tree_server}/page/1')

    master = Crawler(TreeSpider, node_settings('master', 'node-master'))
    worker = Crawler(TreeSpider, node_settings('worker', 'node-worker'))

    await asyncio.wait_for(
        asyncio.gather(master.crawl(), worker.crawl()), timeout=60)

    rows = [json.loads(r) for r in
            await redis_client.lrange(f'{PROJECT}:items', 0, -1)]
    pages = sorted(row['page'] for row in rows)

    # 不重不漏:15 个页面恰好各出现一次(共享去重生效)
    assert pages == list(range(1, TOTAL_PAGES + 1))
    # 队列与去重集合按 persist=False 已清理
    assert await redis_client.zcard(f'{PROJECT}:requests') == 0
    assert await redis_client.scard(f'{PROJECT}:dupefilter') == 0


async def test_worker_skips_start_requests(redis_client, tree_server):
    """worker 角色不消费 start_urls,仅消费共享队列。"""
    class WorkerOnlySpider(TreeSpider):
        start_urls = [f'{tree_server}/page/1']

    worker = Crawler(WorkerOnlySpider, node_settings('worker', 'w'))
    await asyncio.wait_for(worker.crawl(), timeout=30)

    rows = await redis_client.lrange(f'{PROJECT}:items', 0, -1)
    assert rows == []  # start_urls 被跳过,队列里也没有种子
