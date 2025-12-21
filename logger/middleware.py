import json 
import time 
import traceback
from .utils import log, get_user_context


class LogMiddleware:
    """
    - Logs request start and end duration
    - Sanitizes sensetive data
    - Automatically adjusts log level by response code 
    - Handles both Django DRF requests
    - Async compatibe (works under ASGI)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Entry point for each request. Works for both sync and async Django views
        """
        start_time = time.time()
        user, ip_address, user_agent, meta = get_user_context(request)

        self.log_request(request, user, ip_address, user_agent, meta)

        try: 
            response = self._get_response(request)
        except Exception as e:
            self.log_exception(request, e, user, ip_address)
            raise

        self.log_response(request, response, start_time, user, ip_address)

        return response
    
    def _get_response(self, request):
        """
        Internal helper to handle both sync views 
        """
        return self.get_response(request)
    
    def log_request(self, request, user, ip_address, user_agent, meta):
        """ Log request start details"""

        request_body = None
        if request.method in ['POST', 'PUT', 'PATCH']:
            try: 
                if hasattr(request, 'body') and request.body:
                    content_type = meta.get('CONTENT_TYPE', "")
                    if "application/json" in content_type: 
                        request_body = json.loads(request.body.decode("utf-8"))
                    elif "multipart/form-data" not in content_type:
                        request_body = request.POST.dict()
                    if isinstance(request_body, dict):
                        request_body = self.sanitize_data(request_body)
            
            except Exception:
                request_body = None 
        
        extra_data = {
            "query_params": dict(request.GET),
            "request_body": request_body,
            "headers": {
                "content_type": meta.get("CONTENT_TYPE", "") if meta else None,
                "referer": meta.get("HTTP_REFERER", "") if meta else None,
            },
        }

        log(
            level="INFO",
            action_type="REQUEST",
            message=f"{request.method} {request.path}",
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request.method,
            request_path=request.path,
            extra_data=extra_data,
        )
                
    def log_response(self, request, response, start_time, user, ip_address):
        """Logs response after view execution."""

        duration = round(time.time() - start_time, 3)
        level = "INFO"
        if response.status_code >= 500:
            level = "ERROR"
        elif response.status_code >= 400:
            level = "WARNING"

        extra_data = {
            "status_code": response.status_code,
            "duration_seconds": duration,
            "content_type": response.get("Content-Type", ""),
        }

        log(
            level=level,
            action_type="RESPONSE",
            message=f"{request.method} {request.path} - {response.status_code}",
            user=user,
            ip_address=ip_address,
            request_method=request.method,
            request_path=request.path,
            extra_data=extra_data,
        )

    def log_exception(self, request, exception, user, ip_address):
        """Logs unhandled exceptions."""

        log(
            level="ERROR",
            action_type="EXCEPTION",
            message=f"Exception in {request.method} {request.path}: {exception}",
            user=user,
            ip_address=ip_address,
            request_method=request.method,
            request_path=request.path,
            extra_data={
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "traceback": traceback.format_exc(),
            },
        )

    @staticmethod
    def sanitize_data(data):
        """Redacts sensitive fields from the request body."""

        sensitive_keys = [
            "password", "token", "secret", "api_key", "authorization",
            "csrf", "session", "cookie"
        ]

        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(s in key.lower() for s in sensitive_keys):
                    sanitized[key] = "***REDACTED***"
                elif isinstance(value, dict):
                    sanitized[key] = LogMiddleware.sanitize_data(value)
                elif isinstance(value, list):
                    sanitized[key] = [
                        LogMiddleware.sanitize_data(v) if isinstance(v, dict) else v
                        for v in value
                    ]
                else:
                    sanitized[key] = value
            return sanitized
        return data