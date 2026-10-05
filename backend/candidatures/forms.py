from django import forms
from django.forms import formset_factory, BaseFormSet
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from commun.utils import ajouter_mois
from .models import Candidat, Candidature, PieceJointe, TypeDemande, TypePiece, MotifRefus
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


class CandidatureCreerForm(forms.ModelForm):
    """Formulaire de création de candidature (inclut la validation début >= aujourd'hui)."""

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
        self._init_commun()

    def _init_commun(self):
        from offres.models import Offre
        from referentiels.models import TypeStage
        self.fields["offre"].queryset = Offre.objects.filter(statut="OUVERTE")
        self.fields["offre"].required = False
        self.fields["offre"].empty_label = "— Aucune offre —"
        self.fields["offre"].help_text = (
            "À remplir uniquement si le candidat répond à une offre publiée."
        )
        self.fields["type_demande"].help_text = (
            "<strong>Spontanée</strong> : le candidat se présente de lui-même, sans offre. "
            "<strong>Suite à une offre</strong> : il répond à une offre publiée — "
            "vous devrez alors sélectionner l'offre ci-dessous. "
            "<strong>Autre</strong> : autre type de demande, sans offre."
        )
        self.fields["debut_disponibilite"].help_text = (
            "Date à partir de laquelle le candidat peut commencer son stage."
        )
        self.fields["fin_disponibilite"].help_text = (
            "Dernière date à laquelle le candidat est disponible (max 12 mois après le début)."
        )
        self.fields["duree_souhaitee"].help_text = (
            "Durée souhaitée du stage, en mois entiers."
        )
        # Injecter data-min/data-max sur chaque option du type_stage
        ts_qs = self.fields["type_stage"].queryset
        choices_with_attrs = []
        for ts in ts_qs:
            choices_with_attrs.append((ts.pk, ts.libelle, ts.duree_min_mois, ts.duree_max_mois))
        self._type_stage_bornes = {ts.pk: (ts.duree_min_mois, ts.duree_max_mois) for ts in ts_qs}
        self.helper = FormHelper()
        self.helper.form_tag = False

    def clean_debut_disponibilite(self):
        debut = self.cleaned_data.get("debut_disponibilite")
        if debut and debut < timezone.localdate():
            raise forms.ValidationError(
                "La date de début de disponibilité doit être aujourd'hui ou dans le futur."
            )
        return debut

    def clean(self):
        cleaned = super().clean()
        self._valider_rg09(cleaned)
        self._valider_fin_disponibilite(cleaned)
        self._valider_duree_souhaitee(cleaned)
        return cleaned

    def _valider_rg09(self, cleaned):
        type_demande = cleaned.get("type_demande")
        offre = cleaned.get("offre")
        if type_demande == TypeDemande.SUITE_OFFRE and not offre:
            self.add_error("offre", "Une offre est obligatoire pour ce type de demande.")
        if type_demande in (TypeDemande.SPONTANEE, TypeDemande.AUTRE) and offre:
            self.add_error("offre", "Ce type de demande ne doit pas être lié à une offre.")

    def _valider_fin_disponibilite(self, cleaned):
        debut = cleaned.get("debut_disponibilite")
        fin = cleaned.get("fin_disponibilite")
        if not (debut and fin):
            return
        if fin <= debut:
            self.add_error("fin_disponibilite", "La fin de disponibilité doit être postérieure au début.")
            return
        limite = ajouter_mois(debut, 12)
        if fin > limite:
            self.add_error(
                "fin_disponibilite",
                f"La fin de disponibilité ne peut pas dépasser 12 mois après le début "
                f"(au plus tard le {limite.strftime('%d/%m/%Y')}).",
            )

    def _valider_duree_souhaitee(self, cleaned):
        type_stage = cleaned.get("type_stage")
        duree = cleaned.get("duree_souhaitee")
        if not (type_stage and duree is not None):
            return
        if duree < type_stage.duree_min_mois:
            self.add_error(
                "duree_souhaitee",
                f"La durée minimale pour « {type_stage} » est de {type_stage.duree_min_mois} mois.",
            )
        elif duree > type_stage.duree_max_mois:
            self.add_error(
                "duree_souhaitee",
                f"La durée maximale pour « {type_stage} » est de {type_stage.duree_max_mois} mois.",
            )


class CandidatureModifierForm(CandidatureCreerForm):
    """Formulaire de modification : le début de dispo n'est contrôlé que s'il a changé."""

    def __init__(self, *args, instance=None, **kwargs):
        self._debut_original = instance.debut_disponibilite if instance else None
        super().__init__(*args, instance=instance, **kwargs)

    def clean_debut_disponibilite(self):
        debut = self.cleaned_data.get("debut_disponibilite")
        # Contrôle >= aujourd'hui uniquement si la date a été modifiée
        if debut and debut != self._debut_original and debut < timezone.localdate():
            raise forms.ValidationError(
                "La date de début de disponibilité doit être aujourd'hui ou dans le futur."
            )
        return debut


