"""cola CLI 补充命令,对齐 scrapy:runspider / parse / view / shell / edit。

这些命令大多脱离项目也能用(直接用下载器抓一个 URL);parse 需要能发现
项目里的爬虫。注册方式见 add_commands(),分发见 handle()。
"""
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import webbrowser
from pathlib import Path


def _coerce(v: str):
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return v


def _parse_set(pairs) -> dict:
    """把 -s KEY=VALUE 列表解析成配置字典(VALUE 尝试按 JSON 解析)。"""
    out = {}
    for p in pairs or []:
        if '=' in p:
            k, v = p.split('=', 1)
            out[k.strip()] = _coerce(v.strip())
    return out


def _mock_crawler(settings, spider=None):
    """给下载器/回调用的最小 crawler(无引擎)。"""
    from cola.stats_collector import StatsCollector
    from cola.subscriber import Subscriber

    class _MC:
        pass

    mc = _MC()
    mc.settings = settings
    mc.spider = spider
    mc.stat_collector = StatsCollector(settings)
    mc.subscriber = Subscriber()
    mc.pipeline_manager = None
    mc.engine = None
    return mc


async def _download(url, settings, method='GET'):
    from cola.http.request import Request
    from cola.downloaders.aio_http_downloader import AioHttpDownloader
    downloader = AioHttpDownloader(_mock_crawler(settings))
    downloader.open()
    try:
        return await downloader.fetch(Request(url=url, method=method))
    finally:
        await downloader.close()


def _load_spider_from_file(path_str: str):
    from cola.spiders import Spider
    path = Path(path_str).resolve()
    if not path.exists():
        return None
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for obj in vars(module).values():
        if (isinstance(obj, type) and issubclass(obj, Spider)
                and obj is not Spider):
            return obj
    return None


# ---------------- runspider ----------------

def cmd_runspider(args):
    """运行单个爬虫文件,无需项目结构(对齐 scrapy runspider)。"""
    from cola.crawler import CrawlerProcess
    from cola.settings.settings_manager import SettingsManager
    spider_cls = _load_spider_from_file(args.spider_file)
    if spider_cls is None:
        print(f"错误: {args.spider_file} 中未找到 Spider 子类")
        return 1
    settings = SettingsManager(_parse_set(args.set))

    async def run():
        process = CrawlerProcess(settings)
        await process.crawl(spider_cls)
        await process.start()

    asyncio.run(run())
    return 0


# ---------------- parse ----------------

def cmd_parse(args):
    """抓取一个 URL,过指定爬虫的回调,打印产出的 Item 与 Request。"""
    from cola.settings.settings_manager import SettingsManager
    from cola.http.request import Request
    from cola.runner import discover_spiders

    settings = SettingsManager(_parse_set(args.set))
    try:
        spiders = discover_spiders(args.project_dir)
    except SystemExit as exc:
        print(exc)
        return 1
    spider_cls = spiders.get(args.spider)
    if spider_cls is None:
        print(f"未找到爬虫 {args.spider!r},可用: {sorted(spiders)}")
        return 1

    spider = spider_cls()
    spider.crawler = _mock_crawler(settings, spider)
    callback = getattr(spider, args.callback, None)
    if callback is None or not callable(callback):
        print(f"爬虫 {args.spider} 无回调方法 {args.callback!r}")
        return 1

    items, requests = [], []

    async def run():
        response = await _download(args.url, settings)
        if response is None:
            return None
        response.request = Request(url=args.url)
        out = callback(response)
        if out is None:
            return response
        if hasattr(out, '__aiter__'):
            async for x in out:
                _bucket(x, items, requests)
        elif hasattr(out, '__iter__'):
            for x in out:
                _bucket(x, items, requests)
        return response

    response = asyncio.run(run())
    if response is None:
        print(f"下载失败: {args.url}")
        return 1

    print(f"[{response.status_code}] {response.url}")
    print(f"\n>>> 回调 {args.spider}.{args.callback} 产出 <<<")
    print(f"\n# Items ({len(items)}) " + "-" * 40)
    for it in items[:args.limit]:
        data = dict(it) if hasattr(it, 'items') else it
        print(json.dumps(data, ensure_ascii=False))
    print(f"\n# Requests ({len(requests)}) " + "-" * 37)
    for r in requests[:args.limit]:
        print(f"  {r.method} {r.url}")
    return 0


