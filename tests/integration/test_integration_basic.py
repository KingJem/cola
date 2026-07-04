"""
Basic integration tests for Cola framework.

These tests verify that components work together correctly.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from src.http.request import Request
from src.http.response import Response
from src.spiders import Spider
from src.settings.settings_manager import SettingsManager
from src.stats_collector import StatsCollector
from src.core.scheduler import Scheduler


class SimpleSpider(Spider):
    """A simple test spider."""
    name = 'simple_spider'
    start_urls = ['https://example.com']
    
    def parse(self, response):
        """Parse method that yields items."""
        yield {'title': 'Test', 'url': response.url}


@pytest.mark.integration
class TestBasicCrawlFlow:
    """Test basic crawl flow integration."""
    
    @pytest.mark.asyncio
    async def test_request_response_flow(self):
        """Test request to response flow."""
        # Create request
        req = Request(url='https://example.com', priority=0)
        assert req.url == 'https://example.com'
        
        # Simulate response
        resp = Response(
            url='https://example.com',
            status=200,
            headers={'Content-Type': 'text/html'},
            body=b'<html><body>Test</body></html>',
            request=req
        )
        
        # Verify response has request
        assert resp.request == req
        assert resp.meta == req.meta


@pytest.mark.integration
class TestSchedulerIntegration:
    """Test scheduler integration with other components."""
    
    @pytest.mark.asyncio
    async def test_scheduler_with_stats(self):
        """Test scheduler updates statistics correctly."""
        # Create mock crawler with real stats collector
        settings = SettingsManager()
        stats = StatsCollector(Mock(settings=settings))
        
        crawler = Mock()
        crawler.settings = settings
        crawler.stat_collector = stats
        
        # Create scheduler
        scheduler = Scheduler(crawler)
        
        # Enqueue some requests
        for i in range(5):
            req = Request(url=f'https://example.com/{i}', priority=i)
            await scheduler.enqueue_request(req)
        
        # Check stats were updated
        count = stats.get_value('scheduled.enqueued.requests.count')
        assert count == 5
        
        # Process requests
        processed = 0
        while not scheduler.idle():
            req = await scheduler.next_request()
            if req:
                processed += 1
        
        assert processed == 5


@pytest.mark.integration
class TestSpiderParsing:
    """Test spider parsing integration."""
    
    def test_spider_creates_requests(self):
        """Test spider creates requests from start_urls."""
        spider = SimpleSpider()
        requests = list(spider.start_requests())
        
        assert len(requests) == 1
        assert isinstance(requests[0], Request)
        assert requests[0].url == 'https://example.com'
    
    def test_spider_parse_yields_items(self):
        """Test spider parse yields items."""
        spider = SimpleSpider()
        
        # Create mock response
        response = Mock()
        response.url = 'https://example.com'
        
        # Parse response
        items = list(spider.parse(response))
        
        assert len(items) == 1
        assert items[0]['title'] == 'Test'
        assert items[0]['url'] == 'https://example.com'


@pytest.mark.integration
class TestSettingsStatsIntegration:
    """Test settings and stats integration."""
    
    def test_stats_uses_settings(self):
        """Test that stats collector uses settings."""
        settings = SettingsManager({
            'PROJECT_NAME': 'TestProject',
            'LOG_LEVEL': 'DEBUG'
        })
        
        crawler = Mock()
        crawler.settings = settings
        
        stats = StatsCollector(crawler)
        
        # Stats should have reference to crawler with settings
        assert stats.crawler.settings == settings
        assert stats.crawler.settings['PROJECT_NAME'] == 'TestProject'


@pytest.mark.integration
class TestRequestResponseChain:
    """Test request-response chaining."""
    
    def test_response_follow_creates_new_request(self):
        """Test that response.follow creates new request."""
        original_req = Request(url='https://example.com')
        original_req.meta['depth'] = 0
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b'',
            request=original_req
        )
        
        # Follow to new URL
        new_req = resp.follow('https://example.com/page2')
        
        assert isinstance(new_req, Request)
        assert new_req.url == 'https://example.com/page2'
    
    def test_meta_inheritance(self):
        """Test meta data inheritance through requests."""
        req1 = Request(url='https://example.com')
        req1.meta['depth'] = 0
        req1.meta['category'] = 'main'
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b'<a href="/page2">Link</a>',
            request=req1
        )
        
        # Meta should be accessible from response
        assert resp.meta['depth'] == 0
        assert resp.meta['category'] == 'main'


@pytest.mark.integration
class TestPriorityScheduling:
    """Test priority-based scheduling."""
    
    @pytest.mark.asyncio
    async def test_high_priority_processed_first(self):
        """Test that high priority requests are processed first."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        
        # 文档语义:priority 越大越优先
        low_priority = Request(url='https://example.com/low', priority=1)
        high_priority = Request(url='https://example.com/high', priority=10)
        medium_priority = Request(url='https://example.com/medium', priority=5)
        
        # Enqueue in non-priority order
        await scheduler.enqueue_request(medium_priority)
        await scheduler.enqueue_request(low_priority)
        await scheduler.enqueue_request(high_priority)
        
        # Get requests - should come out in priority order
        first = await scheduler.next_request()
        second = await scheduler.next_request()
        third = await scheduler.next_request()
        
        assert 'high' in first.url
        assert 'medium' in second.url
        assert 'low' in third.url


@pytest.mark.integration
@pytest.mark.slow
class TestFullCrawlSimulation:
    """Test simulating a full crawl cycle."""
    
    @pytest.mark.asyncio
    async def test_simple_crawl_simulation(self):
        """Simulate a simple crawl with all components."""
        # Setup
        settings = SettingsManager({
            'PROJECT_NAME': 'TestCrawl',
            'CONCURRENT_REQUESTS': 1
        })
        
        crawler = Mock()
        crawler.settings = settings
        
        stats = StatsCollector(crawler)
        crawler.stat_collector = stats
        
        scheduler = Scheduler(crawler)
        
        # Start crawl
        spider = SimpleSpider()
        start_requests = list(spider.start_requests())
        
        # Enqueue start requests
        for req in start_requests:
            await scheduler.enqueue_request(req)
        
        stats['start_time'] = '2025-11-23 16:00:00'
        
        # Process requests (simulated)
        processed_count = 0
        while not scheduler.idle():
            req = await scheduler.next_request()
            if req:
                # Simulate download and parse
                stats.inc_value('request_count')
                
                # Mock response
                mock_response = Mock()
                mock_response.url = req.url
                
                # Parse
                items = list(spider.parse(mock_response))
                for item in items:
                    stats.inc_value('item_count')
                
                processed_count += 1
        
        stats['end_time'] = '2025-11-23 16:00:05'
        
        # Verify stats
        assert stats.get_value('scheduled.enqueued.requests.count') == 1
        assert stats.get_value('request_count') == 1
        assert stats.get_value('item_count') == 1
        assert processed_count == 1
