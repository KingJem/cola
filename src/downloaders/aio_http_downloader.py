from typing import Optional

from aiohttp import ClientSession, ClientResponse, TCPConnector
from loguru import logger

from src.downloaders import AsyncDownloaderManager
from src.downloaders import Downloader
from src.http.request import Request
from src.http.response import Response


class AioHttpDownloader(Downloader):

    def __init__(self, crawler):
        super().__init__(crawler)
        self.session = None
        self.connector: Optional = None
        self.active_downloader = AsyncDownloaderManager()
        self.verify_ssl = self.crawler.settings.getbool("VERIFY_SSL")
        self.timeout = self.crawler.settings.getint("TIMEOUT")
        self.max_retry = self.crawler.settings.getint("MAX_RETRY", 3)
        self.logger = logger

    def open(self):
        super().open()
        self.connector = TCPConnector(ssl=None if self.verify_ssl else False)
        self.session = ClientSession(connector=self.connector)
        downloader_name = self.__class__.__name__
        self.logger.info(f"{self.crawler.spider} opened downloader: {downloader_name}")

    async def fetch(self, request: Request) -> Optional[Response]:
        async with self.active_downloader(request):
            response = await self.download_with_retry(request)
            return response

    async def download_with_retry(self, request: Request) -> Optional[Response]:
        """带重试机制的下载"""
        last_exception = None
        for attempt in range(self.max_retry + 1):
            try:
                response = await self.download(request)
                if response is not None:
                    return response
            except Exception as e:
                last_exception = e
                if attempt < self.max_retry:
                    self.logger.warning(f"Download attempt {attempt + 1}/{self.max_retry + 1} failed for {request.url}: {e}")
                else:
                    self.logger.error(f"All download attempts failed for {request.url}: {e}")
        return None

    async def download(self, request: Request):
        try:
            logger.debug(f"Request downloading {request.url} method={request.method}")
            response = await self.send_request(request)
            return response
        except Exception as e:
            logger.error(f"Download failed for {request.url}: {e}")
            raise  # 抛出异常以便重试机制捕获

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
            body = await resp.read()
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
