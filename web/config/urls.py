"""Root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("members/", include("apps.members.urls")),
]

if settings.DEBUG:
    urlpatterns += [
        path("sentry-debug/", views.sentry_debug, name="sentry-debug"),
    ]
