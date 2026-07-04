"""
Backward compatibility module for Request import.
The Request class has been moved to cola.http.request
"""
from cola.http.request import Request

__all__ = ['Request']
