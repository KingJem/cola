"""
Tests for the Scheduler class.
"""
import pytest
import asyncio
from unittest.mock import Mock
from src.core.scheduler import Scheduler
from src.http.request import Request


class TestSchedulerBasics:
    """Test basic Scheduler functionality."""
    
    @pytest.mark.asyncio
    async def test_scheduler_init(self):
        """Test Scheduler initialization."""
        crawler = Mock()
        scheduler = Scheduler(crawler)
        
        assert scheduler.crawler == crawler
        assert scheduler.request_queue is not None
        assert len(scheduler) == 0
    
    @pytest.mark.asyncio
    async def test_scheduler_idle_initial(self):
        """Test scheduler is initially idle."""
        crawler = Mock()
        scheduler = Scheduler(crawler)
        
        assert scheduler.idle() == True


class TestSchedulerEnqueueRequest:
    """Test request enqueueing."""
    
    @pytest.mark.asyncio
    async def test_enqueue_single_request(self):
        """Test enqueueing a single request."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        request = Request(url='https://example.com')
        
        await scheduler.enqueue_request(request)
        
        assert len(scheduler) == 1
        assert not scheduler.idle()
        crawler.stat_collector.inc_value.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enqueue_multiple_requests(self):
        """Test enqueueing multiple requests."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        
        requests = [
            Request(url='https://example.com/1'),
            Request(url='https://example.com/2'),
            Request(url='https://example.com/3')
        ]
        
        for req in requests:
            await scheduler.enqueue_request(req)
        
        assert len(scheduler) == 3
    
    @pytest.mark.asyncio
    async def test_enqueue_updates_stats(self):
        """Test that enqueue updates statistics."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        request = Request(url='https://example.com')
        
        await scheduler.enqueue_request(request)
        
        crawler.stat_collector.inc_value.assert_called_with(
            'scheduled.enqueued.requests.count', 1
        )


class TestSchedulerNextRequest:
    """Test getting next request from scheduler."""
    
    @pytest.mark.asyncio
    async def test_next_request_empty_queue(self):
        """Test getting request from empty queue."""
        crawler = Mock()
        scheduler = Scheduler(crawler)
        
        # With timeout in queue, should return None
        request = await scheduler.next_request()
        assert request is None
    
    @pytest.mark.asyncio
    async def test_next_request_single(self):
        """Test getting single request."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        req = Request(url='https://example.com')
        
        await scheduler.enqueue_request(req)
        retrieved = await scheduler.next_request()
        
        assert retrieved is not None
        assert retrieved.url == 'https://example.com'
        assert len(scheduler) == 0
    
    @pytest.mark.asyncio
    async def test_next_request_fifo_same_priority(self):
        """Test FIFO order for same priority requests."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        
        req1 = Request(url='https://example.com/1', priority=0)
        req2 = Request(url='https://example.com/2', priority=0)
        req3 = Request(url='https://example.com/3', priority=0)
        
        await scheduler.enqueue_request(req1)
        await scheduler.enqueue_request(req2)
        await scheduler.enqueue_request(req3)
        
        # All same priority, should come out in order
        r1 = await scheduler.next_request()
        r2 = await scheduler.next_request()
        r3 = await scheduler.next_request()
        
        assert r1.url == 'https://example.com/1'
        assert r2.url == 'https://example.com/2'
        assert r3.url == 'https://example.com/3'


class TestSchedulerPriority:
    """Test priority queue behavior."""
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test that requests are retrieved by priority."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        
        # Lower priority number = higher priority
        low_priority = Request(url='https://example.com/low', priority=10)
        high_priority = Request(url='https://example.com/high', priority=1)
        medium_priority = Request(url='https://example.com/medium', priority=5)
        
        # Enqueue in random order
        await scheduler.enqueue_request(low_priority)
        await scheduler.enqueue_request(high_priority)
        await scheduler.enqueue_request(medium_priority)
        
        # Should come out in priority order
        first = await scheduler.next_request()
        second = await scheduler.next_request()
        third = await scheduler.next_request()
        
        assert first.priority == 1  # High priority first
        assert second.priority == 5  # Medium priority second
        assert third.priority == 10  # Low priority last
    
    @pytest.mark.asyncio
    async def test_mixed_priority_batch(self):
        """Test scheduler with many mixed priority requests."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        
        # Create requests with various priorities
        requests = [
            Request(url=f'https://example.com/{i}', priority=i % 5)
            for i in range(20)
        ]
        
        # Enqueue all
        for req in requests:
            await scheduler.enqueue_request(req)
        
        # Retrieve all and check they're sorted by priority
        retrieved = []
        while not scheduler.idle():
            req = await scheduler.next_request()
            if req:
                retrieved.append(req)
        
        # Check that priorities are in ascending order
        priorities = [req.priority for req in retrieved]
        assert priorities == sorted(priorities)


