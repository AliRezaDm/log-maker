from typing import Any
from .utils import set_current_request


class RequestMiddleware:
    """
    Middleware to store current request in thread-local or contextvars storage.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_request(request)
        try: 
            response = self.get_response(request)
            return response
        finally:
            # Clear the request after response
            set_current_request(None)
            
