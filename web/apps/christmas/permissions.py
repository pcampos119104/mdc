"""Permission helpers for the Natal Feliz campaign."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def user_can_manage_christmas(user):
    """Return whether a user can manage the Natal Feliz campaign."""
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def christmas_admin_required(view_func):
    """Require authentication and staff or superuser access for a view."""

    @wraps(view_func)
    @login_required
    def wrapped_view(request, *args, **kwargs):
        """Check Natal Feliz administration access before calling the view."""
        if not user_can_manage_christmas(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped_view
