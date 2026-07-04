"""从 RabbitMQ 队列读取种子(basic_get 逐条拉取,队列空即返回)。

消息体为纯 URL 或 JSON 对象。队列名 SEED_RABBITMQ_QUEUE,
默认 '{PROJECT_NAME}:seeds'。消息在成功转为种子后 ack。
"""
import json

from cola.datasources.base import SeedProvider


class RabbitMQSeedProvider(SeedProvider):

    def __init__(self, crawler):
        super().__init__(crawler)
        project = self.settings.get('PROJECT_NAME', 'cola')
        self.queue_name = (self.settings.get('SEED_RABBITMQ_QUEUE')
                           or f'{project}:seeds')
        self.url = self.settings.get('RABBITMQ_URL',
                                     'amqp://guest:guest@localhost:5672/')
        self.connection = None
        self.channel = None

    async def open(self):
        try:
            import aio_pika
        except ImportError as exc:
            raise RuntimeError(
                "RabbitMQSeedProvider 需要 aio-pika,"
                "安装:pip install 'cola[rabbitmq]'") from exc
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()
        await self.channel.declare_queue(self.queue_name, durable=True)

    async def seeds(self):
        queue = await self.channel.get_queue(self.queue_name)
        while True:
            message = await queue.get(fail=False)
            if message is None:
                return
            async with message.process():
                raw = message.body.decode('utf-8').strip()
            if not raw:
                continue
            if raw.startswith('{'):
                try:
                    yield json.loads(raw)
                    continue
                except json.JSONDecodeError:
                    pass
            yield raw

    async def close(self):
        if self.connection:
            await self.connection.close()
