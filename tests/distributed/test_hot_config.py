import asyncio
import json

from cola.extension.hot_config import HotConfig
from cola.task_manager import TaskManager
from tests.distributed.conftest import make_crawler


class FakeSettings:
    def __init__(self, n):
        self._n = n

    def getint(self, key, default=0):
        return self._n


def test_task_manager_resize_grow():
    tm = TaskManager(FakeSettings(2))
    tm.resize(5)
    assert tm.limit == 5
    assert tm.sem._value == 5


def test_task_manager_resize_shrink_idle_permits():
    tm = TaskManager(FakeSettings(5))
    tm.resize(2)
    assert tm.limit == 2
    assert tm.sem._value == 2
    assert tm._debt == 0


async def test_task_manager_resize_shrink_with_inflight():
    tm = TaskManager(FakeSettings(3))
    release = asyncio.Event()

    async def job():
        await release.wait()

    # 占满 3 个许可
    for _ in range(3):
        await tm.sem.acquire()
        tm.create_task(job())
    assert tm.sem._value == 0

    # 缩容到 1:无空闲许可,全部记欠账
    tm.resize(1)
    assert tm._debt == 2
    # 三个在途任务完成:前两个偿还欠账,第三个真正释放许可
    release.set()
    await asyncio.sleep(0.05)
    assert tm._debt == 0
    assert tm.sem._value == 1
    assert tm.all_done()


def test_task_manager_grow_cancels_debt():
    tm = TaskManager(FakeSettings(5))
    tm._debt = 2  # 模拟未吸收的缩容
    tm.limit = 3
    tm.resize(6)
    assert tm._debt == 0
    assert tm.sem._value == 5 + 1  # 原 5 空闲 + 抵消欠账后净增 1


def test_hot_config_apply_updates_settings_and_concurrency():
    crawler = make_crawler()

    class FakeEngine:
        task_manager = TaskManager(FakeSettings(4))
    crawler.engine = FakeEngine()

    hc = HotConfig(crawler)
    hc.apply({'CONCURRENT_REQUESTS': 9, 'DOWNLOAD_DELAY': 0.5})

    assert crawler.settings.getint('CONCURRENT_REQUESTS') == 9
    assert crawler.settings.getfloat('DOWNLOAD_DELAY') == 0.5
    assert crawler.engine.task_manager.limit == 9


async def test_hot_config_pubsub_roundtrip(redis_client):
    crawler = make_crawler()
    crawler.engine = None
    hc = HotConfig(crawler)
    assert hc.channels == ['cola_test:config', 'cola_test:DistTestSpider:config']

    await hc.spider_opened()
    try:
        # SUBSCRIBE 与 PUBLISH 走不同连接,Redis 侧无顺序保证;
        # 循环重发直到生效(幂等),避免订阅尚未注册导致的竞态
        for _ in range(100):
            await redis_client.publish('cola_test:config',
                                       json.dumps({'TIMEOUT': 99}))
            await redis_client.publish('cola_test:DistTestSpider:config',
                                       json.dumps({'MAX_RETRY': 7}))
            if (crawler.settings.getint('TIMEOUT') == 99
                    and crawler.settings.getint('MAX_RETRY') == 7):
                break
            await asyncio.sleep(0.05)
        assert crawler.settings.getint('TIMEOUT') == 99
        assert crawler.settings.getint('MAX_RETRY') == 7
    finally:
        await hc.spider_closed()


async def test_hot_config_ignores_bad_payload(redis_client):
    crawler = make_crawler()
    crawler.engine = None
    hc = HotConfig(crawler)
    await hc.spider_opened()
    try:
        for _ in range(100):
            await redis_client.publish('cola_test:config', 'not-json')
            await redis_client.publish('cola_test:config',
                                       json.dumps({'TIMEOUT': 42}))
            if crawler.settings.getint('TIMEOUT') == 42:
                break
            await asyncio.sleep(0.05)
        assert crawler.settings.getint('TIMEOUT') == 42
    finally:
        await hc.spider_closed()
