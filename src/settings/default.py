"""
default config
"""

PROJECT_NAME = 'test'

LIST = [403, 404]

CONCURRENT_REQUESTS = 16

DOWNLOADER_CLASS = 'src.downloaders.aio_http_downloader.AioHttpDownloader'

VERIFY_SSL = False

TIMEOUT = 30

MAX_RETRY = 3

LOG_LEVEL = 'INFO'

DOWNLOADER_MIDDLEWARES = {}   # {class_path: priority}
ITEM_PIPELINES = {}           # {class_path: priority}
DUPEFILTER_CLASS = 'src.dupefilter.RFPDupeFilter'
DUPEFILTER_DEBUG = False
# RedisRFPDupeFilter settings.  Install with ``pip install cola[redis]`` and
# set DUPEFILTER_CLASS to 'src.redis_dupefilter.RedisRFPDupeFilter' to enable.
REDIS_URL = 'redis://localhost:6379/0'
REDIS_DUPEFILTER_KEY = None
REDIS_DUPEFILTER_PERSIST = True
JSON_FEED_URI = 'output.jl'
CSV_FEED_URI = 'output.csv'


def get_default_settings() -> dict:
    import sys
    module = sys.modules[__name__]
    return {k: getattr(module, k) for k in dir(module) if k.isupper()}
