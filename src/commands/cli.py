"""
Cola CLI - 命令行工具
类似于 Scrapy 的命令行接口
"""
import os
import sys
import argparse
import subprocess
from pathlib import Path


SPIDER_TEMPLATE = '''from src.spiders import Spider
from src.http.request import Request


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
DOWNLOADER_CLASS = 'src.downloaders.aio_http_downloader.AioHttpDownloader'

# 日志级别
LOG_LEVEL = 'INFO'

# 其他自定义设置
# CUSTOM_SETTING = 'value'
'''


INIT_PY = '''"""
{project_name} 项目
"""
'''


README_TEMPLATE = '''# {project_name}

Cola 爬虫项目

## 目录结构

```
{project_name}/
├── cola.py           # CLI 工具
├── settings.py       # 项目配置
├── spiders/          # 爬虫目录
├── items/            # Item 定义
├── middlewares/      # 中间件
└── pipelines/        # 数据管道
```

## 快速开始

### 创建爬虫

```bash
python cola.py genspider example example.com
```

### 运行爬虫

```bash
python cola.py crawl example
```

### 列出所有爬虫

```bash
python cola.py list
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
    print(f"  python cola.py crawl {spider_name}")
    
    return True


def create_project(project_name: str, project_dir: str = None):
    """创建新的 Cola 项目"""
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
    
    # 创建项目内的 cola.py CLI 脚本
    cli_content = generate_project_cli()
    (project_path / 'cola.py').write_text(cli_content)
    
    # 创建 README.md
    readme_content = README_TEMPLATE.format(project_name=project_name)
    (project_path / 'README.md').write_text(readme_content)
    
    print(f"项目 '{project_name}' 创建成功!")
    print(f"\n目录结构:")
    print(f"  {project_name}/")
    print(f"  ├── cola.py")
    print(f"  ├── settings.py")
    print(f"  ├── README.md")
    print(f"  ├── spiders/")
    print(f"  ├── items/")
    print(f"  ├── middlewares/")
    print(f"  └── pipelines/")
    print(f"\n进入项目:")
    print(f"  cd {project_name}")
    print(f"\n创建爬虫:")
    print(f"  python cola.py genspider <name> <domain>")
    print(f"\n运行爬虫:")
    print(f"  python cola.py crawl <name>")
    
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

from src.crawler import CrawlerProcess
from src.settings.settings_manager import SettingsManager
from src.spiders import Spider


SPIDER_TEMPLATE = \'\'\'from src.spiders import Spider
from src.http.request import Request


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
                if (isinstance(obj, type) and 
                    issubclass(obj, Spider) and 
                    obj is not Spider and
                    name.lower() == spider_name.lower()):
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
    print(f"  python cola.py crawl {spider_name}")


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
    cmd = [sys.executable, 'cola.py', 'crawl', spider_name]
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
        '''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # startproject 命令
    startproject_parser = subparsers.add_parser(
        'startproject',
        help='创建新的 Cola 项目'
    )
    startproject_parser.add_argument('project', help='项目名称')
    
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
    
    args = parser.parse_args()
    
    if args.command == 'startproject':
        create_project(args.project)
    elif args.command == 'genspider':
        create_spider(args.name, args.domain)
    elif args.command == 'crawl':
        run_crawl(args.spider, concurrent=args.concurrent, log_level=args.log_level)
    elif args.command == 'list':
        list_spiders()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
