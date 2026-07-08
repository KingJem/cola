"""
Cola CLI - 命令行工具
类似于 Scrapy 的命令行接口
"""
import os
import sys
import argparse
import subprocess
from pathlib import Path


SPIDER_TEMPLATE = '''from cola.spiders import Spider
from cola.http.request import Request


class {class_name}Spider(Spider):
    name = '{spider_name}'
    start_urls = ['{start_url}']
    
    custom_settings = {{
        'CONCURRENT_REQUESTS': 8,
        'TIMEOUT': 30,
    }}
    
    async def parse(self, response):
        """解析响应"""
        # 使用 XPath 提取数据
        # title = response.xpath('//title/text()')
        
        # 使用 CSS 选择器提取数据
        # items = response.css('.item')
        
        # 返回数据
        yield {{
            'url': response.url,
            'status': response.status_code,
        }}
        
        # 跟随链接
        # next_page = response.xpath('//a[@class="next"]/@href')
        # if next_page:
        #     yield Request(url=response._urljoin(next_page[0]))
'''


SETTINGS_TEMPLATE = '''"""
项目配置文件
"""

PROJECT_NAME = '{project_name}'

# 并发设置
CONCURRENT_REQUESTS = 16

# 下载设置
TIMEOUT = 30
MAX_RETRY = 3
VERIFY_SSL = False

# 下载器类
DOWNLOADER_CLASS = 'cola.downloaders.aio_http_downloader.AioHttpDownloader'

# 日志级别
LOG_LEVEL = 'INFO'

# 其他自定义设置
# CUSTOM_SETTING = 'value'
'''


INIT_PY = '''"""
{project_name} 项目
"""
'''


PYPROJECT_TEMPLATE = '''[project]
name = "{project_name}"
version = "0.1.0"
description = "Cola 爬虫项目"
requires-python = ">=3.10"
dependencies = [
    "{cola_dep}",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.metadata]
# 允许 cola @ file:// 本地路径依赖(colad 部署时 uv sync 需要)
allow-direct-references = true

[tool.hatch.build.targets.wheel]
packages = ["spiders"]
'''


def _detect_cola_source() -> str:
    """推断 cola 依赖来源:优先本仓库源码路径(便于 colad 本机部署),
    否则退回裸 'cola'(假设已发布/已安装)。"""
    root = Path(__file__).resolve().parents[2]
    if (root / 'cola' / '__init__.py').exists() and \
            (root / 'pyproject.toml').exists():
        return f'cola @ file://{root}'
    return 'cola'


def _cola_dependency(cola_source: str) -> str:
    """把 --cola 参数规整成 pyproject 依赖串。
    - 空:自动探测本地 cola 仓库
    - 已存在的路径:cola @ file://<abs>
    - 其它(含 == @ 等):原样当作依赖规格
    """
    if not cola_source:
        return _detect_cola_source()
    p = Path(cola_source).expanduser()
    if p.exists():
        return f'cola @ file://{p.resolve()}'
    return cola_source


README_TEMPLATE = '''# {project_name}

Cola 爬虫项目

## 目录结构

```
{project_name}/
├── manage.py         # 本地运行器(python manage.py crawl <name>)
├── settings.py       # 项目配置
├── spiders/          # 爬虫目录
├── items/            # Item 定义
├── middlewares/      # 中间件
└── pipelines/        # 数据管道
```

## 快速开始

### 创建爬虫

```bash
python manage.py genspider example example.com
```

### 运行爬虫

```bash
python manage.py crawl example
```

### 列出所有爬虫

```bash
python manage.py list
```

## 配置

编辑 `settings.py` 修改项目配置。
'''


