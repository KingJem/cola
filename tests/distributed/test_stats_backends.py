"""可插拔导出后端:格式化 + build_backends 选择 + push 后端(aiohttp mock)。"""
import json

import pytest
from aiohttp import web

from src.extension import stats_backends as sb
from src.settings.settings_manager import SettingsManager

SNAP = {
    'node': 'n1', 'pages_per_sec': 1.4, 'items_per_sec': 2.0,
    'success_rate': 0.99, 'responses': 10, 'items': 20, 'retries': 3,
    'pending_requests': 5, 'final': True,   # bool 不应被当数值导出
    'status_codes': {'200': 8, '404': 2},
}
LABELS = {'node': 'n1', 'project': 'proj', 'spider': 'S'}


def test_to_prometheus_format():
    text = sb.to_prometheus(SNAP, 'cola_', LABELS)
    assert 'cola_pages_per_second' not in text  # 字段名不改写
    assert 'cola_pages_per_sec{node="n1",project="proj",spider="S"} 1.4' in text
    assert 'cola_responses{node="n1",project="proj",spider="S"} 10' in text
    # status_codes 展开为带 code 标签的 total
    assert 'cola_status_code_total{node="n1",project="proj",spider="S",code="200"} 8' in text
    # bool 字段不导出
    assert 'final' not in text


def test_to_influx_line_format():
    line = sb.to_influx_line(SNAP, 'cola_stats', LABELS)
    assert line.startswith('cola_stats,node=n1,project=proj,spider=S ')
    assert 'pages_per_sec=1.4' in line
    assert 'responses=10.0' in line
    assert 'status_code_200=8i' in line
    assert 'final' not in line


def test_build_backends_explicit():
    settings = SettingsManager({
        'STATS_EXPORT_BACKENDS': 'file,influxdb',
        'STATS_INFLUXDB_URL': 'http://influx:8086/write'})
    backends = sb.build_backends(
        settings, file_path='/tmp/x.jsonl', redis_key='k', redis_ttl=30,
        base_labels=LABELS)
    kinds = [type(b).__name__ for b in backends]
    assert kinds == ['FileBackend', 'InfluxDBBackend']


def test_build_backends_default_file():
    settings = SettingsManager({})
    backends = sb.build_backends(
        settings, file_path='/tmp/x.jsonl', redis_key='k', redis_ttl=30,
        base_labels=LABELS)
    assert [type(b).__name__ for b in backends] == ['FileBackend']


def test_build_backends_pushgateway_needs_url():
    settings = SettingsManager({'STATS_EXPORT_BACKENDS': 'pushgateway'})
    # 缺 URL -> 跳过,不报错
    backends = sb.build_backends(
        settings, file_path=None, redis_key='k', redis_ttl=30,
        base_labels=LABELS)
    assert backends == []


async def test_pushgateway_backend_pushes():
    received = {}

    async def handler(request):
        received['path'] = request.path
        received['body'] = await request.text()
        return web.Response(text='ok')

    app = web.Application()
    app.router.add_route('PUT', '/metrics/job/{tail:.*}', handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        backend = sb.PushgatewayBackend(
            f'http://127.0.0.1:{port}', job='cola', instance='n1',
            prefix='cola_', labels=LABELS)
        await backend.export(SNAP)
        assert received['path'] == '/metrics/job/cola/instance/n1'
        assert 'cola_pages_per_sec' in received['body']
    finally:
        await runner.cleanup()


async def test_influxdb_backend_writes():
    received = {}

    async def handler(request):
        received['body'] = await request.text()
        received['auth'] = request.headers.get('Authorization')
        return web.Response(status=204)

    app = web.Application()
    app.router.add_route('POST', '/write', handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        backend = sb.InfluxDBBackend(
            f'http://127.0.0.1:{port}/write', token='secret',
            measurement='cola_stats', tags=LABELS)
        await backend.export(SNAP)
        assert 'cola_stats,node=n1' in received['body']
        assert received['auth'] == 'Token secret'
    finally:
        await runner.cleanup()


async def test_backend_push_failure_is_swallowed():
    # 不可达地址,export 不应抛异常
    backend = sb.PushgatewayBackend(
        'http://127.0.0.1:1', job='cola', instance='n1',
        prefix='cola_', labels=LABELS)
    await backend.export(SNAP)  # 不抛即通过
