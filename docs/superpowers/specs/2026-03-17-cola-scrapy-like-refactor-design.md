# Cola — Scrapy-like 改造设计文档

**日期：** 2026-03-17  
**作者：** OpenCode (AI)  
**状态：** 已批准，待实现

---

## 1. 背景与目标

### 现状

Cola 是一个基于 asyncio + aiohttp 的 Python 爬虫框架，已具备：
- Spider 基类、Request/Response 数据类
- 优先级调度器（Scheduler）
- 异步下载器（AioHttpDownloader）
- 基础引擎（Engine）主循环
- Item 数据模型与元类

### 已知缺陷

| 模块 | 问题 |
|---|---|
| `src/middlewares.py` | 中间件加载有 bug，收集的方法从未被调用 |
| `src/core/process.py` | `_process_item()` 是 stub，无 Pipeline 集成 |
| `src/core/engine.py` | `_schedule_request()` 有 `# todo 去重` 注释，未实现 |
| `src/utils/project.py` | `get_settings()` 自引用死循环 |
| `src/downloaders/requests_downloader.py` | 不继承 `Downloader` 抽象基类 |
| `src/middlewares.py:_add_method()` | 中间件缺少任一方法即抛异常，过于严格 |
| `src/middlewares.py:validate_middleware()` | `create_instance()` 未传 `crawler` |

### 目标

在现有代码基础上（方案 A：渐进式分层修复），完整实现以下三大核心系统：

1. **下载中间件管道**（DownloaderMiddlewareManager）—— 真正链式调用
2. **请求去重**（DupeFilter）—— 内存 set 指纹去重
3. **Item Pipeline**（PipelineManager）—— 多 Pipeline 按优先级处理

---

## 2. 整体架构

```
CrawlerProcess
  └── Crawler
        └── Engine  ← 主控循环
              ├── Scheduler                   (已有，基本完好)
              ├── DupeFilter                  ← 【新建】
              ├── DownloaderMiddlewareManager  ← 【重写 middlewares.py】
              │     ├── process_request(request, spider)
              │     ├── → AioHttpDownloader.download(request)
              │     └── process_response(response, request, spider)
              │         process_exception(request, exception, spider)
              └── Processor                   ← 【重写】
                    └── PipelineManager       ← 【新建】
                          ├── ConsolePipeline   (内置)
                          ├── JsonPipeline      (内置，写 .jl 文件)
                          └── CsvPipeline       (内置，写 .csv 文件)
```

数据流：

```
Spider.start_requests()
  → Engine._schedule_request()
        → DupeFilter.is_seen()? → 丢弃
        → Scheduler.enqueue_request()
  → Engine._crawl(request)
        → MiddlewareManager.process_request(request, spider)
              → AioHttpDownloader.download(request)
              ← MiddlewareManager.process_response(response, request, spider)
        → spider.callback(response)
              yield Request → Engine._schedule_request()  [递归]
              yield Item    → Processor.enqueue(item)
                                 → PipelineManager.process_item(item, spider)
```

---

## 3. 下载中间件系统

### 3.1 设计原则

- **Scrapy 兼容接口**：`process_request(request, spider)`、`process_response(request, response, spider)`、`process_exception(request, exception, spider)`
- **同步/异步兼容**：中间件方法可以是普通函数或 `async def`，框架自动适配
- **方法可选**：中间件只需实现需要的方法（不强制三个都有）
- **优先级控制**：通过 `DOWNLOADER_MIDDLEWARES` dict 中的数字控制顺序；`process_request` 按数字升序调用，`process_response` 按降序调用（与 Scrapy 一致）

### 3.2 重写 `src/middlewares.py`

```python
class MiddlewareManager:
    """
    下载中间件管理器。

    DOWNLOADER_MIDDLEWARES 格式：
      {'path.to.MyMiddleware': 100, 'path.to.OtherMiddleware': 200}
    数字为优先级，process_request 按升序执行，process_response 按降序执行。
    """

    def __init__(self, crawler):
        self.crawler = crawler
        self.middlewares = []      # 按 process_request 顺序（优先级升序）
        self._methods = {
            'process_request': [],
            'process_response': [],
            'process_exception': [],
        }
        self._load()

    def _load(self):
        setting = self.crawler.settings.get('DOWNLOADER_MIDDLEWARES', {})
        sorted_mws = sorted(setting.items(), key=lambda x: x[1])
        for class_path, priority in sorted_mws:
            cls = load_class(class_path)
            instance = cls.create_instance(self.crawler) if hasattr(cls, 'create_instance') else cls()
            self.middlewares.append(instance)
            for method_name in ['process_request', 'process_response', 'process_exception']:
                if hasattr(instance, method_name):
                    self._methods[method_name].append(getattr(instance, method_name))

    async def process_request(self, request, spider):
        for method in self._methods['process_request']:
            result = await _call_maybe_async(method, request, spider)
            if result is not None:
                return result  # 短路：中间件返回 Response 或新 Request
        return request

    async def process_response(self, request, response, spider):
        for method in reversed(self._methods['process_response']):
            response = await _call_maybe_async(method, request, response, spider)
        return response

    async def process_exception(self, request, exception, spider):
        for method in self._methods['process_exception']:
            result = await _call_maybe_async(method, request, exception, spider)
            if result is not None:
                return result
        return None
```

### 3.3 Engine._fetch() 重写

