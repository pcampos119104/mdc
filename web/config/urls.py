"""Root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.members import views as member_views

from . import views

urlpatterns = [
    path("", member_views.member_list, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("members/", include("apps.members.urls")),
]

if settings.DEBUG:
    urlpatterns += [
        path("sentry-debug/", views.sentry_debug, name="sentry-debug"),
    ]
