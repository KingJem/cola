"""redis.asyncio 客户端工厂。

分布式组件(调度器/去重器/热配置)各自持有独立连接,互不阻塞;
redis-py 内部自带连接池,无需额外管理。
"""


def get_redis(settings, *, decode_responses: bool = False):
    try:
        from redis import asyncio as aioredis
    except ImportError as exc:
        raise RuntimeError(
            "分布式模式需要 redis 包,安装:pip install 'cola[redis]'"
        ) from exc

    url = settings.get('REDIS_URL', 'redis://localhost:6379/0')
    return aioredis.Redis.from_url(url, decode_responses=decode_responses)
