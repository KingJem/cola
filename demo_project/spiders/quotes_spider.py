"""
示例爬虫：爬取 Quotes to Scrape 网站
演示 Cola 框架的基本功能
"""
from src.spiders import Spider
from src.http.request import Request
from src.http.response import Response
from src.item.items import Item


class QuoteItem(Item):
    """引用数据项"""
    FIELDS = {
        'text': str,
        'author': str,
        'tags': list,
    }


class QuotesSpider(Spider):
    """引用爬虫"""
    
    # 起始 URL
    start_urls = ['http://quotes.toscrape.com/']
    
    # 自定义配置
    custom_settings = {
        'CONCURRENT_REQUESTS': 3,  # 并发数设置为3
        'TIMEOUT': 30,
        'PROJECT_NAME': 'quotes_demo',
    }
    
    async def parse(self, response: Response):
        """解析列表页"""
        print(f"\n{'='*60}")
        print(f"正在解析: {response.url}")
        print(f"状态码: {response.status_code}")
        print(f"{'='*60}\n")
        
        # 提取所有引用
        quotes = response.xpath('//div[@class="quote"]')
        print(f"找到 {len(quotes)} 条引用\n")
        
        for i, quote in enumerate(quotes, 1):
            # 提取文本
            text_elem = quote.xpath('.//span[@class="text"]/text()')
            text = text_elem[0] if text_elem else ''
            
            # 提取作者
            author_elem = quote.xpath('.//small[@class="author"]/text()')
            author = author_elem[0] if author_elem else ''
            
            # 提取标签
            tags = quote.xpath('.//div[@class="tags"]/a[@class="tag"]/text()')
            
            # 打印提取的数据
            print(f"[{i}] {text[:50]}...")
            print(f"    作者: {author}")
            print(f"    标签: {', '.join(tags)}\n")
            
            # 创建并返回 Item
            item = QuoteItem()
            item['text'] = text
            item['author'] = author
            item['tags'] = tags
            yield item
        
        # 查找下一页链接
        next_page = response.xpath('//li[@class="next"]/a/@href')
        if next_page:
            next_url = response._urljoin(next_page[0])
            print(f"🔗 发现下一页: {next_url}\n")
            yield Request(
                url=next_url,
                callback=self.parse,
                priority=5  # 设置优先级
            )
        else:
            print("✅ 没有更多页面了\n")
