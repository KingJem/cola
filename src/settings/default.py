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
