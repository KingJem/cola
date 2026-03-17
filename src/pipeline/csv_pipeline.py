"""CsvPipeline：将 Item 写入 CSV 文件"""
import csv
from pathlib import Path
from loguru import logger
from src.pipeline.base import BasePipeline


class CsvPipeline(BasePipeline):
    """
    将爬取到的 Item 写入 CSV 文件。
    列名从第一个 Item 的 key 自动推断。

    配置：
        ITEM_PIPELINES = {
            'src.pipeline.csv_pipeline.CsvPipeline': 900,
        }
        CSV_FEED_URI = 'output.csv'  # 输出文件路径（默认 output.csv）
    """

    def __init__(self):
        self.file = None
        self.writer = None
        self.uri = None
        self._headers_written = False

    @classmethod
    def create_instance(cls, crawler):
        instance = cls()
        instance.uri = crawler.settings.get('CSV_FEED_URI', 'output.csv')
        return instance

    async def open_spider(self, spider):
        self.file = open(self.uri, 'a', newline='', encoding='utf-8')
        logger.info(f"CsvPipeline: writing to {Path(self.uri).resolve()}")

    async def close_spider(self, spider):
        if self.file:
            self.file.flush()
            self.file.close()
            self.file = None
            logger.info(f"CsvPipeline: closed {self.uri}")

    async def process_item(self, item, spider):
        if self.file is None:
            logger.warning("CsvPipeline: file not open, skipping item")
            return item
        data = dict(item) if hasattr(item, 'items') else item
        if not self._headers_written:
            self.writer = csv.DictWriter(self.file, fieldnames=list(data.keys()))
            self.writer.writeheader()
            self._headers_written = True
        self.writer.writerow(data)
        return item
