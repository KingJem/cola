# Cola Scrapy-like 改造 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 Cola 爬虫框架基础上，实现完整的下载中间件管道、请求去重过滤器和 Item Pipeline 系统，使框架达到 Scrapy 同等能力。

**Architecture:** 渐进式分层修复（方案 A）。保留现有 Spider/Request/Response/Item/Settings/CLI 不动，按依赖顺序逐层修复和扩展：Bug 修复 → 去重层 → 中间件层 → Pipeline 层 → 测试完善。每层独立可测，每步提交。

**Tech Stack:** Python 3.10+, asyncio, aiohttp, lxml, loguru, pytest-asyncio

---

## 文件变更映射

### 新建文件

| 文件 | 职责 |
|---|---|
| `src/dupefilter.py` | 请求指纹去重过滤器（内存 set） |
| `src/pipeline/__init__.py` | PipelineManager + DropItem 异常 |
| `src/pipeline/base.py` | BasePipeline 抽象基类 |
| `src/pipeline/console.py` | ConsolePipeline（调试输出） |
| `src/pipeline/json_pipeline.py` | JsonPipeline（写 .jl 文件） |
| `src/pipeline/csv_pipeline.py` | CsvPipeline（写 .csv 文件） |
| `tests/unit/test_dupefilter.py` | DupeFilter 单元测试 |
| `tests/unit/test_middleware_manager.py` | MiddlewareManager 单元测试 |
| `tests/unit/test_pipeline.py` | Pipeline 单元测试 |

### 修改文件

| 文件 | 变更内容 |
|---|---|
| `src/http/request.py` | 新增 `dont_filter: bool = False` 字段 |
| `src/spiders/__init__.py` | `start_requests()` 设置 `dont_filter=True` |
| `src/middlewares.py` | 完全重写：修复所有 bug，实现真正的链式调用 |
| `src/core/engine.py` | 新增 `dupe_filter`/`middleware_manager` 属性；重写 `_fetch()`、`_schedule_request()` |
| `src/core/process.py` | `_process_item()` 调用 `PipelineManager` |
| `src/crawler.py` | 初始化并管理 `PipelineManager` |
| `src/settings/default.py` | 补充所有新配置项默认值 |
| `src/utils/project.py` | 修复 `get_settings()` 自引用 bug |
| `src/downloaders/requests_downloader.py` | 继承 `Downloader` 基类，实现抽象方法 |
| `src/downloaders/__init__.py` | `Downloader.fetch()` 不再直接调用下载，由 Engine 通过中间件调用 |

---

## Task 1: Bug 修复层

**Files:**
- Modify: `src/utils/project.py`
- Modify: `src/downloaders/requests_downloader.py`
- Modify: `src/settings/default.py`

- [ ] **Step 1.1: 修复 `get_settings()`**

将 `src/utils/project.py` 改为：

```python
import importlib.util
import sys
import os
from cola.settings.settings_manager import SettingsManager


def get_settings(settings_module: str = 'settings') -> SettingsManager:
    """
    动态加载用户项目的 settings.py 并返回 SettingsManager。
    从当前工作目录查找 settings 模块。
    """
    from cola.settings.default import get_default_settings
    manager = SettingsManager(get_default_settings())

    # 尝试加载用户 settings 模块
    cwd = os.getcwd()
    settings_path = os.path.join(cwd, f'{settings_module}.py')
    if os.path.exists(settings_path):
        spec = importlib.util.spec_from_file_location(settings_module, settings_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for key in dir(module):
            if key.isupper():
                manager[key] = getattr(module, key)

    return manager


def load_class(obj):
    if isinstance(obj, str):
        module_name, class_name = obj.rsplit(".", 1)
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)

    if callable(obj):
        return obj
```

在 `src/settings/default.py` 新增辅助函数：

```python
def get_default_settings() -> dict:
    import sys
    module = sys.modules[__name__]
    return {k: getattr(module, k) for k in dir(module) if k.isupper()}
```

- [ ] **Step 1.2: 修复 `requests_downloader.py` 继承**

目标：让 `RequestsDownloader` 正确继承 `Downloader` 抽象基类，实现所有抽象方法。
使用 `asyncio.get_event_loop().run_in_executor()` 在线程池中运行同步请求，不破坏异步主循环。

注意：`active_downloader` 追踪在途请求，用于 `idle()` 检查。

```python
# src/downloaders/requests_downloader.py
import asyncio
import requests

from cola.downloaders import Downloader, SyncDownloaderManager
from cola.http.request import Request
from cola.http.response import Response


class RequestsDownloader(Downloader):
    """同步 requests 库的下载器实现（兼容 Downloader 抽象基类）"""

    def __init__(self, crawler):
        super().__init__(crawler)
        self.active_downloader = SyncDownloaderManager()

    async def fetch(self, request: Request):
        """在线程池中运行同步 download，并追踪活跃请求数"""
        self.active_downloader.add(request)
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self._download_sync, request)
            return response
        finally:
            self.active_downloader.remove(request)

    async def download(self, request: Request):
        """满足抽象基类要求，实际由 fetch() 调用"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._download_sync, request)

    def _download_sync(self, request: Request) -> Response:
        """在线程中执行的同步下载逻辑"""
        resp = requests.get(request.url, headers=request.headers, timeout=30)
        return Response(
            url=str(resp.url),
            status=resp.status_code,
            headers=dict(resp.headers),
            request=request,
            body=resp.content,
        )

    async def close(self):
        pass

    def idle(self):
        return self.active_downloader.idle()
```

