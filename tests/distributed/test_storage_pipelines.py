import json

import pytest

from cola.pipeline.mysql_pipeline import MySQLPipeline
from cola.pipeline.postgres_pipeline import PostgresPipeline
from cola.pipeline.rabbitmq_pipeline import RabbitMQPipeline
from cola.pipeline.redis_pipeline import RedisPipeline
from tests.distributed.conftest import (
    MYSQL, POSTGRES_DSN, RABBITMQ_URL, make_crawler)


async def test_redis_pipeline(redis_client):
    crawler = make_crawler()
    pipeline = RedisPipeline.create_instance(crawler)
    await pipeline.open_spider(crawler.spider)
    await pipeline.process_item({'name': '甲', 'value': 1}, crawler.spider)
    await pipeline.process_item({'name': '乙', 'value': 2}, crawler.spider)
    await pipeline.close_spider(crawler.spider)

    rows = [json.loads(r) for r in
            await redis_client.lrange('cola_test:items', 0, -1)]
    assert rows == [{'name': '甲', 'value': 1}, {'name': '乙', 'value': 2}]


async def test_mysql_pipeline_batching():
    aiomysql = pytest.importorskip('aiomysql')
    try:
        conn = await aiomysql.connect(**MYSQL, autocommit=True)
    except Exception:
        pytest.skip('mysql 不可用')
    async with conn.cursor() as cur:
        await cur.execute('DROP TABLE IF EXISTS test_items')
        await cur.execute(
            'CREATE TABLE test_items (name VARCHAR(32), value INT)')

    crawler = make_crawler({
        'MYSQL_HOST': MYSQL['host'], 'MYSQL_PORT': MYSQL['port'],
        'MYSQL_USER': MYSQL['user'], 'MYSQL_PASSWORD': MYSQL['password'],
        'MYSQL_DB': MYSQL['db'], 'MYSQL_TABLE': 'test_items',
        'MYSQL_BATCH_SIZE': 2,
    })
    pipeline = MySQLPipeline.create_instance(crawler)
    await pipeline.open_spider(crawler.spider)
    for i in range(3):
        await pipeline.process_item({'name': f'n{i}', 'value': i},
                                    crawler.spider)
    # 批大小为 2:前两条已落库,第三条还在缓冲
    async with conn.cursor() as cur:
        await cur.execute('SELECT COUNT(*) FROM test_items')
        assert (await cur.fetchone())[0] == 2
    await pipeline.close_spider(crawler.spider)
    async with conn.cursor() as cur:
        await cur.execute('SELECT name, value FROM test_items ORDER BY value')
        assert await cur.fetchall() == (('n0', 0), ('n1', 1), ('n2', 2))
    conn.close()


async def test_postgres_pipeline():
    asyncpg = pytest.importorskip('asyncpg')
    try:
        conn = await asyncpg.connect(POSTGRES_DSN)
    except Exception:
        pytest.skip('postgres 不可用')
    await conn.execute('DROP TABLE IF EXISTS test_items')
    await conn.execute('CREATE TABLE test_items (name VARCHAR(32), value INT)')

    crawler = make_crawler({
        'POSTGRES_DSN': POSTGRES_DSN,
        'POSTGRES_TABLE': 'test_items',
        'POSTGRES_BATCH_SIZE': 10,
    })
    pipeline = PostgresPipeline.create_instance(crawler)
    await pipeline.open_spider(crawler.spider)
    await pipeline.process_item({'name': 'a', 'value': 1}, crawler.spider)
    await pipeline.process_item({'name': 'b', 'value': 2}, crawler.spider)
    await pipeline.close_spider(crawler.spider)

    rows = await conn.fetch('SELECT name, value FROM test_items ORDER BY value')
    assert [(r['name'], r['value']) for r in rows] == [('a', 1), ('b', 2)]
    await conn.close()


async def test_rabbitmq_pipeline():
    aio_pika = pytest.importorskip('aio_pika')
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
    except Exception:
        pytest.skip('rabbitmq 不可用')

    crawler = make_crawler()
    pipeline = RabbitMQPipeline.create_instance(crawler)
    await pipeline.open_spider(crawler.spider)
    await pipeline.process_item({'name': 'x'}, crawler.spider)
    await pipeline.close_spider(crawler.spider)

    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue('cola_test:items', durable=True)
        message = await queue.get(fail=False)
        assert message is not None
        async with message.process():
            assert json.loads(message.body) == {'name': 'x'}
        await queue.purge()