def create_spider_in_project(spider_name: str, domain: str, project_dir: str = None):
    """在项目中创建新的爬虫"""
    if project_dir is None:
        project_dir = os.getcwd()
    
    project_path = Path(project_dir)
    spiders_dir = project_path / 'spiders'
    
    # 检查是否在项目目录中
    if not spiders_dir.exists():
        print("错误: 当前目录不是 Cola 项目目录 (找不到 spiders/ 目录)")
        print("请在 Cola 项目根目录中运行此命令")
        return False
    
    # 转换爬虫名称为类名
    class_name = ''.join(word.capitalize() for word in spider_name.split('_'))
    
    # 生成 start_url
    start_url = f'https://{domain}'
    
    # 创建爬虫文件
    spider_file = spiders_dir / f'{spider_name}.py'
    if spider_file.exists():
        print(f"错误: 爬虫 '{spider_name}' 已存在")
        return False
    
    spider_content = SPIDER_TEMPLATE.format(
        class_name=class_name,
        spider_name=spider_name,
        start_url=start_url
    )
    
    spider_file.write_text(spider_content)
    print(f"创建爬虫 '{spider_name}' 成功!")
    print(f"  文件: spiders/{spider_name}.py")
    print(f"  域名: {domain}")
    print(f"\n运行爬虫:")
    print(f"  python manage.py crawl {spider_name}")
    
    return True


def create_project(project_name: str, project_dir: str = None,
                   cola_source: str = ''):
    """创建新的 Cola 项目(含 colad 可部署的 pyproject.toml)"""
    if project_dir is None:
        project_dir = os.getcwd()

    project_path = Path(project_dir) / project_name
    
    # 检查项目是否已存在
    if project_path.exists():
        print(f"错误: 目录 '{project_name}' 已存在")
        return False
    
    # 创建项目结构
    print(f"创建项目 '{project_name}'...")
    
    # 创建目录
    (project_path / 'spiders').mkdir(parents=True)
    (project_path / 'items').mkdir(parents=True)
    (project_path / 'middlewares').mkdir(parents=True)
    (project_path / 'pipelines').mkdir(parents=True)
    
    # 创建文件
    (project_path / '__init__.py').write_text(
        INIT_PY.format(project_name=project_name)
    )
    (project_path / 'spiders' / '__init__.py').write_text('')
    (project_path / 'items' / '__init__.py').write_text('')
    (project_path / 'middlewares' / '__init__.py').write_text('')
    (project_path / 'pipelines' / '__init__.py').write_text('')
    
    # 创建 settings.py
    (project_path / 'settings.py').write_text(
        SETTINGS_TEMPLATE.format(project_name=project_name)
    )
    
    # 创建项目内的 manage.py 运行器
    cli_content = generate_project_cli()
    (project_path / 'manage.py').write_text(cli_content)
    
    # 创建 README.md
    readme_content = README_TEMPLATE.format(project_name=project_name)
    (project_path / 'README.md').write_text(readme_content)

    # 创建 pyproject.toml（依赖 cola，供 colad 部署 uv sync 安装）
    (project_path / 'pyproject.toml').write_text(
        PYPROJECT_TEMPLATE.format(
            project_name=project_name,
            cola_dep=_cola_dependency(cola_source)))
    
    print(f"项目 '{project_name}' 创建成功!")
    print(f"\n目录结构:")
    print(f"  {project_name}/")
    print(f"  ├── manage.py")
    print(f"  ├── settings.py")
    print(f"  ├── README.md")
    print(f"  ├── spiders/")
    print(f"  ├── items/")
    print(f"  ├── middlewares/")
    print(f"  └── pipelines/")
    print(f"\n进入项目:")
    print(f"  cd {project_name}")
    print(f"\n创建爬虫:")
    print(f"  python manage.py genspider <name> <domain>")
    print(f"\n运行爬虫:")
    print(f"  python manage.py crawl <name>")
    print("")
    print(f"colad 部署: colad deploy --master http://<master>:8080"
          f" --name {project_name} --path . --runtime uv")

    return True


