import threading 
import inspect 
import json
import sys
import os
import logging
import hashlib
import hmac
import redis
from django.utils import timezone
from django.utils.functional import Promise
from django.utils.encoding import force_str
from pprint import pprint


try: 
    import contextvars
    _current_request = contextvars.ContextVar("current_request")
    
    def set_current_request(request):
        """ Store current request"""
        _current_request.set(request)

    def get_current_request():
        """Retrive the current request"""
        return _current_request.get(None)
    
except ImportError:
    import threading
    _thread_locals = threading.local()

    def set_current_request(request):
        """ Store all current request in thread-local storage"""
        _thread_locals.request = request

    def get_current_request():
        """Retrive the current request from thread-local storage"""
        return getattr(_thread_locals, 'request', None)


def get_user_context(request):

    if request is None:
        return None, None, None, None
    
    # Detect DRF request vs Django request
    meta = getattr(request, 'META', None) or getattr(getattr(request, '_request', None), 'META', None)

    user = getattr(request, 'user', None) or getattr(getattr(request, '_request', None), 'user', None)

    ip_address = None
    if meta:
        x_forward_for = meta.get('HTTP_X_FORWARDED_FOR')
        ip_address = x_forward_for.split(',')[0] if x_forward_for else meta.get('REMOTE_ADDR')

    user_agent = meta.get('HTTP_USER_AGENT', '') if meta else None

    return user, ip_address, user_agent, meta

# Convert lazy objects to str
def convert_lazy(obj):
    if isinstance(obj, Promise):
        return force_str(obj)
    if isinstance(obj, dict):
        return {k: convert_lazy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_lazy(i) for i in obj]
    return obj


# Log to redis 

# Environment
LOG_TO_REDIS_QUEUE = os.environ.get('LOG_TO_REDIS_QUEUE')
REDIS_QUEUE = os.environ.get('REDIS_LOG_QUEUE', 'defualt_django_logs')
REDIS_TTL = int(os.environ.get('REDIS_LOG_TTL_SECONDS', '86400'))
FALLBACK_FILE = os.environ.get('LOG_FAILOVER_FILE', '/tmp/django_log_fallback.log')
REDIS_HOST = os.environ.get('REDIS_HOST', 'log-queue')
REDIS_PORT = os.environ.get('REDIS_PORT', '6379')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
REDIS_LOG_DB = os.environ.get('REDIS_LOG_DB', '2')




def init_redis():
    """Initiallize Redis connection if enabled. Return None if fails"""
    if not LOG_TO_REDIS_QUEUE:
        return None
    
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            db=int(REDIS_LOG_DB),
            # password=REDIS_PASSWORD,
            socket_timeout=0.2,
            socket_connect_timeout=0.2,
        )
        
        client.ping()
        return client
    except redis.ConnectionError:
        print("[ERROR] Cloud not connect to redis")
        return None
    
# initializing redis client 
redis_client = init_redis()

def fallback_write(log_data):
    try:
        with open(FALLBACK_FILE, 'a') as file:
            file.write(json.dumps(log_data) + '\n')
    except Exception as e:
        print('[ERROR] could not write logs into fallback file :) ')

def push_to_redis_queue(log_data, max_queue_size=50000):
    """
    Push log to Redis safely:
        - Validate format
        - Encode JSON
        - Retry connection
        - Apply queue trimming
        - Apply TTL
    """

    global redis_client

    # Validate log format
    if not isinstance(log_data, dict):
        print("[ERROR] log_data must be dict, got:", type(log_data), log_data)
        fallback_write(log_data)
        return False

    # Encode log into JSON
    try:
        payload = json.dumps(log_data, ensure_ascii=False)
    except Exception as e:
        print("[ERROR] Failed to JSON encode log:", e, log_data)
        fallback_write(log_data)
        return False

    if redis_client is None:
        fallback_write(log_data)
        return False

    try:
        redis_client.rpush(REDIS_QUEUE, payload)
        redis_client.ltrim(REDIS_QUEUE, -max_queue_size, -1)

        if REDIS_TTL > 0:
            redis_client.expire(REDIS_QUEUE, REDIS_TTL)

        return True

    except Exception:
        # Reconnect attempt
        redis_client = init_redis()
        if redis_client:
            try:
                redis_client.rpush(REDIS_QUEUE, payload)
                return True
            except Exception as e:
                print("[ERROR] Could not push logs to queue on retry:", e)

        fallback_write(log_data)
        return False

    
                
            
