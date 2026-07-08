"""cola CLI 补充命令的单元测试(不联网的部分)。"""
from cola.commands import extra
from cola.http.request import Request


def test_parse_set_json_and_plain():
    d = extra._parse_set(['CONCURRENT_REQUESTS=8', 'NAME=foo',
                          'FLAG=true', 'BAD'])
    assert d['CONCURRENT_REQUESTS'] == 8      # JSON int
    assert d['NAME'] == 'foo'                 # 非 JSON 原样字符串
    assert d['FLAG'] is True                  # JSON bool
    assert 'BAD' not in d                      # 无 = 忽略


def test_parse_set_empty():
    assert extra._parse_set(None) == {}


def test_bucket_splits_items_and_requests():
    items, requests = [], []
    extra._bucket({'a': 1}, items, requests)
    extra._bucket(Request(url='https://e.com'), items, requests)
    extra._bucket({'b': 2}, items, requests)
    assert items == [{'a': 1}, {'b': 2}]
    assert len(requests) == 1 and requests[0].url == 'https://e.com'


def test_load_spider_from_file(tmp_path):
    f = tmp_path / 'myspider.py'
    f.write_text(
        'from cola.spiders import Spider\n'
        'class MySpider(Spider):\n'
        "    start_urls = ['https://e.com']\n",
        encoding='utf-8')
    cls = extra._load_spider_from_file(str(f))
    assert cls is not None and cls.__name__ == 'MySpider'


def test_load_spider_missing_file(tmp_path):
    assert extra._load_spider_from_file(str(tmp_path / 'none.py')) is None


def test_handle_unknown_returns_false():
    class Args:
        command = 'nonexistent'
    assert extra.handle(Args()) is False
