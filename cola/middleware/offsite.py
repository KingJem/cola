"""Offsite 过滤:请求域名不在 spider.allowed_domains 内时丢弃。

allowed_domains 为域名后缀列表(如 ['example.com'] 同时放行
example.com 与 *.example.com)。spider 未定义该属性则不过滤。

配置:
    DOWNLOADER_MIDDLEWARES = {'cola.middleware.offsite.Offsite': 50}
"""
from urllib.parse import urlparse

from cola.exceptions import IgnoreRequest
from cola.utils.log import get_logger


class Offsite:

    def __init__(self, allowed_domains, log_level=None):
        self.allowed_domains = [d.lstrip('.').lower()
                                for d in (allowed_domains or [])]
        self.logger = get_logger(self.__class__.__name__, log_level)

    @classmethod
    def create_instance(cls, crawler):
        allowed = getattr(crawler.spider, 'allowed_domains', None)
        return cls(allowed, log_level=crawler.settings.get('LOG_LEVEL'))

    def _allowed(self, host: str) -> bool:
        if not self.allowed_domains:
            return True
        host = (host or '').lower()
        return any(host == domain or host.endswith('.' + domain)
                   for domain in self.allowed_domains)

    def process_request(self, request, spider):
        host = urlparse(request.url).hostname
        if not self._allowed(host):
            raise IgnoreRequest(f'offsite: {host}')
        return None
