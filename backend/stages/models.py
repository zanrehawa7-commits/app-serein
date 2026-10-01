from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import models


def _get_stockage_rapport():
    return FileSystemStorage(location=settings.FICHIERS_PRIVES_ROOT, base_url=None)


class StatutStage(models.TextChoices):
    A_VENIR = "A_VENIR", "À venir"
    EN_COURS = "EN_COURS", "En cours"
    TERMINE = "TERMINE", "Terminé"
    INTERROMPU = "INTERROMPU", "Interrompu"


class Stage(models.Model):
    candidature = models.OneToOneField(
        "candidatures.Candidature",
        on_delete=models.PROTECT,
        related_name="stage",
        verbose_name="candidature",
    )
    maitre_stage = models.ForeignKey(
        "referentiels.Membre",
        on_delete=models.PROTECT,
        related_name="stages_encadres",
        verbose_name="maître de stage",
    )
    date_debut = models.DateField(verbose_name="date de début")
    date_fin_prevue = models.DateField(verbose_name="date de fin prévue")
    date_fin_reelle = models.DateField(null=True, blank=True, verbose_name="date de fin réelle")
    statut = models.CharField(
        max_length=20,
        choices=StatutStage.choices,
        default=StatutStage.A_VENIR,
        verbose_name="statut",
    )
    motif_interruption = models.TextField(blank=True, verbose_name="motif d'interruption")
    note = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="note /20")
    vivier = models.BooleanField(default=False, verbose_name="vivier")
    rapport = models.FileField(
        storage=_get_stockage_rapport,
        upload_to="stages/rapports/%Y/",
        null=True,
        blank=True,
        verbose_name="rapport de stage",
    )
    date_evaluation = models.DateField(null=True, blank=True, verbose_name="date d'évaluation")
    rappel_evaluation_envoye = models.BooleanField(
        default=False,
        verbose_name="rappel évaluation envoyé",
    )

    class Meta:
        verbose_name = "Stage"
        verbose_name_plural = "Stages"
        ordering = ["-date_debut"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_fin_prevue__gt=models.F("date_debut")),
                name="stage_date_fin_prevue_gt_date_debut",
            ),
            models.CheckConstraint(
                condition=models.Q(note__isnull=True) | models.Q(note__gte=1, note__lte=20),
                name="stage_note_entre_1_et_20",
            ),
            # vivier ne peut être True que si note >= 12
            models.CheckConstraint(
                condition=models.Q(vivier=False) | models.Q(note__gte=12),
                name="stage_vivier_necessite_note_gte_12",
            ),
        ]

    def __str__(self):
        return f"Stage {self.candidature.reference} — {self.candidature.candidat}"

    def clean(self):
        if self.date_debut and self.date_fin_prevue and self.date_fin_prevue <= self.date_debut:
            raise ValidationError(
                {"date_fin_prevue": "La date de fin prévue doit être postérieure à la date de début."}
            )
        if self.note is not None and not (1 <= self.note <= 20):
            raise ValidationError({"note": "La note doit être comprise entre 1 et 20."})
        if self.vivier and (self.note is None or self.note < 12):
            raise ValidationError({"vivier": "Le vivier ne peut être activé que si la note est >= 12."})
        # RG22 : le maître de stage doit appartenir au département de la candidature
        if self.maitre_stage_id and self.candidature_id:
            dept_candidature = self.candidature.departement_id
            dept_maitre = self.maitre_stage.departement_id
            if dept_maitre != dept_candidature:
                raise ValidationError(
                    {"maitre_stage": "Le maître de stage doit appartenir au département de la candidature."}
                )