- [ ] **Step 1.3: 补充 `src/settings/default.py` 新配置项**

```python
# 新增到 default.py
DOWNLOADER_MIDDLEWARES = {}   # {class_path: priority}
ITEM_PIPELINES = {}           # {class_path: priority}
DUPEFILTER_CLASS = 'cola.dupefilter.RFPDupeFilter'
DUPEFILTER_DEBUG = False
JSON_FEED_URI = 'output.jl'
CSV_FEED_URI = 'output.csv'
```

- [ ] **Step 1.4: 运行现有测试确认不破坏**

```bash
cd /Users/king/code/cola && python -m pytest tests/ -x -q 2>&1 | head -50
```

预期：全部通过（或与修改前相同的失败数量）

- [ ] **Step 1.5: Commit**

```bash
git add src/utils/project.py src/downloaders/requests_downloader.py src/settings/default.py
git commit -m "fix: repair get_settings bug, requests_downloader inheritance, add new default config keys"
```

---

## Task 2: 请求去重（DupeFilter）

**Files:**
- Create: `src/dupefilter.py`
- Create: `tests/unit/test_dupefilter.py`
- Modify: `src/http/request.py`
- Modify: `src/spiders/__init__.py`
- Modify: `src/core/engine.py`

- [ ] **Step 2.1: 写失败测试**

新建 `tests/unit/test_dupefilter.py`：

```python
import pytest
from cola.dupefilter import RFPDupeFilter
from cola.http.request import Request


def make_request(url, method='GET'):
    return Request(url=url, method=method)


def test_new_request_not_seen():
    f = RFPDupeFilter()
    req = make_request('http://example.com/page1')
    assert not f.is_seen(req)


def test_seen_after_mark():
    f = RFPDupeFilter()
    req = make_request('http://example.com/page1')
    f.mark_seen(req)
    assert f.is_seen(req)


def test_different_urls_not_duplicate():
    f = RFPDupeFilter()
    req1 = make_request('http://example.com/page1')
    req2 = make_request('http://example.com/page2')
    f.mark_seen(req1)
    assert not f.is_seen(req2)


def test_same_url_different_method_not_duplicate():
    f = RFPDupeFilter()
    req1 = make_request('http://example.com/api', method='GET')
    req2 = make_request('http://example.com/api', method='POST')
    f.mark_seen(req1)
    assert not f.is_seen(req2)


def test_query_param_order_same_fingerprint():
    """查询参数顺序不同，但应视为同一请求"""
    f = RFPDupeFilter()
    req1 = make_request('http://example.com/search?b=2&a=1')
    req2 = make_request('http://example.com/search?a=1&b=2')
    f.mark_seen(req1)
    assert f.is_seen(req2)


def test_close_clears_fingerprints():
    f = RFPDupeFilter()
    req = make_request('http://example.com/page1')
    f.mark_seen(req)
    f.close()
    assert not f.is_seen(req)


def test_dont_filter_bypasses_dupefilter():
    """dont_filter=True 的请求字段存在"""
    req = Request(url='http://example.com/', dont_filter=True)
    assert req.dont_filter is True
```

- [ ] **Step 2.2: 运行测试，确认失败**

```bash
cd /Users/king/code/cola && python -m pytest tests/unit/test_dupefilter.py -v 2>&1 | head -30
```

预期：`ModuleNotFoundError: No module named 'cola.dupefilter'`

- [ ] **Step 2.3: 实现 `src/dupefilter.py`**

```python
import hashlib
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse
from typing import Set


class RFPDupeFilter:
    """
    基于请求指纹（Request Fingerprint）的内存去重过滤器。

    指纹算法：SHA1(METHOD + canonical_url)
    - canonical_url：对 query string 参数排序后重建，去除 fragment
    进程重启后去重状态丢失（内存存储）。
    """

    def __init__(self, debug: bool = False):
        self.fingerprints: Set[str] = set()
        self.debug = debug

    @classmethod
    def from_crawler(cls, crawler):
        debug = crawler.settings.getbool('DUPEFILTER_DEBUG', False)
        return cls(debug=debug)

    def request_fingerprint(self, request) -> str:
        parsed = urlparse(request.url)
        # 对 query 参数排序，使参数顺序不影响指纹
        sorted_query = urlencode(sorted(parse_qsl(parsed.query)))
        canonical = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            sorted_query,
            '',  # 去掉 fragment
        ))
        raw = f"{request.method.upper()}{canonical}"
        return hashlib.sha1(raw.encode('utf-8')).hexdigest()

    def is_seen(self, request) -> bool:
        return self.request_fingerprint(request) in self.fingerprints

    def mark_seen(self, request):
        self.fingerprints.add(self.request_fingerprint(request))

    def close(self):
        self.fingerprints.clear()

    def __len__(self):
        return len(self.fingerprints)
```

- [ ] **Step 2.4: 为 `Request` 新增 `dont_filter` 字段**

修改 `src/http/request.py`：

