"""master 角色的种子加载器。

从 SEED_SOURCES 配置的各 SeedProvider 拉取种子,转成 Request 后经引擎入队
(走去重 + 调度器,即写入共享 Redis 队列)。作为独立 asyncio 任务运行,
与抓取主循环解耦;引擎退出判定会等待其完成。
"""
import asyncio

from loguru import logger

from src.http.request import Request
from src.utils import load_class


def seed_to_request(seed, spider, *, default_callback: str = None) -> Request:
    """种子 -> Request。种子可为 URL 字符串或 dict(url 必填)。"""
    if isinstance(seed, (str, bytes)):
        seed = {'url': seed.decode() if isinstance(seed, bytes) else seed}
    if 'url' not in seed:
        raise ValueError(f"种子缺少 url 字段: {seed!r}")

    known = {'url', 'method', 'headers', 'cookies', 'proxy', 'body',
             'priority', 'dont_filter', 'callback', 'meta'}
    callback_name = seed.get('callback') or default_callback
    callback = None
    if callback_name:
        callback = getattr(spider, callback_name, None)
        if callback is None:
            raise ValueError(f"spider {spider} 上不存在种子回调 {callback_name!r}")

    request = Request(
        url=seed['url'],
        method=seed.get('method', 'GET'),
        headers=seed.get('headers'),
        cookies=seed.get('cookies'),
        proxy=seed.get('proxy'),
        body=seed.get('body'),
        priority=int(seed.get('priority', 0) or 0),
        dont_filter=bool(seed.get('dont_filter', False)),
        callback=callback,
    )
    request.meta.update(seed.get('meta') or {})
    # 数据源多余的列一律进 meta,方便回调里取业务字段
    for key, value in seed.items():
        if key not in known:
            request.meta[key] = value
    return request


class SeedLoader:

    def __init__(self, crawler):
        self.crawler = crawler
        self.settings = crawler.settings
        self.providers = []
        for path in self.settings.getlist('SEED_SOURCES'):
            provider_cls = load_class(path)
            if hasattr(provider_cls, 'create_instance'):
                provider = provider_cls.create_instance(crawler)
            else:
                provider = provider_cls(crawler)
            self.providers.append(provider)

    async def run(self, engine):
        total = 0
        for provider in self.providers:
            name = provider.__class__.__name__
            try:
                await provider.open()
                async for seed in provider.seeds():
                    # 统一走 spider 钩子;默认委托 seed_to_request,子类可重写
                    try:
                        request = self.crawler.spider.make_request_from_seed(seed)
                    except ValueError as exc:
                        logger.error(f"[{name}] 丢弃非法种子: {exc}")
                        continue
                    except Exception as exc:
                        logger.error(
                            f"[{name}] make_request_from_seed 异常,丢弃种子: {exc}")
                        continue
                    if request is None:
                        continue
                    await engine.enqueue_requests(request)
                    total += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(f"[{name}] 种子加载失败: {exc}")
            finally:
                try:
                    await provider.close()
                except Exception as exc:
                    logger.warning(f"[{name}] 关闭数据源异常: {exc}")
        logger.info(f"SeedLoader 完成,共注入 {total} 个种子")
        self.crawler.stat_collector['seeds.loaded.count'] = total
