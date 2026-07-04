# Cola 爬虫框架用户指南

## 📖 简介

Cola 是一个高性能的异步 Python 爬虫框架，基于 asyncio 和 aiohttp 构建。

### 主要特性

- ⚡ 异步架构，高效并发
- 🎯 简洁易用的 API
- 🔧 灵活的配置系统
- 📊 内置统计收集
- 🔄 智能请求调度

## 🚀 快速开始

### 安装

```bash
uv sync
```

### 第一个爬虫

```python
from cola.spiders import Spider
from cola.http.request import Request

class MySpider(Spider):
    start_urls = ['https://example.com']
    
    async def parse(self, response):
        title = response.xpath('//title/text()')
        print(f"标题: {title}")
        
        # 生成新请求
        for link in response.xpath('//a/@href'):
            yield Request(url=response._urljoin(link))
```

### 运行爬虫

```python
import asyncio
from cola.crawler import CrawlerProcess
from cola.utils.project import get_settings

async def main():
    settings = get_settings()
    process = CrawlerProcess(settings)
    await process.crawl(MySpider)
    await process.start()

asyncio.run(main())
```

## 📝 核心概念

### Spider（爬虫）

继承 `Spider` 类创建爬虫：

```python
class MySpider(Spider):
    start_urls = ['url1', 'url2']  # 起始URLs
    custom_settings = {}            # 自定义配置
    
    async def parse(self, response):
        # 解析逻辑
        pass
```

### Request（请求）

```python
request = Request(
    url='https://example.com',
    method='GET',
    headers={'User-Agent': '...'},
    priority=10,              # 优先级
    callback=self.parse_page  # 回调函数
)

# 传递元数据
request.meta['page'] = 1
```

### Response（响应）

```python
# 常用方法
data = response.json()                    # 解析JSON
titles = response.xpath('//h1/text()')    # XPath
items = response.css('.item')             # CSS选择器
emails = response.re(r'[\w\.-]+@[\w\.-]+')  # 正则
next_req = response.follow('/page/2')     # 生成新请求
```

### Item（数据项）

```python
from cola.item.items import Item

class ProductItem(Item):
    FIELDS = {
        'name': str,
        'price': float,
        'url': str,
    }

# 使用
item = ProductItem()
item['name'] = 'Product'
yield item
```

## ⚙️ 配置

### 默认配置

```python
PROJECT_NAME = 'test'
CONCURRENT_REQUESTS = 16              # 全局并发数
CONCURRENT_REQUESTS_PER_DOMAIN = 0   # 每域名并发上限(0 不限)
TIMEOUT = 30                         # 请求超时
VERIFY_SSL = False                   # SSL 验证
DOWNLOAD_MAXSIZE = 0                 # 响应体字节上限(0 不限)
DEPTH_LIMIT = 0                      # 爬取深度上限(种子为 0;0 不限)
LOG_FILE = None                      # 追加日志文件

# 重试(由 Retry 中间件统一负责)
MAX_RETRY_TIMES = 3
RETRY_HTTP_CODES = [408, 429, 500, 502, 503, 504, 522, 524]
```

### 重试、限流与过滤

重试由 `cola.middleware.retry.Retry` 中间件负责(默认启用):命中
`RETRY_HTTP_CODES` 的响应或网络异常会重新入队,超过 `MAX_RETRY_TIMES`
放弃;单请求可 `request.meta['dont_retry'] = True` 关闭。

```python
DOWNLOADER_MIDDLEWARES = {
    'cola.middleware.retry.Retry': 100,
    'cola.middleware.offsite.Offsite': 50,   # 按 spider.allowed_domains 过滤
}

class MySpider(Spider):
    allowed_domains = ['example.com']       # 仅抓本域及子域
    custom_settings = {
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEPTH_LIMIT': 3,
        'DOWNLOAD_MAXSIZE': 10 * 1024 * 1024,
    }
```

### 自定义配置

爬虫级别：

```python
class MySpider(Spider):
    custom_settings = {
        'CONCURRENT_REQUESTS': 5,
        'TIMEOUT': 60,
    }
```

全局级别：

```python
settings = SettingsManager({
    'PROJECT_NAME': 'my_project',
    'CONCURRENT_REQUESTS': 32,
})
```

### 多机 Redis 去重

多个 Worker 使用同一个 Redis key 时，请求指纹通过 Redis 的原子 `SADD`
去重；每个 Worker 仍由自己的 `CONCURRENT_REQUESTS` 限制协程数。

```bash
pip install 'cola[redis]'
```

```python
DUPEFILTER_CLASS = 'cola.redis_dupefilter.RedisRFPDupeFilter'
REDIS_URL = 'redis://redis:6379/0'
REDIS_DUPEFILTER_KEY = 'my-project:dupefilter'
# 保持 True，避免任一 Worker 结束时清空所有节点共用的去重集合。
REDIS_DUPEFILTER_PERSIST = True
```

