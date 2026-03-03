class Middleware:
    def __init__(self, crawlers):
        self.crawlers = crawlers
        self.settings = crawlers.settings

    async def process_request(self, request):
        return request

    async def process_response(self,request, response):
        return response

    async def process_exception(self, exception):
        return exception

