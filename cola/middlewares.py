"""
下载中间件管理器。

中间件配置（DOWNLOADER_MIDDLEWARES）格式：
    {
        'path.to.MyMiddleware': 100,
        'path.to.OtherMiddleware': 200,
    }
数字为优先级（升序），process_request 按升序执行，process_response 按降序执行。

中间件接口（方法均为可选）：
    process_request(request, spider)           -> None | Request | Response
    process_response(request, response, spider) -> Response | Request
    process_exception(request, exception, spider) -> None | Response | Request
"""
import asyncio
import inspect
from typing import Optional

from loguru import logger

from cola.utils import load_class


async def _call_maybe_async(method, *args):
    """统一调用同步或异步方法"""
    if inspect.iscoroutinefunction(method):
        return await method(*args)
    else:
        return method(*args)


class MiddlewareManager:

    def __init__(self, crawler):
        self.crawler = crawler
        self.middlewares = []
        self._methods = {
            'process_request': [],
            'process_response': [],
            'process_exception': [],
        }
        self._load()

    @classmethod
    def create_instance(cls, crawler):
        return cls(crawler)

    def _load(self):
        setting = self.crawler.settings.get('DOWNLOADER_MIDDLEWARES', {})
        if not setting:
            return

        sorted_mws = sorted(setting.items(), key=lambda x: x[1])
        enabled = []
        for class_path, priority in sorted_mws:
            try:
                cls = load_class(class_path)
                if hasattr(cls, 'create_instance'):
                    instance = cls.create_instance(self.crawler)
                else:
                    instance = cls()
                self.middlewares.append(instance)
                enabled.append(f"  {priority:4d} {class_path}")

                # 只注册存在的方法（不强制全部有）
                for method_name in ('process_request', 'process_response', 'process_exception'):
                    if hasattr(instance, method_name):
                        self._methods[method_name].append(getattr(instance, method_name))

            except Exception as e:
                logger.error(f"Failed to load middleware {class_path}: {e}")

        if enabled:
            logger.info("Enabled downloader middlewares:\n" + "\n".join(enabled))

    async def process_request(self, request, spider):
        """
        按优先级顺序执行 process_request。
        - 返回 None：继续下一个中间件
        - 返回 Request：用新请求继续链（修改后的请求）
        - 返回 Response：短路，直接进入 process_response（跳过下载）
        """
        for method in self._methods['process_request']:
            result = await _call_maybe_async(method, request, spider)
            if result is not None:
                return result  # 短路：Response 或新 Request
        return request

    async def process_response(self, request, response, spider):
        """
        按优先级逆序执行 process_response。
        - 返回 Response：继续下一个中间件
        - 返回 Request：短路返回,由引擎重新入队(后续中间件不再执行)
        """
        from cola.http.request import Request
        for method in reversed(self._methods['process_response']):
            response = await _call_maybe_async(method, request, response, spider)
            if isinstance(response, Request):
                return response
        return response

    async def process_exception(self, request, exception, spider):
        """
        下载发生异常时按顺序执行。
        - 返回 None：继续下一个中间件（异常继续传播）
        - 返回 Response 或 Request：停止异常传播
        """
        for method in self._methods['process_exception']:
            result = await _call_maybe_async(method, request, exception, spider)
            if result is not None:
                return result
        return None
