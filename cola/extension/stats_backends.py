"""StatsExporter 的可插拔导出后端。

每个后端接收周期快照 dict,推送到对应存储:
    file        逐行 append JSON(默认,本地/colad 读取)
    redis       SET {project}:stats:{node} 最新 JSON(master 聚合)
    pushgateway Prometheus Pushgateway(短命任务;POST 文本)
    influxdb    InfluxDB v2 line protocol(POST 写点)

pushgateway/influxdb 用 aiohttp(cola 已有依赖)推送,失败只告警不影响爬取。
配置见 settings/default.py 的 STATS_* 项。
"""
import json
from pathlib import Path

from loguru import logger

# 数值型指标字段(gauge 语义)与计数字段;两类都按 gauge/counter 值直接导出
_NUMERIC_FIELDS = [
    'pages_per_sec', 'items_per_sec', 'avg_response_time', 'max_response_time',
    'success_rate', 'pending_requests', 'in_flight', 'concurrency_limit',
    'elapsed', 'requests_scheduled', 'responses', 'items', 'items_discarded',
    'retries', 'exceptions', 'requests_ignored',
]


def _esc_label(value) -> str:
    return str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')


def to_prometheus(snapshot: dict, prefix: str, labels: dict) -> str:
    """快照 -> Prometheus 文本(gauge)。labels 为公共标签。"""
    label_str = ''
    if labels:
        label_str = '{' + ','.join(
            f'{k}="{_esc_label(v)}"' for k, v in labels.items()) + '}'
    lines = []
    for key in _NUMERIC_FIELDS:
        v = snapshot.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            lines.append(f'{prefix}{key}{label_str} {v}')
    for code, count in (snapshot.get('status_codes') or {}).items():
        merged = dict(labels or {})
        merged['code'] = str(code)
        ls = '{' + ','.join(
            f'{k}="{_esc_label(v)}"' for k, v in merged.items()) + '}'
        lines.append(f'{prefix}status_code_total{ls} {count}')
    return '\n'.join(lines) + '\n'


def _esc_tag(value) -> str:
    return str(value).replace(' ', '\\ ').replace(',', '\\,').replace('=', '\\=')


def to_influx_line(snapshot: dict, measurement: str, tags: dict) -> str:
    """快照 -> InfluxDB line protocol(不带时间戳,由服务端补)。"""
    head = measurement
    if tags:
        head += ',' + ','.join(f'{k}={_esc_tag(v)}' for k, v in tags.items())
    fields = []
    for key in _NUMERIC_FIELDS:
        v = snapshot.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            fields.append(f'{key}={float(v)}')
    for code, count in (snapshot.get('status_codes') or {}).items():
        fields.append(f'status_code_{code}={int(count)}i')
    if not fields:
        return ''
    return f'{head} {",".join(fields)}'


class StatsBackend:
    async def open(self):
        pass

    async def export(self, snapshot: dict):
        raise NotImplementedError

    async def close(self):
        pass


class FileBackend(StatsBackend):
    def __init__(self, path: str):
        self.path = path

    async def open(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.path).write_text('', encoding='utf-8')  # 覆盖旧文件

    async def export(self, snapshot: dict):
        try:
            with open(self.path, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(snapshot, ensure_ascii=False) + '\n')
        except OSError as exc:
            logger.warning(f'StatsBackend[file] 写入失败: {exc}')


class RedisBackend(StatsBackend):
    def __init__(self, settings, key: str, ttl: int):
        self.settings = settings
        self.key = key
        self.ttl = ttl
        self.redis = None

    async def open(self):
        from cola.distributed.connection import get_redis
        self.redis = get_redis(self.settings, decode_responses=True)

    async def export(self, snapshot: dict):
        try:
            await self.redis.set(self.key,
                                 json.dumps(snapshot, ensure_ascii=False),
                                 ex=self.ttl)
        except Exception as exc:
            logger.warning(f'StatsBackend[redis] 写入失败: {exc}')

    async def close(self):
        if self.redis:
            try:
                await self.redis.aclose()
            except Exception:
                pass


