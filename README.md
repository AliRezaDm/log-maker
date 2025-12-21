# Django Logger

A comprehensive Django and Django REST Framework (DRF) compatible logging package that automatically logs everything in your project - from HTTP requests and responses to model changes and authentication events.

## Features

- 🔍 **Automatic Request/Response Logging** - Logs all HTTP requests and responses with detailed metadata
- 🔒 **Sensitive Data Sanitization** - Automatically redacts passwords, tokens, and other sensitive information
- 📊 **Model Change Tracking** - Logs all model CREATE, UPDATE, and DELETE operations with field-level change tracking
- 🔐 **Authentication Logging** - Tracks user login, logout, and failed login attempts
- ⚡ **ASGI/Async Compatible** - Works seamlessly with both sync and async Django views
- 🎨 **Decorator Support** - Easy-to-use decorators for function-based views, class-based views, and custom functions
- 📝 **Flexible Output** - Logs to stdout (JSON format) or integrates with Django's logging framework
- 🌐 **DRF Compatible** - Full support for Django REST Framework views and serializers
- ⏱️ **Performance Metrics** - Automatically tracks request duration
- 🎯 **Context-Aware** - Extracts user, IP address, and user agent information automatically
- 🔗 **Chain Hash Logging** (tamper-detection)
- 📨 **Redis Queue Logging** with auto-trim, TTL, and secure password
support
- 🧱 **Per-Project Queue Names** for multi-service setups
- 💾 **Fail-Safe Fallback File Logging** (no data loss)

## Installation

```bash
pip install roshan-logger
```
## Environment Variables

### Output Options

  ---------------------------------------------------------------------------
  Variable                 Default              Description
  ------------------------ -------------------- -----------------------------
  `DJANGO_LOG_TO_STDOUT`   `True`               Print logs to stdout as JSON

  `DJANGO_LOG_PRETTY`      `True`               Pretty-print logs (ignored if
                                                stdout disabled)
  ---------------------------------------------------------------------------
**Note:** if `DJANGO_LOG_TO_STDOUT` is set False setting `DJANGO_LOG_PRETTY` True would not have any effect

### Redis Queue Logging (Optional)

  ----------------------------------------------------------------------------------------
  Variable                  Default                          Description
  ------------------------- -------------------------------- -----------------------------
  `LOG_TO_REDIS_QUEUE`      `False`                          Enable Redis queue logging

  `REDIS_HOST`              `localhost`                      Redis host

  `REDIS_PORT`              `6379`                           Redis port

  `REDIS_PASSWORD`          *None*                           Redis password (optional)

  `REDIS_LOG_DB`            `2`                              Redis logical DB number

  `REDIS_LOG_QUEUE`         `django_logs`                    Redis queue/list name

  `REDIS_LOG_TTL_SECONDS`   `0`                              TTL for the Redis list key (0
                                                             = no TTL)

  `REDIS_LOG_MAX_SIZE`      `50000`                          Maximum queue size (auto
                                                             LTRIM)

  `LOG_FAILOVER_FILE`       `/tmp/django_log_fallback.log`   Local fallback file when
                                                             Redis fails
  ----------------------------------------------------------------------------------------
Redis logging includes:

- Automatic retry
- TTL for queue cleanup
- Memory protection via LTRIM
- Password authentication
- Per-project queue names
- Automatic fallback file logging


### Chain Hashing (Security)

  -----------------------------------------------------------------------
  Variable             Default              Description
  -------------------- -------------------- -----------------------------
  `LOG_CHAIN_SECRET`   `change_me`          Secret used for HMAC chain
                                            hashing

  -----------------------------------------------------------------------
This ensures:

- Tamper detection
- Full chronological verification
- Audit-grade integrity



## Quick Start

### 1. Add to Installed Apps
If you wish to use the package signals add `logger` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps
    'logger.apps.LoggerConfig',
]
```
**Note:** 
Add the package to `INSTALLED_APPS` only if you want to use the package signals, which logs 
- User login
- User logout
- User failed login attemps 
- Tracks changes made to objects created from your models

### 2. Configure Middleware

Add the middleware to your `MIDDLEWARE` in `settings.py`. The order matters

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'logger.request_middleware.RequestMiddleware',  # Add this first
    'logger.middleware.LogMiddleware',              # Add this second
    # ... other middleware
]
```

**Note:** 
- `RequestMiddleware` - Stores the current request in context for access in decorators and signals
- `LogMiddleware` - Logs all HTTP requests, responses, and exceptions

### 3. Configure Logging Output (Optional)

By default, logs are printed to stdout in JSON format. To use Django's logging framework instead:

