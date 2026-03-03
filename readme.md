# Cola 爬虫框架

一个高性能的异步 Python 爬虫框架，基于 asyncio 和 aiohttp 构建。

## ✨ 特性

- ⚡ **异步架构** - 基于 asyncio 实现高效并发
- 🎯 **简洁 API** - 类似 Scrapy 的易用接口
- 🔧 **灵活配置** - 支持全局和爬虫级别配置
- 📊 **统计收集** - 内置性能监控
- 🔄 **智能调度** - 基于优先级的请求队列
- 🛡️ **错误处理** - 完善的异常处理机制
- 🖥️ **CLI 工具** - 命令行创建项目和爬虫

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone <repository-url>
cd cola

# 安装依赖 (使用 uv)
uv sync

# 或使用 pip
pip install -e .
```

### 使用 CLI 创建项目

Cola 提供了类似 Scrapy 的 CLI 工具，可以快速创建项目和管理爬虫：

```bash
# 创建新项目
cola startproject myproject
cd myproject

# 创建新爬虫
cola genspider example example.com

# 列出所有爬虫
cola list

# 运行爬虫
cola crawl example

# 指定并发数和日志级别
cola crawl example -c 10 -l DEBUG
```

### CLI 命令参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `cola startproject <name>` | 创建新项目 | `cola startproject myproject` |
| `cola genspider <name> <domain>` | 创建新爬虫 | `cola genspider baidu baidu.com` |
| `cola crawl <name>` | 运行爬虫 | `cola crawl baidu` |
| `cola list` | 列出所有爬虫 | `cola list` |

### 手动创建爬虫

如果不使用 CLI，也可以手动创建爬虫：

```python
from src.spiders import Spider
from src.http.request import Request

class MySpider(Spider):
    start_urls = ['https://example.com']
    
    async def parse(self, response):
        title = response.xpath('//title/text()')
        print(f"标题: {title}")
```

### 运行爬虫（代码方式）

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

## 📚 文档

- **[用户指南](USER_GUIDE.md)** - 详细的使用教程和最佳实践
- **[API 参考](API_REFERENCE.md)** - 完整的 API 文档
- **[测试报告](TEST_REPORT.md)** - 测试结果和问题修复记录

## 🎯 示例项目

查看 `demo_project` 目录获取完整示例：

```bash
cd demo_project
python run.py
```

包含两个示例爬虫：
- **SimpleSpider** - 基础HTTP请求测试
- **QuotesSpider** - 完整功能演示（分页、Item等）

## ⚙️ 配置

在 Spider 类中自定义配置：

```python
class MySpider(Spider):
    custom_settings = {
        'CONCURRENT_REQUESTS': 5,
        'TIMEOUT': 60,
        'PROJECT_NAME': 'my_project',
    }
```

默认配置位于 `src/settings/default.py`。

## 🏗️ 项目结构

使用 CLI 创建的项目结构：

```
myproject/
├── cola.py           # 项目 CLI 工具
├── settings.py       # 项目配置
├── README.md         # 项目说明
├── spiders/          # 爬虫目录
│   ├── __init__.py
│   └── example.py    # 生成的爬虫
├── items/            # Item 定义
├── middlewares/      # 中间件
└── pipelines/        # 数据管道
```

框架源代码结构：

```
cola/
├── src/                    # 源代码
│   ├── commands/          # CLI 工具
│   ├── core/              # 核心引擎和调度器
│   ├── http/              # Request和Response
│   ├── spiders/           # Spider基类
│   ├── downloaders/       # 下载器
│   ├── item/              # Item数据结构
│   ├── settings/          # 配置管理
│   └── utils/             # 工具函数
├── tests/                 # 测试用例
├── demo_project/          # 示例项目
├── USER_GUIDE.md          # 用户指南
├── API_REFERENCE.md       # API文档
└── TEST_REPORT.md         # 测试报告
```

## 🧪 测试

运行单元测试：

```bash
pytest tests/
```

运行示例爬虫：

```bash
cd demo_project
python run.py
```

## 📈 测试结果

✅ 核心功能已验证：
- HTTP 请求和响应处理
- XPath 数据提取
- Item 数据结构
- 异步并发控制
- 分页处理
- 优先级队列
- 统计收集

详见 [测试报告](TEST_REPORT.md)。

## 💡 使用示例

### 基础爬虫

```python
class SimpleSpider(Spider):
    start_urls = ['http://httpbin.org/html']
    
    async def parse(self, response):
        title = response.xpath('//h1/text()')
        yield {'title': title}
```

### 使用 Item

```python
from src.item.items import Item

class ProductItem(Item):
    FIELDS = {'name': str, 'price': float}

class ShopSpider(Spider):
    async def parse(self, response):
        item = ProductItem()
        item['name'] = response.xpath('//h1/text()')
        item['price'] = response.xpath('//span[@class="price"]/text()')
        yield item
```

### 分页处理

```python
async def parse(self, response):
    # 提取数据
    for item in response.xpath('//div[@class="item"]'):
        yield data
    
    # 跟随下一页
    next_page = response.xpath('//a[@class="next"]/@href')
    if next_page:
        yield Request(url=response._urljoin(next_page[0]))
```

## 🔧 高级功能

### 优先级队列

```python
yield Request(url=url, priority=100)  # 高优先级
```

### 元数据传递

```python
request = Request(url=url)
request.meta['page'] = 1
request.meta['category'] = 'books'
```

### 自定义回调

```python
yield Request(url=url, callback=self.parse_detail)
```

### POST 请求

```python
yield Request(
    url=url,
    method='POST',
    body='data',
    headers={'Content-Type': 'application/json'}
)
```

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

## 📄 许可证

本项目采用开源许可证。

## 🙏 致谢

灵感来源于 Scrapy 框架。

---

**开始使用 Cola 构建您的爬虫吧！** 🎉

有问题？查看 [用户指南](USER_GUIDE.md) 或 [API 文档](API_REFERENCE.md)。
