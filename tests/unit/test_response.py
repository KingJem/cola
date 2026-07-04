"""
Tests for the Response class.
"""
import pytest
import json
from cola.http.request import Request
from cola.http.response import Response


class TestResponseBasics:
    """Test basic Response functionality."""
    
    def test_response_init(self):
        """Test basic response initialization."""
        resp = Response(
            url='https://example.com',
            status=200,
            headers={'Content-Type': 'text/html'},
            body=b'<html>Test</html>'
        )
        
        assert resp.url == 'https://example.com'
        assert resp.status_code == 200
        assert resp.headers == {'Content-Type': 'text/html'}
        assert resp.body == b'<html>Test</html>'
        assert resp.request is None
        assert resp.exception is None
    
    def test_response_with_request(self):
        """Test response with associated request."""
        req = Request(url='https://example.com')
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b'test',
            request=req
        )
        
        assert resp.request == req
        assert resp.request.url == 'https://example.com'
    
    def test_response_repr(self):
        """Test __repr__ method."""
        resp = Response(
            url='https://example.com/page',
            status=404,
            headers={},
            body=b''
        )
        
        repr_str = repr(resp)
        assert 'https://example.com/page' in repr_str
        assert '404' in repr_str
        assert 'Response' in repr_str


class TestResponseText:
    """Test Response text property."""
    
    def test_text_basic(self):
        """Test basic text decoding."""
        html = '<html><body>Hello World</body></html>'
        resp = Response(
            url='https://example.com',
            status=200,
            headers={'Content-Type': 'text/html; charset=utf-8'},
            body=html.encode('utf-8')
        )
        resp._encoding = 'utf-8'
        
        assert resp.text == html
    
    def test_text_caching(self):
        """Test that text is cached after first access."""
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b'test content'
        )
        resp._encoding = 'utf-8'
        
        # First access
        text1 = resp.text
        assert resp._cached_text == text1
        
        # Second access should return cached value
        text2 = resp.text
        assert text1 == text2
        assert text1 is text2  # Same object
    
    def test_text_different_encodings(self):
        """Test text with different encodings."""
        content = '你好世界'  # Chinese: Hello World
        
        # UTF-8
        resp_utf8 = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=content.encode('utf-8')
        )
        resp_utf8._encoding = 'utf-8'
        assert resp_utf8.text == content


class TestResponseJson:
    """Test Response json method."""
    
    def test_json_basic(self):
        """Test parsing JSON response."""
        data = {'name': 'test', 'value': 123, 'active': True}
        json_str = json.dumps(data)
        
        resp = Response(
            url='https://api.example.com/data',
            status=200,
            headers={'Content-Type': 'application/json'},
            body=json_str.encode('utf-8')
        )
        resp._encoding = 'utf-8'
        
        result = resp.json()
        assert result == data
        assert result['name'] == 'test'
        assert result['value'] == 123
    
    def test_json_array(self):
        """Test parsing JSON array."""
        data = [1, 2, 3, 4, 5]
        json_str = json.dumps(data)
        
        resp = Response(
            url='https://api.example.com/list',
            status=200,
            headers={},
            body=json_str.encode('utf-8')
        )
        resp._encoding = 'utf-8'
        
        result = resp.json()
        assert result == data
        assert len(result) == 5
    
    def test_json_nested(self):
        """Test parsing nested JSON."""
        data = {
            'user': {
                'id': 1,
                'name': 'John',
                'tags': ['admin', 'user']
            }
        }
        json_str = json.dumps(data)
        
        resp = Response(
            url='https://api.example.com/user/1',
            status=200,
            headers={},
            body=json_str.encode('utf-8')
        )
        resp._encoding = 'utf-8'
        
        result = resp.json()
        assert result['user']['name'] == 'John'
        assert 'admin' in result['user']['tags']


class TestResponseXPath:
    """Test Response xpath method."""
    
    def test_xpath_basic(self):
        """Test basic XPath selection."""
        html = b'''
        <html>
            <body>
                <h1>Title</h1>
                <p class="content">Paragraph 1</p>
                <p class="content">Paragraph 2</p>
            </body>
        </html>
        '''
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=html
        )
        
        # Select h1 text
        result = resp.xpath('//h1/text()')
        assert len(result) == 1
        assert result[0] == 'Title'
    
    def test_xpath_multiple_elements(self):
        """Test XPath selecting multiple elements."""
        html = b'''
        <html>
            <body>
                <div class="item">Item 1</div>
                <div class="item">Item 2</div>
                <div class="item">Item 3</div>
            </body>
        </html>
        '''
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=html
        )
        
        result = resp.xpath('//div[@class="item"]/text()')
        assert len(result) == 3
        assert result[0] == 'Item 1'
        assert result[2] == 'Item 3'
    
    def test_xpath_attribute(self):
        """Test XPath selecting attributes."""
        html = b'<html><body><a href="https://example.com">Link</a></body></html>'
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=html
        )
        
        result = resp.xpath('//a/@href')
        assert len(result) == 1
        assert result[0] == 'https://example.com'


