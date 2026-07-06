import re
from typing import Callable


class Request:
    def __init__(self,
                 url: str,
                 *,
                 headers: dict = None,
                 priority: int = 0,
                 method: str = "GET",
                 cookies: dict = None,
                 proxy: dict = None,
                 body: str = None,
                 callback: Callable = None,
                 dont_filter: bool = False,
                 meta: dict = None,
                 ):
        self.url = url
        # 始终为 dict,便于中间件 setdefault 合并请求头
        self.headers = dict(headers) if headers else {}
        self.priority = priority
        self.method = method.upper()
        self.cookies = cookies
        self.proxy = proxy
        self.body = body
        self.callback = callback
        self.dont_filter = dont_filter
        self.meta = dict(meta) if meta else {}

    def __lt__(self, other):
        return self.priority < other.priority

    def copy(self) -> "Request":
        request = Request(
            url=self.url,
            headers=dict(self.headers) if self.headers else None,
            priority=self.priority,
            method=self.method,
            cookies=dict(self.cookies) if self.cookies else None,
            proxy=self.proxy,
            body=self.body,
            callback=self.callback,
            dont_filter=self.dont_filter,
            meta=dict(self.meta),
        )
        return request

    def encoding(self):
        """获取请求的编码（占位方法，暂未实现）"""
        return None

    def __repr__(self):
        return f"<Request {self.method} {self.url}>"
