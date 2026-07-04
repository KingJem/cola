"""
简单的HTTP服务器测试爬虫
用于测试本地网页爬取
"""
from cola.spiders import Spider
from cola.http.request import Request
from cola.http.response import Response


class SimpleSpider(Spider):
    """简单测试爬虫"""
    
    # 使用 httpbin.org 作为测试站点（可靠的测试API）
    start_urls = [
        'http://httpbin.org/html',
        'http://httpbin.org/links/5',
    ]
    
    custom_settings = {
        'CONCURRENT_REQUESTS': 2,
        'PROJECT_NAME': 'simple_demo',
    }
    
    async def parse(self, response: Response):
        """解析响应"""
        print(f"\n{'='*60}")
        print(f"✅ 成功访问: {response.url}")
        print(f"📊 状态码: {response.status_code}")
        print(f"📏 内容长度: {len(response.body)} 字节")
        print(f"{'='*60}")
        
        # 提取所有链接
        links = response.xpath('//a/@href')
        print(f"\n🔗 发现 {len(links)} 个链接:")
        for link in links[:5]:  # 只显示前5个
            print(f"   - {link}")
        
        # 提取标题
        title = response.xpath('//h1/text()')
        if title:
            print(f"\n📝 标题: {title[0]}")
        
        # 提取所有段落
        paragraphs = response.xpath('//p/text()')
        if paragraphs:
            print(f"\n📄 段落数: {len(paragraphs)}")
            if paragraphs:
                print(f"   第一段: {paragraphs[0][:100]}...")
        
        print("\n")
        
        # 返回数据
        yield {
            'url': response.url,
            'status': response.status_code,
            'title': title[0] if title else None,
            'links_count': len(links),
        }
