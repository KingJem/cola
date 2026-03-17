import hashlib
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse
from typing import Set


class RFPDupeFilter:
    """
    基于请求指纹（Request Fingerprint）的内存去重过滤器。

    指纹算法：SHA1(METHOD + canonical_url)
    - canonical_url：对 query string 参数排序后重建，去除 fragment
    进程重启后去重状态丢失（内存存储）。
    """

    def __init__(self, debug: bool = False):
        self.fingerprints: Set[str] = set()
        self.debug = debug

    @classmethod
    def from_crawler(cls, crawler):
        debug = crawler.settings.getbool('DUPEFILTER_DEBUG', False)
        return cls(debug=debug)

    def request_fingerprint(self, request) -> str:
        parsed = urlparse(request.url)
        # 对 query 参数排序，使参数顺序不影响指纹
        sorted_query = urlencode(sorted(parse_qsl(parsed.query)))
        canonical = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            sorted_query,
            '',  # 去掉 fragment
        ))
        raw = f"{request.method.upper()}{canonical}"
        return hashlib.sha1(raw.encode('utf-8')).hexdigest()

    def is_seen(self, request) -> bool:
        return self.request_fingerprint(request) in self.fingerprints

    def mark_seen(self, request):
        self.fingerprints.add(self.request_fingerprint(request))

    def close(self):
        self.fingerprints.clear()

    def __len__(self):
        return len(self.fingerprints)
