"""2026-07 批量修复的回归测试:
follow 相对 URL、proxy/cookies 传递、POST 指纹、配置优先级分层、
选择器树缓存。
"""
from unittest.mock import Mock

from cola.downloaders.aio_http_downloader import AioHttpDownloader
from cola.dupefilter import RFPDupeFilter
from cola.http.request import Request
from cola.http.response import Response
from cola.settings.settings_manager import (
    PRIORITY_SPIDER, SettingsManager)


def make_response(body=b'<html></html>', url='https://e.com/a/b'):
    return Response(url=url, status=200, headers={}, body=body)


# ---------------- response.follow ----------------

class TestFollow:
    def test_relative_path(self):
        req = make_response().follow('/page/2')
        assert req.url == 'https://e.com/page/2'

    def test_relative_no_slash(self):
        req = make_response(url='https://e.com/list/index.html').follow('p2.html')
        assert req.url == 'https://e.com/list/p2.html'

    def test_absolute_untouched(self):
        req = make_response().follow('https://other.com/x')
        assert req.url == 'https://other.com/x'

    def test_callback_and_kwargs(self):
        cb = lambda r: None  # noqa: E731
        req = make_response().follow('/x', callback=cb, priority=9)
        assert req.callback is cb
        assert req.priority == 9


# ---------------- proxy / cookies 传递 ----------------

class TestRequestKwargs:
    def _downloader(self):
        crawler = Mock()
        crawler.settings = SettingsManager()
        return AioHttpDownloader(crawler)

    def test_cookies_and_proxy_str(self):
        d = self._downloader()
        request = Request(url='https://e.com', cookies={'sid': '1'},
                          proxy='http://proxy:8080')
        kwargs = d._build_request_kwargs(request)
        assert kwargs['cookies'] == {'sid': '1'}
        assert kwargs['proxy'] == 'http://proxy:8080'

    def test_proxy_dict_compat(self):
        d = self._downloader()
        request = Request(url='https://e.com',
                          proxy={'http': 'http://p1:8080',
                                 'https': 'http://p2:8080'})
        assert d._build_request_kwargs(request)['proxy'] == 'http://p2:8080'

    def test_no_proxy_no_cookie_keys(self):
        d = self._downloader()
        kwargs = d._build_request_kwargs(Request(url='https://e.com'))
        assert 'proxy' not in kwargs
        assert 'cookies' not in kwargs


# ---------------- POST 指纹含 body ----------------

class TestFingerprintBody:
    def test_different_body_different_fingerprint(self):
        f = RFPDupeFilter()
        r1 = Request(url='https://e.com/api', method='POST', body='{"a": 1}')
        r2 = Request(url='https://e.com/api', method='POST', body='{"a": 2}')
        assert f.request_fingerprint(r1) != f.request_fingerprint(r2)

    def test_same_body_same_fingerprint(self):
        f = RFPDupeFilter()
        r1 = Request(url='https://e.com/api', method='POST', body='x')
        r2 = Request(url='https://e.com/api', method='POST', body='x')
        assert f.request_fingerprint(r1) == f.request_fingerprint(r2)


# ---------------- Request meta 构造参数 ----------------

def test_request_meta_kwarg():
    req = Request(url='https://e.com', meta={'page': 1})
    assert req.meta == {'page': 1}


# ---------------- 配置优先级分层 ----------------

class TestSettingsPriority:
    def test_spider_cannot_override_runtime(self):
        settings = SettingsManager({'CONCURRENT_REQUESTS': 2})
        settings.update_values({'CONCURRENT_REQUESTS': 99},
                               priority=PRIORITY_SPIDER)
        assert settings.getint('CONCURRENT_REQUESTS') == 2

    def test_spider_overrides_default(self):
        settings = SettingsManager()
        settings.update_values({'CONCURRENT_REQUESTS': 99},
                               priority=PRIORITY_SPIDER)
        assert settings.getint('CONCURRENT_REQUESTS') == 99

    def test_runtime_set_always_wins(self):
        settings = SettingsManager()
        settings.update_values({'TIMEOUT': 5}, priority=PRIORITY_SPIDER)
        settings.set('TIMEOUT', 60)  # 热配置 / 运行时
        assert settings.getint('TIMEOUT') == 60

    def test_copy_preserves_priorities(self):
        settings = SettingsManager({'TIMEOUT': 1})
        cloned = settings.copy()
        cloned.update_values({'TIMEOUT': 99}, priority=PRIORITY_SPIDER)
        assert cloned.getint('TIMEOUT') == 1


# ---------------- 选择器树缓存 ----------------

def test_selector_tree_cached():
    resp = make_response(b'<html><p>a</p></html>')
    assert resp.xpath('//p/text()') == ['a']
    first_tree = resp._cached_tree
    resp.xpath('//p')
    assert resp._cached_tree is first_tree
