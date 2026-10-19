"""Forms for the Natal Feliz campaign."""

from django import forms

from apps.members.models import Member

from .models import Child, ChristmasEvent, ChristmasSponsorship


def _brazilian_date_input():
    """Return a date widget that displays and submits dates as dd/mm/yyyy."""
    return forms.DateInput(
        attrs={
            "autocomplete": "off",
            "date_mask": True,
            "inputmode": "numeric",
            "maxlength": "10",
            "pattern": r"\d{2}/\d{2}/\d{4}",
            "placeholder": "dd/mm/aaaa",
            "title": "Informe uma data no formato dd/mm/aaaa.",
        },
        format="%d/%m/%Y",
    )


def _time_input():
    """Return a browser-native time widget using hours and minutes."""
    return forms.TimeInput(
        attrs={"type": "time"},
        format="%H:%M",
    )


class ChildForm(forms.ModelForm):
    """Validate the registration data for a Natal Feliz child."""

    class Meta:
        model = Child
        fields = ["name", "mother_name", "birth_date", "clothing_size"]
        labels = {
            "name": "Nome completo da criança",
            "mother_name": "Nome completo da mãe",
            "birth_date": "Data de nascimento",
            "clothing_size": "Tamanho da roupa",
        }
        widgets = {
            "birth_date": _brazilian_date_input(),
            "clothing_size": forms.NumberInput(
                attrs={"inputmode": "numeric", "min": 0},
            ),
        }
        error_messages = {
            "name": {"required": "Informe o nome da criança."},
            "mother_name": {"required": "Informe o nome da mãe."},
            "birth_date": {
                "required": "Informe a data de nascimento.",
                "invalid": "Informe uma data válida no formato dd/mm/aaaa.",
            },
            "clothing_size": {
                "required": "Informe o tamanho da roupa.",
                "invalid": "Informe um tamanho de roupa válido.",
                "min_value": "Informe um tamanho de roupa válido.",
            },
        }

    def __init__(self, *args, **kwargs):
        """Configure parsing for the Brazilian birth date input."""
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].input_formats = ["%d/%m/%Y"]


class ChristmasEventForm(forms.ModelForm):
    """Validate the scheduling data for a Natal Feliz event."""

    class Meta:
        model = ChristmasEvent
        fields = ["name", "event_date", "event_time", "label_note"]
        labels = {
            "name": "Nome do evento",
            "event_date": "Data do evento",
            "event_time": "Horário do evento",
            "label_note": "Observação da etiqueta",
        }
        widgets = {
            "event_date": _brazilian_date_input(),
            "event_time": _time_input(),
            "label_note": forms.TextInput(
                attrs={"placeholder": "Ex.: Entregar o presente sem embalagem"}
            ),
        }
        error_messages = {
            "name": {"required": "Informe o nome do evento."},
            "event_date": {
                "required": "Informe a data do evento.",
                "invalid": "Informe uma data válida no formato dd/mm/aaaa.",
            },
            "event_time": {
                "required": "Informe o horário do evento.",
                "invalid": "Informe um horário válido.",
            },
            "label_note": {
                "max_length": "A observação deve ter no máximo 100 caracteres.",
            },
        }

    def __init__(self, *args, **kwargs):
        """Configure Brazilian date and time parsing."""
        super().__init__(*args, **kwargs)
        self.fields["event_date"].input_formats = ["%d/%m/%Y"]
        self.fields["event_time"].input_formats = ["%H:%M"]


class ChristmasSponsorshipForm(forms.ModelForm):
    """Validate a sponsor and child relationship for an event."""

    class Meta:
        model = ChristmasSponsorship
        fields = ["sponsor", "child"]
        labels = {
            "sponsor": "Padrinho",
            "child": "Criança",
        }
        error_messages = {
            "sponsor": {"required": "Selecione o padrinho."},
            "child": {"required": "Selecione a criança."},
        }

    def __init__(self, *args, **kwargs):
        """Limit sponsors to active church members and order form choices."""
        self.event = kwargs.pop("event")
        super().__init__(*args, **kwargs)
        self.instance.event = self.event
        self.fields["sponsor"].queryset = Member.objects.filter(
            is_church_member=True,
            is_active=True,
        ).order_by("name")
        self.fields["child"].queryset = Child.objects.order_by("name")

    def clean(self):
        """Ensure a child has only one sponsor in the event."""
        cleaned_data = super().clean()
        child = cleaned_data.get("child")

        if child is None:
            return cleaned_data

        existing_sponsorships = ChristmasSponsorship.objects.filter(
            event=self.event,
            child=child,
        )
        if self.instance.pk:
            existing_sponsorships = existing_sponsorships.exclude(pk=self.instance.pk)

        if existing_sponsorships.exists():
            self.add_error(
                "child",
                "Esta criança já possui um padrinho neste evento.",
            )

        return cleaned_data
