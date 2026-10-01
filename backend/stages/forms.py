from django import forms
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Row, Column, Submit, HTML, Div

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


class EvaluerStageForm(forms.Form):
    note = forms.IntegerField(
        label="Note /20",
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={"min": "1", "max": "20", "id": "id_note"}),
    )
    vivier = forms.BooleanField(
        label="Ajouter au vivier de talents (note ≥ 12 requise)",
        required=False,
        widget=forms.CheckboxInput(attrs={"id": "id_vivier"}),
    )
    rapport = forms.FileField(
        label="Rapport de stage (PDF, max 10 Mo)",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column(Field("note"), css_class="col-md-4"),
                Column(
                    Div(Field("vivier"), css_class="mt-4 pt-2"),
                    css_class="col-md-8",
                ),
            ),
            Field("rapport"),
            Submit("submit", "Enregistrer l'évaluation", css_class="btn btn-primary mt-2"),
        )

    def clean_rapport(self):
        rapport = self.cleaned_data.get("rapport")
        if rapport:
            if not rapport.name.lower().endswith(".pdf"):
                raise forms.ValidationError("Le rapport doit être un fichier PDF.")
            if rapport.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Le rapport ne doit pas dépasser 10 Mo.")
        return rapport

    def clean(self):
        cleaned = super().clean()
        note = cleaned.get("note")
        vivier = cleaned.get("vivier")
        if vivier and (note is None or note < 12):
            self.add_error("vivier", "Le vivier nécessite une note ≥ 12.")
        return cleaned
