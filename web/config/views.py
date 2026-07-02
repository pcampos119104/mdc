"""Project-level views."""


def sentry_debug(request):
    """Trigger an error to verify Sentry integration in development."""
    division_by_zero = 1 / 0
    return division_by_zero
