from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from .utils import log, get_current_request, get_user_context
import threading

# Thread-local storage for tracking changes
_thread_locals = threading.local()

def get_model_changes(instance, original_instance):
    """ Compare two model instances and return a dictionary of changes"""
    changes = {}

    if not original_instance:
        return changes 
    
    for field in instance._meta.fields:
        field_name = field.name
        old_value = getattr(original_instance, field_name, None)
        new_value = getattr(instance, field_name, None)

        if old_value != new_value:
            # Convert to string for JSON serialization
            changes[field_name] = {
                'old': str(old_value) if old_value is not None else None,
                'new': str(new_value) if new_value is not None else None,
            }

        return changes
    
def get_client_ip(request):
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@receiver(pre_save)
def track_model_changes(sender, instance, **kwargs):
    """Track the original state before save for comparison"""
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            _thread_locals.original_instance = original
        except sender.DoesNotExist:
            _thread_locals.original_instance = None
    else:
        _thread_locals.original_instance = None


@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    """Log model creation and updates"""

    # Skip if this is a migration
    if kwargs.get('raw', False):
        return
    
    request = get_current_request()
    user = getattr(request, 'user', None) if request else None
    ip_address = get_client_ip(request)
    action_type = 'CREATE' if created else 'UPDATED'

    # Get changes for updates
    changes = {}
    if not created:
        original_instance = getattr(_thread_locals, 'original_instance', None)
        if original_instance:
            changes = get_model_changes(instance, original_instance)

    # Get model representation
    instance_repr = str(instance)
    message = f"{action_type}: {sender._meta.label} - {instance_repr}"

    log(
        level='INFO',
        action_type=action_type,
        message=message,
        user=user,
        ip_address=ip_address,
        model_name=sender._meta.app_label,
        object_id=str(instance.pk),
        changes=changes,
        extra_data={
            'app_label': sender._meta.app_label,
            'model_verbose_name': sender._meta.verbose_name,
        }       
    )

    # Clean up thread local
    if hasattr(_thread_locals, 'original_instance'):
        delattr(_thread_locals, 'original_instance')


@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    """Log model deletion"""

    request = get_current_request()
    user = getattr(request, 'user', None) if request else None
    ip_address = get_client_ip(request)
    instance_repr = str(instance)

    message = f'DELETE: {sender.__name__} - {instance_repr}'

    deleted_data = {
        f.name: str(getattr(instance, f.name, None)) for f in instance._meta.fields
    }

    log(
        level='WARNING',
        action_type='DELETE',
        message=f"DELETE: {sender._meta.label} - {instance_repr}",
        user=user,
        ip_address=ip_address,
        model_name=sender._meta.app_label,
        object_id=str(instance.pk) if instance.pk else None,
        extra_data={
            'deleted_data' : deleted_data,
            'app_label': sender._meta.app_label,
        }
    )


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Log successful user login
    """
    _, ip_address, user_agent, _ = get_user_context(request)
    
    log(
        level='INFO',
        action_type='LOGIN',
        message=f"User logged in: {user.username}",
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data={
            'login_method': kwargs.get('backend', 'web'),
        }
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """
    Log user logout
    """
    _, ip_address, user_agent, _ = get_user_context(request)
    
    log(
        level='INFO',
        action_type='LOGOUT',
        message=f"User logged out: {user.username if user else 'Unknown'}",
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data={
            'logout_method': kwargs.get('backend', 'web'),
        },
    )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    """
    Log failed login attempts
    """
    _, ip_address, user_agent, _ = get_user_context(request)
    
    username = credentials.get('username', 'Unknown')
    
    log(
        level='WARNING',
        action_type='LOGIN',
        message=f"Failed login attempt for user: {username}",
        username=username,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data={
            'login_method': kwargs.get('backend', 'web'),
            'reason': 'Invalid credentials',
        },
    )