def _bucket(x, items, requests):
    from cola.http.request import Request
    (requests if isinstance(x, Request) else items).append(x)


# ---------------- view ----------------

def cmd_view(args):
    """下载 URL,存为临时 HTML 并尝试在浏览器打开(对齐 scrapy view)。"""
    from cola.settings.settings_manager import SettingsManager
    settings = SettingsManager(_parse_set(args.set))
    response = asyncio.run(_download(args.url, settings))
    if response is None:
        print(f"下载失败: {args.url}")
        return 1
    fname = 'cola-view-%x.html' % (abs(hash(args.url)) & 0xFFFFFF)
    path = Path(tempfile.gettempdir()) / fname
    path.write_bytes(response.body)
    print(f"[{response.status_code}] {response.url}")
    print(f"已保存: {path}")
    try:
        webbrowser.open(path.as_uri())
    except Exception:
        pass
    return 0


# ---------------- shell ----------------

def cmd_shell(args):
    """交互式 shell:可选抓取一个 URL,把 response 注入命名空间。"""
    from cola.settings.settings_manager import SettingsManager
    settings = SettingsManager(_parse_set(args.set))
    ns = {'settings': settings}
    if args.url:
        response = asyncio.run(_download(args.url, settings))
        ns['response'] = response
        ns['url'] = args.url
        code = response.status_code if response else 'ERR'
        print(f"[{code}] {args.url}  ->  变量 `response` 可用")

    def fetch(url):
        return asyncio.run(_download(url, settings))
    ns['fetch'] = fetch

    banner = ("cola shell — 可用对象: response, settings, fetch(url)\n"
              "  response.xpath(...) / .css(...) / .json() / .text")
    try:
        from IPython import embed
        embed(banner1=banner, user_ns=ns)
    except ImportError:
        import code as _code
        _code.interact(banner=banner, local=ns)
    return 0


# ---------------- edit ----------------

def cmd_edit(args):
    """用 $EDITOR 打开项目内的爬虫文件(对齐 scrapy edit)。"""
    editor = os.environ.get('EDITOR', 'vi')
    path = Path('spiders') / f'{args.spider}.py'
    if not path.exists():
        print(f"未找到 {path}(请在项目根目录运行)")
        return 1
    return os.system(f'{editor} "{path}"')


# ---------------- 注册 / 分发 ----------------

_HANDLERS = {
    'runspider': cmd_runspider,
    'parse': cmd_parse,
    'view': cmd_view,
    'shell': cmd_shell,
    'edit': cmd_edit,
}


def add_commands(subparsers):
    rs = subparsers.add_parser('runspider', help='运行单个爬虫文件(无需项目)')
    rs.add_argument('spider_file', help='爬虫 .py 文件路径')
    rs.add_argument('-s', '--set', action='append', help='KEY=VALUE 配置覆盖')

    p = subparsers.add_parser('parse', help='用爬虫回调解析一个 URL,打印产出')
    p.add_argument('url', help='要解析的 URL')
    p.add_argument('--spider', required=True, help='爬虫名(类名)')
    p.add_argument('-c', '--callback', default='parse', help='回调方法名')
    p.add_argument('--project-dir', default='.', help='含 spiders/ 的目录')
    p.add_argument('--limit', type=int, default=20, help='最多打印条数')
    p.add_argument('-s', '--set', action='append', help='KEY=VALUE 配置覆盖')

    v = subparsers.add_parser('view', help='下载 URL 并在浏览器打开')
    v.add_argument('url', help='要查看的 URL')
    v.add_argument('-s', '--set', action='append', help='KEY=VALUE 配置覆盖')

    sh = subparsers.add_parser('shell', help='交互式 shell(response 可用)')
    sh.add_argument('url', nargs='?', help='可选:先抓取此 URL')
    sh.add_argument('-s', '--set', action='append', help='KEY=VALUE 配置覆盖')

    ed = subparsers.add_parser('edit', help='用 $EDITOR 打开爬虫文件')
    ed.add_argument('spider', help='爬虫名')


def handle(args) -> bool:
    fn = _HANDLERS.get(args.command)
    if fn is None:
        return False
    rc = fn(args)
    if isinstance(rc, int) and rc:
        sys.exit(rc)
    return True
