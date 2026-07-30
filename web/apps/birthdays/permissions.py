"""Permission helpers for birthday report views."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def user_can_manage_birthday_reports(user):
    """Return whether a user can manage birthday report settings and history."""
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def birthday_admin_required(view_func):
    """Require authentication and staff/superuser access for a view."""
    @wraps(view_func)
    @login_required
    def wrapped_view(request, *args, **kwargs):
        """Check birthday report administration access before calling the view."""
        if not user_can_manage_birthday_reports(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped_view
