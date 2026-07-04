"""Redis-backed request deduplication for distributed Cola workers."""

from typing import Any, Optional

from cola.dupefilter import RFPDupeFilter


class RedisRFPDupeFilter(RFPDupeFilter):
    """A Redis implementation of :class:`RFPDupeFilter`.

    ``is_seen`` deliberately performs the Redis ``SADD`` itself.  ``SADD`` is
    atomic, so two workers receiving the same request cannot both consider it
    new.  The engine still calls ``mark_seen`` after a request is accepted;
    that method is intentionally a no-op for this implementation.
    """

    def __init__(
        self,
        redis_client: Any,
        key: str,
        debug: bool = False,
        persist: bool = True,
        owns_client: bool = False,
    ):
        super().__init__(debug=debug)
        self.redis = redis_client
        self.key = key
        self.persist = persist
        self._owns_client = owns_client

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        redis_client = settings.get('REDIS_DUPEFILTER_CLIENT')
        owns_client = redis_client is None

        if redis_client is None:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError(
                    'RedisRFPDupeFilter requires the redis package. '
                    'Install it with: pip install cola[redis]'
                ) from exc

            redis_client = redis.Redis.from_url(
                settings.get('REDIS_URL', 'redis://localhost:6379/0'),
                decode_responses=False,
            )

        project_name = settings.get('PROJECT_NAME', 'cola')
        key = settings.get('REDIS_DUPEFILTER_KEY') or f'{project_name}:dupefilter'
        return cls(
            redis_client=redis_client,
            key=key,
            debug=settings.getbool('DUPEFILTER_DEBUG', False),
            # A worker must never erase the shared set when it exits by default.
            persist=settings.getbool('REDIS_DUPEFILTER_PERSIST', True),
            owns_client=owns_client,
        )

    def is_seen(self, request) -> bool:
        fingerprint = self.request_fingerprint(request)
        return not bool(self.redis.sadd(self.key, fingerprint))

    def mark_seen(self, request) -> None:
        """Kept for Engine compatibility; ``is_seen`` already added the key."""

    def close(self) -> None:
        if not self.persist:
            self.redis.delete(self.key)
        if self._owns_client and hasattr(self.redis, 'close'):
            self.redis.close()

    def __len__(self) -> int:
        return int(self.redis.scard(self.key))
