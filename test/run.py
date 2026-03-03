import asyncio
import uvloop


from baidu.spiders.baidu import BaiduSpider
from baidu.spiders.baidu2 import BaiduSpider2


from src.crawler import CrawlerProcess
from src.utils.project import get_settings


async def main():
    settings = get_settings()
    process = CrawlerProcess(settings)
    await process.crawl(BaiduSpider)
    await process.start()



asyncio.run(main() )
