from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from .models import CanalPublication, Departement, Etablissement, Personnel, TypeStage


def _helper(label_submit="Enregistrer"):
    h = FormHelper()
    h.add_input(Submit("submit", label_submit, css_class="btn-primary"))
    return h


class DepartementCreerForm(forms.ModelForm):
    # Champ non-modèle : personnels actifs sans département (disponibles pour rattachement)
    nouveau_responsable = forms.ModelChoiceField(
        queryset=Personnel.objects.none(),
        required=False,
        label="Responsable (optionnel)",
        help_text="Personnels actifs sans département actuellement affecté.",
    )

    class Meta:
        model = Departement
        fields = ["nom", "description", "actif"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()
        self.fields["nouveau_responsable"].queryset = Personnel.objects.filter(
            departement__isnull=True, actif=True
        ).order_by("nom", "prenom")


class DepartementModifierForm(forms.ModelForm):
    # Champ non-modèle pour contourner le save() automatique et passer par le service
    responsable = forms.ModelChoiceField(
        queryset=Personnel.objects.none(),
        required=False,
        label="Responsable",
        help_text="Personnels actifs de ce département (RG31).",
    )

    class Meta:
        model = Departement
        fields = ["nom", "description", "actif"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()
        if self.instance and self.instance.pk:
            qs = Personnel.objects.filter(
                departement=self.instance, actif=True
            ).order_by("nom", "prenom")
            self.fields["responsable"].queryset = qs
            self.fields["responsable"].initial = self.instance.responsable


class PersonnelForm(forms.ModelForm):
    designer_responsable = forms.BooleanField(
        required=False,
        label="Désigner comme responsable du département",
    )

    class Meta:
        model = Personnel
        # Pas de champ « actif » : l'activation passe uniquement par PersonnelDesactiverView, qui
        # applique RG-P3 / RG-P4 (responsable de département, maître d'un stage en cours).
        fields = ["nom", "prenom", "fonction", "telephone", "email", "departement"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()
        self.fields["departement"].queryset = Departement.objects.filter(actif=True).order_by("nom")
        self.fields["departement"].required = False

    def clean(self):
        cleaned = super().clean()
        nouveau_dept = cleaned.get("departement")

        if self.instance and self.instance.pk:
            # Correction 3 : interdit de changer le département si le personnel est responsable
            dept_dirige = Departement.objects.filter(responsable=self.instance).first()
            if dept_dirige and nouveau_dept != self.instance.departement:
                raise forms.ValidationError(
                    f"Ce personnel est responsable du département « {dept_dirige.nom} ». "
                    "Désignez d'abord un autre responsable ou décochez la case."
                )

        # Désigner responsable exige un département
        if cleaned.get("designer_responsable") and not nouveau_dept:
            raise forms.ValidationError(
                "Impossible de désigner comme responsable : aucun département sélectionné."
            )
        return cleaned


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
        fields = ["libelle", "description", "remunere", "actif", "duree_min_mois", "duree_max_mois"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()
        self.fields["duree_min_mois"].help_text = "Durée minimale en mois entiers (≥ 1)."
        self.fields["duree_max_mois"].help_text = "Durée maximale en mois entiers (≥ durée minimale)."

    def clean(self):
        cleaned = super().clean()
        min_m = cleaned.get("duree_min_mois")
        max_m = cleaned.get("duree_max_mois")
        if min_m is not None and max_m is not None and max_m < min_m:
            self.add_error(
                "duree_max_mois",
                "La durée maximale doit être supérieure ou égale à la durée minimale.",
            )
        return cleaned


class CanalPublicationForm(forms.ModelForm):
    class Meta:
        model = CanalPublication
        fields = ["nom", "description", "actif"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = _helper()
