"""Forms for member management views."""

import re

from django import forms
from django.forms import inlineformset_factory

from .models import Address, Member, Phone


PHONE_KIND_CHOICES = [
    (Phone.KIND_MOBILE, "Celular"),
    (Phone.KIND_HOME, "Residencial"),
    (Phone.KIND_WORK, "Comercial"),
    (Phone.KIND_CONTACT, "Contato"),
]


def _only_digits(value):
    """Return only numeric characters from a user-submitted value."""
    return re.sub(r"\D", "", value or "")


class MemberForm(forms.ModelForm):
    """Validate the main registration data for a member."""

    cpf = forms.CharField(required=False, max_length=14, label="CPF")

    class Meta:
        model = Member
        fields = [
            "name",
            "registration_type",
            "person_type",
            "member_type",
            "cpf",
            "birth_date",
            "include_in_birthday_list",
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
            "include_in_birthday_list": "Incluir na lista de aniversariantes",
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
        """Configure date parsing for browser date inputs."""
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].input_formats = ["%Y-%m-%d"]
        self.fields["marriage_date"].input_formats = ["%Y-%m-%d"]

    def clean_cpf(self):
        """Store CPF with digits only while accepting common masks."""
        cpf = self.cleaned_data.get("cpf")

        if not cpf:
            return None

        digits = _only_digits(cpf)
        if len(digits) != 11:
            raise forms.ValidationError("Informe um CPF com 11 digitos.")

        return digits


class AddressForm(forms.ModelForm):
    """Validate the residential address for a member."""

    postal_code = forms.CharField(required=False, max_length=9, label="CEP")

    class Meta:
        model = Address
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

    def clean_postal_code(self):
        """Store CEP with digits only while accepting common masks."""
        postal_code = self.cleaned_data.get("postal_code")

        if not postal_code:
            return ""

        digits = _only_digits(postal_code)
        if len(digits) != 8:
            raise forms.ValidationError("Informe um CEP com 8 digitos.")

        return digits

    def clean_state(self):
        """Store Brazilian state abbreviation in uppercase."""
        return (self.cleaned_data.get("state") or "").upper()


class PhoneForm(forms.ModelForm):
    """Validate a phone number attached to a member."""

    kind = forms.ChoiceField(choices=PHONE_KIND_CHOICES, label="Tipo")
    number = forms.CharField(max_length=20, label="Telefone")

    class Meta:
        model = Phone
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

    def clean_number(self):
        """Store phone numbers with digits only while accepting common masks."""
        number = self.cleaned_data.get("number")
        digits = _only_digits(number)

        if not 8 <= len(digits) <= 15:
            raise forms.ValidationError("Informe um telefone com 8 a 15 digitos.")

        return digits


PhoneFormSet = inlineformset_factory(
    Member,
    Phone,
    form=PhoneForm,
    extra=2,
    max_num=2,
    validate_max=True,
    can_delete=False,
)