```python
async def _fetch(self, request):
    result = await self.middleware_manager.process_request(request, self.spider)

    if isinstance(result, Response):
        response = result
    else:
        request = result if isinstance(result, Request) else request
        try:
            response = await self.downloader.download(request)
            if response is None:
                return None
        except Exception as e:
            result = await self.middleware_manager.process_exception(request, e, self.spider)
            if result is None:
                logger.error(f"Unhandled download exception: {request.url}: {e}")
                return None
            response = result

    response = await self.middleware_manager.process_response(request, response, self.spider)

    callback = request.callback or self.spider.parse
    outputs = callback(response)
    if outputs is None:
        return None
    if inspect.iscoroutine(outputs):
        await outputs
        return None
    return self._transform(outputs)
```

---

## 4. 请求去重（DupeFilter）

### 4.1 新建 `src/dupefilter.py`

指纹算法：`SHA1(method.upper() + canonical_url)`，其中 canonical_url 对 query string 参数排序后重建。

```python
class RFPDupeFilter:
    def __init__(self, debug: bool = False):
        self.fingerprints: set = set()
        self.debug = debug

    @classmethod
    def from_crawler(cls, crawler):
        return cls(debug=crawler.settings.getbool('DUPEFILTER_DEBUG', False))

    def request_fingerprint(self, request) -> str:
        ...  # SHA1(method + canonical_url)

    def is_seen(self, request) -> bool:
        return self.request_fingerprint(request) in self.fingerprints

    def mark_seen(self, request):
        self.fingerprints.add(self.request_fingerprint(request))

    def close(self):
        self.fingerprints.clear()
```

### 4.2 Request 新增字段

```python
# src/http/request.py
dont_filter: bool = False  # True 时跳过去重
```

### 4.3 Engine 集成

```python
async def _schedule_request(self, request):
    if not request.dont_filter and self.dupe_filter.is_seen(request):
        if self.dupe_filter.debug:
            logger.debug(f"Filtered duplicate: {request.url}")
        return
    self.dupe_filter.mark_seen(request)
    await self.scheduler.enqueue_request(request)
```

`start_requests()` 默认设置 `dont_filter=True`（与 Scrapy 一致）。

### 4.4 新增默认配置

```python
DUPEFILTER_CLASS = 'src.dupefilter.RFPDupeFilter'
DUPEFILTER_DEBUG = False
```

---

## 5. Item Pipeline 系统

### 5.1 目录结构

```
src/pipeline/
├── __init__.py          # PipelineManager + DropItem
├── base.py              # BasePipeline
├── console.py           # ConsolePipeline
├── json_pipeline.py     # JsonPipeline（写 .jsonlines 文件）
└── csv_pipeline.py      # CsvPipeline（写 .csv 文件）
```

### 5.2 接口

```python
class DropItem(Exception):
    """在 Pipeline 中抛出以丢弃当前 Item"""

class BasePipeline:
    async def open_spider(self, spider): pass
    async def close_spider(self, spider): pass
    async def process_item(self, item, spider): raise NotImplementedError
```

### 5.3 PipelineManager

```python
class PipelineManager:
    # ITEM_PIPELINES = {'path.to.Pipeline': priority_int}
    # 按优先级升序执行

    async def open_spider(self, spider): ...
    async def close_spider(self, spider): ...
    async def process_item(self, item, spider) -> item | None:
        for pipeline in self.pipelines:
            try:
                item = await _call_maybe_async(pipeline.process_item, item, spider)
            except DropItem as e:
                logger.info(f"Item dropped by {type(pipeline).__name__}: {e}")
                return None
        return item
```

### 5.4 内置 Pipeline

- **ConsolePipeline**：`print(dict(item))`，调试用
- **JsonPipeline**：写 `.jl`（JSON Lines），从 `JSON_FEED_URI` 读路径
- **CsvPipeline**：写 `.csv`，从 `CSV_FEED_URI` 读路径，自动推断列名

### 5.5 Processor 重写

```python
async def _process_item(self, item):
    await self.crawler.pipeline_manager.process_item(item, self.crawler.spider)
```

### 5.6 配置

```python
ITEM_PIPELINES = {}     # {class_path: priority}
JSON_FEED_URI = 'output.jl'
CSV_FEED_URI = 'output.csv'
```

---

## 6. Bug 修复清单

| 文件 | 问题 | 修复 |
|---|---|---|
| `src/utils/project.py` | `get_settings()` 自引用 | 正确加载用户 `settings.py` 模块 |
| `src/middlewares.py` | `_add_method()` 缺方法即抛异常 | 只注册存在的方法 |
| `src/middlewares.py` | `validate_middleware()` 不传 `crawler` | 传入 `self.crawler` |
| `src/middlewares.py` | 收集的方法从未被调用 | 重写（见第3节） |
| `src/downloaders/requests_downloader.py` | 不继承 `Downloader` 基类 | 修改继承，实现抽象方法 |
| `src/settings/default.py` | 缺少新配置项 | 补充所有新 key |

---

## 7. 实现顺序

1. **Bug 修复层** — 修复独立 bug，不影响架构
2. **去重层** — 新建 `DupeFilter`，集成到 `Engine._schedule_request()`
3. **中间件层** — 重写 `MiddlewareManager`，重写 `Engine._fetch()`
4. **Pipeline 层** — 新建 `src/pipeline/`，重写 `Processor`，初始化 `PipelineManager`
5. **测试 & 完善** — 补充单元测试，更新 demo_project

---

## 8. 不在本次范围内

- Spider 中间件（SpiderMiddlewareManager）
- Redis 持久化去重
- 分布式爬虫
- AutoThrottle
- HTTP 缓存中间件