def generate_project_cli():
    """生成项目内的 cola.py 文件内容"""
    return '''#!/usr/bin/env python
"""
Cola 项目 CLI
"""
import sys
import argparse
import importlib
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cola.crawler import CrawlerProcess
from cola.settings.settings_manager import SettingsManager
from cola.spiders import Spider


SPIDER_TEMPLATE = \'\'\'from cola.spiders import Spider
from cola.http.request import Request


class {class_name}Spider(Spider):
    name = \'{spider_name}\'
    start_urls = [\'{start_url}\']
    
    custom_settings = {{
        \'CONCURRENT_REQUESTS\': 8,
        \'TIMEOUT\': 30,
    }}
    
    async def parse(self, response):
        """解析响应"""
        # 使用 XPath 提取数据
        # title = response.xpath(\'//title/text()\')
        
        # 使用 CSS 选择器提取数据
        # items = response.css(\'.item\')
        
        # 返回数据
        yield {{
            \'url\': response.url,
            \'status\': response.status_code,
        }}
        
        # 跟随链接
        # next_page = response.xpath(\'//a[@class="next"]/@href\')
        # if next_page:
        #     yield Request(url=response._urljoin(next_page[0]))
\'\'\'


def cmd_crawl(args):
    """运行爬虫"""
    import asyncio
    
    spider_name = args.spider
    settings_dict = {}
    
    if args.concurrent:
        settings_dict[\'CONCURRENT_REQUESTS\'] = args.concurrent
    if args.log_level:
        settings_dict[\'LOG_LEVEL\'] = args.log_level
    
    # 动态导入爬虫
    spiders_dir = project_root / \'spiders\'
    spider_class = None
    
    for py_file in spiders_dir.glob(\'*.py\'):
        if py_file.name.startswith(\'_\'):
            continue
        module_name = f"spiders.{py_file.stem}"
        try:
            module = importlib.import_module(module_name)
            for name, obj in module.__dict__.items():
                if not (isinstance(obj, type) and issubclass(obj, Spider)
                        and obj is not Spider):
                    continue
                sname = getattr(obj, 'name', None)
                sname = sname if isinstance(sname, str) else name
                if sname.lower() == spider_name.lower() or                         name.lower() == spider_name.lower():
                    spider_class = obj
                    break
        except Exception as e:
            print(f"导入模块 {module_name} 失败: {e}")
            continue
    
    if spider_class is None:
        print(f"错误: 找不到爬虫 \'{spider_name}\'")
        print("可用的爬虫:")
        cmd_list(args)
        return
    
    settings = SettingsManager(settings_dict)
    
    async def run():
        process = CrawlerProcess(settings)
        await process.crawl(spider_class)
        await process.start()
    
    asyncio.run(run())


def cmd_list(args):
    """列出所有爬虫"""
    spiders_dir = project_root / \'spiders\'
    spiders_found = []
    
    for py_file in spiders_dir.glob(\'*.py\'):
        if py_file.name.startswith(\'_\'):
            continue
        module_name = f"spiders.{py_file.stem}"
        try:
            module = importlib.import_module(module_name)
            for name, obj in module.__dict__.items():
                if (isinstance(obj, type) and 
                    issubclass(obj, Spider) and 
                    obj is not Spider):
                    spiders_found.append(name)
        except Exception:
            continue
    
    if spiders_found:
        print("可用的爬虫:")
        for name in spiders_found:
            print(f"  - {name}")
    else:
        print("没有找到爬虫")


def cmd_genspider(args):
    """创建新的爬虫"""
    spider_name = args.name
    domain = args.domain
    
    spiders_dir = project_root / \'spiders\'
    
    # 转换爬虫名称为类名
    class_name = \'\'.join(word.capitalize() for word in spider_name.split(\'_\'))
    start_url = f\'https://{domain}\'
    
    # 创建爬虫文件
    spider_file = spiders_dir / f\'{spider_name}.py\'
    if spider_file.exists():
        print(f"错误: 爬虫 \'{spider_name}\' 已存在")
        return
    
    spider_content = SPIDER_TEMPLATE.format(
        class_name=class_name,
        spider_name=spider_name,
        start_url=start_url
    )
    
    spider_file.write_text(spider_content)
    print(f"创建爬虫 \'{spider_name}\' 成功!")
    print(f"  文件: spiders/{spider_name}.py")
    print(f"  域名: {domain}")
    print(f"\\n运行爬虫:")
    print(f"  python manage.py crawl {spider_name}")


def main():
    parser = argparse.ArgumentParser(
        prog=\'cola\',
        description=\'Cola 爬虫框架 CLI\'
    )
    subparsers = parser.add_subparsers(dest=\'command\', help=\'可用命令\')
    
    # crawl 命令
    crawl_parser = subparsers.add_parser(\'crawl\', help=\'运行爬虫\')
    crawl_parser.add_argument(\'spider\', help=\'爬虫名称\')
    crawl_parser.add_argument(\'-c\', \'--concurrent\', type=int, help=\'并发请求数\')
    crawl_parser.add_argument(\'-l\', \'--log-level\', help=\'日志级别\')
    
    # list 命令
    list_parser = subparsers.add_parser(\'list\', help=\'列出所有爬虫\')
    
    # genspider 命令
    genspider_parser = subparsers.add_parser(\'genspider\', help=\'创建新的爬虫\')
    genspider_parser.add_argument(\'name\', help=\'爬虫名称\')
    genspider_parser.add_argument(\'domain\', help=\'目标域名\')
    
    args = parser.parse_args()
    
    if args.command == \'crawl\':
        cmd_crawl(args)
    elif args.command == \'list\':
        cmd_list(args)
    elif args.command == \'genspider\':
        cmd_genspider(args)
    else:
        parser.print_help()


if __name__ == \'__main__\':
    main()
'''


