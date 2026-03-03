import requests


class Downloader:

    def __init__(self):
        self._activate = set()

    async def fetch(self, request):
        self._activate.add(request)
        resp = await self.download(request)
        self._activate.discard(request)
        return resp

    async def download(self, request):  # noqa
        response = requests.get(request.url)
        return response


    def __len__(self):
        return len(self._activate)

    def idle(self):
        return len(self) ==0
