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
from src.spiders import Spider
from src.http.request import Request

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
from src.crawler import CrawlerProcess
from src.utils.project import get_settings

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
from src.item.items import Item

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
CONCURRENT_REQUESTS = 16      # 并发数
TIMEOUT = 30                  # 超时
MAX_RETRY = 3                 # 重试次数
VERIFY_SSL = False            # SSL验证
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

查看 `test/baidu/spiders/baidu.py` 获取完整示例。

运行示例：

```bash
cd test
python run.py
```

## 🔗 相关文档

- [API 参考文档](API_REFERENCE.md)
- [测试代码](tests/)
- [默认配置](src/settings/default.py)