## 🌐 分布式主从架构

完整设计见 [docs/DISTRIBUTED_DESIGN.md](docs/DISTRIBUTED_DESIGN.md)。
所有节点运行同一份 Spider 代码,差别只在 settings:

```python
# master 节点:从数据源读种子,写入共享 Redis 队列,同时参与消费
master_settings = {
    'PROJECT_NAME': 'myproj',
    'NODE_ROLE': 'master',
    'REDIS_URL': 'redis://redis:6379/0',
    'SCHEDULER_CLASS': 'cola.distributed.scheduler.RedisScheduler',
    'DUPEFILTER_CLASS': 'cola.distributed.dupefilter.AsyncRedisDupeFilter',
    # 种子来源(可多个):redis / mysql / postgres / doris / rabbitmq
    'SEED_SOURCES': ['cola.datasources.mysql_source.MySQLSeedProvider'],
    'SEED_SQL': 'SELECT url, category FROM seeds WHERE status = 0',
    'MYSQL_HOST': 'mysql', 'MYSQL_DB': 'crawler',
    'MYSQL_USER': 'root', 'MYSQL_PASSWORD': '***',
    # 结果存储(可多个):redis / mysql / postgres / doris / rabbitmq
    'ITEM_PIPELINES': {'cola.pipeline.mysql_pipeline.MySQLPipeline': 300},
    'MYSQL_TABLE': 'results',
}

# worker 节点:跳过 start_requests,只消费共享队列
worker_settings = {
    **master_settings,
    'NODE_ROLE': 'worker',
    'SEED_SOURCES': [],
    'SCHEDULER_IDLE_TIMEOUT': 0,   # 常驻;>0 表示空闲 N 秒后自动退出
}
```

种子协议:URL 字符串或 JSON 对象
`{"url": "...", "callback": "parse_detail", "priority": 5, "meta": {...}}`;
关系型数据源(`SEED_SQL`)行内 `url` 列必填,其余列自动进入 `request.meta`。

### 自定义种子转换(make_request_from_seed)

所有种子源(redis/mysql/pg/doris/rabbitmq)统一经 Spider 的
`make_request_from_seed(seed)` 钩子转成 Request,重写它即可完全掌控转换,
例如把整个 task 放进 `request.meta`:

```python
class MySpider(Spider):
    def make_request_from_seed(self, seed):
        # seed 是 URL 字符串或已解析的 dict
        return Request(seed['url'], callback=self.parse, meta={'task': seed})

    async def parse(self, response):
        task = response.meta['task']   # 拿到完整原始 task
        ...
```

返回 `None` 可跳过该种子。不重写时默认按上面的种子协议处理。

## 🔥 热配置更新

```python
settings = {'HOT_CONFIG_ENABLED': True}   # 自动挂载 HotConfig 扩展
```

运行中发布配置(项目级或爬虫级频道):

```bash
redis-cli PUBLISH 'myproj:config' '{"CONCURRENT_REQUESTS": 32}'
redis-cli PUBLISH 'myproj:MySpider:config' '{"DOWNLOAD_DELAY": 0.5}'
```

`CONCURRENT_REQUESTS` 即时调整并发信号量;`DOWNLOAD_DELAY`/`RANDOMNESS`
由中间件每次请求动态读取。

## 🎯 高级用法

### 优先级队列

```python
yield Request(url='important.com', priority=100)  # 高优先级
yield Request(url='normal.com', priority=1)       # 低优先级
```

### 传递元数据

```python
request = Request(url=url)
request.meta['page'] = 1
request.meta['category'] = 'books'

# 在回调中访问
page = response.meta['page']
```

### POST 请求

```python
yield Request(
    url='https://example.com/api',
    method='POST',
    body='{"key": "value"}',
    headers={'Content-Type': 'application/json'}
)
```

### 使用代理

```python
request = Request(
    url='https://example.com',
    proxy={'http': 'http://proxy.com:8080'}
)
```

## 📊 统计收集

```python
# 访问统计
stats = self.crawler.stat_collector
stats['custom_metric'] = 100
stats.inc_value('items_count', 1)

# 自动收集的统计
# - start_time/end_time
# - scheduled.enqueued.requests.count
# - reason
```

## 💡 最佳实践

1. **设置合适的并发数**：小网站 1-5，中等 5-16，大型 16-32
2. **添加延迟**：`await asyncio.sleep(1)`
3. **设置 User-Agent**：模拟真实浏览器
4. **错误处理**：使用 try-except 捕获异常
5. **遵守 robots.txt**：检查爬取许可

## 📚 示例

查看 `demo_project/spiders/quotes_spider.py` 获取完整示例。

运行示例：

```bash
python demo_project/run.py
```

## 🔗 相关文档

- [API 参考文档](API_REFERENCE.md)
- [测试代码](tests/)
- [默认配置](cola/settings/default.py)
