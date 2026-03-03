"""
Backward compatibility module for Request import.
The Request class has been moved to src.http.request
"""
from src.http.request import Request

__all__ = ['Request']
