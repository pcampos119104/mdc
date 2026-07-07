"""Views for member management."""

import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .forms import AddressForm, MemberForm, PhoneFormSet
from .models import Address, Member


def _only_digits(value):
    """Return only numeric characters from a search term."""
    return re.sub(r"\D", "", value or "")


@login_required
def member_list(request):
    """Display the list of members, optionally filtered by search query."""
    query = request.GET.get("q", "").strip()
    query_digits = _only_digits(query)
    members = Member.objects.select_related("address").prefetch_related("phones")

    if query:
        search_filter = (
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(cpf__icontains=query)
            | Q(phones__number__icontains=query)
            | Q(phones__contact_name__icontains=query)
            | Q(address__city__icontains=query)
            | Q(address__district__icontains=query)
        )

        if query_digits:
            search_filter |= Q(cpf__icontains=query_digits) | Q(
                phones__number__icontains=query_digits
            )

        members = members.filter(search_filter).distinct()

    return render(
        request,
        "members/member_list.html",
        {
            "members": members,
            "query": query,
        },
    )


def _get_member_address(member):
    """Return a member address instance when one exists."""
    try:
        return member.address
    except Address.DoesNotExist:
        return None


def _member_form_context(member_form, address_form, phone_formset, *, title, submit_label):
    """Build context data shared by member create and update views."""
    return {
        "member_form": member_form,
        "address_form": address_form,
        "phone_formset": phone_formset,
        "title": title,
        "submit_label": submit_label,
        "cancel_url": reverse("members:list"),
    }


class MemberCreateView(LoginRequiredMixin, View):
    """Create a new church member with address and phone numbers."""

    def get(self, request):
        """Display the member creation form."""
        context = _member_form_context(
            MemberForm(),
            AddressForm(),
            PhoneFormSet(),
            title="Novo membro",
            submit_label="Salvar membro",
        )
        return render(request, "members/member_form.html", context)

    def post(self, request):
        """Validate and create a member with address and phone numbers."""
        member = Member()
        member_form = MemberForm(request.POST, request.FILES, instance=member)
        address_form = AddressForm(request.POST)
        phone_formset = PhoneFormSet(request.POST, instance=member)

        if member_form.is_valid() and address_form.is_valid() and phone_formset.is_valid():
            with transaction.atomic():
                member = member_form.save()

                address = address_form.save(commit=False)
                address.member = member
                address.save()

                phone_formset.instance = member
                phone_formset.save()

            messages.success(request, "Membro criado com sucesso.")
            return redirect("members:list")

        context = _member_form_context(
            member_form,
            address_form,
            phone_formset,
            title="Novo membro",
            submit_label="Salvar membro",
        )
        return render(request, "members/member_form.html", context)


class MemberUpdateView(LoginRequiredMixin, View):
    """Update a church member with address and phone numbers."""

    def get(self, request, pk):
        """Display the member update form."""
        member = get_object_or_404(
            Member.objects.select_related("address").prefetch_related("phones"),
            pk=pk,
        )
        context = _member_form_context(
            MemberForm(instance=member),
            AddressForm(instance=_get_member_address(member)),
            PhoneFormSet(instance=member),
            title=f"Editar {member.name}",
            submit_label="Atualizar membro",
        )
        return render(request, "members/member_form.html", context)

    def post(self, request, pk):
        """Validate and update a member with address and phone numbers."""
        member = get_object_or_404(Member, pk=pk)
        member_form = MemberForm(request.POST, request.FILES, instance=member)
        address_form = AddressForm(
            request.POST,
            instance=_get_member_address(member),
        )
        phone_formset = PhoneFormSet(request.POST, instance=member)

        if member_form.is_valid() and address_form.is_valid() and phone_formset.is_valid():
            with transaction.atomic():
                member = member_form.save()

                address = address_form.save(commit=False)
                address.member = member
                address.save()

                phone_formset.save()

            messages.success(request, "Membro atualizado com sucesso.")
            return redirect("members:list")

        context = _member_form_context(
            member_form,
            address_form,
            phone_formset,
            title=f"Editar {member.name}",
            submit_label="Atualizar membro",
        )
        return render(request, "members/member_form.html", context)


class MemberRemoveView(LoginRequiredMixin, View):
    """Soft delete a church member after confirmation."""

    def get(self, request, pk):
        """Display the member removal confirmation page."""
        member = get_object_or_404(
            Member.objects.select_related("address").prefetch_related("phones"),
            pk=pk,
        )
        return render(request, "members/member_confirm_remove.html", {"member": member})

    def post(self, request, pk):
        """Soft delete a member and return to the members list."""
        member = get_object_or_404(Member, pk=pk)
        member_name = member.name
        member.delete()

        messages.success(request, f"Membro {member_name} removido da lista com sucesso.")
        return redirect("members:list")