```python
# In your environment or settings.py
import os
os.environ['DJANGO_LOG_TO_STDOUT'] = 'False'
```
After setting the variable the package will follow your project logging configurations if you don't have one, follow the instruction below:

**Django logging in `settings.py`:**

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Usage

### Automatic Logging

Once configured, the following are logged automatically:

#### 1. HTTP Requests and Responses
All HTTP requests and responses are automatically logged with:
- Request method, path, and query parameters
- Request headers and body (with sensitive data redacted)
- Response status code and duration
- User information and IP address

#### 2. Model Changes
All model operations are tracked:
- **CREATE** - New object creation
- **UPDATE** - Object updates with field-level change tracking
- **DELETE** - Object deletion with final state

#### 3. Authentication Events
- User login (successful)
- User logout
- Failed login attempts

### Manual Logging with Decorators

#### Function-Based Views

```python
from logger.decorators import log_view

@log_view(action_type='READ', level='INFO')
def my_view(request):
    # Your view logic
    return JsonResponse({'status': 'ok'})
```

#### Class-Based Views

```python
from django.utils.decorators import method_decorator
from logger.decorators import log_class_view
from django.views import View

@method_decorator(log_class_view(action_type='READ'), name='dispatch')
class MyView(View):
    def get(self, request):
        return JsonResponse({'status': 'ok'})
```

Or for specific methods:

```python
@method_decorator(log_class_view(action_type='CREATE', methods=['post']), name='post')
class MyView(View):
    def post(self, request):
        return JsonResponse({'status': 'created'})
```

#### Custom Functions

```python
from logger.decorators import log_action

@log_action(action_type='CALCULATION', level='INFO')
def complex_calculation(x, y):
    result = x * y
    return result
```

### Direct Logging

You can also log directly using the `log()` function:

```python
from logger.utils import log

log(
    level='INFO',
    action_type='CUSTOM',
    message='Custom log message',
    extra_data={'key': 'value'}
)
```

#### Log Function Parameters

- `level` - Log level: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
- `action_type` - Type of action: 'CREATE', 'UPDATE', 'DELETE', 'READ', 'LOGIN', 'LOGOUT', 'REQUEST', 'RESPONSE', 'SYSTEM', 'OTHER'
- `message` - Log message
- `user` - User instance (auto-detected from request)
- `username` - Username string (if user not available)
- `ip_address` - IP address (auto-detected from request)
- `user_agent` - User agent string (auto-detected from request)
- `request_method` - HTTP method
- `request_path` - Request path
- `model_name` - Model name (for model changes)
- `object_id` - Object ID
- `extra_data` - Additional data as dictionary
- `changes` - Changes dictionary (for updates)
- `include_caller` - Include caller information (default: True)

## Log Output Format

Logs are output in JSON format for easy parsing and integration with log aggregation tools:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456+00:00",
  "level": "INFO",
  "action_type": "REQUEST",
  "message": "GET /api/users/",
  "username": "john_doe",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "request_method": "GET",
  "request_path": "/api/users/",
  "extra_data": {
    "query_params": {"page": "1"},
    "headers": {
      "content_type": "application/json"
    }
  },
  "module": "/app/views.py",
  "function": "user_list",
  "line_number": 42
}
```

## Sensitive Data Protection

The following fields are automatically redacted in request bodies and headers:
- password
- token
- secret
- api_key
- authorization
- csrf
- session
- cookie

Example:
```json
{
  "username": "john_doe",
  "password": "***REDACTED***",
  "api_key": "***REDACTED***"
}
```

## Action Types

The package uses standardized action types for consistent logging:

- `CREATE` - Resource creation
- `UPDATE` - Resource modification
- `DELETE` - Resource deletion
- `READ` - Resource retrieval
- `LOGIN` - User authentication
- `LOGOUT` - User logout
- `REQUEST` - HTTP request
- `RESPONSE` - HTTP response
- `EXCEPTION` - Error/exception
- `SYSTEM` - System events
- `OTHER` - Custom events

## Log Levels

Automatic log level assignment based on HTTP status codes:
- `INFO` - Status codes 200-399
- `WARNING` - Status codes 400-499
- `ERROR` - Status codes 500+
- Custom levels for manual logging

## Performance Considerations

- Minimal performance impact due to efficient logging
- Async/ASGI compatible
- Thread-safe and context-aware
- Sensitive data sanitization happens before logging

## Requirements

- Python >= 3.8
- Django >= 3.2.1, < 5.2.8
- djangorestframework >= 3.12.2, < 3.16 (optional, for DRF support)
- Redis >= 6.2 (preferred) or Redis >= 5.0 (minimum)



