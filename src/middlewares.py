from pprint import pformat
from collections import defaultdict 

import loguru

from src.exceptions import MiddlewareException


class MiddlewareManager:
    def __init__(self, crawler):
        self.crawler = crawler
        self.logger = loguru.logger
        self.middlewares = []
        self.method = defaultdict(list)
        self.load_middlewares()
        self.add_method()

    @classmethod
    def create_instance(cls, crawler, *args, **kwargs):
        return cls(crawler)

    def load_middlewares(self):
        middlewares = self.crawler.settings.getlist('MIDDLEWARES')
        enable_middlewares = [i for i in middlewares if self.validate_middleware(i)]

        if enable_middlewares:
            self.logger.info(f"Enabled middlewares: \n" + pformat(enable_middlewares))

    def validate_middleware(self, middleware):
        middleware_cls = self.crawler.utils.load_class(middleware)
        if not hasattr(middleware_cls, 'create_instance'):
            raise MiddlewareException(f"Middleware {middleware_cls} does not have create_instance method")

        instance = middleware_cls.create_instance()
        self.middlewares.append(instance)
        return True

    def add_method(self):
        for middleware in self.middlewares:
            for method in ['process_request','process_response','process_exception']:
                self._add_method(middleware,method)

    def _add_method(self,middleware,name:str):
        if hasattr(middleware, name):
            self.method[name].append(getattr(middleware, name))
        else:
            raise MiddlewareException(f"Middleware {middleware} does not have {name} method")

    def validate_method(self,method):
        if not hasattr(self, method):
            raise MiddlewareException(f"MiddlewareManager does not have {method} method")