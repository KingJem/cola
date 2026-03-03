# Cola 框架 API 参考文档

## 核心模块

### Spider

**路径**: `src.spiders.Spider`

基础爬虫类，所有爬虫必须继承此类。

#### 类属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `start_urls` | list | 起始URL列表 |
| `custom_settings` | dict | 自定义配置 |
| `name` | property | 爬虫名称（只读） |

#### 方法

##### `start_requests(self) -> Generator`

生成初始请求。

**返回**: Request 对象的生成器

**示例**:
```python
def start_requests(self):
    for url in self.start_urls:
        yield Request(url=url)
```

##### `parse(self, response) -> AsyncGenerator`

默认响应解析回调函数。

**参数**:
- `response` (Response): HTTP响应对象

**返回**: Request 或 Item 的异步生成器

**示例**:
```python
async def parse(self, response):
    yield {'title': response.xpath('//title/text()')}
```

---

### Request

**路径**: `src.http.request.Request`

HTTP 请求封装类。

#### 构造函数

```python
Request(
    url: str,
    *,
    headers: dict = None,
    priority: int = 0,
    method: str = "GET",
    cookies: dict = None,
    proxy: dict = None,
    body: str = None,
    callback: Callable = None
)
```

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | str | 必需 | 请求URL |
| `method` | str | 'GET' | HTTP方法 |
| `headers` | dict | None | 请求头 |
| `cookies` | dict | None | Cookies |
| `priority` | int | 0 | 优先级（越大越优先） |
| `callback` | Callable | None | 回调函数 |
| `body` | str | None | 请求体 |
| `proxy` | dict | None | 代理配置 |

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `url` | str | 请求URL |
| `method` | str | HTTP方法 |
| `headers` | dict | 请求头 |
| `priority` | int | 优先级 |
| `meta` | dict | 元数据字典 |

---

### Response

**路径**: `src.http.response.Response`

HTTP 响应封装类。

#### 构造函数

```python
Response(
    url: str,
    *,
    status: int,
    headers: Dict[str, str],
    body: bytes,
    request: Request = None
)
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `url` | str | 响应URL |
| `status_code` | int | HTTP状态码 |
| `headers` | dict | 响应头 |
| `body` | bytes | 原始字节内容 |
| `text` | property | 文本内容（自动解码） |
| `request` | Request | 原始请求对象 |
| `meta` | property | 元数据（来自request） |

#### 方法

##### `json(self) -> dict`

解析JSON响应。

**返回**: 解析后的Python对象

##### `xpath(self, query: str) -> list`

使用XPath选择器提取数据。

**参数**:
- `query` (str): XPath表达式

**返回**: 匹配元素列表

**示例**:
```python
titles = response.xpath('//h1/text()')
links = response.xpath('//a/@href')
```

##### `css(self, query: str) -> list`

使用CSS选择器提取数据。

**参数**:
- `query` (str): CSS选择器

**返回**: 匹配元素列表

##### `re(self, pattern: str) -> list`

使用正则表达式提取数据。

**参数**:
- `pattern` (str): 正则表达式

**返回**: 匹配字符串列表

##### `follow(self, url: str, callback=None, **kwargs) -> Request`

生成新请求（自动处理相对URL）。

**参数**:
- `url` (str): 相对或绝对URL
- `callback` (Callable): 回调函数
- `**kwargs`: Request的其他参数

**返回**: Request对象

---

### Item

**路径**: `src.item.items.Item`

结构化数据容器。

#### 使用方法

```python
from src.item.items import Item

class MyItem(Item):
    FIELDS = {
        'field1': str,
        'field2': int,
    }

# 创建实例
item = MyItem()
item['field1'] = 'value'
item['field2'] = 42

