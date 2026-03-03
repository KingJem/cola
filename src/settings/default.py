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
