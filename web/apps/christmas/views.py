"""Views for the Natal Feliz campaign."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from .forms import ChildForm, ChristmasEventForm, ChristmasSponsorshipForm
from .models import Child, ChristmasEvent, ChristmasSponsorship
from .permissions import christmas_admin_required
from .services.labels import generate_sponsorship_labels_pdf


@christmas_admin_required
def event_list(request):
    """Display Natal Feliz events, optionally filtered by name."""
    query = request.GET.get("q", "").strip()
    events = ChristmasEvent.objects.annotate(
        sponsorship_count=Count("sponsorships")
    ).order_by("-event_date", "-event_time", "name")

    if query:
        events = events.filter(name__icontains=query)

    paginator = Paginator(events, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "christmas/event_list.html",
        {"page_obj": page_obj, "query": query},
    )


def _event_form_context(form, *, title, submit_label):
    """Build context shared by event create and update forms."""
    return {
        "form": form,
        "title": title,
        "submit_label": submit_label,
    }


@method_decorator(christmas_admin_required, name="dispatch")
class ChristmasEventCreateView(View):
    """Create a Natal Feliz event."""

    def get(self, request):
        """Display the event creation form."""
        return render(
            request,
            "christmas/event_form.html",
            _event_form_context(
                ChristmasEventForm(),
                title="Novo evento",
                submit_label="Salvar evento",
            ),
        )

    def post(self, request):
        """Validate and create a Natal Feliz event."""
        form = ChristmasEventForm(request.POST)
        if form.is_valid():
            event = form.save()
            messages.success(request, f"Evento {event.name} criado com sucesso.")
            return redirect("christmas:event_list")

        return render(
            request,
            "christmas/event_form.html",
            _event_form_context(
                form,
                title="Novo evento",
                submit_label="Salvar evento",
            ),
        )


@christmas_admin_required
def event_detail(request, pk):
    """Display a Natal Feliz event."""
    event = get_object_or_404(ChristmasEvent, pk=pk)
    return render(
        request,
        "christmas/event_detail.html",
        {
            "event": event,
            "sponsorship_count": event.sponsorships.count(),
        },
    )


@christmas_admin_required
def event_labels_pdf(request, pk):
    """Generate a printable PDF with labels for all event sponsorships."""
    event = get_object_or_404(ChristmasEvent, pk=pk)
    sponsorships = list(
        event.sponsorships.select_related("sponsor", "child").order_by("pk")
    )
    if not sponsorships:
        raise Http404("Evento sem apadrinhamentos para gerar etiquetas.")

    pdf_content = generate_sponsorship_labels_pdf(event, sponsorships)
    response = HttpResponse(pdf_content, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="natal-feliz-evento-{event.pk}-etiquetas.pdf"'
    )
    return response


@method_decorator(christmas_admin_required, name="dispatch")
class ChristmasEventUpdateView(View):
    """Update a Natal Feliz event."""

    def get(self, request, pk):
        """Display the event update form."""
        event = get_object_or_404(ChristmasEvent, pk=pk)
        return render(
            request,
            "christmas/event_form.html",
            _event_form_context(
                ChristmasEventForm(instance=event),
                title=f"Editar {event.name}",
                submit_label="Atualizar evento",
            ),
        )

    def post(self, request, pk):
        """Validate and update a Natal Feliz event."""
        event = get_object_or_404(ChristmasEvent, pk=pk)
        form = ChristmasEventForm(request.POST, instance=event)
        if form.is_valid():
            event = form.save()
            messages.success(request, "Evento atualizado com sucesso.")
            return redirect("christmas:event_detail", pk=event.pk)

        return render(
            request,
            "christmas/event_form.html",
            _event_form_context(
                form,
                title=f"Editar {event.name}",
                submit_label="Atualizar evento",
            ),
        )


@method_decorator(christmas_admin_required, name="dispatch")
class ChristmasEventRemoveView(View):
    """Permanently delete a Natal Feliz event after confirmation."""

    def get(self, request, pk):
        """Display the event removal confirmation page."""
        event = get_object_or_404(ChristmasEvent, pk=pk)
        return render(
            request,
            "christmas/event_confirm_remove.html",
            {"event": event},
        )

    def post(self, request, pk):
        """Delete an event and its sponsorships."""
        event = get_object_or_404(ChristmasEvent, pk=pk)
        event_name = event.name
        event.delete()
        messages.success(request, f"Evento {event_name} removido com sucesso.")
        return redirect("christmas:event_list")


@christmas_admin_required
def sponsorship_list(request, event_pk):
    """Display sponsorships belonging to a Natal Feliz event."""
    event = get_object_or_404(ChristmasEvent, pk=event_pk)
    query = request.GET.get("q", "").strip()
    sponsorships = ChristmasSponsorship.objects.filter(event=event).select_related(
        "sponsor",
        "child",
    )

    if query:
        sponsorships = sponsorships.filter(
            Q(sponsor__name__icontains=query)
            | Q(child__name__icontains=query)
            | Q(child__mother_name__icontains=query)
        )

    paginator = Paginator(sponsorships, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "christmas/sponsorship_list.html",
        {"event": event, "page_obj": page_obj, "query": query},
    )


def _sponsorship_form_context(event, form, *, title, submit_label):
    """Build context shared by sponsorship create and update forms."""
    return {
        "event": event,
        "form": form,
        "title": title,
        "submit_label": submit_label,
    }


@method_decorator(christmas_admin_required, name="dispatch")
class ChristmasSponsorshipCreateView(View):
    """Create a sponsorship inside a Natal Feliz event."""

    def get(self, request, event_pk):
        """Display the sponsorship creation form."""
        event = get_object_or_404(ChristmasEvent, pk=event_pk)
        return render(
            request,
            "christmas/sponsorship_form.html",
            _sponsorship_form_context(
                event,
                ChristmasSponsorshipForm(event=event),
                title="Novo apadrinhamento",
                submit_label="Salvar apadrinhamento",
            ),
        )

    def post(self, request, event_pk):
        """Validate and create a sponsorship in the selected event."""
        event = get_object_or_404(ChristmasEvent, pk=event_pk)
        form = ChristmasSponsorshipForm(request.POST, event=event)
        if form.is_valid():
            sponsorship = form.save(commit=False)
            sponsorship.event = event
            sponsorship.save()
            messages.success(
                request,
                f"Apadrinhamento de {sponsorship.child.name} cadastrado com sucesso.",
            )
            return redirect("christmas:sponsorship_list", event_pk=event.pk)

        return render(
            request,
            "christmas/sponsorship_form.html",
            _sponsorship_form_context(
                event,
                form,
                title="Novo apadrinhamento",
                submit_label="Salvar apadrinhamento",
            ),
        )


def _get_event_sponsorship(event, pk):
    """Return a sponsorship only when it belongs to the selected event."""
    return get_object_or_404(
        ChristmasSponsorship.objects.select_related("sponsor", "child", "event"),
        event=event,
        pk=pk,
    )


@christmas_admin_required
def sponsorship_detail(request, event_pk, pk):
    """Display a sponsorship belonging to a Natal Feliz event."""
    event = get_object_or_404(ChristmasEvent, pk=event_pk)
    sponsorship = _get_event_sponsorship(event, pk)
    return render(
        request,
        "christmas/sponsorship_detail.html",
        {"event": event, "sponsorship": sponsorship},
    )


@method_decorator(christmas_admin_required, name="dispatch")
class ChristmasSponsorshipUpdateView(View):
    """Update a sponsorship belonging to a Natal Feliz event."""

    def get(self, request, event_pk, pk):
        """Display the sponsorship update form."""
        event = get_object_or_404(ChristmasEvent, pk=event_pk)
        sponsorship = _get_event_sponsorship(event, pk)
        return render(
            request,
            "christmas/sponsorship_form.html",
            _sponsorship_form_context(
                event,
                ChristmasSponsorshipForm(instance=sponsorship, event=event),
                title=f"Editar apadrinhamento de {sponsorship.child.name}",
                submit_label="Atualizar apadrinhamento",
            ),
        )

    def post(self, request, event_pk, pk):
        """Validate and update a sponsorship in the selected event."""
        event = get_object_or_404(ChristmasEvent, pk=event_pk)
        sponsorship = _get_event_sponsorship(event, pk)
        form = ChristmasSponsorshipForm(
            request.POST,
            instance=sponsorship,
            event=event,
        )
        if form.is_valid():
            sponsorship = form.save()
            messages.success(request, "Apadrinhamento atualizado com sucesso.")
            return redirect(
                "christmas:sponsorship_detail",
                event_pk=event.pk,
                pk=sponsorship.pk,
            )

        return render(
            request,
            "christmas/sponsorship_form.html",
            _sponsorship_form_context(
                event,
                form,
                title=f"Editar apadrinhamento de {sponsorship.child.name}",
                submit_label="Atualizar apadrinhamento",
            ),
        )


@method_decorator(christmas_admin_required, name="dispatch")
class ChristmasSponsorshipRemoveView(View):
    """Permanently delete a sponsorship after confirmation."""

    def get(self, request, event_pk, pk):
        """Display the sponsorship removal confirmation page."""
        event = get_object_or_404(ChristmasEvent, pk=event_pk)
        sponsorship = _get_event_sponsorship(event, pk)
        return render(
            request,
            "christmas/sponsorship_confirm_remove.html",
            {"event": event, "sponsorship": sponsorship},
        )

    def post(self, request, event_pk, pk):
        """Delete a sponsorship and return to its event list."""
        event = get_object_or_404(ChristmasEvent, pk=event_pk)
        sponsorship = _get_event_sponsorship(event, pk)
        child_name = sponsorship.child.name
        sponsorship.delete()
        messages.success(
            request,
            f"Apadrinhamento de {child_name} removido com sucesso.",
        )
        return redirect("christmas:sponsorship_list", event_pk=event.pk)


@christmas_admin_required
def child_list(request):
    """Display Natal Feliz children, optionally filtered by name."""
    query = request.GET.get("q", "").strip()
    children = Child.objects.all()

    if query:
        children = children.filter(
            Q(name__icontains=query) | Q(mother_name__icontains=query)
        )

    paginator = Paginator(children, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "christmas/child_list.html",
        {"page_obj": page_obj, "query": query},
    )


@method_decorator(christmas_admin_required, name="dispatch")
class ChildCreateView(View):
    """Create a child registration for the Natal Feliz campaign."""

    def get(self, request):
        """Display the child creation form."""
        return render(
            request,
            "christmas/child_form.html",
            _child_form_context(
                ChildForm(),
                title="Nova criança",
                submit_label="Salvar criança",
            ),
        )

    def post(self, request):
        """Validate and create a child registration."""
        form = ChildForm(request.POST)
        if form.is_valid():
            child = form.save()
            messages.success(request, f"Criança {child.name} cadastrada com sucesso.")
            return redirect("christmas:child_list")

        return render(
            request,
            "christmas/child_form.html",
            _child_form_context(
                form,
                title="Nova criança",
                submit_label="Salvar criança",
            ),
        )


def _child_form_context(form, *, title, submit_label):
    """Build context shared by child create and update forms."""
    return {
        "form": form,
        "title": title,
        "submit_label": submit_label,
    }


@christmas_admin_required
def child_detail(request, pk):
    """Display a Natal Feliz child registration."""
    child = get_object_or_404(Child, pk=pk)
    return render(request, "christmas/child_detail.html", {"child": child})


@method_decorator(christmas_admin_required, name="dispatch")
class ChildUpdateView(View):
    """Update a Natal Feliz child registration."""

    def get(self, request, pk):
        """Display the child update form."""
        child = get_object_or_404(Child, pk=pk)
        return render(
            request,
            "christmas/child_form.html",
            _child_form_context(
                ChildForm(instance=child),
                title=f"Editar {child.name}",
                submit_label="Atualizar criança",
            ),
        )

    def post(self, request, pk):
        """Validate and update a child registration."""
        child = get_object_or_404(Child, pk=pk)
        form = ChildForm(request.POST, instance=child)
        if form.is_valid():
            child = form.save()
            messages.success(request, f"Cadastro de {child.name} atualizado com sucesso.")
            return redirect("christmas:child_detail", pk=child.pk)

        return render(
            request,
            "christmas/child_form.html",
            _child_form_context(
                form,
                title=f"Editar {child.name}",
                submit_label="Atualizar criança",
            ),
        )


@method_decorator(christmas_admin_required, name="dispatch")
class ChildRemoveView(View):
    """Soft delete a Natal Feliz child after confirmation."""

    def get(self, request, pk):
        """Display the child removal confirmation page."""
        child = get_object_or_404(Child, pk=pk)
        return render(
            request,
            "christmas/child_confirm_remove.html",
            {"child": child},
        )

    def post(self, request, pk):
        """Soft delete a child and return to the campaign list."""
        child = get_object_or_404(Child, pk=pk)
        child_name = child.name
        child.delete()
        messages.success(request, f"Criança {child_name} removida da lista com sucesso.")
        return redirect("christmas:child_list")
