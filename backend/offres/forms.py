from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from commun.utils import ajouter_mois
from referentiels.models import CanalPublication, TypeStage

from .models import Besoin, Offre, Publication


def _helper(label="Enregistrer"):
    h = FormHelper()
    h.add_input(Submit("submit", label, css_class="btn-primary"))
    return h


def _valider_duree_type_stage(cleaned, prefix_debut="date_debut", prefix_fin="date_fin"):
    """Vérifie que la durée (fin − début) est dans les bornes du type de stage."""
    type_stage = cleaned.get("type_stage")
    date_debut = cleaned.get(prefix_debut)
    date_fin = cleaned.get(prefix_fin)
    if not (type_stage and date_debut and date_fin):
        return
    date_min_fin = ajouter_mois(date_debut, type_stage.duree_min_mois)
    date_max_fin = ajouter_mois(date_debut, type_stage.duree_max_mois)
    if date_fin < date_min_fin:
        raise forms.ValidationError(
            f"La durée est trop courte pour ce type de stage "
            f"(minimum {type_stage.duree_min_mois} mois — fin au plus tôt le {date_min_fin.strftime('%d/%m/%Y')})."
        )
    if date_fin > date_max_fin:
        raise forms.ValidationError(
            f"La durée est trop longue pour ce type de stage "
            f"(maximum {type_stage.duree_max_mois} mois — fin au plus tard le {date_max_fin.strftime('%d/%m/%Y')})."
        )


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

    def clean(self):
        cleaned = super().clean()
        _valider_duree_type_stage(cleaned)
        return cleaned


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

    def clean(self):
        cleaned = super().clean()
        _valider_duree_type_stage(cleaned)
        return cleaned


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
