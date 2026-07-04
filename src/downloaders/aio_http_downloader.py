import time
from asyncio import Semaphore
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse

from aiohttp import ClientSession, ClientResponse, TCPConnector
from loguru import logger

from src.downloaders import AsyncDownloaderManager
from src.downloaders import Downloader
from src.exceptions import DownloadMaxsizeExceeded
from src.http.request import Request
from src.http.response import Response


class AioHttpDownloader(Downloader):
    """aiohttp 下载器:单次请求,失败原样抛出(重试由 Retry 中间件负责)。

    可选限制:
        CONCURRENT_REQUESTS_PER_DOMAIN  每域名并发上限(0 不限)
        DOWNLOAD_MAXSIZE                响应体字节上限(0 不限)
    """

    def __init__(self, crawler):
        super().__init__(crawler)
        self.session = None
        self.connector: Optional = None
        self.active_downloader = AsyncDownloaderManager()
        self.verify_ssl = self.crawler.settings.getbool("VERIFY_SSL")
        self.timeout = self.crawler.settings.getint("TIMEOUT")
        self.maxsize = self.crawler.settings.getint("DOWNLOAD_MAXSIZE", 0)
        per_domain = self.crawler.settings.getint(
            "CONCURRENT_REQUESTS_PER_DOMAIN", 0)
        self._domain_limit = per_domain
        self._domain_sems = defaultdict(lambda: Semaphore(per_domain))
        self.logger = logger

    def open(self):
        super().open()
        self.connector = TCPConnector(ssl=None if self.verify_ssl else False)
        self.session = ClientSession(connector=self.connector)
        downloader_name = self.__class__.__name__
        self.logger.info(f"{self.crawler.spider} opened downloader: {downloader_name}")

    async def fetch(self, request: Request) -> Optional[Response]:
        async with self.active_downloader(request):
            if self._domain_limit:
                host = urlparse(request.url).hostname or ''
                async with self._domain_sems[host]:
                    return await self.download(request)
            return await self.download(request)

    async def download(self, request: Request):
        logger.debug(f"Request downloading {request.url} method={request.method}")
        start = time.monotonic()
        try:
            return await self.send_request(request)
        finally:
            self._record_time(time.monotonic() - start)

    def _record_time(self, elapsed: float):
        stats = getattr(self.crawler, 'stat_collector', None)
        if stats is None:
            return
        stats.inc_value('downloader/response_time_total', elapsed)
        stats.inc_value('downloader/request_count')
        stats.max_value('downloader/response_time_max', elapsed)

    @staticmethod
    def _resolve_proxy(proxy) -> Optional[str]:
        """aiohttp 的 proxy 参数是 URL 字符串;兼容文档中的 dict 写法
        {'http': 'http://host:port'}(按 https/http 顺序取)。"""
        if not proxy:
            return None
        if isinstance(proxy, str):
            return proxy
        if isinstance(proxy, dict):
            return proxy.get('https') or proxy.get('http') \
                or next(iter(proxy.values()), None)
        return None

    def _build_request_kwargs(self, request: Request) -> dict:
        kwargs = dict(
            method=request.method,
            url=request.url,
            headers=request.headers,
            data=request.body,
            timeout=self.timeout,
        )
        if request.cookies:
            kwargs['cookies'] = request.cookies
        proxy = self._resolve_proxy(request.proxy)
        if proxy:
            kwargs['proxy'] = proxy
        return kwargs

    async def send_request(self, request: Request) -> Response:
        async with self.session.request(
                **self._build_request_kwargs(request)) as resp:
            if self.maxsize:
                length = resp.headers.get('Content-Length')
                if length and int(length) > self.maxsize:
                    raise DownloadMaxsizeExceeded(
                        f'{request.url} Content-Length {length} '
                        f'> DOWNLOAD_MAXSIZE {self.maxsize}')
            body = await resp.read()
            if self.maxsize and len(body) > self.maxsize:
                raise DownloadMaxsizeExceeded(
                    f'{request.url} body {len(body)} bytes '
                    f'> DOWNLOAD_MAXSIZE {self.maxsize}')
            return self.structure_response(resp, request, body)

    @staticmethod
    def structure_response(response: ClientResponse, request: Request, body) -> Response:
        return Response(
            url=str(response.url),
            status=response.status,
            headers=dict(response.headers),
            request=request,
            body=body,
        )

    async def close(self):
        if self.session:
            await self.session.close()
        if self.connector:
            await self.connector.close()

    def idle(self):
        return self.active_downloader.idle()
