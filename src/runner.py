"""通用爬虫运行器:按名字发现并运行项目中的 Spider。

colad 部署代理即通过本入口启动爬虫:

    python -m src.runner --project-dir demo_project --spider QuotesSpider \
        --settings '{"CONCURRENT_REQUESTS": 8}'

约定:--project-dir 下有 spiders/ 包,内含 Spider 子类;--settings 为
JSON 字符串(或 --settings-file 指向 JSON 文件),覆盖默认配置。
"""
import argparse
import asyncio
import importlib
import json
import pkgutil
import sys
from pathlib import Path

from loguru import logger

from src.crawler import CrawlerProcess
from src.settings.settings_manager import SettingsManager
from src.spiders import Spider


def discover_spiders(project_dir: str) -> dict:
    """导入 {project_dir}/spiders 包中所有模块,返回 {名字: Spider 子类}。

    名字同时登记类名与类的 name 属性(默认即类名)。
    """
    root = Path(project_dir).resolve()
    spiders_pkg = root / 'spiders'
    if not spiders_pkg.is_dir():
        raise SystemExit(f"未找到 spiders 包: {spiders_pkg}")

    # 项目目录与仓库根都要可导入(项目里 from src... / from spiders... 均可用)
    for path in (str(root), str(root.parent)):
        if path not in sys.path:
            sys.path.insert(0, path)

    package_name = f'{root.name}.spiders' if (root / '__init__.py').exists() \
        else 'spiders'
    package = importlib.import_module(package_name)

    found = {}
    for module_info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(
            f'{package_name}.{module_info.name}')
        for attr in vars(module).values():
            if (isinstance(attr, type) and issubclass(attr, Spider)
                    and attr is not Spider):
                found[attr.__name__] = attr
    return found


def load_settings(args) -> SettingsManager:
    values = {}
    if args.settings_file:
        values.update(json.loads(Path(args.settings_file).read_text('utf-8')))
    if args.settings:
        values.update(json.loads(args.settings))
    return SettingsManager(values)


async def run(spider_cls, settings: SettingsManager):
    process = CrawlerProcess(settings)
    await process.crawl(spider_cls)
    await process.start()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run a cola spider by name')
    parser.add_argument('--spider', default=None, help='Spider 类名')
    parser.add_argument('--project-dir', default='.',
                        help='包含 spiders/ 包的项目目录')
    parser.add_argument('--settings', default=None, help='JSON 配置覆盖')
    parser.add_argument('--settings-file', default=None, help='JSON 配置文件')
    parser.add_argument('--list', action='store_true', dest='list_spiders',
                        help='仅列出可用爬虫')
    args = parser.parse_args(argv)

    spiders = discover_spiders(args.project_dir)
    if args.list_spiders:
        print(json.dumps(sorted(spiders), ensure_ascii=False))
        return
    if not args.spider:
        parser.error('--spider 必填(或用 --list 查看可用爬虫)')

    spider_cls = spiders.get(args.spider)
    if spider_cls is None:
        raise SystemExit(
            f"未找到爬虫 {args.spider!r},可用: {sorted(spiders)}")

    settings = load_settings(args)
    logger.info(f"Runner starting spider {args.spider} "
                f"(project_dir={args.project_dir})")
    asyncio.run(run(spider_cls, settings))


if __name__ == '__main__':
    main()
