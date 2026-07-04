"""
default config
"""

PROJECT_NAME = 'test'

LIST = [403, 404]

CONCURRENT_REQUESTS = 16

DOWNLOADER_CLASS = 'src.downloaders.aio_http_downloader.AioHttpDownloader'

VERIFY_SSL = False

TIMEOUT = 30

LOG_LEVEL = 'INFO'
# 追加日志文件(loguru sink);None 只输出到 stderr
LOG_FILE = None

# ---- 重试(由 Retry 中间件统一负责,下载器本身只请求一次)----
MAX_RETRY_TIMES = 3
RETRY_HTTP_CODES = [408, 429, 500, 502, 503, 504, 522, 524]
IGNORE_HTTP_CODES = []
RETRY_EXCEPTIONS = []          # 额外的可重试异常类
RETRY_PRIORITY = -1            # 重试请求的优先级偏移

# 每域名并发上限;0 = 不限制(仅受全局 CONCURRENT_REQUESTS 约束)
CONCURRENT_REQUESTS_PER_DOMAIN = 0
# 响应体大小上限(字节);0 = 不限制
DOWNLOAD_MAXSIZE = 0
# 爬取深度上限(种子为 0);0 = 不限制
DEPTH_LIMIT = 0
# Processor 队列长度(满时反压解析协程)
PROCESSOR_QUEUE_SIZE = 128

DOWNLOADER_MIDDLEWARES = {   # {class_path: priority}
    'src.middleware.retry.Retry': 100,
}
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

EXTENSIONS = []

# ---- 分布式(Redis 主从)----
# 节点角色:standalone | master | worker
NODE_ROLE = 'standalone'
# 调度器实现;分布式模式设为 'src.distributed.scheduler.RedisScheduler'
SCHEDULER_CLASS = 'src.core.scheduler.Scheduler'
# Redis 请求队列键;None 时取 '{PROJECT_NAME}:requests'
SCHEDULER_QUEUE_KEY = None
# 退出前允许队列持续为空的秒数;0 表示永不因空闲退出(常驻 worker)
SCHEDULER_IDLE_TIMEOUT = 10.0
# 爬虫结束时是否保留 Redis 队列
SCHEDULER_PERSIST = True
# 启动时清空请求队列与去重集合(重跑全量时用)
SCHEDULER_FLUSH_ON_START = False

# ---- 种子数据源(master 角色)----
# SeedProvider 类路径列表,如:
#   ['src.datasources.mysql_source.MySQLSeedProvider']
SEED_SOURCES = []
# 关系型数据源的种子查询,行须含 url 列,其余列进 meta
SEED_SQL = None
# 种子默认回调方法名(spider 上的方法)
SEED_CALLBACK = None
SEED_REDIS_KEY = None          # None -> '{PROJECT_NAME}:seeds'
SEED_RABBITMQ_QUEUE = None     # None -> '{PROJECT_NAME}:seeds'

# ---- 数据源连接 ----
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = ''
MYSQL_DB = None
MYSQL_TABLE = None             # MySQLPipeline 目标表
MYSQL_BATCH_SIZE = 100

POSTGRES_DSN = None            # 如 'postgresql://user:pass@host:5432/db'
POSTGRES_TABLE = None
POSTGRES_BATCH_SIZE = 100

# Doris 走 MySQL 协议(FE 查询端口,默认 9030)
DORIS_HOST = 'localhost'
DORIS_PORT = 9030
DORIS_USER = 'root'
DORIS_PASSWORD = ''
DORIS_DB = None
DORIS_TABLE = None
DORIS_BATCH_SIZE = 100

RABBITMQ_URL = 'amqp://guest:guest@localhost:5672/'
RABBITMQ_ITEMS_QUEUE = None    # None -> '{PROJECT_NAME}:items'

REDIS_ITEMS_KEY = None         # None -> '{PROJECT_NAME}:items'

# ---- 热配置 ----
HOT_CONFIG_ENABLED = False     # True 时自动挂载 HotConfig 扩展
HOT_CONFIG_CHANNEL = None      # None -> '{PROJECT_NAME}:config'


def get_default_settings() -> dict:
    import sys
    module = sys.modules[__name__]
    return {k: getattr(module, k) for k in dir(module) if k.isupper()}
