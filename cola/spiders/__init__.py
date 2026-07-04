from cola.http.request import Request


class Spider:

    @classmethod
    def create_instance(cls, crawler):
        o = cls()
        o.crawler = crawler
        return o

    def __init__(self):
        if not hasattr(self, 'start_urls'):
            self.start_urls = []

    def start_requests(self):
        if self.start_urls:
            for url in self.start_urls:
                yield Request(url=url, dont_filter=True)
        else:
            if hasattr(self, 'start_url') and isinstance(getattr(self, 'start_url'), str):
                yield Request(url=getattr(self, 'start_url'), dont_filter=True)

    def parse(self, response):
        pass

    def make_request_from_seed(self, seed):
        """种子(URL 字符串或 dict)-> Request 的钩子,对所有种子源(redis/
        mysql/pg/doris/rabbitmq)统一生效。

        重写以自定义转换,例如把整个 task 放进 request.meta::

            def make_request_from_seed(self, seed):
                return Request(seed['url'], callback=self.parse,
                               meta={'task': seed})

        返回 None 可跳过该种子。默认按 seed_to_request 规则处理
        (url 必填,已知字段进 Request,其余键并入 meta)。
        """
        from cola.distributed.seed_loader import seed_to_request
        default_callback = None
        if getattr(self, 'crawler', None) is not None:
            default_callback = self.crawler.settings.get('SEED_CALLBACK')
        return seed_to_request(seed, self, default_callback=default_callback)

    def __str__(self):
        return f"<{self.__class__.__name__}>"

    @property
    def name(self):
        return self.__class__.__name__
