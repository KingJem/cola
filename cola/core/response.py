"""
Backward compatibility module for Response import.
The Response class has been moved to cola.http.response
"""
from cola.http.response import Response

__all__ = ['Response']
