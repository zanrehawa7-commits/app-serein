from django import forms
from django.forms import formset_factory, BaseFormSet
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .models import Candidat, Candidature, PieceJointe, TypeDemande, TypePiece
from .services import normaliser_telephone


class CandidatRechercheForm(forms.Form):
    q = forms.CharField(
        label="Recherche",
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Nom, prénom, téléphone ou email", "autofocus": True}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "get"
        self.helper.add_input(Submit("", "Rechercher", css_class="btn-primary"))


class CandidatForm(forms.ModelForm):
    class Meta:
        model = Candidat
        fields = [
            "nom", "prenom", "telephone", "email", "adresse",
            "niveau_etudes", "filiere", "etablissement", "etablissement_autre",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._instance_pk = self.instance.pk if self.instance and self.instance.pk else None
        self.fields["etablissement"].empty_label = "— Choisir un établissement —"
        self.fields["etablissement"].required = False
        self.fields["etablissement"].widget.attrs["class"] = "form-select"
        self.fields["etablissement_autre"].widget.attrs.update({
            "placeholder": "Ex : Université Joseph Ki-Zerbo, ISTIC Ouagadougou…",
            "class": "form-control",
        })
        self.helper = FormHelper()
        self.helper.form_tag = False

    def clean_telephone(self):
        tel = normaliser_telephone(self.cleaned_data["telephone"])
        if not tel:
            raise forms.ValidationError("Numéro de téléphone invalide.")
        qs = Candidat.objects.filter(telephone=tel)
        if self._instance_pk:
            qs = qs.exclude(pk=self._instance_pk)
        if qs.exists():
            raise forms.ValidationError("Un candidat avec ce numéro de téléphone existe déjà.")
        return tel

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("etablissement"):
            cleaned["etablissement_autre"] = ""
        return cleaned


class CandidatureForm(forms.ModelForm):
    class Meta:
        model = Candidature
        fields = [
            "departement", "type_stage", "type_demande", "offre",
            "debut_disponibilite", "fin_disponibilite", "duree_souhaitee", "commentaire",
        ]
        widgets = {
            "debut_disponibilite": forms.DateInput(attrs={"type": "date"}),
            "fin_disponibilite": forms.DateInput(attrs={"type": "date"}),
            "commentaire": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from offres.models import Offre
        self.fields["offre"].queryset = Offre.objects.filter(statut="OUVERTE")
        self.fields["offre"].required = False
        self.fields["offre"].empty_label = "— Aucune offre —"
        self.fields["offre"].help_text = (
            "À remplir uniquement si le candidat répond à une offre publiée."
        )
        self.fields["type_demande"].help_text = (
            "<strong>Spontanée</strong> : le candidat se présente de lui-même, sans offre. "
            "<strong>Suite à une offre</strong> : il répond à une offre publiée — "
            "vous devrez alors sélectionner l'offre ci-dessous."
        )
        self.fields["debut_disponibilite"].help_text = (
            "Date à partir de laquelle le candidat peut commencer son stage."
        )
        self.fields["fin_disponibilite"].help_text = (
            "Dernière date à laquelle le candidat est disponible."
        )
        self.fields["duree_souhaitee"].help_text = (
            "Durée souhaitée du stage, en mois entiers (ex : 2 pour deux mois)."
        )
        self.helper = FormHelper()
        self.helper.form_tag = False

    def clean(self):
        cleaned = super().clean()
        type_demande = cleaned.get("type_demande")
        offre = cleaned.get("offre")
        if type_demande == TypeDemande.SUITE_OFFRE and not offre:
            self.add_error("offre", "Une offre est obligatoire pour ce type de demande.")
        if type_demande == TypeDemande.SPONTANEE and offre:
            self.add_error("offre", "Une candidature spontanée ne doit pas être liée à une offre.")
        return cleaned


class PieceJointeForm(forms.Form):
    type_piece = forms.ChoiceField(
        choices=TypePiece.choices,
        label="Type de pièce",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fichier = forms.FileField(
        label="Fichier",
        help_text="Formats acceptés : PDF, JPG, PNG — 5 Mo max.",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

    def clean_fichier(self):
        fichier = self.cleaned_data.get("fichier")
        if not fichier:
            return fichier
        import os
        ext = os.path.splitext(fichier.name)[1].lower()
        if ext not in (".pdf", ".jpg", ".jpeg", ".png"):
            raise forms.ValidationError(
                f"Format non accepté ({ext}). Utilisez : PDF, JPG ou PNG."
            )
        if fichier.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Le fichier dépasse la taille maximale de 5 Mo.")
        return fichier


class BasePieceJointeFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        has_cv = any(
            form.cleaned_data.get("type_piece") == TypePiece.CV
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False)
        )
        if not has_cv:
            raise forms.ValidationError("Au moins un CV est obligatoire.")


PieceJointeFormSet = formset_factory(
    PieceJointeForm,
    formset=BasePieceJointeFormSet,
    extra=1,
    can_delete=False,
)