```python
class Request:
    def __init__(self,
                 url: str,
                 *,
                 headers: dict = None,
                 priority: int = 0,
                 method: str = "GET",
                 cookies: dict = None,
                 proxy: dict = None,
                 body: str = None,
                 callback: Callable = None,
                 dont_filter: bool = False,
                 ):
        self.url = url
        self.headers = headers
        self.priority = priority
        self.method = method.upper()
        self.cookies = cookies
        self.proxy = proxy
        self.body = body
        self.callback = callback
        self.dont_filter = dont_filter
        self.meta = {}
```

- [ ] **Step 2.5: Spider.start_requests() 设置 dont_filter=True**

修改 `src/spiders/__init__.py`：

```python
def start_requests(self):
    if self.start_urls:
        for url in self.start_urls:
            yield Request(url=url, dont_filter=True)
    else:
        if hasattr(self, 'start_url') and isinstance(getattr(self, 'start_url'), str):
            yield Request(url=getattr(self, 'start_url'), dont_filter=True)
```

- [ ] **Step 2.6: Engine 集成 DupeFilter**

在 `src/core/engine.py` 中：

1. `__init__` 新增 `self.dupe_filter = None`
2. `start_spider()` 初始化：
   ```python
   from cola.utils import load_class
   dupefilter_cls_path = self.settings.get('DUPEFILTER_CLASS', 'cola.dupefilter.RFPDupeFilter')
   dupefilter_cls = load_class(dupefilter_cls_path)
   self.dupe_filter = dupefilter_cls.from_crawler(self.crawler)
   ```
3. `_schedule_request()` 改为：
   ```python
   async def _schedule_request(self, request):
       if not request.dont_filter and self.dupe_filter.is_seen(request):
           if self.dupe_filter.debug:
               self.logger.debug(f"Filtered duplicate request: {request.url}")
           return
       self.dupe_filter.mark_seen(request)
       await self.scheduler.enqueue_request(request)
   ```
4. `close()` 中调用 `self.dupe_filter.close()`

- [ ] **Step 2.7: 运行测试确认通过**

```bash
cd /Users/king/code/cola && python -m pytest tests/unit/test_dupefilter.py -v
```

预期：7 个测试全部 PASS

- [ ] **Step 2.8: 运行全部测试确认不破坏**

```bash
cd /Users/king/code/cola && python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 2.9: Commit**

```bash
git add src/dupefilter.py src/http/request.py src/spiders/__init__.py src/core/engine.py tests/unit/test_dupefilter.py
git commit -m "feat: add RFPDupeFilter request deduplication with SHA1 fingerprinting"
```

---

## Task 3: 下载中间件管道（MiddlewareManager 重写）

**Files:**
- Create: `tests/unit/test_middleware_manager.py`
- Modify: `src/middlewares.py`（完全重写）
- Modify: `src/core/engine.py`（重写 `_fetch()`）
- Modify: `src/downloaders/__init__.py`（`Downloader.fetch()` 简化）
- Modify: `src/downloaders/aio_http_downloader.py`（`fetch()` 只负责下载，去掉重试外壳）

- [ ] **Step 3.1: 写失败测试**

新建 `tests/unit/test_middleware_manager.py`：

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cola.middlewares import MiddlewareManager
from cola.http.request import Request
from cola.http.response import Response


def make_crawler(middlewares=None):
    crawler = MagicMock()
    crawler.settings.get.return_value = middlewares or {}
    return crawler


def make_request(url='http://example.com/'):
    return Request(url=url)


def make_response(url='http://example.com/', status=200):
    return Response(url=url, status=status, headers={}, request=make_request(url), body=b'')


class SyncMiddleware:
    @classmethod
    def create_instance(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        request.headers = {'X-Test': 'sync'}
        return None  # 继续链

    def process_response(self, request, response, spider):
        return response


class AsyncMiddleware:
    @classmethod
    def create_instance(cls, crawler):
        return cls()

    async def process_request(self, request, spider):
        request.headers = {'X-Async': 'yes'}
        return None

    async def process_response(self, request, response, spider):
        return response


class ShortCircuitMiddleware:
    """在 process_request 中直接返回 Response（短路）"""
    @classmethod
    def create_instance(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        return make_response()  # 短路


@pytest.mark.asyncio
async def test_empty_middleware_returns_request():
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = []
    manager._methods = {'process_request': [], 'process_response': [], 'process_exception': []}
    req = make_request()
    result = await manager.process_request(req, spider=None)
    assert result is req


@pytest.mark.asyncio
async def test_sync_middleware_process_request():
    """同步中间件方法应被正确调用"""
    mw = SyncMiddleware()
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = [mw]
    manager._methods = {
        'process_request': [mw.process_request],
        'process_response': [mw.process_response],
        'process_exception': [],
    }
    req = make_request()
    result = await manager.process_request(req, spider=None)
    assert result is req
    assert req.headers == {'X-Test': 'sync'}


@pytest.mark.asyncio
async def test_async_middleware_process_request():
    """异步中间件方法应被正确调用"""
    mw = AsyncMiddleware()
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = [mw]
    manager._methods = {
        'process_request': [mw.process_request],
        'process_response': [mw.process_response],
        'process_exception': [],
    }
    req = make_request()
    result = await manager.process_request(req, spider=None)
    assert result is req
    assert req.headers == {'X-Async': 'yes'}


@pytest.mark.asyncio
async def test_short_circuit_returns_response():
    """中间件返回 Response 时应短路"""
    mw = ShortCircuitMiddleware()
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = [mw]
    manager._methods = {
        'process_request': [mw.process_request],
        'process_response': [],
        'process_exception': [],
    }
    req = make_request()
    result = await manager.process_request(req, spider=None)
    assert isinstance(result, Response)


@pytest.mark.asyncio
async def test_process_response_called_in_reverse():
    """process_response 应按逆序调用"""
    order = []

    class MW1:
        @classmethod
        def create_instance(cls, crawler): return cls()
        def process_response(self, request, response, spider):
            order.append(1)
            return response

    class MW2:
        @classmethod
        def create_instance(cls, crawler): return cls()
        def process_response(self, request, response, spider):
            order.append(2)
            return response

    mw1, mw2 = MW1(), MW2()
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = [mw1, mw2]
    manager._methods = {
        'process_request': [],
        'process_response': [mw1.process_response, mw2.process_response],
        'process_exception': [],
    }
    req = make_request()
    resp = make_response()
    await manager.process_response(req, resp, spider=None)
    assert order == [2, 1]  # 逆序


@pytest.mark.asyncio
async def test_process_exception_returns_none_when_no_handler():
    manager = MiddlewareManager.__new__(MiddlewareManager)
    manager.crawler = make_crawler()
    manager.middlewares = []
    manager._methods = {'process_request': [], 'process_response': [], 'process_exception': []}
    result = await manager.process_exception(make_request(), Exception('err'), spider=None)
    assert result is None
```

