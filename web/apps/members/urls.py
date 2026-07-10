"""URL routes for member management."""

from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("", views.member_list, name="list"),
    path("new/", views.MemberCreateView.as_view(), name="create"),
    path("<int:pk>/", views.member_detail, name="detail"),
    path("<int:pk>/edit/", views.MemberUpdateView.as_view(), name="update"),
    path("<int:pk>/remove/", views.MemberRemoveView.as_view(), name="remove"),
]
