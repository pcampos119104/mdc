"""Forms for member management views."""

from django import forms
from django.forms import inlineformset_factory

from .models import Member, MemberAddress, MemberPhone


FIELD_CLASS = (
    "block w-full rounded-lg border border-slate-300 bg-slate-50 p-2.5 "
    "text-sm text-slate-900 focus:border-blue-600 focus:ring-blue-600"
)
CHECKBOX_CLASS = (
    "h-4 w-4 rounded border-slate-300 bg-slate-100 text-blue-700 "
    "focus:ring-blue-600"
)
SELECT_CLASS = (
    "block w-full rounded-lg border border-slate-300 bg-slate-50 p-2.5 "
    "text-sm text-slate-900 focus:border-blue-600 focus:ring-blue-600"
)

PHONE_KIND_CHOICES = [
    (MemberPhone.KIND_MOBILE, "Celular"),
    (MemberPhone.KIND_HOME, "Residencial"),
    (MemberPhone.KIND_WORK, "Comercial"),
    (MemberPhone.KIND_CONTACT, "Contato"),
]


def _apply_widget_class(field):
    """Apply the project form CSS classes to a Django form field."""
    widget = field.widget

    if isinstance(widget, forms.CheckboxInput):
        css_class = CHECKBOX_CLASS
    elif isinstance(widget, forms.Select):
        css_class = SELECT_CLASS
    else:
        css_class = FIELD_CLASS

    existing_classes = widget.attrs.get("class", "")
    widget.attrs["class"] = f"{existing_classes} {css_class}".strip()


class MemberForm(forms.ModelForm):
    """Validate the main registration data for a member."""

    class Meta:
        model = Member
        fields = [
            "name",
            "registration_type",
            "person_type",
            "member_type",
            "cpf",
            "birth_date",
            "sex",
            "nationality",
            "birthplace",
            "email",
            "father_name",
            "mother_name",
            "spouse_name",
            "marital_status",
            "marriage_date",
            "is_active",
        ]
        labels = {
            "name": "Nome completo",
            "registration_type": "Tipo de cadastro",
            "person_type": "Classificacao",
            "member_type": "Tipo de membro",
            "cpf": "CPF",
            "birth_date": "Data de nascimento",
            "sex": "Sexo",
            "nationality": "Nacionalidade",
            "birthplace": "Naturalidade",
            "email": "E-mail",
            "father_name": "Nome do pai",
            "mother_name": "Nome da mae",
            "spouse_name": "Nome do conjuge",
            "marital_status": "Estado civil",
            "marriage_date": "Data do casamento",
            "is_active": "Cadastro ativo",
        }
        widgets = {
            "birth_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "marriage_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
        }

    def __init__(self, *args, **kwargs):
        """Style all member form fields for the server-rendered UI."""
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].input_formats = ["%Y-%m-%d"]
        self.fields["marriage_date"].input_formats = ["%Y-%m-%d"]

        for field in self.fields.values():
            _apply_widget_class(field)


class MemberAddressForm(forms.ModelForm):
    """Validate the residential address for a member."""

    class Meta:
        model = MemberAddress
        fields = [
            "postal_code",
            "country",
            "state",
            "city",
            "street",
            "street_number",
            "complement",
            "district",
        ]
        labels = {
            "postal_code": "CEP",
            "country": "Pais",
            "state": "Estado",
            "city": "Cidade",
            "street": "Logradouro",
            "street_number": "Numero",
            "complement": "Complemento",
            "district": "Bairro",
        }

    def __init__(self, *args, **kwargs):
        """Style all address form fields for the server-rendered UI."""
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            _apply_widget_class(field)


class MemberPhoneForm(forms.ModelForm):
    """Validate a phone number attached to a member."""

    kind = forms.ChoiceField(choices=PHONE_KIND_CHOICES, label="Tipo")

    class Meta:
        model = MemberPhone
        fields = [
            "kind",
            "number",
            "contact_name",
            "is_primary",
            "receives_sms",
            "has_whatsapp",
        ]
        labels = {
            "number": "Telefone",
            "contact_name": "Nome do contato",
            "is_primary": "Telefone principal",
            "receives_sms": "Recebe SMS",
            "has_whatsapp": "Possui WhatsApp",
        }

    def __init__(self, *args, **kwargs):
        """Style all phone form fields for the server-rendered UI."""
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            _apply_widget_class(field)


MemberPhoneFormSet = inlineformset_factory(
    Member,
    MemberPhone,
    form=MemberPhoneForm,
    extra=2,
    can_delete=True,
)
