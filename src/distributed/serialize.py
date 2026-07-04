"""Request 与 JSON 的互转,供 Redis 队列跨进程传输。

callback 序列化为 spider 方法名字符串;meta 必须 JSON 可序列化。
"""
import json

from src.http.request import Request


def request_to_dict(request: Request, spider=None) -> dict:
    callback = request.callback
    if callable(callback):
        name = getattr(callback, '__name__', None)
        if spider is not None and name and getattr(spider, name, None) is None:
            raise ValueError(
                f"callback {callback!r} 不是 spider 方法,无法序列化到 Redis 队列"
            )
        callback = name
    return {
        'url': request.url,
        'method': request.method,
        'headers': request.headers,
        'cookies': request.cookies,
        'proxy': request.proxy,
        'body': request.body,
        'priority': request.priority,
        'dont_filter': request.dont_filter,
        'meta': request.meta,
        'callback': callback,
    }


def request_from_dict(data: dict, spider=None) -> Request:
    callback = data.get('callback')
    if isinstance(callback, str):
        if spider is None:
            raise ValueError(f"反序列化 callback {callback!r} 需要 spider 实例")
        resolved = getattr(spider, callback, None)
        if resolved is None:
            raise ValueError(f"spider {spider} 上不存在回调方法 {callback!r}")
        callback = resolved
    request = Request(
        url=data['url'],
        method=data.get('method', 'GET'),
        headers=data.get('headers'),
        cookies=data.get('cookies'),
        proxy=data.get('proxy'),
        body=data.get('body'),
        priority=data.get('priority', 0),
        dont_filter=data.get('dont_filter', False),
        callback=callback,
    )
    request.meta.update(data.get('meta') or {})
    return request


def request_to_json(request: Request, spider=None) -> str:
    return json.dumps(request_to_dict(request, spider), ensure_ascii=False,
                      sort_keys=True)


def request_from_json(raw, spider=None) -> Request:
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    return request_from_dict(json.loads(raw), spider)