def create_spider(spider_name: str, domain: str, project_dir: str = None):
    """创建新的爬虫（全局命令，检查是否在项目目录中）"""
    return create_spider_in_project(spider_name, domain, project_dir)


def run_crawl(spider_name: str, project_dir: str = None, concurrent: int = None, log_level: str = None):
    """运行爬虫"""
    if project_dir is None:
        project_dir = os.getcwd()
    
    project_path = Path(project_dir)
    
    # 检查项目结构
    if not (project_path / 'spiders').exists():
        print("错误: 当前目录不是 Cola 项目目录")
        return False
    
    # 构建命令
    cmd = [sys.executable, 'manage.py', 'crawl', spider_name]
    if concurrent:
        cmd.extend(['-c', str(concurrent)])
    if log_level:
        cmd.extend(['-l', log_level])
    
    # 运行
    try:
        subprocess.run(cmd, cwd=project_dir, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"爬虫运行失败: {e}")
        return False
    except KeyboardInterrupt:
        print("\n爬虫被中断")
        return False


def list_spiders(project_dir: str = None):
    """列出所有爬虫"""
    if project_dir is None:
        project_dir = os.getcwd()
    
    project_path = Path(project_dir)
    spiders_dir = project_path / 'spiders'
    
    if not spiders_dir.exists():
        print("错误: 当前目录不是 Cola 项目目录 (找不到 spiders/ 目录)")
        return False
    
    spiders = []
    for py_file in spiders_dir.glob('*.py'):
        if py_file.name.startswith('_'):
            continue
        spiders.append(py_file.stem)
    
    if spiders:
        print("可用的爬虫:")
        for name in spiders:
            print(f"  - {name}")
    else:
        print("没有找到爬虫")
        print(f"创建爬虫: cola genspider <name> <domain>")
    
    return True


def cmd_fetch(args):
    """使用 cola 下载器直接获取 URL"""
    import asyncio
    from cola.http.request import Request
    from cola.http.response import Response
    from cola.settings.settings_manager import SettingsManager
    from cola.downloaders.aio_http_downloader import AioHttpDownloader
    
    url = args.url
    method = args.method.upper() if args.method else 'GET'
    headers = {}
    if args.headers:
        for h in args.headers:
            if ':' in h:
                key, value = h.split(':', 1)
                headers[key.strip()] = value.strip()
    
    request = Request(
        url=url,
        method=method,
        headers=headers if headers else None
    )
    
    class MockCrawler:
        def __init__(self, settings):
            self.settings = settings
            self.spider = None
            self.stat_collector = None
            self.pipeline_manager = None
    
    settings = SettingsManager({})
    crawler = MockCrawler(settings)
    
    async def run():
        downloader = AioHttpDownloader(crawler)
        downloader.open()
        try:
            response = await downloader.fetch(request)
            if response:
                print(f"[{response.status_code}] {response.url}")
                print("-" * 60)
                print(response.text[:args.limit] if args.limit > 0 else response.text)
                return 0
            else:
                print(f"Failed to fetch: {url}")
                return 1
        finally:
            await downloader.close()
    
    return asyncio.run(run())


