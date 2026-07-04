from asyncio import sleep
from random import uniform

from src.exceptions import NotConfigured
from src.utils.log import get_logger


class DownloadDelay:

    def __init__(self, settings, log_level):
        # 每次请求动态读取 settings,支持热配置更新 DOWNLOAD_DELAY / RANDOMNESS
        self.settings = settings
        if not settings.getfloat("DOWNLOAD_DELAY"):
            raise NotConfigured()

        self.logger = get_logger(self.__class__.__name__, log_level)

    @classmethod
    def create_instance(cls, crawler):
        o = cls(
            settings=crawler.settings,
            log_level=crawler.settings.get("LOG_LEVEL")
        )
        return o

    async def process_request(self, _request, _spider):
        delay = self.settings.getfloat("DOWNLOAD_DELAY")
        if not delay:
            return
        if self.settings.getbool("RANDOMNESS"):
            floor, upper = self.settings.getlist("RANDOM_RANGE")
            await sleep(uniform(delay * float(floor), delay * float(upper)))
        else:
            await sleep(delay)
