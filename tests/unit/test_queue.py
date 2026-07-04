"""
Tests for the SpiderPriorityQueue class.
"""
import pytest
import asyncio
from src.utils.queue import SpiderPriorityQueue
from src.http.request import Request


class TestQueueBasics:
    """Test basic queue functionality."""
    
    @pytest.mark.asyncio
    async def test_queue_init(self):
        """Test queue initialization."""
        queue = SpiderPriorityQueue()
        assert queue.qsize() == 0
        assert queue.empty() == True
    
    @pytest.mark.asyncio
    async def test_queue_init_with_maxsize(self):
        """Test queue initialization with maxsize."""
        queue = SpiderPriorityQueue(maxsize=10)
        assert queue.qsize() == 0


class TestQueuePutGet:
    """Test put and get operations."""
    
    @pytest.mark.asyncio
    async def test_put_get_single_item(self):
        """Test putting and getting single item."""
        queue = SpiderPriorityQueue()
        req = Request(url='https://example.com', priority=5)
        
        await queue.put(req)
        assert queue.qsize() == 1
        
        retrieved = await queue.get()
        assert retrieved.url == 'https://example.com'
        assert queue.qsize() == 0
    
    @pytest.mark.asyncio
    async def test_put_multiple_items(self):
        """Test putting multiple items."""
        queue = SpiderPriorityQueue()
        
        requests = [
            Request(url=f'https://example.com/{i}', priority=i)
            for i in range(5)
        ]
        
        for req in requests:
            await queue.put(req)
        
        assert queue.qsize() == 5
    
    @pytest.mark.asyncio
    async def test_get_empty_queue_timeout(self):
        """Test getting from empty queue with timeout."""
        queue = SpiderPriorityQueue()
        
        # Should return None after timeout (0.1s)
        result = await queue.get()
        assert result is None


class TestQueuePriority:
    """Test priority queue ordering."""
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test that items are retrieved by priority."""
        queue = SpiderPriorityQueue()
        
        # Add requests with different priorities
        high_priority = Request(url='https://example.com/high', priority=10)
        low_priority = Request(url='https://example.com/low', priority=1)
        medium_priority = Request(url='https://example.com/medium', priority=5)

        # Put in random order
        await queue.put(low_priority)
        await queue.put(high_priority)
        await queue.put(medium_priority)

        # 文档语义:priority 越大越优先
        first = await queue.get()
        second = await queue.get()
        third = await queue.get()

        assert first.priority == 10
        assert second.priority == 5
        assert third.priority == 1
    
    @pytest.mark.asyncio
    async def test_priority_with_many_items(self):
        """Test priority ordering with many items."""
        queue = SpiderPriorityQueue()
        
        # Create requests with random priorities
        requests = [
            Request(url=f'https://example.com/{i}', priority=i % 10)
            for i in range(50)
        ]
        
        # Put all requests
        for req in requests:
            await queue.put(req)
        
        # Get all and verify they're in priority order
        retrieved = []
        for _ in range(50):
            item = await queue.get()
            if item:
                retrieved.append(item)
        
        priorities = [req.priority for req in retrieved]
        assert priorities == sorted(priorities, reverse=True)


class TestQueueTimeout:
    """Test queue timeout behavior."""
    
    @pytest.mark.asyncio
    async def test_get_timeout_on_empty(self):
        """Test that get returns None after timeout on empty queue."""
        queue = SpiderPriorityQueue()
        
        start = asyncio.get_event_loop().time()
        result = await queue.get()
        elapsed = asyncio.get_event_loop().time() - start
        
        assert result is None
        # Should timeout around 0.1 seconds
        assert 0.05 < elapsed < 0.2
    
    @pytest.mark.asyncio
    async def test_get_no_timeout_when_item_available(self):
        """Test that get returns immediately when item is available."""
        queue = SpiderPriorityQueue()
        req = Request(url='https://example.com')
        
        await queue.put(req)
        
        start = asyncio.get_event_loop().time()
        result = await queue.get()
        elapsed = asyncio.get_event_loop().time() - start
        
        assert result is not None
        assert result.url == 'https://example.com'
        # Should be very fast
        assert elapsed < 0.05


class TestQueueConcurrency:
    """Test concurrent queue operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_put(self):
        """Test concurrent putting to queue."""
        queue = SpiderPriorityQueue()
        
        async def put_requests(start_idx, count):
            for i in range(start_idx, start_idx + count):
                req = Request(url=f'https://example.com/{i}', priority=i)
                await queue.put(req)
        
        # Concurrently put requests from different "producers"
        await asyncio.gather(
            put_requests(0, 10),
            put_requests(10, 10),
            put_requests(20, 10)
        )
        
        assert queue.qsize() == 30
    
    @pytest.mark.asyncio
    async def test_concurrent_get(self):
        """Test concurrent getting from queue."""
        queue = SpiderPriorityQueue()
        
        # Fill queue
        for i in range(20):
            await queue.put(Request(url=f'https://example.com/{i}', priority=i))
        
        results = []
        
        async def consumer(count):
            for _ in range(count):
                item = await queue.get()
                if item:
                    results.append(item)
        
        # Multiple consumers
        await asyncio.gather(
            consumer(7),
            consumer(7),
            consumer(6)
        )
        
        assert len(results) == 20
    
    @pytest.mark.asyncio
    async def test_producer_consumer(self):
        """Test producer-consumer pattern."""
        queue = SpiderPriorityQueue()
        produced = []
        consumed = []
        
        async def producer():
            for i in range(10):
                req = Request(url=f'https://example.com/{i}', priority=i)
                await queue.put(req)
                produced.append(req)
                await asyncio.sleep(0.01)
        
        async def consumer():
            for _ in range(10):
                item = await queue.get()
                while item is None:
                    await asyncio.sleep(0.01)
                    item = await queue.get()
                consumed.append(item)
        
        await asyncio.gather(producer(), consumer())
        
        assert len(produced) == 10
        assert len(consumed) == 10


