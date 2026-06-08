"""Project-level views."""

from django.shortcuts import render


def home(request):
    """Render the initial home page."""
    return render(request, "home.html")
