from pprint import pformat

from loguru import logger


class StatsCollector:
    def __init__(self, crawler):
        self.crawler = crawler
        self.stats = {}

    def inc_value(self, key, count=1, start=0):
        self.stats[key] = self.stats.setdefault(key, start) + count

    def get_value(self, key, default=None):
        return self.stats.get(key, default)

    def get_stat(self):
        return self.stats

    def set_stat(self, stats):
        self.stats = stats

    def clear_stat(self):
        self.stats.clear()

    def max_value(self, key, value):
        self.stats[key] = max(self.stats.setdefault(key, value), value)

    def min_value(self, key, value):
        self.stats[key] = min(self.stats.setdefault(key, value), value)

    def open_spider(self, spider):
        pass

    def close_spider(self, spider, reason):
        self.stats['reason'] = reason

        logger.info(f"Spider {spider.name} stat:\n" + pformat(self.stats))

    def __setitem__(self, key, value):
        self.stats[key] = value

    def __getitem__(self, item):
        return self.stats.get(item)

    def __delitem__(self, key):
        del self.stats[key]
