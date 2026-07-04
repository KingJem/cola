"""make_request_from_seed 钩子:默认委托 seed_to_request,子类可重写。"""
from cola.http.request import Request
from tests.distributed.conftest import make_crawler


def test_default_hook_matches_seed_to_request():
    crawler = make_crawler()
    req = crawler.spider.make_request_from_seed(
        {'url': 'https://e.com', 'priority': 5, 'category': 'books'})
    assert req.url == 'https://e.com'
    assert req.priority == 5
    # 未知字段默认展开进 meta
    assert req.meta['category'] == 'books'


def test_default_hook_url_string():
    crawler = make_crawler()
    req = crawler.spider.make_request_from_seed('https://e.com/a')
    assert req.url == 'https://e.com/a'


def test_default_hook_uses_seed_callback_setting():
    crawler = make_crawler({'SEED_CALLBACK': 'parse_detail'})
    req = crawler.spider.make_request_from_seed('https://e.com')
    assert req.callback == crawler.spider.parse_detail


def test_override_puts_whole_task_in_meta():
    from tests.distributed.conftest import DistTestSpider

    class TaskSpider(DistTestSpider):
        def make_request_from_seed(self, seed):
            return Request(seed['url'], callback=self.parse,
                           meta={'task': seed})

    crawler = make_crawler()
    crawler.spider = TaskSpider.create_instance(crawler)
    seed = {'url': 'https://e.com', 'task_id': 42, 'extra': {'k': 'v'}}
    req = crawler.spider.make_request_from_seed(seed)
    # 整个原始 task 作为一个对象进 meta
    assert req.meta['task'] == seed
    assert req.callback == crawler.spider.parse


def test_override_can_skip_seed():
    from tests.distributed.conftest import DistTestSpider

    class FilterSpider(DistTestSpider):
        def make_request_from_seed(self, seed):
            if isinstance(seed, dict) and seed.get('skip'):
                return None
            return super().make_request_from_seed(seed)

    crawler = make_crawler()
    crawler.spider = FilterSpider.create_instance(crawler)
    assert crawler.spider.make_request_from_seed({'url': 'x', 'skip': True}) is None
    assert crawler.spider.make_request_from_seed(
        {'url': 'https://e.com'}).url == 'https://e.com'


async def test_seed_loader_uses_override(redis_client):
    """SeedLoader 经钩子加载:重写后整个 task 进 meta,写入共享队列。"""
    import json
    from cola.distributed.scheduler import RedisScheduler
    from cola.distributed.seed_loader import SeedLoader
    from cola.datasources.redis_source import RedisSeedProvider
    from tests.distributed.conftest import DistTestSpider

    class TaskSpider(DistTestSpider):
        def make_request_from_seed(self, seed):
            return Request(seed['url'], callback=self.parse,
                           meta={'task': seed})

    await redis_client.rpush(
        'cola_test:seeds',
        json.dumps({'url': 'https://e.com/1', 'task_id': 7}))

    crawler = make_crawler({
        'SEED_SOURCES': ['cola.datasources.redis_source.RedisSeedProvider'],
        'SCHEDULER_CLASS': 'cola.distributed.scheduler.RedisScheduler',
    })
    crawler.spider = TaskSpider.create_instance(crawler)

    scheduler = RedisScheduler(crawler)
    await scheduler.open()

    class _Engine:
        def __init__(self, sched):
            self.scheduler = sched

        async def enqueue_requests(self, request):
            await self.scheduler.enqueue_request(request)

    engine = _Engine(scheduler)
    try:
        await SeedLoader(crawler).run(engine)
        req = await scheduler.next_request()
        assert req is not None
        assert req.url == 'https://e.com/1'
        assert req.meta['task'] == {'url': 'https://e.com/1', 'task_id': 7}
    finally:
        await scheduler.close()
