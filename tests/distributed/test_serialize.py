import pytest

from src.distributed.serialize import (
    request_from_dict, request_from_json, request_to_dict, request_to_json)
from src.http.request import Request
from tests.distributed.conftest import make_crawler


@pytest.fixture
def spider():
    return make_crawler().spider


def test_roundtrip_preserves_fields(spider):
    request = Request(
        url='https://example.com/a?b=1',
        method='post',
        headers={'X-Test': '1'},
        body='{"k": "v"}',
        priority=7,
        dont_filter=True,
        callback=spider.parse_detail,
    )
    request.meta['page'] = 3

    data = request_to_dict(request, spider)
    restored = request_from_dict(data, spider)

    assert restored.url == request.url
    assert restored.method == 'POST'
    assert restored.headers == {'X-Test': '1'}
    assert restored.body == '{"k": "v"}'
    assert restored.priority == 7
    assert restored.dont_filter is True
    assert restored.meta == {'page': 3}
    assert restored.callback == spider.parse_detail


def test_json_roundtrip(spider):
    request = Request(url='https://example.com', callback=spider.parse)
    raw = request_to_json(request, spider)
    restored = request_from_json(raw, spider)
    assert restored.url == 'https://example.com'
    assert restored.callback == spider.parse


def test_json_accepts_bytes(spider):
    raw = request_to_json(Request(url='https://example.com'), spider)
    restored = request_from_json(raw.encode('utf-8'), spider)
    assert restored.url == 'https://example.com'


def test_none_callback_roundtrip(spider):
    data = request_to_dict(Request(url='https://example.com'), spider)
    assert data['callback'] is None
    assert request_from_dict(data, spider).callback is None


def test_foreign_callback_rejected(spider):
    def not_a_spider_method(response):
        pass

    request = Request(url='https://example.com', callback=not_a_spider_method)
    with pytest.raises(ValueError, match='不是 spider 方法'):
        request_to_dict(request, spider)


def test_unknown_callback_name_rejected(spider):
    with pytest.raises(ValueError, match='不存在回调方法'):
        request_from_dict(
            {'url': 'https://example.com', 'callback': 'nope'}, spider)
