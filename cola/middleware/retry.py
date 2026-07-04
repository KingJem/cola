"""重试中间件:HTTP 状态码与下载异常的统一重试入口。

下载器只请求一次,失败原样抛出;本中间件决定是否重试:
- process_response:状态码命中 RETRY_HTTP_CODES 时返回新 Request,
  引擎将其重新入队(dont_filter),放弃后原样返回响应
- process_exception:网络类异常(aiohttp 连接/超时等 + RETRY_EXCEPTIONS)
  返回新 Request;返回 None 则异常继续按未处理流程丢弃该请求

请求级开关:request.meta['dont_retry'] = True
统计:retry_count / retry/max_reached
"""
from asyncio.exceptions import TimeoutError

from aiohttp import (
    ClientConnectionError, ClientConnectorError, ClientPayloadError,
    ClientResponseError, ServerTimeoutError)

from cola.http.request import Request
from cola.utils.log import get_logger

_RETRY_EXCEPTIONS = (
    ClientConnectionError,
    ClientConnectorError,
    ClientPayloadError,
    ClientResponseError,
    ServerTimeoutError,
    TimeoutError,
    ConnectionError,
    OSError,
)


class Retry:

    def __init__(self, *, retry_http_codes, ignore_http_codes,
                 max_retry_times, retry_exceptions, stats, retry_priority,
                 log_level=None):
        self.retry_http_codes = {int(c) for c in retry_http_codes}
        self.ignore_http_codes = {int(c) for c in ignore_http_codes}
        self.max_retry_times = max_retry_times
        self.retry_exceptions = tuple(retry_exceptions) + _RETRY_EXCEPTIONS
        self.stats = stats
        self.retry_priority = retry_priority
        self.logger = get_logger(self.__class__.__name__, log_level)

    @classmethod
    def create_instance(cls, crawler):
        settings = crawler.settings
        return cls(
            retry_http_codes=settings.getlist('RETRY_HTTP_CODES'),
            ignore_http_codes=settings.getlist('IGNORE_HTTP_CODES'),
            max_retry_times=settings.getint('MAX_RETRY_TIMES', 3),
            retry_exceptions=list(settings.getlist('RETRY_EXCEPTIONS')),
            stats=crawler.stat_collector,
            retry_priority=settings.getint('RETRY_PRIORITY', -1),
            log_level=settings.get('LOG_LEVEL'),
        )

    def process_response(self, request, response, spider):
        if request.meta.get('dont_retry', False):
            return response
        status = response.status_code
        if status in self.ignore_http_codes:
            return response
        if status in self.retry_http_codes:
            return self._retry(request, f'status {status}', spider) or response
        return response

    def process_exception(self, request, exc, spider):
        if (isinstance(exc, self.retry_exceptions)
                and not request.meta.get('dont_retry', False)):
            return self._retry(request, type(exc).__name__, spider)
        return None

    def _retry(self, request: Request, reason, spider):
        retry_times = request.meta.get('retry_times', 0)
        if retry_times >= self.max_retry_times:
            self.stats.inc_value('retry/max_reached')
            self.logger.warning(
                f'{spider} {request} {reason}: 已重试 {retry_times} 次,放弃')
            return None
        new_request = request.copy()
        new_request.meta['retry_times'] = retry_times + 1
        new_request.dont_filter = True
        new_request.priority = request.priority + self.retry_priority
        self.stats.inc_value('retry_count')
        self.logger.info(
            f'{spider} {request} {reason}: 第 {retry_times + 1} 次重试')
        return new_request