# Alias legacy pour les vues qui utilisent encore CandidatureForm
CandidatureForm = CandidatureCreerForm


class PieceJointeForm(forms.Form):
    type_piece = forms.ChoiceField(
        choices=TypePiece.choices,
        label="Type de pièce",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fichier = forms.FileField(
        label="Fichier",
        help_text="Seul le format PDF est accepté — 3 Mo max.",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdf"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

    def clean_fichier(self):
        import os
        fichier = self.cleaned_data.get("fichier")
        if not fichier:
            return fichier
        ext = os.path.splitext(fichier.name)[1].lower()
        if ext != ".pdf":
            raise forms.ValidationError(
                f"Format non accepté ({ext}). Seul le PDF est accepté."
            )
        if fichier.size > 3 * 1024 * 1024:
            raise forms.ValidationError("Le fichier dépasse la taille maximale de 3 Mo.")
        fichier.seek(0)
        magic = fichier.read(4)
        fichier.seek(0)
        if magic != b"%PDF":
            raise forms.ValidationError("Le fichier n'est pas un PDF valide.")
        return fichier


class BasePieceJointeFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        types_vus = {}
        has_cv = False
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE", False):
                continue
            type_piece = form.cleaned_data.get("type_piece")
            if type_piece == TypePiece.CV:
                has_cv = True
            if type_piece and type_piece != TypePiece.AUTRE:
                if type_piece in types_vus:
                    label = dict(TypePiece.choices).get(type_piece, type_piece)
                    raise forms.ValidationError(
                        f"Vous ne pouvez joindre qu'un seul fichier de type « {label} »."
                    )
                types_vus[type_piece] = True
        if not has_cv:
            raise forms.ValidationError("Au moins un CV est obligatoire.")


PieceJointeFormSet = formset_factory(
    PieceJointeForm,
    formset=BasePieceJointeFormSet,
    extra=1,
    can_delete=False,
)


# ─── Étape 7 — Formulaires de décision (Responsable) ─────────────────────────


class PreselectionnerForm(forms.Form):
    commentaire = forms.CharField(
        label="Commentaire (optionnel)",
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 2, "class": "form-control",
            "placeholder": "Ex : profil correspondant, dossier complet…",
        }),
    )


class EntretienForm(forms.Form):
    date_entretien = forms.DateTimeField(
        label="Date et heure de l'entretien",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
        help_text="L'entretien doit être planifié au moins 72 h à l'avance.",
    )

    def clean_date_entretien(self):
        from datetime import timedelta
        dt = self.cleaned_data.get("date_entretien")
        if dt and dt < timezone.now() + timedelta(hours=72):
            raise forms.ValidationError(
                "L'entretien doit être planifié au moins 72 h à l'avance."
            )
        return dt


class AccorderForm(forms.Form):
    commentaire = forms.CharField(
        label="Commentaire (optionnel)",
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 2, "class": "form-control",
            "placeholder": "Ex : profil validé, stage confirmé…",
        }),
    )
    confirmer_depassement = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
    )


class RefuserForm(forms.Form):
    motif = forms.ChoiceField(
        choices=[("", "— Choisir un motif —")] + list(MotifRefus.choices),
        label="Motif de refus",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_motif_refus"}),
    )
    precision_motif = forms.CharField(
        label="Précision du motif",
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 2, "class": "form-control",
            "placeholder": "Obligatoire si motif = Autre",
        }),
    )
    commentaire = forms.CharField(
        label="Commentaire interne (optionnel)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
    )

    def clean(self):
        cleaned = super().clean()
        motif = cleaned.get("motif")
        precision = cleaned.get("precision_motif", "").strip()
        if not motif:
            self.add_error("motif", "Le motif de refus est obligatoire.")
        if motif == MotifRefus.AUTRE and not precision:
            self.add_error("precision_motif", "La précision est obligatoire pour le motif « Autre ».")
        return cleaned


class RedirigerForm(forms.Form):
    nouveau_departement = forms.ModelChoiceField(
        queryset=None,
        label="Nouveau département",
        empty_label="— Choisir un département —",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    motif = forms.CharField(
        label="Motif de la redirection",
        max_length=300,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ex : compétences plus adaptées à ce département",
        }),
    )

    def __init__(self, *args, departement_actuel=None, **kwargs):
        super().__init__(*args, **kwargs)
        from referentiels.models import Departement
        qs = Departement.objects.filter(actif=True)
        if departement_actuel:
            qs = qs.exclude(pk=departement_actuel.pk)
        self.fields["nouveau_departement"].queryset = qs
