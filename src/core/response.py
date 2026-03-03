"""
Backward compatibility module for Response import.
The Response class has been moved to src.http.response
"""
from src.http.response import Response

__all__ = ['Response']