class PushgatewayBackend(StatsBackend):
    def __init__(self, url: str, job: str, instance: str, prefix: str,
                 labels: dict):
        self.base = url.rstrip('/')
        self.job = job
        self.instance = instance
        self.prefix = prefix
        self.labels = labels

    def _endpoint(self) -> str:
        url = f'{self.base}/metrics/job/{self.job}'
        if self.instance:
            url += f'/instance/{self.instance}'
        return url

    async def export(self, snapshot: dict):
        import aiohttp
        body = to_prometheus(snapshot, self.prefix, self.labels)
        timeout = aiohttp.ClientTimeout(total=5)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.put(self._endpoint(), data=body) as resp:
                    if resp.status >= 400:
                        logger.warning(
                            f'StatsBackend[pushgateway] {resp.status}: '
                            f'{(await resp.text())[:200]}')
        except Exception as exc:
            logger.warning(f'StatsBackend[pushgateway] 推送失败: {exc}')


class InfluxDBBackend(StatsBackend):
    def __init__(self, url: str, token: str, measurement: str, tags: dict):
        self.url = url
        self.token = token
        self.measurement = measurement
        self.tags = tags

    async def export(self, snapshot: dict):
        import aiohttp
        line = to_influx_line(snapshot, self.measurement, self.tags)
        if not line:
            return
        headers = {'Content-Type': 'text/plain'}
        if self.token:
            headers['Authorization'] = f'Token {self.token}'
        timeout = aiohttp.ClientTimeout(total=5)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.url, data=line,
                                        headers=headers) as resp:
                    if resp.status >= 400:
                        logger.warning(
                            f'StatsBackend[influxdb] {resp.status}: '
                            f'{(await resp.text())[:200]}')
        except Exception as exc:
            logger.warning(f'StatsBackend[influxdb] 写入失败: {exc}')


def build_backends(settings, *, file_path, redis_key, redis_ttl,
                   base_labels) -> list:
    """按配置构建后端列表。

    STATS_EXPORT_BACKENDS 显式指定(逗号分隔)时以它为准;
    未指定时按兼容规则:有 file_path 则含 file,分布式/配了 redis 键则含 redis。
    """
    names = list(settings.getlist('STATS_EXPORT_BACKENDS') or [])
    if not names:
        if file_path:
            names.append('file')
        if (settings.get('STATS_EXPORT_REDIS_KEY') is not None
                or settings.get('NODE_ROLE', 'standalone') != 'standalone'):
            names.append('redis')

    prefix = settings.get('STATS_METRIC_PREFIX', 'cola_') or 'cola_'
    backends = []
    for name in names:
        name = name.strip()
        if name == 'file' and file_path:
            backends.append(FileBackend(file_path))
        elif name == 'redis':
            backends.append(RedisBackend(settings, redis_key, redis_ttl))
        elif name == 'pushgateway':
            url = settings.get('STATS_PUSHGATEWAY_URL')
            if not url:
                logger.warning('pushgateway 后端缺少 STATS_PUSHGATEWAY_URL,跳过')
                continue
            backends.append(PushgatewayBackend(
                url,
                job=settings.get('STATS_PUSHGATEWAY_JOB', 'cola') or 'cola',
                instance=base_labels.get('node', ''),
                prefix=prefix, labels=base_labels))
        elif name == 'influxdb':
            url = settings.get('STATS_INFLUXDB_URL')
            if not url:
                logger.warning('influxdb 后端缺少 STATS_INFLUXDB_URL,跳过')
                continue
            backends.append(InfluxDBBackend(
                url,
                token=settings.get('STATS_INFLUXDB_TOKEN', '') or '',
                measurement=settings.get('STATS_INFLUXDB_MEASUREMENT',
                                         'cola_stats') or 'cola_stats',
                tags=base_labels))
        else:
            logger.warning(f'未知 stats 后端: {name!r}')
    return backends
