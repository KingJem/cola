import re
from typing import Dict, Optional

from src.http.request import Request


class Response:
    def __init__(self, url, *, status: int, headers: Dict[str, str], body: bytes, request: Request = None, ):
        self.url = url
        self.status_code = status
        self.headers = headers
        self.body = body
        self.request: Optional[Request] = request
        self.exception: Optional[Exception] = None
        self._encoding: Optional[str] = None
        self._cached_text: Optional[str] = None
        self._meta: dict = {}

    def __repr__(self):
        return f"<Response {self.url} status_code={self.status_code}>"

    @property
    def text(self):
        if self._cached_text is None:
            encoding = self._encoding or 'utf-8'
            self._cached_text = self.body.decode(encoding, errors='replace')
        return self._cached_text

    def encoding(self):
        """获取响应编码（占位方法）"""
        return None

    def json(self):
        import json
        return json.loads(self.text)

    def follow(self, url: str, callback=None, **kwargs):
        from src.http.request import Request
        return Request(url, callback=callback, **kwargs)

    def xpath(self, query: str):
        from lxml import html
        tree = html.fromstring(self.body)
        return tree.xpath(query)

    def css(self, query: str):
        from lxml import html
        tree = html.fromstring(self.body)
        return tree.cssselect(query)

    def re(self, pattern: str):
        import re
        return re.findall(pattern, self.text)

    @property
    def meta(self):
        if self.request:
            return self.request.meta
        return self._meta

    @meta.setter
    def meta(self, value):
        self._meta = value

    def _urljoin(self, url: str):
        from urllib.parse import urljoin
        return urljoin(self.url, url)
