from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from .models import CanalPublication, Departement, Etablissement, Membre, TypeStage


def _helper(label_submit="Enregistrer"):
    h = FormHelper()
    h.add_input(Submit("submit", label_submit, css_class="btn-primary"))
    return h


class DepartementCreerForm(forms.ModelForm):
    class Meta:
        model = Departement
        fields = ["nom", "description", "actif"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()


class DepartementModifierForm(forms.ModelForm):
    class Meta:
        model = Departement
        fields = ["nom", "description", "responsable", "actif"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()
        if self.instance.pk:
            self.fields["responsable"].queryset = Membre.objects.filter(
                departement=self.instance, actif=True
            )
            self.fields["responsable"].help_text = (
                "Uniquement les membres actifs de ce département (RG31)."
            )
        else:
            self.fields["responsable"].queryset = Membre.objects.none()


class MembreForm(forms.ModelForm):
    class Meta:
        model = Membre
        fields = ["nom", "prenom", "fonction", "telephone", "email", "departement"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()


class EtablissementForm(forms.ModelForm):
    class Meta:
        model = Etablissement
        fields = ["nom", "ville", "contact", "partenaire", "actif"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()


class TypeStageForm(forms.ModelForm):
    class Meta:
        model = TypeStage
        fields = ["libelle", "description", "remunere", "actif"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()


class CanalPublicationForm(forms.ModelForm):
    class Meta:
        model = CanalPublication
        fields = ["nom", "description", "actif"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()
