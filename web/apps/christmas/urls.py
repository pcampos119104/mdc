"""URL routes for the Natal Feliz campaign."""

from django.urls import path

from . import views

app_name = "christmas"

urlpatterns = [
    path("", views.event_list, name="event_list"),
    path("events/new/", views.ChristmasEventCreateView.as_view(), name="event_create"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path(
        "events/<int:pk>/labels/pdf/",
        views.event_labels_pdf,
        name="event_labels_pdf",
    ),
    path(
        "events/<int:pk>/edit/",
        views.ChristmasEventUpdateView.as_view(),
        name="event_update",
    ),
    path(
        "events/<int:pk>/remove/",
        views.ChristmasEventRemoveView.as_view(),
        name="event_remove",
    ),
    path(
        "events/<int:event_pk>/sponsorships/",
        views.sponsorship_list,
        name="sponsorship_list",
    ),
    path(
        "events/<int:event_pk>/sponsorships/new/",
        views.ChristmasSponsorshipCreateView.as_view(),
        name="sponsorship_create",
    ),
    path(
        "events/<int:event_pk>/sponsorships/<int:pk>/",
        views.sponsorship_detail,
        name="sponsorship_detail",
    ),
    path(
        "events/<int:event_pk>/sponsorships/<int:pk>/edit/",
        views.ChristmasSponsorshipUpdateView.as_view(),
        name="sponsorship_update",
    ),
    path(
        "events/<int:event_pk>/sponsorships/<int:pk>/remove/",
        views.ChristmasSponsorshipRemoveView.as_view(),
        name="sponsorship_remove",
    ),
    path("sponsors/", views.sponsor_list, name="sponsor_list"),
    path(
        "sponsors/new/",
        views.ChristmasSponsorCreateView.as_view(),
        name="sponsor_create",
    ),
    path(
        "sponsors/<int:pk>/edit/",
        views.ChristmasSponsorUpdateView.as_view(),
        name="sponsor_update",
    ),
    path(
        "sponsors/<int:pk>/remove/",
        views.ChristmasSponsorRemoveView.as_view(),
        name="sponsor_remove",
    ),
    path("children/", views.child_list, name="child_list"),
    path("children/new/", views.ChildCreateView.as_view(), name="child_create"),
    path("children/<int:pk>/", views.child_detail, name="child_detail"),
    path(
        "children/<int:pk>/edit/",
        views.ChildUpdateView.as_view(),
        name="child_update",
    ),
    path(
        "children/<int:pk>/remove/",
        views.ChildRemoveView.as_view(),
        name="child_remove",
    ),
]