- [ ] **Step 3.2: 运行测试确认失败**

```bash
cd /Users/king/code/cola && python -m pytest tests/unit/test_middleware_manager.py -v 2>&1 | head -40
```

- [ ] **Step 3.3: 完全重写 `src/middlewares.py`**

```python
"""
下载中间件管理器。

中间件配置（DOWNLOADER_MIDDLEWARES）格式：
    {
        'path.to.MyMiddleware': 100,
        'path.to.OtherMiddleware': 200,
    }
数字为优先级（升序），process_request 按升序执行，process_response 按降序执行。

中间件接口（方法均为可选）：
    process_request(request, spider)           -> None | Request | Response
    process_response(request, response, spider) -> Response | Request
    process_exception(request, exception, spider) -> None | Response | Request
"""
import asyncio
import inspect
from pprint import pformat
from typing import Optional

from loguru import logger

from cola.utils import load_class


async def _call_maybe_async(method, *args):
    """统一调用同步或异步方法"""
    if inspect.iscoroutinefunction(method):
        return await method(*args)
    else:
        return method(*args)


class MiddlewareManager:

    def __init__(self, crawler):
        self.crawler = crawler
        self.middlewares = []
        self._methods = {
            'process_request': [],
            'process_response': [],
            'process_exception': [],
        }
        self._load()

    @classmethod
    def create_instance(cls, crawler):
        return cls(crawler)

    def _load(self):
        setting = self.crawler.settings.get('DOWNLOADER_MIDDLEWARES', {})
        if not setting:
            return

        sorted_mws = sorted(setting.items(), key=lambda x: x[1])
        enabled = []
        for class_path, priority in sorted_mws:
            try:
                cls = load_class(class_path)
                if hasattr(cls, 'create_instance'):
                    instance = cls.create_instance(self.crawler)
                else:
                    instance = cls()
                self.middlewares.append(instance)
                enabled.append(f"  {priority:4d} {class_path}")

                # 只注册存在的方法（不强制全部有）
                for method_name in ('process_request', 'process_response', 'process_exception'):
                    if hasattr(instance, method_name):
                        self._methods[method_name].append(getattr(instance, method_name))

            except Exception as e:
                logger.error(f"Failed to load middleware {class_path}: {e}")

        if enabled:
            logger.info("Enabled downloader middlewares:\n" + "\n".join(enabled))

    async def process_request(self, request, spider):
        """
        按优先级顺序执行 process_request。
        - 返回 None：继续下一个中间件
        - 返回 Request：用新请求继续链（修改后的请求）
        - 返回 Response：短路，直接进入 process_response（跳过下载）
        """
        for method in self._methods['process_request']:
            result = await _call_maybe_async(method, request, spider)
            if result is not None:
                return result  # 短路：Response 或新 Request
        return request

    async def process_response(self, request, response, spider):
        """
        按优先级逆序执行 process_response。
        - 返回 Response：继续下一个中间件
        - 返回 Request：重新入队下载
        """
        for method in reversed(self._methods['process_response']):
            response = await _call_maybe_async(method, request, response, spider)
        return response

    async def process_exception(self, request, exception, spider):
        """
        下载发生异常时按顺序执行。
        - 返回 None：继续下一个中间件（异常继续传播）
        - 返回 Response 或 Request：停止异常传播
        """
        for method in self._methods['process_exception']:
            result = await _call_maybe_async(method, request, exception, spider)
            if result is not None:
                return result
        return None
```

- [ ] **Step 3.4: 重写 `Engine._fetch()` 使用中间件管道**

修改 `src/core/engine.py`：

1. `__init__` 新增 `self.middleware_manager = None`

2. `start_spider()` 中初始化（在 `open_spider()` 调用之前）：
   ```python
   from cola.middlewares import MiddlewareManager
   self.middleware_manager = MiddlewareManager(self.crawler)
   ```

