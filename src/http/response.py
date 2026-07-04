import codecs
import re
from typing import Dict, Optional

from src.http.request import Request

# 从 Content-Type 头或 HTML meta 标签探测字符集
_CHARSET_HEADER_RE = re.compile(r'charset=["\']?([\w.-]+)', re.I)
_CHARSET_META_RE = re.compile(rb'charset=["\']?([\w.-]+)', re.I)


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
        self._cached_tree = None
        self._meta: dict = {}

    def __repr__(self):
        return f"<Response {self.url} status_code={self.status_code}>"

    def encoding(self) -> str:
        """响应编码:Content-Type 头 -> HTML meta 标签 -> utf-8。"""
        if self._encoding:
            return self._encoding
        encoding = None
        content_type = ''
        for key, value in (self.headers or {}).items():
            if key.lower() == 'content-type':
                content_type = value or ''
                break
        match = _CHARSET_HEADER_RE.search(content_type)
        if match:
            encoding = match.group(1)
        if not encoding and self.body:
            match = _CHARSET_META_RE.search(self.body[:2048])
            if match:
                encoding = match.group(1).decode('ascii', errors='ignore')
        if encoding:
            try:
                codecs.lookup(encoding)
            except LookupError:
                encoding = None
        self._encoding = (encoding or 'utf-8').lower()
        return self._encoding

    @property
    def text(self):
        if self._cached_text is None:
            self._cached_text = self.body.decode(self.encoding(),
                                                 errors='replace')
        return self._cached_text

    def json(self):
        import json
        return json.loads(self.text)

    def follow(self, url: str, callback=None, **kwargs):
        from src.http.request import Request
        # 相对 URL 基于当前响应地址补全
        return Request(self._urljoin(url), callback=callback, **kwargs)

    def _tree(self):
        if self._cached_tree is None:
            from lxml import html
            self._cached_tree = html.fromstring(self.body)
        return self._cached_tree

    def xpath(self, query: str):
        return self._tree().xpath(query)

    def css(self, query: str):
        return self._tree().cssselect(query)

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
