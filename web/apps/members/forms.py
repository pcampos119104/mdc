"""Forms for member management views."""

import re

from django import forms

from .models import Address, Member


def _only_digits(value):
    """Return only numeric characters from a user-submitted value."""
    return re.sub(r"\D", "", value or "")


class MemberForm(forms.ModelForm):
    """Validate the main registration data for a member."""

    cpf = forms.CharField(required=False, max_length=14, label="CPF")
    phone = forms.CharField(required=False, max_length=20, label="Telefone")
    classifications = forms.MultipleChoiceField(
        choices=Member.Classification.choices,
        required=False,
        label="Classificação",
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Member
        fields = [
            "name",
            "photo",
            "registration_type",
            "classifications",
            "cpf",
            "birth_date",
            "baptism_date",
            "acclamation_date",
            "include_in_birthday_list",
            "sex",
            "birthplace",
            "profession",
            "email",
            "phone",
            "father_name",
            "mother_name",
            "spouse_name",
            "marital_status",
            "marriage_date",
            "is_active",
            "inactive_reason",
        ]
        labels = {
            "name": "Nome completo",
            "photo": "Foto",
            "registration_type": "Tipo de cadastro",
            "cpf": "CPF",
            "birth_date": "Data de nascimento",
            "baptism_date": "Data do batismo",
            "acclamation_date": "Data da aclamação",
            "include_in_birthday_list": "Incluir na lista de aniversariantes",
            "sex": "Sexo",
            "birthplace": "Naturalidade",
            "profession": "Profissão",
            "email": "E-mail",
            "phone": "Telefone",
            "father_name": "Nome do pai",
            "mother_name": "Nome da mãe",
            "spouse_name": "Nome do cônjuge",
            "marital_status": "Estado civil",
            "marriage_date": "Data do casamento",
            "is_active": "Cadastro ativo",
            "inactive_reason": "Motivo da inativação",
        }
        widgets = {
            "photo": forms.FileInput(attrs={"accept": "image/*"}),
            "registration_type": forms.Select,
            "birth_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "baptism_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "acclamation_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "marriage_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "inactive_reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        """Configure date parsing for browser date inputs."""
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].input_formats = ["%Y-%m-%d"]
        self.fields["baptism_date"].input_formats = ["%Y-%m-%d"]
        self.fields["acclamation_date"].input_formats = ["%Y-%m-%d"]
        self.fields["marriage_date"].input_formats = ["%Y-%m-%d"]

    def clean_cpf(self):
        """Store CPF with digits only while accepting common masks."""
        cpf = self.cleaned_data.get("cpf")

        if not cpf:
            return None

        digits = _only_digits(cpf)
        if len(digits) != 11:
            raise forms.ValidationError("Informe um CPF com 11 dígitos.")

        return digits

    def clean_phone(self):
        """Store phone numbers with digits only while accepting common masks."""
        phone = self.cleaned_data.get("phone")

        if not phone:
            return ""

        digits = _only_digits(phone)
        if not 8 <= len(digits) <= 15:
            raise forms.ValidationError("Informe um telefone com 8 a 15 dígitos.")

        return digits


class AddressForm(forms.ModelForm):
    """Validate the residential address for a member."""

    postal_code = forms.CharField(required=False, max_length=9, label="CEP")

    class Meta:
        model = Address
        fields = [
            "postal_code",
            "state",
            "city",
            "street",
            "street_number",
            "complement",
            "district",
        ]
        labels = {
            "postal_code": "CEP",
            "state": "Estado",
            "city": "Cidade",
            "street": "Logradouro",
            "street_number": "Número",
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
            raise forms.ValidationError("Informe um CEP com 8 dígitos.")

        return digits

    def clean_state(self):
        """Store Brazilian state abbreviation in uppercase."""
        return (self.cleaned_data.get("state") or "").upper()
