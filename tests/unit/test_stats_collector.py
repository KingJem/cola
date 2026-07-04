"""
Tests for the StatsCollector class.
"""
import pytest
from unittest.mock import Mock
from cola.stats_collector import StatsCollector


class TestStatsCollectorBasics:
    """Test basic StatsCollector functionality."""
    
    def test_init(self, mock_crawler):
        """Test StatsCollector initialization."""
        collector = StatsCollector(mock_crawler)
        assert collector.crawler == mock_crawler
        assert collector.stats == {}
        assert isinstance(collector.stats, dict)
    
    def test_init_empty_stats(self, mock_crawler):
        """Test that stats dict is initially empty."""
        collector = StatsCollector(mock_crawler)
        assert len(collector.stats) == 0


class TestStatsCollectorIncValue:
    """Test inc_value method."""
    
    def test_inc_value_new_key(self, mock_crawler):
        """Test incrementing new key."""
        collector = StatsCollector(mock_crawler)
        collector.inc_value('request_count')
        
        assert collector.stats['request_count'] == 1
    
    def test_inc_value_existing_key(self, mock_crawler):
        """Test incrementing existing key."""
        collector = StatsCollector(mock_crawler)
        collector.inc_value('request_count')
        collector.inc_value('request_count')
        collector.inc_value('request_count')
        
        assert collector.stats['request_count'] == 3
    
    def test_inc_value_custom_count(self, mock_crawler):
        """Test incrementing by custom count."""
        collector = StatsCollector(mock_crawler)
        collector.inc_value('bytes_downloaded', count=1024)
        collector.inc_value('bytes_downloaded', count=2048)
        
        assert collector.stats['bytes_downloaded'] == 3072
    
    def test_inc_value_custom_start(self, mock_crawler):
        """Test incrementing with custom start value."""
        collector = StatsCollector(mock_crawler)
        collector.inc_value('items', count=5, start=100)
        
        assert collector.stats['items'] == 105
    
    def test_inc_value_multiple_keys(self, mock_crawler):
        """Test incrementing multiple different keys."""
        collector = StatsCollector(mock_crawler)
        collector.inc_value('requests')
        collector.inc_value('responses')
        collector.inc_value('items')
        
        assert collector.stats['requests'] == 1
        assert collector.stats['responses'] == 1
        assert collector.stats['items'] == 1


class TestStatsCollectorGetValue:
    """Test get_value method."""
    
    def test_get_value_existing(self, mock_crawler):
        """Test getting existing value."""
        collector = StatsCollector(mock_crawler)
        collector.stats['count'] = 42
        
        assert collector.get_value('count') == 42
    
    def test_get_value_nonexistent(self, mock_crawler):
        """Test getting non-existent value."""
        collector = StatsCollector(mock_crawler)
        assert collector.get_value('nonexistent') is None
    
    def test_get_value_with_default(self, mock_crawler):
        """Test getting value with default."""
        collector = StatsCollector(mock_crawler)
        assert collector.get_value('nonexistent', 'default') == 'default'


class TestStatsCollectorDictInterface:
    """Test dict-like interface."""
    
    def test_setitem(self, mock_crawler):
        """Test __setitem__."""
        collector = StatsCollector(mock_crawler)
        collector['key'] = 'value'
        
        assert collector.stats['key'] == 'value'
    
    def test_getitem(self, mock_crawler):
        """Test __getitem__."""
        collector = StatsCollector(mock_crawler)
        collector.stats['key'] = 'value'
        
        assert collector['key'] == 'value'
    
    def test_getitem_nonexistent(self, mock_crawler):
        """Test __getitem__ for non-existent key."""
        collector = StatsCollector(mock_crawler)
        # Returns None instead of raising KeyError
        assert collector['nonexistent'] is None
    
    def test_delitem(self, mock_crawler):
        """Test __delitem__."""
        collector = StatsCollector(mock_crawler)
        collector.stats['key'] = 'value'
        
        del collector['key']
        assert 'key' not in collector.stats


class TestStatsCollectorGetSetStat:
    """Test get_stat and set_stat methods."""
    
    def test_get_stat(self, mock_crawler):
        """Test get_stat returns stats dict."""
        collector = StatsCollector(mock_crawler)
        collector.stats = {'a': 1, 'b': 2}
        
        result = collector.get_stat()
        assert result == {'a': 1, 'b': 2}
        assert result is collector.stats
    
    def test_set_stat(self, mock_crawler):
        """Test set_stat replaces stats dict."""
        collector = StatsCollector(mock_crawler)
        new_stats = {'x': 10, 'y': 20}
        
        collector.set_stat(new_stats)
        assert collector.stats == new_stats
    
    def test_clear_stat(self, mock_crawler):
        """Test clear_stat empties stats."""
        collector = StatsCollector(mock_crawler)
        collector.stats = {'a': 1, 'b': 2}
        
        collector.clear_stat()
        assert collector.stats == {}
        assert len(collector.stats) == 0


