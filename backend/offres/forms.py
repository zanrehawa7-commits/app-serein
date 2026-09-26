from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from referentiels.models import CanalPublication, TypeStage

from .models import Besoin, Offre, Publication


def _helper(label="Enregistrer"):
    h = FormHelper()
    h.add_input(Submit("submit", label, css_class="btn-primary"))
    return h


class BesoinForm(forms.ModelForm):
    class Meta:
        model = Besoin
        fields = ["departement", "type_stage", "date_debut", "date_fin", "profil_recherche", "nombre_places"]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
            "profil_recherche": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()
        self.fields["type_stage"].queryset = TypeStage.objects.filter(actif=True)


class OffreForm(forms.ModelForm):
    class Meta:
        model = Offre
        fields = ["type_stage", "titre", "description", "profil_recherche", "date_debut", "date_fin", "nombre_places"]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "profil_recherche": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()
        self.fields["type_stage"].queryset = TypeStage.objects.filter(actif=True)


class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ["canal", "url", "date_publication", "description"]
        widgets = {
            "date_publication": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper("Publier")
        self.fields["canal"].queryset = CanalPublication.objects.filter(actif=True)
