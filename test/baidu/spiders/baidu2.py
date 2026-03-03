from src.core.request import Request
from src.spiders import Spider


class BaiduSpider2(Spider):

    start_urls = ['http://www.baidu.com/','http://www.baidu.com/']

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
    }


    async def parse(self, response):
        print( 'response')
    #
        for i in range(2):
            url = 'http://www.baidu.com/'
            request = Request(url=url,callback=self.parse_page)
            yield request
    #
    async def parse_page(self, response):
        print( 'page')
        return 'result'

