from src.core.request import Request
from src.core.response import Response
from src.spiders import Spider


class BaiduSpider(Spider):

    start_urls = ['http://www.baidu.com/','http://www.baidu.com/']

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
    }


    async def parse(self, response):
        print( 'response')
        for i in range(10):
            url = 'http://www.baidu.com/'
            request = Request(url=url,callback=self.parse_page)
            yield request

    @staticmethod
    async def parse_page(response:Response):
        print( 'page')

