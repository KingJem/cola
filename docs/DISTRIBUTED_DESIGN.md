# Cola 分布式架构设计

## 目标

1. **Redis 主从架构**:master 节点负责种子注入与全局协调,worker 节点从共享 Redis
   队列消费请求;所有节点共享 Redis 去重集合(类 scrapy-redis)。
2. **多数据源**:master 可从 redis / mysql / postgresql / doris / rabbitmq 读取种子,
   抓取结果可写入上述任意存储。
3. **热配置更新**:运行中的爬虫通过 Redis Pub/Sub 接收配置变更(并发数、下载延迟等)。

## 节点角色(NODE_ROLE)

| 角色 | start_requests | 种子数据源 | 队列 | 退出条件 |
|------|----------------|-----------|------|----------|
| `standalone`(默认) | 消费 | 不启用 | 内存 | 队列空即退出 |
| `master` | 消费 | 启用(SEED_SOURCES) | Redis | 空闲超时 SCHEDULER_IDLE_TIMEOUT |
| `worker` | 跳过 | 不启用 | Redis | 空闲超时(0 = 永不退出) |

同一份 Spider 代码在所有节点运行;区别只在 settings。master 同时也参与消费(可通过
CONCURRENT_REQUESTS=0 以外的手段专职调度,通常无必要)。

## 新增模块

```
src/distributed/
    connection.py   # redis.asyncio 客户端工厂(按 REDIS_URL)
    serialize.py    # Request <-> dict/JSON(callback 序列化为方法名)
    queue.py        # RedisPriorityQueue:ZSET,score=-priority,BZPOPMIN 阻塞弹出
    dupefilter.py   # AsyncRedisDupeFilter:SADD 原子去重(异步)
    scheduler.py    # RedisScheduler:与内存 Scheduler 同接口
    seed_loader.py  # master 专用:从 SEED_SOURCES 拉种子 -> engine.enqueue_requests
src/datasources/
    base.py         # SeedProvider 抽象:open()/seeds() 异步迭代/close()
    redis_source.py # LPOP 列表
    mysql_source.py # aiomysql,SEED_SQL 查询
    postgres_source.py # asyncpg
    doris_source.py # 走 MySQL 协议(复用 mysql_source)
    rabbitmq_source.py # aio-pika 消费队列
src/pipeline/
    redis_pipeline.py     # RPUSH items JSON
    mysql_pipeline.py     # aiomysql 批量 INSERT
    postgres_pipeline.py  # asyncpg 批量 INSERT
    doris_pipeline.py     # MySQL 协议 INSERT(Doris 兼容)
    rabbitmq_pipeline.py  # 发布 JSON 消息
src/extension/
    hot_config.py   # 订阅 {PROJECT_NAME}:config 与 {PROJECT_NAME}:{spider}:config
```

## 引擎改动(最小侵入)

- `SCHEDULER_CLASS` 配置化(默认仍为内存 Scheduler)。
- 去重器 `is_seen`/`mark_seen` 支持协程(awaitable 则 await)。
- `NODE_ROLE=worker` 时跳过 start_requests。
- Crawler 接线 `Subscriber` 与 `ExtensionManager`(修复既有半成品事件系统),
  发出 spider_opened / spider_closed 事件。
- TaskManager 支持 `resize(n)` 动态调整并发上限(热配置用)。

## Redis 键约定

| 键 | 类型 | 用途 |
|----|------|------|
| `{PROJECT_NAME}:requests` | zset | 请求队列(score = -priority) |
| `{PROJECT_NAME}:dupefilter` | set | 请求指纹 |
| `{PROJECT_NAME}:items` | list | RedisPipeline 输出 |
| `{PROJECT_NAME}:config` | pubsub | 项目级热配置 |
| `{PROJECT_NAME}:{spider}:config` | pubsub | 爬虫级热配置 |
| `colad:nodes:{node_id}` | hash+TTL | colad 节点注册(心跳) |

## Request 序列化

JSON 字段:`url, method, headers, body, cookies, proxy, priority, dont_filter,
meta, callback`。`callback` 存 spider 方法名;反序列化时 `getattr(spider, name)`。
`meta` 必须 JSON 可序列化。

## 热配置协议

发布 JSON 到配置频道:`{"CONCURRENT_REQUESTS": 32, "DOWNLOAD_DELAY": 0.5}`。
HotConfig 扩展逐键 `settings.set()`;`CONCURRENT_REQUESTS` 额外调用
`task_manager.resize()`;DownloadDelay 中间件改为每次请求动态读取 settings。

## 种子协议

种子为 JSON 对象或纯 URL 字符串:
`{"url": "...", "method": "GET", "meta": {...}, "priority": 0, "callback": "parse"}`
关系型数据源(mysql/pg/doris)由 `SEED_SQL` 查询,行内 `url` 列必填,其余列进 `meta`。

## 可选依赖(pyproject extras)

- `redis`: redis>=5(含 asyncio,分布式必备)
- `mysql`: aiomysql(mysql + doris)
- `postgres`: asyncpg
- `rabbitmq`: aio-pika
- `all`: 以上全部
