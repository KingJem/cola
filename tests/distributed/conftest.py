"""分布式组件测试的共享 fixture。

依赖本机 docker 容器:
    redis  localhost:6379(测试用 db 15)
    mysql  localhost:3307  root/cola123 库 cola
    pg     localhost:5433  postgres/cola123 库 cola
    rabbit localhost:5672  guest/guest
服务不可达时自动 skip。
"""
import pytest

from src.crawler import Crawler
from src.settings.settings_manager import SettingsManager
from src.spiders import Spider
from src.stats_collector import StatsCollector

REDIS_URL = 'redis://localhost:6379/15'
MYSQL = dict(host='localhost', port=3307, user='root', password='cola123',
             db='cola')
POSTGRES_DSN = 'postgresql://postgres:cola123@localhost:5433/cola'
RABBITMQ_URL = 'amqp://guest:guest@localhost:5672/'


class DistTestSpider(Spider):
    start_urls = []

    async def parse(self, response):
        yield {'url': response.url}

    async def parse_detail(self, response):
        yield {'url': response.url, 'detail': True}


def make_crawler(extra_settings=None) -> Crawler:
    values = {
        'PROJECT_NAME': 'cola_test',
        'REDIS_URL': REDIS_URL,
        'SCHEDULER_POLL_TIMEOUT': 0.1,
    }
    values.update(extra_settings or {})
    settings = SettingsManager(values)
    crawler = Crawler(DistTestSpider, settings)
    crawler.spider = DistTestSpider.create_instance(crawler)
    crawler.stat_collector = StatsCollector(settings)
    return crawler


@pytest.fixture
def dist_crawler():
    return make_crawler()


@pytest.fixture
async def redis_client():
    aioredis = pytest.importorskip('redis.asyncio')
    client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await client.ping()
    except Exception:
        pytest.skip('redis 不可用')
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
