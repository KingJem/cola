"""
Tests for the Request class.
"""
import pytest
from cola.http.request import Request


class TestRequestBasics:
    """Test basic Request functionality."""
    
    def test_request_init_basic(self):
        """Test basic request initialization."""
        req = Request(url='https://example.com')
        assert req.url == 'https://example.com'
        assert req.method == 'GET'
        assert req.priority == 0
        assert req.headers is None
        assert req.cookies is None
        assert req.proxy is None
        assert req.body is None
        assert req.callback is None
        assert req.meta == {}
    
    def test_request_init_with_params(self):
        """Test request initialization with all parameters."""
        def callback(response):
            pass
        
        headers = {'User-Agent': 'TestBot'}
        cookies = {'session': 'abc123'}
        proxy = {'http': 'http://proxy.com:8080'}
        
        req = Request(
            url='https://api.example.com/data',
            method='POST',
            headers=headers,
            priority=5,
            cookies=cookies,
            proxy=proxy,
            body='{"key": "value"}',
            callback=callback
        )
        
        assert req.url == 'https://api.example.com/data'
        assert req.method == 'POST'
        assert req.headers == headers
        assert req.priority == 5
        assert req.cookies == cookies
        assert req.proxy == proxy
        assert req.body == '{"key": "value"}'
        assert req.callback == callback
        assert req.meta == {}
    
    def test_request_methods(self):
        """Test different HTTP methods."""
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD']
        
        for method in methods:
            req = Request(url='https://example.com', method=method)
            assert req.method == method


class TestRequestPriority:
    """Test Request priority handling."""
    
    def test_priority_comparison(self):
        """Test __lt__ method for priority queue."""
        req1 = Request(url='https://example.com', priority=1)
        req2 = Request(url='https://example.com', priority=5)
        req3 = Request(url='https://example.com', priority=3)
        
        # Lower priority value should be "less than" higher priority
        assert req1 < req2
        assert req1 < req3
        assert req3 < req2
        assert not (req2 < req1)
    
    def test_priority_sorting(self):
        """Test that requests can be sorted by priority."""
        requests = [
            Request(url='https://example.com/3', priority=10),
            Request(url='https://example.com/1', priority=1),
            Request(url='https://example.com/2', priority=5),
        ]
        
        sorted_requests = sorted(requests)
        assert sorted_requests[0].priority == 1
        assert sorted_requests[1].priority == 5
        assert sorted_requests[2].priority == 10


class TestRequestMeta:
    """Test Request meta dictionary."""
    
    def test_meta_initialization(self):
        """Test that meta is initialized as empty dict."""
        req = Request(url='https://example.com')
        assert req.meta == {}
        assert isinstance(req.meta, dict)
    
    def test_meta_modification(self):
        """Test modifying meta dictionary."""
        req = Request(url='https://example.com')
        req.meta['key1'] = 'value1'
        req.meta['key2'] = {'nested': 'data'}
        
        assert req.meta['key1'] == 'value1'
        assert req.meta['key2'] == {'nested': 'data'}
    
    def test_meta_persistence(self):
        """Test that meta persists across request lifecycle."""
        req = Request(url='https://example.com')
        req.meta['trace_id'] = '12345'
        req.meta['depth'] = 2
        
        # Simulate passing through various stages
        assert req.meta['trace_id'] == '12345'
        assert req.meta['depth'] == 2


class TestRequestCallback:
    """Test Request callback functionality."""
    
    def test_callback_assignment(self):
        """Test assigning callback function."""
        def my_callback(response):
            return response.text
        
        req = Request(url='https://example.com', callback=my_callback)
        assert req.callback == my_callback
        assert callable(req.callback)
    
    def test_callback_none(self):
        """Test request without callback."""
        req = Request(url='https://example.com')
        assert req.callback is None
    
    def test_callback_lambda(self):
        """Test lambda function as callback."""
        req = Request(
            url='https://example.com',
            callback=lambda resp: resp.json()
        )
        assert callable(req.callback)


class TestRequestHeaders:
    """Test Request headers handling."""
    
    def test_headers_none(self):
        """Test request with no headers."""
        req = Request(url='https://example.com')
        assert req.headers is None
    
    def test_headers_dict(self):
        """Test request with headers dict."""
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
            'Authorization': 'Bearer token123'
        }
        req = Request(url='https://example.com', headers=headers)
        assert req.headers == headers
        assert req.headers['User-Agent'] == 'Mozilla/5.0'


class TestRequestCookies:
    """Test Request cookies handling."""
    
    def test_cookies_none(self):
        """Test request without cookies."""
        req = Request(url='https://example.com')
        assert req.cookies is None
    
    def test_cookies_dict(self):
        """Test request with cookies."""
        cookies = {'sessionid': 'abc123', 'csrftoken': 'xyz789'}
        req = Request(url='https://example.com', cookies=cookies)
        assert req.cookies == cookies


class TestRequestProxy:
    """Test Request proxy handling."""
    
    def test_proxy_none(self):
        """Test request without proxy."""
        req = Request(url='https://example.com')
        assert req.proxy is None
    
    def test_proxy_dict(self):
        """Test request with proxy."""
        proxy = {
            'http': 'http://proxy.example.com:8080',
            'https': 'https://proxy.example.com:8080'
        }
        req = Request(url='https://example.com', proxy=proxy)
        assert req.proxy == proxy


class TestRequestBody:
    """Test Request body handling."""
    
    def test_body_none(self):
        """Test GET request with no body."""
        req = Request(url='https://example.com', method='GET')
        assert req.body is None
    
    def test_body_string(self):
        """Test POST request with string body."""
        body = '{"name": "test", "value": 123}'
        req = Request(url='https://api.example.com', method='POST', body=body)
        assert req.body == body
    
    def test_body_form_data(self):
        """Test POST request with form data."""
        body = 'name=test&value=123'
        req = Request(
            url='https://example.com/form',
            method='POST',
            body=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        assert req.body == body


class TestRequestEncoding:
    """Test Request encoding method."""
    
    def test_encoding_method_exists(self):
        """Test that encoding method exists."""
        req = Request(url='https://example.com')
        assert hasattr(req, 'encoding')
        assert callable(req.encoding)
    
    def test_encoding_method_call(self):
        """Test calling encoding method."""
        req = Request(url='https://example.com')
        # Currently returns None as it's not implemented
        result = req.encoding()
        assert result is None