class TestStatsCollectorMaxMin:
    """Test max_value and min_value methods."""
    
    def test_max_value_new_key(self, mock_crawler):
        """Test max_value with new key."""
        collector = StatsCollector(mock_crawler)
        collector.max_value('max_depth', 5)
        
        assert collector.stats['max_depth'] == 5
    
    def test_max_value_larger(self, mock_crawler):
        """Test max_value updates when new value is larger."""
        collector = StatsCollector(mock_crawler)
        collector.max_value('max_depth', 5)
        collector.max_value('max_depth', 10)
        
        assert collector.stats['max_depth'] == 10
    
    def test_max_value_smaller(self, mock_crawler):
        """Test max_value doesn't update when new value is smaller."""
        collector = StatsCollector(mock_crawler)
        collector.max_value('max_depth', 10)
        collector.max_value('max_depth', 5)
        
        assert collector.stats['max_depth'] == 10
    
    def test_min_value_new_key(self, mock_crawler):
        """Test min_value with new key."""
        collector = StatsCollector(mock_crawler)
        collector.min_value('min_response_time', 0.5)
        
        assert collector.stats['min_response_time'] == 0.5
    
    def test_min_value_smaller(self, mock_crawler):
        """Test min_value updates when new value is smaller."""
        collector = StatsCollector(mock_crawler)
        collector.min_value('min_response_time', 0.5)
        collector.min_value('min_response_time', 0.2)
        
        assert collector.stats['min_response_time'] == 0.2
    
    def test_min_value_larger(self, mock_crawler):
        """Test min_value doesn't update when new value is larger."""
        collector = StatsCollector(mock_crawler)
        collector.min_value('min_response_time', 0.2)
        collector.min_value('min_response_time', 0.5)
        
        assert collector.stats['min_response_time'] == 0.2


class TestStatsCollectorSpiderLifecycle:
    """Test spider lifecycle methods."""
    
    def test_open_spider(self, mock_crawler):
        """Test open_spider method."""
        collector = StatsCollector(mock_crawler)
        spider = Mock()
        spider.name = 'TestSpider'
        
        # Currently does nothing, should not raise
        collector.open_spider(spider)
    
    def test_close_spider_sets_reason(self, mock_crawler):
        """Test close_spider sets reason."""
        collector = StatsCollector(mock_crawler)
        spider = Mock()
        spider.name = 'TestSpider'
        
        collector.close_spider(spider, 'finished')
        
        assert collector.stats['reason'] == 'finished'
    
    def test_close_spider_different_reasons(self, mock_crawler):
        """Test close_spider with different reasons."""
        reasons = ['finished', 'cancelled', 'shutdown', 'error']
        
        for reason in reasons:
            collector = StatsCollector(mock_crawler)
            spider = Mock()
            spider.name = 'TestSpider'
            
            collector.close_spider(spider, reason)
            assert collector.stats['reason'] == reason


class TestStatsCollectorIntegration:
    """Test integration scenarios."""
    
    def test_typical_crawl_stats(self, mock_crawler):
        """Test typical crawl statistics tracking."""
        collector = StatsCollector(mock_crawler)
        spider = Mock()
        spider.name = 'ProductSpider'
        
        # Simulate crawl statistics
        collector.open_spider(spider)
        
        # Track requests
        for _ in range(100):
            collector.inc_value('request_count')
        
        # Track responses
        for _ in range(95):
            collector.inc_value('response_count')
        
        # Track items
        for _ in range(50):
            collector.inc_value('item_scraped_count')
        
        # Track response times
        collector.min_value('min_response_time', 0.1)
        collector.max_value('max_response_time', 2.5)
        
        # Track errors
        collector.inc_value('error_count', count=5)
        
        collector.close_spider(spider, 'finished')
        
        # Verify stats
        assert collector.stats['request_count'] == 100
        assert collector.stats['response_count'] == 95
        assert collector.stats['item_scraped_count'] == 50
        assert collector.stats['min_response_time'] == 0.1
        assert collector.stats['max_response_time'] == 2.5
        assert collector.stats['error_count'] == 5
        assert collector.stats['reason'] == 'finished'
    
    def test_scheduler_enqueue_tracking(self, mock_crawler):
        """Test tracking scheduler enqueue operations."""
        collector = StatsCollector(mock_crawler)
        
        # Simulate scheduler enqueuing requests
        for _ in range(50):
            collector.inc_value('scheduled.enqueued.requests.count', 1)
        
        assert collector.stats['scheduled.enqueued.requests.count'] == 50
    
    def test_bandwidth_tracking(self, mock_crawler):
        """Test tracking bandwidth usage."""
        collector = StatsCollector(mock_crawler)
        
        # Simulate downloading pages
        collector.inc_value('downloader/response_bytes', count=1024)
        collector.inc_value('downloader/response_bytes', count=2048)
        collector.inc_value('downloader/response_bytes', count=4096)
        
        total_bytes = collector.get_value('downloader/response_bytes')
        assert total_bytes == 7168
    
    def test_multiple_stat_types(self, mock_crawler):
        """Test using multiple stat tracking methods together."""
        collector = StatsCollector(mock_crawler)
        
        # Use different tracking methods
        collector['start_time'] = '2025-11-23 16:00:00'
        collector.inc_value('request_count', count=10)
        collector.max_value('max_depth', 5)
        collector.min_value('min_latency', 0.05)
        collector['end_time'] = '2025-11-23 16:05:00'
        
        stats = collector.get_stat()
        assert stats['start_time'] == '2025-11-23 16:00:00'
        assert stats['end_time'] == '2025-11-23 16:05:00'
        assert stats['request_count'] == 10
        assert stats['max_depth'] == 5
        assert stats['min_latency'] == 0.05
