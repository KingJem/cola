from cola.http.request import Request
from cola.redis_dupefilter import RedisRFPDupeFilter


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.closed = False

    def sadd(self, key, value):
        values = self.values.setdefault(key, set())
        if value in values:
            return 0
        values.add(value)
        return 1

    def scard(self, key):
        return len(self.values.get(key, set()))

    def delete(self, key):
        self.values.pop(key, None)

    def close(self):
        self.closed = True


def test_first_worker_claims_request_and_second_worker_sees_duplicate():
    redis = FakeRedis()
    first = RedisRFPDupeFilter(redis, 'cola:dupefilter')
    second = RedisRFPDupeFilter(redis, 'cola:dupefilter')
    request = Request('https://example.com/products?id=1')

    assert first.is_seen(request) is False
    first.mark_seen(request)  # Engine compatibility call
    assert second.is_seen(request) is True
    assert len(first) == 1


def test_equivalent_query_order_has_one_fingerprint():
    redis = FakeRedis()
    dupefilter = RedisRFPDupeFilter(redis, 'cola:dupefilter')

    assert dupefilter.is_seen(Request('https://example.com/?b=2&a=1')) is False
    assert dupefilter.is_seen(Request('https://example.com/?a=1&b=2')) is True


def test_non_persistent_filter_clears_its_key_on_close():
    redis = FakeRedis()
    dupefilter = RedisRFPDupeFilter(redis, 'cola:dupefilter', persist=False)
    dupefilter.is_seen(Request('https://example.com/'))

    dupefilter.close()

    assert redis.scard('cola:dupefilter') == 0


def test_does_not_close_an_injected_client():
    redis = FakeRedis()
    dupefilter = RedisRFPDupeFilter(redis, 'cola:dupefilter')

    dupefilter.close()

    assert redis.closed is False
