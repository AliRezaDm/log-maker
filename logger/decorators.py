from functools import wraps
from .utils import log, get_current_request, get_user_context


    
def log_action(action_type='OTHER', level='INFO'):
    """ Decorator to automatically log function calls"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = None
            exception = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                exception = e
                raise
            finally:
                # Prepare log message
                if exception:
                    message = f"Exception in {func.__name__}:{str(exception)}"
                    actual_level = "ERROR"
                else:
                    message = f"Function {func.__name__} executed"
                    actual_level = level

                # Get request context
                request = get_current_request()
                
                _, ip_address, _, _ = get_user_context(request)

                try:     
                    log(
                        level = actual_level, 
                        action_type=action_type,
                        message=message,
                        ip_address=ip_address,
                        extra_data={
                            'function':func.__name__,
                            'module':func.__module__,
                            'args':str(args),
                            'kwargs':str(kwargs),
                            'exception':str(exception) if exception else None,
                        }
                    )
                except Exception as log_error:
                    print(f"[WARN] Logging failed {func.__name__}:{log_error}")
                    
        return wrapper
    return decorator



def log_view(action_type='REQUEST', level='INFO'):
    """ Decorator for Django and DRF funtion-based views"""
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            
            user, ip_address, user_agent, _ = get_user_context(request)

            result = None
            exception = None
            status_code = None

            try:
                result = view_func(request, *args, **kwargs)

                # Extract status code if view returned a response
                if hasattr(result, 'status_code'):
                    status_code = result.status_code
                return result
            
            except Exception as e:
                exception = e
                raise
            
            finally:
                # Log the view access
                if exception:
                    message = f"Exception in view {view_func.__name__}: {str(exception)}"
                    actual_level = 'ERROR'
                else:
                    message = f"View {view_func.__name__} accessed"
                    actual_level = level
                
                try:   
                    log(
                        level=actual_level,
                        action_type=action_type,
                        message=message, 
                        user=user, 
                        ip_address=ip_address,
                        user_agent=user_agent,
                        request_path=getattr(request, 'path', None),
                        extra_data={
                            'view_name' : view_func.__name__,
                            'view_module' : view_func.__module__,
                            'url_kwargs' : kwargs,
                            'status_code' : status_code,
                            'exception' : str(exception) if exception else None,
                        }
                     )
                    
                except Exception as log_error:
                    print(f"[WARN] Logging failed {view_func.__name__}:{log_error}")
                    
        return wrapper
    return decorator



def log_class_view(action_type='REQUEST', level='INFO', methods=None):
    """
    Decorator for Django class-based views.
    
    Args:
        action_type: Type of action being logged (default: 'REQUEST')
        level: Log level (default: 'INFO')
        methods: List of HTTP methods to log (e.g., ['get', 'post']). 
                 If None, logs all methods.
    
    Usage:
        @method_decorator(log_class_view(action_type='READ', level='INFO'), name='dispatch')
        class MyView(View):
            ...
        
        Or for specific methods:
        @method_decorator(log_class_view(action_type='CREATE', methods=['post']), name='post')
        class MyView(View):
            ...
    """
    
    def decorator(func):
        @wraps(func)
        def _wrapper(*args, **kwargs):
            # Extract self and request from args
            # args[0] is self, args[1] is request for class methods
            if len(args) < 2:
                # Fallback if called incorrectly
                return func(*args, **kwargs)
            
            self = args[0]
            request = args[1]
            remaining_args = args[2:]

            user, ip_address, user_agent, _ = get_user_context(request)
            
            # Check if we should log this method
            method_name = func.__name__.lower()
            if methods and method_name not in [m.lower() for m in methods]:
                return func(*args, **kwargs)
            
            user = user if getattr(user, 'is_authenticated', False) else None

            result = None
            exception = None
            status_code = None

            try:
                result = func(*args, **kwargs)
                # Try to get status code from response
                if hasattr(result, 'status_code'):
                    status_code = result.status_code
                return result
            
            except Exception as e:
                exception = e
                status_code = getattr(e, 'status_code', 500) 
                raise

            finally:
                # Determine actual action type based on HTTP method if not specified
                if action_type == 'REQUEST' and hasattr(request, 'method'):
                    method_to_action = {
                        'GET': 'READ',
                        'POST': 'CREATE',
                        'PUT': 'UPDATE',
                        'PATCH': 'UPDATE',
                        'DELETE': 'DELETE',
                    }
                    actual_action_type = method_to_action.get(request.method, action_type)
                else:
                    actual_action_type = action_type

                # Log the view access
                if exception:
                    message = f"Exception in {self.__class__.__name__}.{func.__name__}: {str(exception)}"
                    actual_level = 'ERROR'
                else:
                    message = f"{self.__class__.__name__}.{func.__name__} executed"
                    actual_level = level
                try:
                    log(
                        level=actual_level,
                        action_type=actual_action_type,
                        message=message,
                        user=user,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        request_method=request.method,
                        request_path=request.path,
                        extra_data={
                            'view_class': self.__class__.__name__,
                            'view_method': func.__name__,
                            'view_module': self.__class__.__module__,
                            'url_kwargs': kwargs,
                            'status_code': status_code,
                            'exception': str(exception) if exception else None,
                            'http_method': request.method,
                        }
                    )
                except Exception as log_error:
                    print(f"[WARN] Logging failed {self.__class__.__name__}.{func.__name__}:{log_error}")

        return _wrapper
    return decorator