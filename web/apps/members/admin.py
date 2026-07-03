"""Admin configuration for the members app."""

from django.contrib import admin

from .models import Address, Member, Phone


class AddressInline(admin.StackedInline):
    """Manage a member address inside the member admin page."""

    model = Address
    extra = 0


class PhoneInline(admin.TabularInline):
    """Manage member phone numbers inside the member admin page."""

    model = Phone
    extra = 0


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    """Admin interface for member records."""

    list_display = (
        "name",
        "person_type",
        "member_type",
        "email",
        "include_in_birthday_list",
        "is_active",
        "created_at",
    )
    list_filter = ("person_type", "member_type", "include_in_birthday_list", "is_active")
    search_fields = ("name", "email", "cpf", "father_name", "mother_name", "spouse_name")
    inlines = [AddressInline, PhoneInline]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    """Admin interface for member addresses."""

    list_display = ("member", "city", "state", "district")
    search_fields = ("member__name", "street", "district", "city", "state")


@admin.register(Phone)
class PhoneAdmin(admin.ModelAdmin):
    """Admin interface for member phone numbers."""

    list_display = ("member", "kind", "number", "is_primary", "has_whatsapp")
    list_filter = ("kind", "is_primary", "has_whatsapp", "receives_sms")
    search_fields = ("member__name", "number", "contact_name")
