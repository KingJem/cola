"""
Tests for the Spider base class.
"""
import pytest
from cola.spiders import Spider
from cola.http.request import Request
from unittest.mock import Mock


class TestSpiderBasics:
    """Test basic Spider functionality."""
    
    def test_spider_init(self):
        """Test Spider initialization."""
        spider = Spider()
        assert hasattr(spider, 'start_urls')
        assert spider.start_urls == []
    
    def test_spider_with_start_urls(self):
        """Test Spider with predefined start_urls."""
        class MySpider(Spider):
            start_urls = ['https://example.com', 'https://test.com']
        
        spider = MySpider()
        assert len(spider.start_urls) == 2
        assert 'https://example.com' in spider.start_urls


class TestSpiderCreateInstance:
    """Test Spider create_instance class method."""
    
    def test_create_instance_basic(self):
        """Test creating spider instance."""
        crawler = Mock()
        spider = Spider.create_instance(crawler)
        
        assert isinstance(spider, Spider)
        assert spider.crawler == crawler
    
    def test_create_instance_custom_spider(self):
        """Test creating custom spider instance."""
        class CustomSpider(Spider):
            custom_attr = 'test'
        
        crawler = Mock()
        spider = CustomSpider.create_instance(crawler)
        
        assert isinstance(spider, CustomSpider)
        assert spider.crawler == crawler
        assert spider.custom_attr == 'test'


class TestSpiderStartRequests:
    """Test Spider start_requests method."""
    
    def test_start_requests_from_urls(self):
        """Test generating requests from start_urls."""
        class MySpider(Spider):
            start_urls = [
                'https://example.com/page1',
                'https://example.com/page2',
                'https://example.com/page3'
            ]
        
        spider = MySpider()
        requests = list(spider.start_requests())
        
        assert len(requests) == 3
        assert all(isinstance(req, Request) for req in requests)
        assert requests[0].url == 'https://example.com/page1'
        assert requests[1].url == 'https://example.com/page2'
        assert requests[2].url == 'https://example.com/page3'
    
    def test_start_requests_empty(self):
        """Test start_requests with no start_urls."""
        spider = Spider()
        requests = list(spider.start_requests())
        
        assert requests == []
    
    def test_start_requests_generator(self):
        """Test that start_requests is a generator."""
        class MySpider(Spider):
            start_urls = ['https://example.com']
        
        spider = MySpider()
        result = spider.start_requests()
        
        # Should be a generator
        assert hasattr(result, '__iter__')
        assert hasattr(result, '__next__')


class TestSpiderParse:
    """Test Spider parse method."""
    
    def test_parse_default(self):
        """Test default parse method."""
        spider = Spider()
        response = Mock()
        
        # Default parse does nothing
        result = spider.parse(response)
        assert result is None
    
    def test_parse_custom(self):
        """Test custom parse implementation."""
        class MySpider(Spider):
            def parse(self, response):
                return {'url': response.url, 'status': response.status}
        
        spider = MySpider()
        response = Mock()
        response.url = 'https://example.com'
        response.status = 200
        
        result = spider.parse(response)
        assert result == {'url': 'https://example.com', 'status': 200}


class TestSpiderName:
    """Test Spider name property."""
    
    def test_name_default(self):
        """Test default spider name."""
        spider = Spider()
        assert spider.name == 'Spider'
    
    def test_name_custom_class(self):
        """Test custom spider class name."""
        class ProductSpider(Spider):
            pass
        
        spider = ProductSpider()
        assert spider.name == 'ProductSpider'
    
    def test_name_property(self):
        """Test that name is a property."""
        class MySpider(Spider):
            pass
        
        spider = MySpider()
        # Should not be able to set name
        assert hasattr(MySpider.name, 'fget')


class TestSpiderStr:
    """Test Spider string representation."""
    
    def test_str_default(self):
        """Test __str__ method."""
        spider = Spider()
        result = str(spider)
        assert 'Spider' in result
    
    def test_str_custom(self):
        """Test __str__ with custom spider."""
        class NewsSpider(Spider):
            pass
        
        spider = NewsSpider()
        result = str(spider)
        assert 'NewsSpider' in result


class TestSpiderIntegration:
    """Test Spider integration scenarios."""
    
    def test_spider_with_crawler(self):
        """Test spider with full crawler integration."""
        class TestSpider(Spider):
            start_urls = ['https://example.com']
            
            def parse(self, response):
                yield {'title': 'test'}
        
        crawler = Mock()
        crawler.settings = Mock()
        
        spider = TestSpider.create_instance(crawler)
        
        assert spider.crawler == crawler
        assert len(list(spider.start_requests())) == 1
    
    def test_spider_custom_settings(self):
        """Test spider with custom settings."""
        class TestSpider(Spider):
            custom_settings = {
                'CONCURRENT_REQUESTS': 32,
                'DOWNLOAD_DELAY': 0.5
            }
            start_urls = ['https://example.com']
        
        spider = TestSpider()
        
        assert hasattr(spider, 'custom_settings')
        assert spider.custom_settings['CONCURRENT_REQUESTS'] == 32
    
    def test_spider_multiple_parse_outputs(self):
        """Test spider yielding multiple outputs."""
        class TestSpider(Spider):
            def parse(self, response):
                yield {'item': 1}
                yield {'item': 2}
                yield Request(url='https://example.com/next')
        
        spider = TestSpider()
        response = Mock()
        
        results = list(spider.parse(response))
        assert len(results) == 3
        assert results[0] == {'item': 1}
        assert isinstance(results[2], Request)
    
    def test_spider_meta_passthrough(self):
        """Test that meta data passes through requests."""
        class TestSpider(Spider):
            start_urls = ['https://example.com']
        
        spider = TestSpider()
        requests = list(spider.start_requests())
        req = requests[0]
        
        # Add meta data
        req.meta['depth'] = 0
        req.meta['category'] = 'main'
        
        assert req.meta['depth'] == 0
        assert req.meta['category'] == 'main'