class TestQueueEmpty:
    """Test queue empty state."""
    
    @pytest.mark.asyncio
    async def test_empty_initially(self):
        """Test queue is empty initially."""
        queue = SpiderPriorityQueue()
        assert queue.empty() == True
    
    @pytest.mark.asyncio
    async def test_not_empty_after_put(self):
        """Test queue is not empty after putting item."""
        queue = SpiderPriorityQueue()
        await queue.put(Request(url='https://example.com'))
        
        assert queue.empty() == False
    
    @pytest.mark.asyncio
    async def test_empty_after_get_all(self):
        """Test queue is empty after getting all items."""
        queue = SpiderPriorityQueue()
        
        await queue.put(Request(url='https://example.com/1'))
        await queue.put(Request(url='https://example.com/2'))
        
        await queue.get()
        await queue.get()
        
        assert queue.empty() == True


class TestQueueSize:
    """Test queue size tracking."""
    
    @pytest.mark.asyncio
    async def test_qsize_empty(self):
        """Test qsize on empty queue."""
        queue = SpiderPriorityQueue()
        assert queue.qsize() == 0
    
    @pytest.mark.asyncio
    async def test_qsize_increases(self):
        """Test qsize increases with puts."""
        queue = SpiderPriorityQueue()
        
        await queue.put(Request(url='https://example.com/1'))
        assert queue.qsize() == 1
        
        await queue.put(Request(url='https://example.com/2'))
        assert queue.qsize() == 2
        
        await queue.put(Request(url='https://example.com/3'))
        assert queue.qsize() == 3
    
    @pytest.mark.asyncio
    async def test_qsize_decreases(self):
        """Test qsize decreases with gets."""
        queue = SpiderPriorityQueue()
        
        for i in range(5):
            await queue.put(Request(url=f'https://example.com/{i}'))
        
        assert queue.qsize() == 5
        
        await queue.get()
        assert queue.qsize() == 4
        
        await queue.get()
        assert queue.qsize() == 3