# 转换为字典
data = item.todict()
```

#### 方法

##### `todict(self) -> str`

转换为格式化字典字符串。

---

## 引擎与调度

### Crawler

**路径**: `src.crawler.Crawler`

爬虫实例管理器。

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `spider` | Spider | Spider实例 |
| `engine` | Engine | 引擎实例 |
| `settings` | SettingsManager | 配置管理器 |
| `stat_collector` | StatsCollector | 统计收集器 |

#### 方法

##### `crawl(self) -> Coroutine`

启动爬取流程。

##### `close(self, reason='finished') -> Coroutine`

关闭爬虫。

---

### CrawlerProcess

**路径**: `src.crawler.CrawlerProcess`

爬虫进程管理器。

#### 构造函数

```python
CrawlerProcess(settings: SettingsManager)
```

#### 方法

##### `crawl(self, spider: Type[Spider]) -> Coroutine`

添加爬虫到进程。

**参数**:
- `spider` (Type[Spider]): Spider类（非实例）

##### `start(self) -> Coroutine`

启动所有爬虫。

**示例**:
```python
process = CrawlerProcess(settings)
await process.crawl(MySpider)
await process.start()
```

---

### Engine

**路径**: `src.core.engine.Engine`

爬虫引擎，协调各组件。

#### 主要属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `downloader` | Downloader | 下载器 |
| `scheduler` | Scheduler | 调度器 |
| `running` | bool | 运行状态 |

#### 方法

##### `start_spider(self, spider) -> Coroutine`

启动Spider。

---

### Scheduler

**路径**: `src.core.scheduler.Scheduler`

请求调度器（优先级队列）。

#### 方法

##### `enqueue_request(self, request) -> Coroutine`

将请求加入队列。

##### `next_request(self) -> Coroutine`

获取下一个请求。

##### `idle(self) -> bool`

检查队列是否为空。

---

## 下载器

### Downloader

**路径**: `src.downloaders.Downloader`

下载器基类。

### AioHttpDownloader

**路径**: `src.downloaders.aio_http_downloader.AioHttpDownloader`

基于 aiohttp 的异步下载器。

#### 方法

##### `fetch(self, request: Request) -> Response`

执行HTTP请求。

---

## 配置管理

### SettingsManager

**路径**: `src.settings.settings_manager.SettingsManager`

配置管理器。

#### 构造函数

```python
SettingsManager(custom_settings: dict = None)
```

#### 方法

##### `get(self, key, default=None) -> Any`

获取配置值。

##### `getint(self, key, default=0) -> int`

获取整数配置。

##### `getbool(self, key, default=False) -> bool`

获取布尔配置。

##### `getlist(self, key, default=None) -> list`

获取列表配置。

##### `set(self, key, value)`

设置配置值。

**示例**:
```python
settings = SettingsManager({'KEY': 'value'})
value = settings.get('KEY')
timeout = settings.getint('TIMEOUT', 30)
```

---

## 统计收集

### StatsCollector

**路径**: `src.stats_collector.StatsCollector`

统计信息收集器。

#### 使用方法

```python
# 在Spider中访问
stats = self.crawler.stat_collector

# 设置值
stats['custom_key'] = 'value'

# 递增计数
stats.inc_value('count', 1)
```

#### 自动收集的统计

- `start_time`: 开始时间
- `end_time`: 结束时间
- `scheduled.enqueued.requests.count`: 入队请求数
- `reason`: 完成原因

---

## 工具函数

### 项目工具

**路径**: `src.utils.project`

##### `get_settings() -> SettingsManager`

获取项目默认配置。

### 类加载器

**路径**: `src.utils`

##### `load_class(path: str) -> type`

动态加载类。

**参数**:
- `path` (str): 类的完整路径，如 'src.spiders.Spider'

**返回**: 类对象

---

## 默认配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `PROJECT_NAME` | 'test' | 项目名称 |
| `CONCURRENT_REQUESTS` | 16 | 并发请求数 |
| `DOWNLOADER_CLASS` | 'src.downloaders.aio_http_downloader.AioHttpDownloader' | 下载器类 |
| `VERIFY_SSL` | False | SSL验证 |
| `TIMEOUT` | 30 | 请求超时（秒） |
| `MAX_RETRY` | 3 | 最大重试次数 |
| `LOG_LEVEL` | 'INFO' | 日志级别 |

---

## 异常类

**路径**: `src.exceptions`

框架定义的自定义异常（待补充）。

---

**文档版本**: 1.0  
**更新日期**: 2025-11-24
