from django import forms
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Row, Column, Submit, HTML

from referentiels.models import Membre


class ConstituerStageForm(forms.Form):
    date_debut = forms.DateField(
        label="Date de début",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    date_fin_prevue = forms.DateField(
        label="Date de fin prévue",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    maitre_stage = forms.ModelChoiceField(
        label="Maître de stage",
        queryset=Membre.objects.none(),
    )

    def __init__(self, *args, departement=None, **kwargs):
        super().__init__(*args, **kwargs)
        if departement is not None:
            self.fields["maitre_stage"].queryset = Membre.objects.filter(
                departement=departement, actif=True
            ).order_by("nom", "prenom")

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("date_debut", css_class="col-md-6"),
                Column("date_fin_prevue", css_class="col-md-6"),
            ),
            Field("maitre_stage"),
            Submit("submit", "Constituer le stage", css_class="btn btn-success mt-2"),
        )

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get("date_debut")
        fin = cleaned.get("date_fin_prevue")
        if debut and fin and fin <= debut:
            self.add_error("date_fin_prevue", "La date de fin doit être postérieure à la date de début.")
        return cleaned


class ModifierStageForm(forms.Form):
    date_debut = forms.DateField(
        label="Date de début",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        required=False,
    )
    date_fin_prevue = forms.DateField(
        label="Date de fin prévue",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    maitre_stage = forms.ModelChoiceField(
        label="Maître de stage",
        queryset=Membre.objects.none(),
    )

    def __init__(self, *args, departement=None, stage=None, **kwargs):
        super().__init__(*args, **kwargs)
        if departement is not None:
            self.fields["maitre_stage"].queryset = Membre.objects.filter(
                departement=departement, actif=True
            ).order_by("nom", "prenom")

        from stages.models import StatutStage
        if stage and stage.statut == StatutStage.EN_COURS:
            self.fields["date_debut"].widget.attrs["disabled"] = True
            self.fields["date_debut"].required = False

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("date_debut", css_class="col-md-6"),
                Column("date_fin_prevue", css_class="col-md-6"),
            ),
            Field("maitre_stage"),
            Submit("submit", "Enregistrer les modifications", css_class="btn btn-primary mt-2"),
        )

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get("date_debut")
        fin = cleaned.get("date_fin_prevue")
        if debut and fin and fin <= debut:
            self.add_error("date_fin_prevue", "La date de fin doit être postérieure à la date de début.")
        return cleaned


class TerminerStageForm(forms.Form):
    date_fin_reelle = forms.DateField(
        label="Date de fin réelle",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args, stage=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._stage = stage
        today = timezone.localdate()
        self.fields["date_fin_reelle"].widget.attrs["max"] = today.isoformat()

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field("date_fin_reelle"),
            Submit("submit", "Confirmer la clôture", css_class="btn btn-success mt-2"),
        )

    def clean_date_fin_reelle(self):
        date = self.cleaned_data["date_fin_reelle"]
        today = timezone.localdate()
        if date > today:
            raise forms.ValidationError("La date de fin réelle ne peut pas être dans le futur.")
        if self._stage and date < self._stage.date_debut:
            raise forms.ValidationError("La date de fin réelle ne peut pas être antérieure à la date de début.")
        return date


class InterrompreStageForm(forms.Form):
    date_fin_reelle = forms.DateField(
        label="Date d'interruption",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    motif_interruption = forms.CharField(
        label="Motif d'interruption",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, stage=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._stage = stage
        today = timezone.localdate()
        self.fields["date_fin_reelle"].widget.attrs["max"] = today.isoformat()

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field("date_fin_reelle"),
            Field("motif_interruption"),
            Submit("submit", "Confirmer l'interruption", css_class="btn btn-danger mt-2"),
        )

    def clean_date_fin_reelle(self):
        date = self.cleaned_data["date_fin_reelle"]
        today = timezone.localdate()
        if date > today:
            raise forms.ValidationError("La date d'interruption ne peut pas être dans le futur.")
        if self._stage and date < self._stage.date_debut:
            raise forms.ValidationError("La date d'interruption ne peut pas être antérieure à la date de début.")
        return date

    def clean_motif_interruption(self):
        motif = self.cleaned_data["motif_interruption"].strip()
        if not motif:
            raise forms.ValidationError("Le motif d'interruption est obligatoire.")
        return motif
