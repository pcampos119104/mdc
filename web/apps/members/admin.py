"""Admin configuration for the members app."""

from django.contrib import admin

from .models import Address, Member


class AddressInline(admin.StackedInline):
    """Manage a member address inside the member admin page."""

    model = Address
    extra = 0


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    """Admin interface for member records."""

    list_display = (
        "name",
        "registration_type",
        "classifications_display",
        "profession",
        "email",
        "phone",
        "baptism_date",
        "acclamation_date",
        "include_in_birthday_list",
        "is_active",
        "created_at",
    )
    list_filter = ("registration_type", "include_in_birthday_list", "is_active")
    search_fields = (
        "name",
        "email",
        "cpf",
        "profession",
        "phone",
        "father_name",
        "mother_name",
        "spouse_name",
    )
    inlines = [AddressInline]

    @admin.display(description="Classificação")
    def classifications_display(self, obj):
        """Return member classifications for the admin changelist."""
        return obj.get_classifications_display()


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    """Admin interface for member addresses."""

    list_display = ("member", "city", "state", "district")
    search_fields = ("member__name", "street", "district", "city", "state")