def cmd_version(args):
    """显示 Cola 版本信息"""
    try:
        import cola
        cola_version = getattr(cola, '__version__', 'unknown')
    except ImportError:
        cola_version = "unknown"
    
    print(f"Cola {cola_version}")
    print(f"Python: {sys.version}")
    print(f"Platform: {sys.platform}")
    
    if args.verbose:
        import aiohttp
        import lxml
        import loguru
        print(f"aiohttp: {aiohttp.__version__}")
        print(f"lxml: {lxml.__version__}")
        print(f"loguru: {loguru.__version__}")
    
    return 0


def cmd_settings(args):
    """获取设置值"""
    from cola.settings.settings_manager import SettingsManager
    from cola.settings.default import get_default_settings
    
    settings = SettingsManager(get_default_settings())
    
    if args.setting:
        value = settings.get(args.setting)
        if value is None:
            print(f"Setting '{args.setting}' not found")
            return 1
        print(value)
    else:
        print("Current settings:")
        print("-" * 40)
        defaults = get_default_settings()
        for key in sorted(defaults.keys()):
            value = settings.get(key)
            print(f"{key}: {value}")
    
    return 0


def cmd_bench(args):
    """并发/吞吐基准:内置本地 mock 服务器 + 真实引擎全速爬,报 pages/min。

    与 scrapy bench 对齐——离线、可复现,测的是引擎调度与并发吞吐,而非外网。
    每个 mock 页面生成 FANOUT 个链接;BenchSpider 爬满 --pages 个响应后停止
    产生新链接,引擎在队列耗尽后自然退出。
    """
    import asyncio
    import time
    from datetime import datetime

    from aiohttp import web

    from cola.crawler import CrawlerProcess
    from cola.settings.settings_manager import SettingsManager
    from cola.spiders import Spider
    from cola.http.request import Request

    concurrent = args.concurrent
    max_pages = args.pages
    fanout = 8

    print("Cola Benchmark(内置 mock server + 真实引擎)")
    print("=" * 60)
    print(f"Concurrent requests: {concurrent}")
    print(f"Target pages:        {max_pages}")
    print(f"Link fanout/page:    {fanout}")
    print("")
    print("Running benchmark...")
    print("")

    class BenchSpider(Spider):
        start_urls = ['__PLACEHOLDER__']

        def __init__(self):
            super().__init__()
            self._scheduled = 0

        async def parse(self, response):
            data = response.json()
            yield {'page': data['page']}
            # 爬满目标页数前持续产生链接,喂饱引擎
            if self._scheduled < max_pages:
                for link in data['links']:
                    self._scheduled += 1
                    yield Request(url=link, callback=self.parse)

    async def run():
        # 1) 起本地 mock server
        async def page(request):
            n = int(request.match_info['n'])
            base = f"http://{request.host}"
            links = [f"{base}/{n * fanout + i}" for i in range(1, fanout + 1)]
            return web.json_response({'page': n, 'links': links})

        app = web.Application()
        app.router.add_get('/{n}', page)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        BenchSpider.start_urls = [f'http://127.0.0.1:{port}/1']

        settings = SettingsManager({
            'PROJECT_NAME': 'bench',
            'CONCURRENT_REQUESTS': concurrent,
            'LOG_LEVEL': 'WARNING',
            'EXTENSIONS': ['cola.extension.log_stats.LogStats'],
        })
        process = CrawlerProcess(settings)
        crawler = process.create_crawler(BenchSpider)
        process.crawlers.add(crawler)

        t0 = time.time()
        await crawler.crawl()
        elapsed = time.time() - t0

        await runner.cleanup()
        return elapsed, crawler.stat_collector

    elapsed, stats = asyncio.run(run())

    pages = stats.get_value('response_received_count', 0)
    items = stats.get_value('item_successful_count', 0)
    req_time = stats.get_value('downloader/response_time_total', 0.0)
    req_count = stats.get_value('downloader/request_count', 0)
    avg_lat = (req_time / req_count) if req_count else 0.0

    print("=" * 60)
    print("Benchmark Results")
    print("-" * 60)
    print(f"Elapsed:          {elapsed:.3f}s")
    print(f"Pages crawled:    {pages}")
    print(f"Items scraped:    {items}")
    if elapsed > 0:
        print(f"Pages/min:        {pages / elapsed * 60:.0f}")
        print(f"Pages/sec:        {pages / elapsed:.1f}")
    print(f"Avg download:     {avg_lat * 1000:.1f}ms")
    print(f"Concurrency:      {concurrent}")
    print("=" * 60)

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog='cola',
        description='Cola 爬虫框架 CLI 工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  cola startproject myproject          # 创建新项目
  cd myproject                         # 进入项目目录
  cola genspider example example.com   # 创建爬虫
  cola crawl example                   # 运行爬虫
  cola list                            # 列出所有爬虫
  cola fetch https://example.com       # 获取 URL
  cola version                         # 显示版本
  cola settings                        # 显示所有设置
        '''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # startproject 命令
    startproject_parser = subparsers.add_parser(
        'startproject',
        help='创建新的 Cola 项目'
    )
    startproject_parser.add_argument('project', help='项目名称')
    startproject_parser.add_argument(
        '--cola', default='',
        help='cola 依赖来源:本地路径或版本规格,默认自动探测本仓库')
    
    # genspider 命令
    genspider_parser = subparsers.add_parser(
        'genspider',
        help='创建新的爬虫'
    )
    genspider_parser.add_argument('name', help='爬虫名称')
    genspider_parser.add_argument('domain', help='目标域名 (例如: example.com)')
    
    # crawl 命令
    crawl_parser = subparsers.add_parser(
        'crawl',
        help='运行爬虫'
    )
    crawl_parser.add_argument('spider', help='爬虫名称')
    crawl_parser.add_argument('-c', '--concurrent', type=int, help='并发请求数')
    crawl_parser.add_argument('-l', '--log-level', help='日志级别')
    
    # list 命令
    list_parser = subparsers.add_parser(
        'list',
        help='列出所有爬虫'
    )
    
    # fetch 命令
    fetch_parser = subparsers.add_parser(
        'fetch',
        help='使用下载器获取 URL'
    )
    fetch_parser.add_argument('url', help='要获取的 URL')
    fetch_parser.add_argument('-m', '--method', help='HTTP 方法 (GET, POST, etc.)')
    fetch_parser.add_argument('-H', '--headers', action='append', help='HTTP 头 (key:value)')
    fetch_parser.add_argument('-L', '--limit', type=int, default=0, help='限制输出字符数 (0=无限制)')
    
    # version 命令
    version_parser = subparsers.add_parser(
        'version',
        help='显示版本信息'
    )
    version_parser.add_argument('-v', '--verbose', action='store_true', help='显示详细版本信息')
    
    # settings 命令
    settings_parser = subparsers.add_parser(
        'settings',
        help='获取设置值'
    )
    settings_parser.add_argument('setting', nargs='?', help='设置项名称')
    
    # bench 命令
    bench_parser = subparsers.add_parser(
        'bench',
        help='运行快速基准测试'
    )
    bench_parser.add_argument('--concurrent', type=int, default=16, help='并发请求数 (默认: 16)')
    bench_parser.add_argument('--pages', type=int, default=200, help='目标爬取页数 (默认: 200)')
    
    from cola.commands import extra
    extra.add_commands(subparsers)

    args = parser.parse_args()
    
    if args.command == 'startproject':
        create_project(args.project, cola_source=args.cola)
    elif args.command == 'genspider':
        create_spider(args.name, args.domain)
    elif args.command == 'crawl':
        run_crawl(args.spider, concurrent=args.concurrent, log_level=args.log_level)
    elif args.command == 'list':
        list_spiders()
    elif args.command == 'fetch':
        cmd_fetch(args)
    elif args.command == 'version':
        cmd_version(args)
    elif args.command == 'settings':
        cmd_settings(args)
    elif args.command == 'bench':
        cmd_bench(args)
    elif extra.handle(args):
        pass
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
