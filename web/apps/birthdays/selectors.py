"""Reusable selectors for birthday reports."""

from datetime import timedelta

from django.db.models import Q

from apps.members.models import Member


def iter_period_dates(period_start, period_end):
    """Yield all dates between period_start and period_end, inclusive."""
    current_date = period_start
    while current_date <= period_end:
        yield current_date
        current_date += timedelta(days=1)


def get_birthday_members_for_period(period_start, period_end):
    """Return active members whose birthday day/month is inside the period."""
    dates_by_month_day = {
        (current_date.month, current_date.day): current_date
        for current_date in iter_period_dates(period_start, period_end)
    }

    birthday_filter = Q()
    for month, day in dates_by_month_day:
        birthday_filter |= Q(birth_date__month=month, birth_date__day=day)

    if not birthday_filter:
        return []

    members = list(
        Member.objects.filter(
            birthday_filter,
            birth_date__isnull=False,
            include_in_birthday_list=True,
            is_active=True,
        )
    )

    for member in members:
        member.birthday_occurrence = dates_by_month_day[
            (member.birth_date.month, member.birth_date.day)
        ]

    return sorted(
        members,
        key=lambda member: (member.birthday_occurrence, member.name.casefold()),
    )


def get_latest_birthday_reports(limit=5):
    """Return the latest generated birthday reports."""
    from .models import BirthdayReport

    return BirthdayReport.objects.order_by("-generated_at")[:limit]


def get_automatic_report_for_period(period_start, period_end):
    """Return the automatic report for a period, if it already exists."""
    from .models import BirthdayReport

    return BirthdayReport.objects.filter(
        period_start=period_start,
        period_end=period_end,
        is_automatic=True,
    ).first()