class TestSchedulerLength:
    """Test scheduler length tracking."""
    
    @pytest.mark.asyncio
    async def test_len_empty(self):
        """Test length of empty scheduler."""
        crawler = Mock()
        scheduler = Scheduler(crawler)
        
        assert len(scheduler) == 0
    
    @pytest.mark.asyncio
    async def test_len_after_enqueue(self):
        """Test length after enqueueing."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        
        await scheduler.enqueue_request(Request(url='https://example.com/1'))
        assert len(scheduler) == 1
        
        await scheduler.enqueue_request(Request(url='https://example.com/2'))
        assert len(scheduler) == 2
    
    @pytest.mark.asyncio
    async def test_len_after_dequeue(self):
        """Test length after dequeueing."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        
        await scheduler.enqueue_request(Request(url='https://example.com/1'))
        await scheduler.enqueue_request(Request(url='https://example.com/2'))
        
        assert len(scheduler) == 2
        
        await scheduler.next_request()
        assert len(scheduler) == 1
        
        await scheduler.next_request()
        assert len(scheduler) == 0


class TestSchedulerIdle:
    """Test scheduler idle state."""
    
    @pytest.mark.asyncio
    async def test_idle_when_empty(self):
        """Test idle returns True when queue is empty."""
        crawler = Mock()
        scheduler = Scheduler(crawler)
        
        assert scheduler.idle() == True
    
    @pytest.mark.asyncio
    async def test_not_idle_with_requests(self):
        """Test idle returns False when queue has requests."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        
        await scheduler.enqueue_request(Request(url='https://example.com'))
        assert scheduler.idle() == False
    
    @pytest.mark.asyncio
    async def test_idle_after_processing_all(self):
        """Test idle returns True after processing all requests."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        
        await scheduler.enqueue_request(Request(url='https://example.com/1'))
        await scheduler.enqueue_request(Request(url='https://example.com/2'))
        
        assert not scheduler.idle()
        
        await scheduler.next_request()
        await scheduler.next_request()
        
        assert scheduler.idle() == True


class TestSchedulerIntegration:
    """Test scheduler integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_concurrent_enqueue(self):
        """Test concurrent request enqueueing."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        
        # Create multiple requests
        requests = [
            Request(url=f'https://example.com/{i}', priority=i)
            for i in range(10)
        ]
        
        # Enqueue concurrently
        await asyncio.gather(*[
            scheduler.enqueue_request(req) for req in requests
        ])
        
        assert len(scheduler) == 10
    
    @pytest.mark.asyncio
    async def test_producer_consumer_pattern(self):
        """Test producer-consumer pattern with scheduler."""
        crawler = Mock()
        crawler.stat_collector = Mock()
        crawler.stat_collector.inc_value = Mock()
        
        scheduler = Scheduler(crawler)
        processed = []
        
        async def producer():
            for i in range(5):
                req = Request(url=f'https://example.com/{i}')
                await scheduler.enqueue_request(req)
                await asyncio.sleep(0.01)
        
        async def consumer():
            for _ in range(5):
                while scheduler.idle():
                    await asyncio.sleep(0.01)
                req = await scheduler.next_request()
                if req:
                    processed.append(req)
        
        await asyncio.gather(producer(), consumer())
        
        assert len(processed) == 5