3. 重写 `_fetch()`：
   ```python
   async def _fetch(self, request):
       # 1. 中间件 process_request 链
       result = await self.middleware_manager.process_request(request, self.spider)

       from cola.http.response import Response as HttpResponse
       if isinstance(result, HttpResponse):
           response = result  # 中间件短路返回了 Response
       else:
           if isinstance(result, Request):
               request = result  # 中间件返回了修改后的 Request
           # 2. 实际下载
           try:
               response = await self.downloader.fetch(request)
               if response is None:
                   logger.warning(f"Download failed for {request.url}, skipping")
                   return None
           except Exception as e:
               # 3a. 中间件 process_exception 链
               exc_result = await self.middleware_manager.process_exception(request, e, self.spider)
               if exc_result is None:
                   logger.error(f"Unhandled download exception for {request.url}: {e}")
                   return None
               response = exc_result

       # 3b. 中间件 process_response 链
       response = await self.middleware_manager.process_response(request, response, self.spider)

       # 4. 调用 spider callback
       callback = request.callback or self.spider.parse
       outputs = callback(response)
       if outputs is None:
           return None
       if inspect.iscoroutine(outputs):
           await outputs
           return None
       return self._transform(outputs)
   ```

4. 同步更新 `_handle_spider_outputs()`：

   **重要**：当前 `_handle_spider_outputs` 对 `dict` 类型只打 debug 日志而不入队 Processor，这意味着 dict item 不会进入 Pipeline。需要修复：

   ```python
   async def _handle_spider_outputs(self, outputs):
       from collections.abc import MutableMapping
       async for output in outputs:
           if isinstance(output, Request):
               await self.processor.enqueue(output)
           elif isinstance(output, MutableMapping) and hasattr(output, 'FIELDS'):
               # Item 实例（通过 MutableMapping 基类和 FIELDS 属性判断）
               await self.processor.enqueue(output)
           elif isinstance(output, dict):
               # dict 也送入 Processor -> Pipeline 处理（之前只是 debug 日志，现在修复）
               await self.processor.enqueue(output)
           else:
               logger.warning(f"Spider yielded unsupported type {type(output)}: {output}")
   ```

   同时更新 `Processor.enqueue()` 的类型注解为 `Union[Request, Item, dict]`。

- [ ] **Step 3.5: 运行中间件测试**

```bash
cd /Users/king/code/cola && python -m pytest tests/unit/test_middleware_manager.py -v
```

预期：6 个测试全部 PASS

- [ ] **Step 3.6: 运行全部测试**

```bash
cd /Users/king/code/cola && python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 3.7: Commit**

```bash
git add src/middlewares.py src/core/engine.py tests/unit/test_middleware_manager.py
git commit -m "feat: rewrite MiddlewareManager with real chain invocation, sync/async compat, priority ordering"
```

---

## Task 4: Item Pipeline 系统

**Files:**
- Create: `src/pipeline/__init__.py`
- Create: `src/pipeline/base.py`
- Create: `src/pipeline/console.py`
- Create: `src/pipeline/json_pipeline.py`
- Create: `src/pipeline/csv_pipeline.py`
- Create: `tests/unit/test_pipeline.py`
- Modify: `src/core/process.py`
- Modify: `src/crawler.py`

- [ ] **Step 4.1: 写失败测试**

新建 `tests/unit/test_pipeline.py`：

```python
import asyncio
import json
import os
import pytest
from unittest.mock import MagicMock, AsyncMock
from cola.pipeline import PipelineManager, DropItem
from cola.pipeline.base import BasePipeline
from cola.pipeline.console import ConsolePipeline
from cola.item.items import Item


def make_item(**kwargs):
    """创建简单字典 item（测试用）"""
    return kwargs


def make_crawler(pipelines=None):
    crawler = MagicMock()
    crawler.settings.get.return_value = pipelines or {}
    crawler.spider = MagicMock()
    crawler.spider.name = 'test_spider'
    return crawler


class CountPipeline(BasePipeline):
    def __init__(self):
        self.count = 0

    @classmethod
    def create_instance(cls, crawler):
        return cls()

    async def process_item(self, item, spider):
        self.count += 1
        return item


class DropEvenPipeline(BasePipeline):
    @classmethod
    def create_instance(cls, crawler):
        return cls()

    async def process_item(self, item, spider):
        if item.get('value', 0) % 2 == 0:
            raise DropItem(f"Even value: {item['value']}")
        return item


@pytest.mark.asyncio
async def test_empty_pipeline_returns_item():
    manager = PipelineManager.__new__(PipelineManager)
    manager.crawler = make_crawler()
    manager.pipelines = []
    item = make_item(name='test')
    result = await manager.process_item(item, spider=None)
    assert result == item


@pytest.mark.asyncio
async def test_pipeline_processes_item():
    pipeline = CountPipeline()
    manager = PipelineManager.__new__(PipelineManager)
    manager.crawler = make_crawler()
    manager.pipelines = [pipeline]
    item = make_item(name='test')
    result = await manager.process_item(item, spider=None)
    assert result == item
    assert pipeline.count == 1


@pytest.mark.asyncio
async def test_drop_item_returns_none():
    pipeline = DropEvenPipeline()
    manager = PipelineManager.__new__(PipelineManager)
    manager.crawler = make_crawler()
    manager.pipelines = [pipeline]
    item = make_item(value=2)
    result = await manager.process_item(item, spider=None)
    assert result is None


