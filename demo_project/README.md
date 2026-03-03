# Demo 项目

这是使用 Cola 框架创建的演示项目。

## 项目结构

```
demo_project/
├── __init__.py
├── run.py                    # 运行脚本
├── spiders/
│   ├── __init__.py
│   ├── simple_spider.py      # 简单测试爬虫
│   └── quotes_spider.py      # 引用网站爬虫
└── README.md
```

## 爬虫说明

### 1. SimpleSpider (简单爬虫)

- **目标网站**: httpbin.org
- **功能**: 基础HTTP请求测试
- **演示特性**:
  - 基本的HTTP请求
  - XPath数据提取
  - 响应信息展示

### 2. QuotesSpider (引用爬虫)

- **目标网站**: quotes.toscrape.com
- **功能**: 爬取名人名言
- **演示特性**:
  - Item数据结构
  - 分页处理
  - 优先级队列
  - XPath复杂选择器

## 运行方法

### 交互式运行

```bash
cd demo_project
python run.py
```

然后根据提示选择要运行的爬虫。

### 直接运行特定爬虫

```python
import asyncio
from src.crawler import CrawlerProcess
from src.settings.settings_manager import SettingsManager
from demo_project.spiders.simple_spider import SimpleSpider

async def main():
    settings = SettingsManager({'CONCURRENT_REQUESTS': 2})
    process = CrawlerProcess(settings)
    await process.crawl(SimpleSpider)
    await process.start()

asyncio.run(main())
```

## 配置说明

两个爬虫都使用自定义配置：

```python
custom_settings = {
    'CONCURRENT_REQUESTS': 3,  # 并发请求数
    'TIMEOUT': 30,             # 超时时间
    'PROJECT_NAME': 'demo',    # 项目名称
}
```

## 输出示例

运行爬虫后会看到详细的输出信息，包括：

- ✅ 访问的URL
- 📊 HTTP状态码
- 📏 内容长度
- 🔗 发现的链接
- 📝 提取的数据

## 学习要点

通过这个演示项目，你可以学习：

1. 如何创建Spider类
2. 如何使用Request和Response
3. 如何使用Item存储数据
4. 如何处理分页
5. 如何配置并发和超时
6. 如何使用XPath提取数据

## 扩展建议

你可以尝试：

- 修改XPath选择器提取不同数据
- 添加更多的自定义配置
- 实现数据持久化（保存到文件或数据库）
- 添加中间件处理请求/响应
- 实现更复杂的爬取逻辑

## 环境要求

需要先在项目根目录安装依赖：

```bash
cd ..
uv sync
```