class TestResponseCSS:
    """Test Response css method."""
    
    def test_css_basic(self):
        """Test basic CSS selection."""
        html = b'''
        <html>
            <body>
                <h1 class="title">Main Title</h1>
                <p class="content">Content paragraph</p>
            </body>
        </html>
        '''
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=html
        )
        
        result = resp.css('.title')
        assert len(result) == 1
        assert result[0].text_content() == 'Main Title'
    
    def test_css_multiple_elements(self):
        """Test CSS selecting multiple elements."""
        html = b'''
        <html>
            <body>
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
                <p>Paragraph 3</p>
            </body>
        </html>
        '''
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=html
        )
        
        result = resp.css('p')
        assert len(result) == 3


class TestResponseRegex:
    """Test Response re method."""
    
    def test_re_basic(self):
        """Test basic regex matching."""
        html = '<html><body>Email: test@example.com</body></html>'
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=html.encode('utf-8')
        )
        resp._encoding = 'utf-8'
        
        result = resp.re(r'\w+@\w+\.\w+')
        assert len(result) == 1
        assert result[0] == 'test@example.com'
    
    def test_re_multiple_matches(self):
        """Test regex with multiple matches."""
        html = 'Prices: $10.99, $25.50, $100.00'
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=html.encode('utf-8')
        )
        resp._encoding = 'utf-8'
        
        result = resp.re(r'\$\d+\.\d+')
        assert len(result) == 3
        assert result[0] == '$10.99'
        assert result[2] == '$100.00'
    
    def test_re_no_match(self):
        """Test regex with no matches."""
        html = 'No emails here'
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=html.encode('utf-8')
        )
        resp._encoding = 'utf-8'
        
        result = resp.re(r'\w+@\w+\.\w+')
        assert result == []


class TestResponseFollow:
    """Test Response follow method."""
    
    def test_follow_basic(self):
        """Test creating follow-up request."""
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b'<html></html>'
        )
        
        new_req = resp.follow('https://example.com/page2')
        assert isinstance(new_req, Request)
        assert new_req.url == 'https://example.com/page2'
    
    def test_follow_with_callback(self):
        """Test follow with custom callback."""
        def parse_detail(response):
            pass
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b''
        )
        
        new_req = resp.follow('https://example.com/detail', callback=parse_detail)
        assert new_req.callback == parse_detail
    
    def test_follow_with_kwargs(self):
        """Test follow with additional kwargs."""
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b''
        )
        
        new_req = resp.follow(
            'https://example.com/api',
            method='POST',
            headers={'Content-Type': 'application/json'},
            priority=10
        )
        
        assert new_req.method == 'POST'
        assert new_req.priority == 10


class TestResponseMeta:
    """Test Response meta property."""
    
    def test_meta_from_request(self):
        """Test that meta is accessible from request."""
        req = Request(url='https://example.com')
        req.meta['depth'] = 1
        req.meta['category'] = 'news'
        
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b'',
            request=req
        )
        
        assert resp.meta == req.meta
        assert resp.meta['depth'] == 1
        assert resp.meta['category'] == 'news'
    
    def test_meta_setter(self):
        """Test meta setter."""
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b''
        )
        
        new_meta = {'key': 'value'}
        resp.meta = new_meta
        assert resp._meta == new_meta


class TestResponseURLJoin:
    """Test Response _urljoin method."""
    
    def test_urljoin_relative_path(self):
        """Test joining relative path."""
        resp = Response(
            url='https://example.com/page1',
            status=200,
            headers={},
            body=b''
        )
        
        result = resp._urljoin('page2')
        assert result == 'https://example.com/page2'
    
    def test_urljoin_absolute_path(self):
        """Test joining absolute path."""
        resp = Response(
            url='https://example.com/category/page1',
            status=200,
            headers={},
            body=b''
        )
        
        result = resp._urljoin('/newpage')
        assert result == 'https://example.com/newpage'
    
    def test_urljoin_full_url(self):
        """Test joining full URL."""
        resp = Response(
            url='https://example.com/page1',
            status=200,
            headers={},
            body=b''
        )
        
        result = resp._urljoin('https://other.com/page')
        assert result == 'https://other.com/page'


class TestResponseEncoding:
    """Test Response encoding method."""
    
    def test_encoding_method_exists(self):
        """Test that encoding method exists."""
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b''
        )
        
        assert hasattr(resp, 'encoding')
        assert callable(resp.encoding)
    
    def test_encoding_method_call(self):
        """无任何线索时回退 utf-8。"""
        resp = Response(
            url='https://example.com',
            status=200,
            headers={},
            body=b''
        )
        assert resp.encoding() == 'utf-8'

    def test_encoding_from_content_type(self):
        resp = Response(
            url='https://example.com', status=200,
            headers={'Content-Type': 'text/html; charset=GBK'},
            body='中文'.encode('gbk'))
        assert resp.encoding() == 'gbk'
        assert resp.text == '中文'

    def test_encoding_from_meta_tag(self):
        body = (b'<html><head><meta charset="gb2312"></head>'
                b'<body>' + '内容'.encode('gb2312') + b'</body></html>')
        resp = Response(url='https://example.com', status=200,
                        headers={}, body=body)
        assert resp.encoding() == 'gb2312'
        assert '内容' in resp.text

    def test_encoding_invalid_charset_falls_back(self):
        resp = Response(
            url='https://example.com', status=200,
            headers={'Content-Type': 'text/html; charset=bogus-enc'},
            body=b'hi')
        assert resp.encoding() == 'utf-8'
