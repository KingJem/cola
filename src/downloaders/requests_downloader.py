import asyncio
import requests

from src.downloaders import Downloader, SyncDownloaderManager
from src.http.request import Request
from src.http.response import Response


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