LAST_HASH = None

def log(level='INFO', action_type='OTHER', message='', user=None, 
              username=None, ip_address=None, user_agent=None, 
              request_method=None, request_path=None, model_name=None, 
              object_id=None, extra_data=None, changes=None, include_caller=True):
    """ 
    Print log entry to 
        1. standard output 
        OR
        2. use Standard logging (Set DJANGO_LOG_TO_STDOUT in you environment variables to False)

        NOTE: To use the second option make sure Django's logging is configured in settings.py

    Arguments:   
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        action_type: Type of action (CREATE, UPDATE, DELETE, READ, LOGIN, LOGOUT, REQUEST, RESPONSE, SYSTEM, OTHER)
        message: Log message
        user: User instance
        username: Username (if user not available)
        ip_address: IP address
        user_agent: User agent string
        request_method: HTTP method
        request_path: Request path
        model_name: Model name (for model changes)
        object_id: Object ID (for model changes)
        extra_data: Additional data as dictionary
        changes: Changes dictionary (for updates) 
        include_caller: Specify if you want to get Caller Information   
    """
    global LAST_HASH

    # normalize level 
    level = (level or 'INFO').upper()
    
    # Choose between printing log to stdout or using logger
    log_to_stdout = os.environ.setdefault('DJANGO_LOG_TO_STDOUT', 'True')
    pretty = os.environ.get("DJANGO_LOG_PRETTY", "True") == "True"
    SECRET = os.environ.get("LOG_CHAIN_SECRET", "change_me").encode()
    SERVICE_NAME = os.environ.get("SERVICE_NAME", "django-service")

    module = function = line_number = None
    # if include_caller is True in function argument it'll collect caller information
    if include_caller:
        try:
            # Get caller information
            frame = inspect.currentframe()
            caller_frame = inspect.getouterframes(frame)[1]
            module = caller_frame.filename
            function = caller_frame.function
            line_number = caller_frame.lineno
            
        except Exception:
            pass

    # Build log entry as dict
    log_data = {
        'service_name': SERVICE_NAME,
        'timestamp' : timezone.now().isoformat(),
        'level' : level,
        'action_type' : action_type,
        'message' : message,
        'username' : username or (getattr(user, 'username', None) if user else None),
        'ip_address' : ip_address,
        'user_agent' : user_agent, 
        'request_method' : request_method,
        'request_path' : request_path,
        'model_name' : model_name,
        'object_id' :  object_id,
        'extra_data' : extra_data or {},
        'changes' : changes or {},
        'module' : module,
        'function' : function,
        'line_number' : line_number
    }

    # Remove None values 
    log_data = {key : value for key, value in log_data.items() if value is not None and value !={} and value != ''}

    # Converts Lazy objects to str
    log_data = convert_lazy(log_data)
    
    content = json.dumps(log_data, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode()
    
    if LAST_HASH is None:
        to_hash = content 
    else: 
        to_hash = LAST_HASH + content
        
    
    hash_bytes = hmac.new(SECRET, to_hash, hashlib.sha256).digest()
    
    # Add chain fields
    log_data["chain_prev"] = LAST_HASH.hex() if LAST_HASH else None
    log_data["chain_hash"] = hash_bytes.hex()    
    
    # Update state
    LAST_HASH = hash_bytes  
    
    content_str = json.dumps(log_data, separators=(",", ":"), ensure_ascii=False)

    try:
        if log_to_stdout:
            # Printing log to stdout
            if pretty:
                # Human-friendly multi-line debug output
                pprint(log_data, stream=sys.stdout)
                sys.stdout.flush()
            else:
                
                print(content_str, file=sys.stdout)
                sys.stdout.flush()                
        else:
            # Use standrad logging
            numeric_level = getattr(logging, level, logging.INFO)
            logging.log(numeric_level, content_str)
            
    except Exception as e:
        print(f"[LOGGING ERROR] Could not emit log: {e}")
    
    #Push logs to queue
    if os.environ.get("LOG_TO_REDIS_QUEUE", "False") == "True":
        push_to_redis_queue(log_data) 

    return log_data
