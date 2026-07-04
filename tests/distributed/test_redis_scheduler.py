import asyncio

import pytest

from src.distributed.dupefilter import AsyncRedisDupeFilter
from src.distributed.scheduler import RedisScheduler
from src.http.request import Request
from tests.distributed.conftest import make_crawler


@pytest.fixture
async def scheduler(redis_client):
    crawler = make_crawler({'SCHEDULER_IDLE_TIMEOUT': 0.3})
    sched = RedisScheduler(crawler)
    await sched.open()
    yield sched
    await sched.close()


async def test_priority_order(scheduler):
    for priority, url in [(1, 'https://e.com/low'),
                          (100, 'https://e.com/high'),
                          (50, 'https://e.com/mid')]:
        await scheduler.enqueue_request(Request(url=url, priority=priority))

    urls = [(await scheduler.next_request()).url for _ in range(3)]
    assert urls == ['https://e.com/high', 'https://e.com/mid', 'https://e.com/low']


async def test_empty_returns_none(scheduler):
    assert await scheduler.next_request() is None


async def test_callback_survives_queue(scheduler):
    request = Request(url='https://e.com',
                      callback=scheduler.crawler.spider.parse_detail)
    request.meta['k'] = 'v'
    await scheduler.enqueue_request(request)
    restored = await scheduler.next_request()
    assert restored.callback == scheduler.crawler.spider.parse_detail
    assert restored.meta == {'k': 'v'}


async def test_idle_requires_continuous_empty(scheduler):
    # 刚入队过,非空闲
    await scheduler.enqueue_request(Request(url='https://e.com'))
    assert not scheduler.idle()
    assert (await scheduler.next_request()).url == 'https://e.com'

    # 第一次空弹出后开始计时,未到 idle_timeout 前不空闲
    assert await scheduler.next_request() is None
    assert not scheduler.idle()
    await asyncio.sleep(0.35)
    assert scheduler.idle()


async def test_idle_timeout_zero_never_idle(redis_client):
    crawler = make_crawler({'SCHEDULER_IDLE_TIMEOUT': 0})
    sched = RedisScheduler(crawler)
    await sched.open()
    try:
        assert await sched.next_request() is None
        await asyncio.sleep(0.2)
        assert not sched.idle()
    finally:
        await sched.close()


async def test_persist_false_clears_queue(redis_client):
    crawler = make_crawler({'SCHEDULER_PERSIST': False})
    sched = RedisScheduler(crawler)
    await sched.open()
    await sched.enqueue_request(Request(url='https://e.com'))
    await sched.close()
    assert await redis_client.zcard('cola_test:requests') == 0


async def test_flush_on_start(redis_client):
    await redis_client.zadd('cola_test:requests', {'stale': 0})
    crawler = make_crawler({'SCHEDULER_FLUSH_ON_START': True})
    sched = RedisScheduler(crawler)
    await sched.open()
    try:
        assert await redis_client.zcard('cola_test:requests') == 0
    finally:
        await sched.close()


async def test_dupefilter_atomicity(redis_client):
    crawler = make_crawler()
    df = AsyncRedisDupeFilter.from_crawler(crawler)
    request = Request(url='https://e.com/dup')
    try:
        assert await df.is_seen(request) is False
        assert await df.is_seen(request) is True
        # 参数顺序不同的等价 URL 指纹一致
        r1 = Request(url='https://e.com/x?a=1&b=2')
        r2 = Request(url='https://e.com/x?b=2&a=1')
        assert await df.is_seen(r1) is False
        assert await df.is_seen(r2) is True
    finally:
        await df.close()


async def test_dupefilter_persist_false_deletes_key(redis_client):
    crawler = make_crawler({'REDIS_DUPEFILTER_PERSIST': False})
    df = AsyncRedisDupeFilter.from_crawler(crawler)
    await df.is_seen(Request(url='https://e.com'))
    assert await redis_client.scard('cola_test:dupefilter') == 1
    await df.close()
    assert await redis_client.scard('cola_test:dupefilter') == 0
