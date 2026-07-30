"""URL routes for birthday report settings and history."""

from django.urls import path

from . import views

app_name = "birthdays"

urlpatterns = [
    path("", views.birthday_settings, name="settings"),
    path("history/", views.birthday_report_history, name="history"),
    path("reports/<int:pk>/image/", views.birthday_report_image, name="image"),
    path(
        "reports/<int:pk>/image/download/",
        views.birthday_report_image_download,
        name="image_download",
    ),
    path("reports/<int:pk>/resend/", views.birthday_report_resend, name="resend"),
]