@pytest.mark.asyncio
async def test_drop_item_stops_pipeline_chain():
    """DropItem 后后续 Pipeline 不应被调用"""
    drop_pipeline = DropEvenPipeline()
    count_pipeline = CountPipeline()
    manager = PipelineManager.__new__(PipelineManager)
    manager.crawler = make_crawler()
    manager.pipelines = [drop_pipeline, count_pipeline]
    item = make_item(value=2)
    result = await manager.process_item(item, spider=None)
    assert result is None
    assert count_pipeline.count == 0  # 不应被调用


@pytest.mark.asyncio
async def test_console_pipeline(capsys):
    pipeline = ConsolePipeline()
    await pipeline.process_item({'name': 'test', 'value': 42}, spider=MagicMock(name='myspider'))
    captured = capsys.readouterr()
    assert 'test' in captured.out or 'value' in captured.out


@pytest.mark.asyncio
async def test_open_close_spider_called(tmp_path):
    """open_spider / close_spider 应被调用"""
    opened = []
    closed = []

    class TrackPipeline(BasePipeline):
        @classmethod
        def create_instance(cls, crawler): return cls()
        async def open_spider(self, spider): opened.append(True)
        async def close_spider(self, spider): closed.append(True)
        async def process_item(self, item, spider): return item

    pipeline = TrackPipeline()
    manager = PipelineManager.__new__(PipelineManager)
    manager.crawler = make_crawler()
    manager.pipelines = [pipeline]
    spider = MagicMock()
    await manager.open_spider(spider)
    await manager.close_spider(spider)
    assert opened == [True]
    assert closed == [True]
```

- [ ] **Step 4.2: 运行测试确认失败**

```bash
cd /Users/king/code/cola && python -m pytest tests/unit/test_pipeline.py -v 2>&1 | head -30
```

- [ ] **Step 4.3: 创建 `src/pipeline/base.py`**

```python
"""Pipeline 基类与 DropItem 异常"""


class DropItem(Exception):
    """
    在 Pipeline 中抛出此异常以丢弃当前 Item。
    被丢弃的 Item 不会传递给后续 Pipeline。

    用法：
        async def process_item(self, item, spider):
            if not item.get('name'):
                raise DropItem(f"Missing name in item: {item}")
            return item
    """
    pass


