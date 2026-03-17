from src.http.request import Request


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

    def __str__(self):
        return f"<{self.__class__.__name__}>"

    @property
    def name(self):
        return self.__class__.__name__
