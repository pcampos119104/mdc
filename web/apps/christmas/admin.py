"""Admin configuration for the Natal Feliz campaign."""

from django.contrib import admin

from .models import Child, ChristmasEvent, ChristmasSponsorship


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    """Admin interface for children participating in Natal Feliz."""

    list_display = ("name", "mother_name", "birth_date", "clothing_size")
    search_fields = ("name", "mother_name")


@admin.register(ChristmasSponsorship)
class ChristmasSponsorshipAdmin(admin.ModelAdmin):
    """Admin interface for Natal Feliz sponsorships."""

    list_display = ("child", "sponsor", "event")
    list_filter = ("event",)
    search_fields = (
        "event__name",
        "child__name",
        "child__mother_name",
        "sponsor__name",
    )


@admin.register(ChristmasEvent)
class ChristmasEventAdmin(admin.ModelAdmin):
    """Admin interface for Natal Feliz events."""

    list_display = ("name", "event_date", "event_time")
    search_fields = ("name",)
