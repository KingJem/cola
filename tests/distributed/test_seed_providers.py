import json

import pytest

from cola.datasources.mysql_source import MySQLSeedProvider
from cola.datasources.postgres_source import PostgresSeedProvider
from cola.datasources.rabbitmq_source import RabbitMQSeedProvider
from cola.datasources.redis_source import RedisSeedProvider
from cola.distributed.seed_loader import seed_to_request
from tests.distributed.conftest import (
    MYSQL, POSTGRES_DSN, RABBITMQ_URL, make_crawler)


async def collect(provider):
    await provider.open()
    try:
        return [seed async for seed in provider.seeds()]
    finally:
        await provider.close()


def test_seed_to_request_url_string():
    crawler = make_crawler()
    request = seed_to_request('https://e.com/a', crawler.spider)
    assert request.url == 'https://e.com/a'
    assert request.callback is None


def test_seed_to_request_dict_with_extras():
    crawler = make_crawler()
    seed = {'url': 'https://e.com', 'priority': 5, 'callback': 'parse_detail',
            'category': 'books', 'meta': {'page': 1}}
    request = seed_to_request(seed, crawler.spider)
    assert request.priority == 5
    assert request.callback == crawler.spider.parse_detail
    # 未知列进 meta,显式 meta 保留
    assert request.meta == {'page': 1, 'category': 'books'}


def test_seed_to_request_default_callback():
    crawler = make_crawler()
    request = seed_to_request('https://e.com', crawler.spider,
                              default_callback='parse_detail')
    assert request.callback == crawler.spider.parse_detail


def test_seed_missing_url_rejected():
    crawler = make_crawler()
    with pytest.raises(ValueError, match='缺少 url'):
        seed_to_request({'priority': 1}, crawler.spider)


async def test_redis_seed_provider(redis_client):
    await redis_client.rpush(
        'cola_test:seeds',
        'https://e.com/plain',
        json.dumps({'url': 'https://e.com/json', 'priority': 9}))
    provider = RedisSeedProvider(make_crawler())
    seeds = await collect(provider)
    assert seeds == ['https://e.com/plain', {'url': 'https://e.com/json', 'priority': 9}]
    # 队列已被 drain
    assert await redis_client.llen('cola_test:seeds') == 0


async def test_mysql_seed_provider():
    aiomysql = pytest.importorskip('aiomysql')
    try:
        conn = await aiomysql.connect(**MYSQL, autocommit=True)
    except Exception:
        pytest.skip('mysql 不可用')
    async with conn.cursor() as cur:
        await cur.execute('DROP TABLE IF EXISTS test_seeds')
        await cur.execute(
            'CREATE TABLE test_seeds (url VARCHAR(255), category VARCHAR(32))')
        await cur.executemany(
            'INSERT INTO test_seeds VALUES (%s, %s)',
            [('https://e.com/1', 'a'), ('https://e.com/2', 'b')])
    conn.close()

    crawler = make_crawler({
        'MYSQL_HOST': MYSQL['host'], 'MYSQL_PORT': MYSQL['port'],
        'MYSQL_USER': MYSQL['user'], 'MYSQL_PASSWORD': MYSQL['password'],
        'MYSQL_DB': MYSQL['db'],
        'SEED_SQL': 'SELECT url, category FROM test_seeds ORDER BY url',
    })
    seeds = await collect(MySQLSeedProvider(crawler))
    assert seeds == [
        {'url': 'https://e.com/1', 'category': 'a'},
        {'url': 'https://e.com/2', 'category': 'b'},
    ]
    request = seed_to_request(seeds[0], crawler.spider)
    assert request.meta['category'] == 'a'


async def test_postgres_seed_provider():
    asyncpg = pytest.importorskip('asyncpg')
    try:
        conn = await asyncpg.connect(POSTGRES_DSN)
    except Exception:
        pytest.skip('postgres 不可用')
    await conn.execute('DROP TABLE IF EXISTS test_seeds')
    await conn.execute(
        'CREATE TABLE test_seeds (url VARCHAR(255), category VARCHAR(32))')
    await conn.executemany(
        'INSERT INTO test_seeds VALUES ($1, $2)',
        [('https://e.com/1', 'a'), ('https://e.com/2', 'b')])
    await conn.close()

    crawler = make_crawler({
        'POSTGRES_DSN': POSTGRES_DSN,
        'SEED_SQL': 'SELECT url, category FROM test_seeds ORDER BY url',
    })
    seeds = await collect(PostgresSeedProvider(crawler))
    assert seeds == [
        {'url': 'https://e.com/1', 'category': 'a'},
        {'url': 'https://e.com/2', 'category': 'b'},
    ]


async def test_rabbitmq_seed_provider():
    aio_pika = pytest.importorskip('aio_pika')
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
    except Exception:
        pytest.skip('rabbitmq 不可用')
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue('cola_test:seeds', durable=True)
        await queue.purge()
        for body in ['https://e.com/plain',
                     json.dumps({'url': 'https://e.com/json'})]:
            await channel.default_exchange.publish(
                aio_pika.Message(body=body.encode()),
                routing_key='cola_test:seeds')

    provider = RabbitMQSeedProvider(make_crawler())
    seeds = await collect(provider)
    assert seeds == ['https://e.com/plain', {'url': 'https://e.com/json'}]