class BasePipeline:
    """
    所有 Pipeline 的基类。

    子类应实现 process_item()，可选实现 open_spider() 和 close_spider()。
    """

    @classmethod
    def create_instance(cls, crawler):
        return cls()

    async def open_spider(self, spider):
        """Spider 开始爬取时调用。可用于建立数据库连接、打开文件等。"""
        pass

    async def close_spider(self, spider):
        """Spider 结束爬取时调用。可用于关闭连接、刷新文件等。"""
        pass

    async def process_item(self, item, spider):
        """
        处理每个 Item。必须返回 item 或抛出 DropItem。

        Args:
            item: Spider 爬取到的数据（dict 或 Item 实例）
            spider: 当前 Spider 实例

        Returns:
            处理后的 item（可被修改）

        Raises:
            DropItem: 丢弃此 item
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process_item()")
```

- [ ] **Step 4.4: 创建 `src/pipeline/console.py`**

```python
"""ConsolePipeline：将 Item 打印到终端，用于调试"""
from loguru import logger
from cola.pipeline.base import BasePipeline


class ConsolePipeline(BasePipeline):
    """
    将爬取到的 Item 打印到控制台。
    适合开发调试阶段使用。

    配置：
        ITEM_PIPELINES = {
            'cola.pipeline.console.ConsolePipeline': 100,
        }
    """

    async def process_item(self, item, spider):
        print(f"[{getattr(spider, 'name', 'spider')}] Item scraped: {dict(item) if hasattr(item, '__iter__') else item}")
        return item
```

- [ ] **Step 4.5: 创建 `src/pipeline/json_pipeline.py`**

```python
"""JsonPipeline：将 Item 写入 JSON Lines 文件"""
import json
from pathlib import Path
from loguru import logger
from cola.pipeline.base import BasePipeline


class JsonPipeline(BasePipeline):
    """
    将爬取到的 Item 写入 JSON Lines 格式文件（每行一个 JSON 对象）。

    配置：
        ITEM_PIPELINES = {
            'cola.pipeline.json_pipeline.JsonPipeline': 800,
        }
        JSON_FEED_URI = 'output.jl'  # 输出文件路径（默认 output.jl）
    """

    def __init__(self):
        self.file = None
        self.uri = None

    @classmethod
    def create_instance(cls, crawler):
        instance = cls()
        instance.uri = crawler.settings.get('JSON_FEED_URI', 'output.jl')
        return instance

    async def open_spider(self, spider):
        self.file = open(self.uri, 'a', encoding='utf-8')
        logger.info(f"JsonPipeline: writing to {Path(self.uri).resolve()}")

    async def close_spider(self, spider):
        if self.file:
            self.file.flush()
            self.file.close()
            self.file = None
            logger.info(f"JsonPipeline: closed {self.uri}")

    async def process_item(self, item, spider):
        if self.file is None:
            logger.warning("JsonPipeline: file not open, skipping item")
            return item
        data = dict(item) if hasattr(item, 'items') else item
        line = json.dumps(data, ensure_ascii=False)
        self.file.write(line + '\n')
        return item
```

- [ ] **Step 4.6: 创建 `src/pipeline/csv_pipeline.py`**

```python
"""CsvPipeline：将 Item 写入 CSV 文件"""
import csv
from pathlib import Path
from loguru import logger
from cola.pipeline.base import BasePipeline


class CsvPipeline(BasePipeline):
    """
    将爬取到的 Item 写入 CSV 文件。
    列名从第一个 Item 的 key 自动推断。

    配置：
        ITEM_PIPELINES = {
            'cola.pipeline.csv_pipeline.CsvPipeline': 900,
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
```

- [ ] **Step 4.7: 创建 `src/pipeline/__init__.py`（PipelineManager）**

```python
"""
Item Pipeline 管理器。

ITEM_PIPELINES 配置格式：
    {
        'path.to.MyPipeline': 300,   # 数字为优先级，升序执行
        'cola.pipeline.json_pipeline.JsonPipeline': 800,
    }
"""
import inspect
from pprint import pformat
from typing import List, Optional

from loguru import logger

from cola.pipeline.base import BasePipeline, DropItem
from cola.utils import load_class


async def _call_maybe_async(method, *args):
    if inspect.iscoroutinefunction(method):
        return await method(*args)
    return method(*args)


class PipelineManager:

    def __init__(self, crawler):
        self.crawler = crawler
        self.pipelines: List[BasePipeline] = []
        self._load()

    @classmethod
    def create_instance(cls, crawler):
        return cls(crawler)

    def _load(self):
        setting = self.crawler.settings.get('ITEM_PIPELINES', {})
        if not setting:
            return

        sorted_pipelines = sorted(setting.items(), key=lambda x: x[1])
        enabled = []
        for class_path, priority in sorted_pipelines:
            try:
                cls = load_class(class_path)
                if hasattr(cls, 'create_instance'):
                    instance = cls.create_instance(self.crawler)
                else:
                    instance = cls()
                self.pipelines.append(instance)
                enabled.append(f"  {priority:4d} {class_path}")
            except Exception as e:
                logger.error(f"Failed to load pipeline {class_path}: {e}")

        if enabled:
            logger.info("Enabled item pipelines:\n" + "\n".join(enabled))

    async def open_spider(self, spider):
        for pipeline in self.pipelines:
            if hasattr(pipeline, 'open_spider'):
                await _call_maybe_async(pipeline.open_spider, spider)

    async def close_spider(self, spider):
        for pipeline in self.pipelines:
            if hasattr(pipeline, 'close_spider'):
                await _call_maybe_async(pipeline.close_spider, spider)

    async def process_item(self, item, spider) -> Optional[object]:
        """
        依次通过所有 Pipeline 处理 item。
        若某 Pipeline 抛出 DropItem，停止链并返回 None。
        """
        for pipeline in self.pipelines:
            try:
                item = await _call_maybe_async(pipeline.process_item, item, spider)
            except DropItem as e:
                logger.info(f"Item dropped by {type(pipeline).__name__}: {e}")
                return None
        return item
```

- [ ] **Step 4.8: 重写 `src/core/process.py`**

```python
from asyncio.queues import Queue
from typing import Any, Union

from cola.core.request import Request
from cola.item.items import Item


class Processor:
    def __init__(self, crawler):
        self.queue = Queue()
        self.crawler = crawler

    async def process(self) -> Any:
        while not self.idle():
            result = await self.queue.get()
            if isinstance(result, Request):
                await self.crawler.engine.enqueue_requests(result)
            else:
                # Item 或 dict
                await self._process_item(result)

    async def _process_item(self, item: Any) -> Any:
        spider = self.crawler.spider
        pipeline_manager = getattr(self.crawler, 'pipeline_manager', None)
        if pipeline_manager is not None:
            await pipeline_manager.process_item(item, spider)
        return item

    async def enqueue(self, output: Union[Request, Item]) -> Any:
        await self.queue.put(output)
        await self.process()

    def idle(self):
        return len(self) == 0

    def __len__(self):
        return self.queue.qsize()
```

- [ ] **Step 4.9: 在 `src/crawler.py` 中初始化 PipelineManager**

修改 `Crawler` 类：

1. `__init__` 中新增：`self.pipeline_manager = None`

2. `crawl()` 中，在 `engine.start_spider()` 之前初始化：
   ```python
   from cola.pipeline import PipelineManager
   self.pipeline_manager = PipelineManager(self)
   await self.pipeline_manager.open_spider(self.spider)
   ```

3. `close()` 中，在 `stat_collector` 之前：
   ```python
   if self.pipeline_manager:
       await self.pipeline_manager.close_spider(self.spider)
   ```

- [ ] **Step 4.10: 运行 Pipeline 测试**

```bash
cd /Users/king/code/cola && python -m pytest tests/unit/test_pipeline.py -v
```

预期：6 个测试全部 PASS

- [ ] **Step 4.11: 运行全部测试**

```bash
cd /Users/king/code/cola && python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 4.12: Commit**

```bash
git add src/pipeline/ src/core/process.py src/crawler.py tests/unit/test_pipeline.py
git commit -m "feat: implement Item Pipeline system with PipelineManager, ConsolePipeline, JsonPipeline, CsvPipeline"
```

---

## Task 5: 集成测试 & Demo 更新

**Files:**
- Create: `tests/integration/test_middleware_pipeline_integration.py`
- Modify: `demo_project/spiders/quotes_spider.py`（展示 Pipeline 用法）

- [ ] **Step 5.1: 写集成测试**

新建 `tests/integration/test_middleware_pipeline_integration.py`：

```python
"""
集成测试：验证中间件 + 去重 + Pipeline 协同工作
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cola.http.request import Request
from cola.http.response import Response
from cola.middlewares import MiddlewareManager
from cola.dupefilter import RFPDupeFilter
from cola.pipeline import PipelineManager


def make_response(url='http://example.com/', status=200):
    req = Request(url=url)
    return Response(url=url, status=status, headers={}, request=req, body=b'<html></html>')


def make_crawler_with_settings(**settings_dict):
    crawler = MagicMock()
    crawler.settings.get.side_effect = lambda key, default=None: settings_dict.get(key, default)
    crawler.settings.getbool.side_effect = lambda key, default=False: settings_dict.get(key, default)
    return crawler


@pytest.mark.asyncio
async def test_dupefilter_blocks_duplicate():
    """去重过滤器应阻止重复 URL"""
    f = RFPDupeFilter()
    req1 = Request(url='http://example.com/page')
    req2 = Request(url='http://example.com/page')  # 同 URL
    f.mark_seen(req1)
    assert f.is_seen(req2)


@pytest.mark.asyncio
async def test_dupefilter_allows_dont_filter():
    """dont_filter=True 时，即使是相同 URL 也不应视为重复（由 Engine 判断）"""
    f = RFPDupeFilter()
    req = Request(url='http://example.com/', dont_filter=True)
    f.mark_seen(req)
    # DupeFilter 本身仍会标记，由 Engine 决定是否跳过检查
    assert req.dont_filter is True


@pytest.mark.asyncio
async def test_middleware_and_pipeline_independent():
    """中间件和 Pipeline 应相互独立，不互相依赖"""
    # 中间件：空
    crawler_mw = make_crawler_with_settings(DOWNLOADER_MIDDLEWARES={})
    mw_manager = MiddlewareManager(crawler_mw)

    req = Request(url='http://example.com/')
    result = await mw_manager.process_request(req, spider=None)
    assert result is req  # 无中间件，原样返回

    # Pipeline：空
    crawler_pl = make_crawler_with_settings(ITEM_PIPELINES={})
    pl_manager = PipelineManager(crawler_pl)
    item = {'name': 'test', 'value': 42}
    result = await pl_manager.process_item(item, spider=None)
    assert result == item  # 无 pipeline，原样返回


@pytest.mark.asyncio
async def test_middleware_modifies_request_headers():
    """中间件能修改请求头"""
    class HeaderMiddleware:
        @classmethod
        def create_instance(cls, crawler): return cls()
        def process_request(self, request, spider):
            request.headers = request.headers or {}
            request.headers['User-Agent'] = 'ColaBot/1.0'
            return None

    crawler = make_crawler_with_settings(
        DOWNLOADER_MIDDLEWARES={'__main__.HeaderMiddleware': 100}
    )
    with patch('cola.middlewares.load_class', return_value=HeaderMiddleware):
        manager = MiddlewareManager(crawler)
    req = Request(url='http://example.com/')
    await manager.process_request(req, spider=None)
    assert req.headers.get('User-Agent') == 'ColaBot/1.0'
```

- [ ] **Step 5.2: 运行集成测试**

```bash
cd /Users/king/code/cola && python -m pytest tests/integration/test_middleware_pipeline_integration.py -v
```

预期：全部 PASS

- [ ] **Step 5.3: 运行完整测试套件**

```bash
cd /Users/king/code/cola && python -m pytest tests/ -v 2>&1 | tail -30
```

- [ ] **Step 5.4: 更新 demo_project 展示新特性**

在 `demo_project/settings.py`（若存在）或 `demo_project/quotes_spider.py` 中，添加注释展示如何配置 Pipeline：

```python
# demo_project 中展示用法的 custom_settings
custom_settings = {
    'ITEM_PIPELINES': {
        'cola.pipeline.console.ConsolePipeline': 100,
        'cola.pipeline.json_pipeline.JsonPipeline': 800,
    },
    'JSON_FEED_URI': 'quotes_output.jl',
    'DUPEFILTER_DEBUG': True,
}
```

- [ ] **Step 5.5: 最终 Commit**

```bash
git add tests/integration/test_middleware_pipeline_integration.py demo_project/
git commit -m "test: add integration tests for middleware, dupefilter and pipeline; update demo with pipeline config"
```

---

## 验证检查清单

在所有 Task 完成后，确认以下各项：

- [ ] `python -m pytest tests/ -q` 全部通过
- [ ] `RFPDupeFilter` 能正确去重，`dont_filter=True` 的请求不被过滤
- [ ] `MiddlewareManager` 的 `process_request` 按升序、`process_response` 按降序执行
- [ ] 同步和异步中间件方法均可正常工作
- [ ] `PipelineManager` 按优先级依次调用 Pipeline，`DropItem` 能终止链
- [ ] `JsonPipeline` 能写出有效的 `.jl` 文件
- [ ] `CsvPipeline` 能写出有效的 `.csv` 文件
- [ ] `requests_downloader.py` 正确继承 `Downloader` 基类
- [ ] `get_settings()` 能正确加载用户 `settings.py`
