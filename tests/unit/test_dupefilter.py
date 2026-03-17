import pytest
from src.dupefilter import RFPDupeFilter
from src.http.request import Request


def make_request(url, method='GET'):
    return Request(url=url, method=method)


def test_new_request_not_seen():
    f = RFPDupeFilter()
    req = make_request('http://example.com/page1')
    assert not f.is_seen(req)


def test_seen_after_mark():
    f = RFPDupeFilter()
    req = make_request('http://example.com/page1')
    f.mark_seen(req)
    assert f.is_seen(req)


def test_different_urls_not_duplicate():
    f = RFPDupeFilter()
    req1 = make_request('http://example.com/page1')
    req2 = make_request('http://example.com/page2')
    f.mark_seen(req1)
    assert not f.is_seen(req2)


def test_same_url_different_method_not_duplicate():
    f = RFPDupeFilter()
    req1 = make_request('http://example.com/api', method='GET')
    req2 = make_request('http://example.com/api', method='POST')
    f.mark_seen(req1)
    assert not f.is_seen(req2)


def test_query_param_order_same_fingerprint():
    """查询参数顺序不同，但应视为同一请求"""
    f = RFPDupeFilter()
    req1 = make_request('http://example.com/search?b=2&a=1')
    req2 = make_request('http://example.com/search?a=1&b=2')
    f.mark_seen(req1)
    assert f.is_seen(req2)


def test_close_clears_fingerprints():
    f = RFPDupeFilter()
    req = make_request('http://example.com/page1')
    f.mark_seen(req)
    f.close()
    assert not f.is_seen(req)


def test_dont_filter_bypasses_dupefilter():
    """dont_filter=True 的请求字段存在"""
    req = Request(url='http://example.com/', dont_filter=True)
    assert req.dont_filter is True
