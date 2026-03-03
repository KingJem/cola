"""
Pytest configuration and shared fixtures for Cola framework tests.
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock
from src.settings.settings_manager import SettingsManager
from src.http.request import Request
from src.http.response import Response


@pytest.fixture
def settings():
    """Create a basic settings manager for testing."""
    return SettingsManager()


@pytest.fixture
def custom_settings():
    """Create settings with custom values."""
    return SettingsManager({
        'PROJECT_NAME': 'TestProject',
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOADER_CLASS': 'src.downloaders.aio_http_downloader.AioHttpDownloader'
    })


@pytest.fixture
def mock_crawler(settings):
    """Create a mock crawler object."""
    crawler = Mock()
    crawler.settings = settings
    crawler.spider = Mock()
    crawler.spider.name = 'TestSpider'
    crawler.stat_collector = Mock()
    return crawler


@pytest.fixture
def sample_request():
    """Create a sample HTTP request."""
    return Request(
        url='https://example.com',
        method='GET',
        headers={'User-Agent': 'Cola/1.0'},
        priority=0
    )


@pytest.fixture
def sample_response(sample_request):
    """Create a sample HTTP response."""
    html_content = b'''
    <html>
        <head><title>Test Page</title></head>
        <body>
            <div class="content">
                <h1>Hello World</h1>
                <p>This is a test page.</p>
            </div>
        </body>
    </html>
    '''
    return Response(
        url='https://example.com',
        status=200,
        headers={'Content-Type': 'text/html'},
        body=html_content,
        request=sample_request
    )


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
