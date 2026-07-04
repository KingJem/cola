"""RabbitMQPipeline:Item 序列化为 JSON 发布到 RabbitMQ 队列。

配置:
    ITEM_PIPELINES = {'src.pipeline.rabbitmq_pipeline.RabbitMQPipeline': 300}
    RABBITMQ_URL = 'amqp://guest:guest@host:5672/'
    RABBITMQ_ITEMS_QUEUE = None  # 默认 '{PROJECT_NAME}:items'
"""
import json

from loguru import logger

from src.pipeline.base import BasePipeline


class RabbitMQPipeline(BasePipeline):

    def __init__(self, settings):
        self.settings = settings
        project = settings.get('PROJECT_NAME', 'cola')
        self.queue_name = (settings.get('RABBITMQ_ITEMS_QUEUE')
                           or f'{project}:items')
        self.url = settings.get('RABBITMQ_URL',
                                'amqp://guest:guest@localhost:5672/')
        self.connection = None
        self.channel = None

    @classmethod
    def create_instance(cls, crawler):
        return cls(crawler.settings)

    async def open_spider(self, spider):
        try:
            import aio_pika
        except ImportError as exc:
            raise RuntimeError(
                "RabbitMQPipeline 需要 aio-pika,"
                "安装:pip install 'cola[rabbitmq]'") from exc
        self._aio_pika = aio_pika
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()
        await self.channel.declare_queue(self.queue_name, durable=True)
        logger.info(f"RabbitMQPipeline: publishing items to {self.queue_name}")

    async def close_spider(self, spider):
        if self.connection:
            await self.connection.close()

    async def process_item(self, item, spider):
        data = dict(item) if hasattr(item, 'items') else item
        message = self._aio_pika.Message(
            body=json.dumps(data, ensure_ascii=False).encode('utf-8'),
            delivery_mode=self._aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.channel.default_exchange.publish(
            message, routing_key=self.queue_name)
        return item
